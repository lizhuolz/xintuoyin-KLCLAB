"""Offline regressions for SQL fallback, retry state, and request context."""

import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from utils.DB_vllm_32B import DB
from utils.sql_permissions import SQLPermissions
from utils.typed_query import ContractError


class MergeResilienceTests(unittest.TestCase):
    def make_db(self):
        db = DB.__new__(DB)
        db.permissions = SQLPermissions(6, None, allow_all_projects=True)
        db.table_columns = {"t_staff": {"ID", "TENANT_ID", "FULL_NAME"}}
        db.detailed_comments = {"t_staff": {"table_comment": "员工", "columns": []}}
        db.semantic_catalog = {"entities": {"staff": {}}, "relations": {}}
        db.select_table = Mock(return_value=["t_staff"])
        db.generate_sql = Mock(return_value="SELECT FULL_NAME FROM t_staff")
        db.execute_sql = Mock(return_value={"status": "ok", "data": [{"FULL_NAME": "甲"}]})
        db._retry_column_hint = Mock(return_value="")
        return db

    def query_successfully(self, db, question):
        try:
            return db.query_db(question)
        except RuntimeError as error:
            self.fail("The ordinary guarded SQL path should remain available: " + str(error))

    def make_prompt_db(self, response):
        db = self.make_db()
        db.semantic_catalog = {"entities": {}, "relations": {}}
        db._format_schema = Mock(return_value="CREATE TABLE t_staff (FULL_NAME TEXT)")
        db._database_value_hints = Mock(return_value="N/A")
        db.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(
            return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=response))])
        ))))
        db.model_name = "offline-test-model"
        db.selector_temperature = db.generate_temperature = 0
        db.selector_max_tokens = db.generate_max_tokens = 1024
        db.extra_body = {}
        return db

    def model_prompt(self, stage, context, question):
        response = {"selector": "<RES>t_staff</RES>", "generator": "SELECT FULL_NAME FROM t_staff",
                    "contract": '{"bindings":{},"facts":[]}'}[stage]
        db = self.make_prompt_db(response)
        db.query_context = context
        if stage == "selector":
            DB.select_table(db, question)
        elif stage == "generator":
            DB.generate_sql(db, ["t_staff"], question)
            db._database_value_hints.assert_called_once_with(["t_staff"], question)
        else:
            with patch("utils.typed_query.compile_contract", return_value=None) as compile_contract:
                DB.make_fact_contract(db, ["t_staff"], question)
            self.assertEqual(compile_contract.call_args.args[2], question)
        messages = db.client.chat.completions.create.call_args.kwargs["messages"]
        if stage == "contract":
            payload = json.loads(messages[-1]["content"])
            self.assertEqual(payload["original_question"], question)
        return "\n".join(message["content"] for message in messages)

    def test_server_context_reaches_all_three_model_prompts(self):
        context = "SERVER_BACKGROUND_9ab: 研发部门指业务一部，不代表新增授权。"
        for stage in ("selector", "generator", "contract"):
            with self.subTest(stage=stage):
                prompt = self.model_prompt(stage, context, "员工姓名")
                self.assertIn(context, prompt)

    def test_context_is_bounded_without_truncating_the_original_question(self):
        context = "BACKGROUND_START;" + "界" * 25000 + ";BACKGROUND_END"
        question = "仅列姓名，保留原文的问题末尾标记QUESTION_END"
        for stage in ("selector", "generator", "contract"):
            with self.subTest(stage=stage):
                prompt = self.model_prompt(stage, context, question)
                self.assertFalse("BACKGROUND_START" in prompt and "BACKGROUND_END" in prompt,
                                 "Oversized background must be truncated")
                self.assertGreater(prompt.count("界"), 0)
                self.assertLessEqual(prompt.count("界"), 24000)
                self.assertTrue(question in prompt, "Original question must remain complete")

    def test_context_does_not_replace_the_question_used_by_scope_validators(self):
        db = self.make_db()
        db.query_context = "背景提及项目991和2025年，但并非用户要求增加筛选条件。"
        db.semantic_catalog = {}
        question = "员工姓名"
        self.query_successfully(db, question)
        self.assertEqual(db.select_table.call_args.args[0], question)
        self.assertEqual(db.generate_sql.call_args.args[1], question)
        self.assertEqual(db.execute_sql.call_args.kwargs["source_question"], question)

    def test_client_has_bounded_timeout_without_hidden_retries(self):
        for configured, expected in ((None, 60), ("17.5", 17.5)):
            with self.subTest(configured=configured), patch.dict(os.environ):
                if configured is None:
                    os.environ.pop("DB_LLM_TIMEOUT", None)
                else:
                    os.environ["DB_LLM_TIMEOUT"] = configured
                with patch.object(DB, "_init_mysql"), \
                        patch.object(DB, "_extract_all_table_detailed_comments", return_value={}), \
                        patch.object(DB, "_read_internal", return_value=[]), \
                        patch("utils.DB_vllm_32B.OpenAI") as client:
                    db = DB(tenant_id=6, staff_id=51)
                    try:
                        options = client.call_args.kwargs
                        self.assertEqual(options.get("timeout"), expected)
                        self.assertEqual(options.get("max_retries"), 0)
                    finally:
                        db.close()

    def test_invalid_contract_falls_back_once_to_guarded_sql(self):
        failures = [json.JSONDecodeError("bad contract", "{", 1), ContractError("invalid binding")]
        question = "研发部门员工姓名"
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                db = self.make_db()
                db.make_fact_contract = Mock(side_effect=failure)
                result = self.query_successfully(db, question)
                self.assertEqual(result["status"], "ok")
                db.make_fact_contract.assert_called_once()
                db.select_table.assert_called_once()
                db.generate_sql.assert_called_once()
                db.execute_sql.assert_called_once_with(
                    "SELECT FULL_NAME FROM t_staff", validate_generated=True, source_question=question
                )

    def test_failed_compiled_sql_is_recompiled_with_execution_error(self):
        db = self.make_db()
        good_sql = "SELECT FULL_NAME FROM t_staff"
        bad_sql = "SELECT nonexistent_name FROM t_staff"
        seen = []

        def compile_again(selected, question, error_context=None):
            seen.append((getattr(db, "_compiled_query", None), error_context))
            db._typed_contract = {"mode": "fixed", "bindings": {}, "facts": []}
            db._compiled_query = {"sql": bad_sql if len(seen) == 1 else good_sql}

        db.make_fact_contract = Mock(side_effect=compile_again)
        db.generate_sql = Mock(side_effect=lambda *args, **kwargs: db._compiled_query["sql"])
        db.execute_sql = Mock(side_effect=lambda sql, **kwargs: (
            {"error": "Unknown column nonexistent_name", "error_type": "sql_execution"}
            if sql == bad_sql else {"status": "ok", "data": [{"FULL_NAME": "甲"}]}
        ))
        result = self.query_successfully(db, "员工姓名")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(db.make_fact_contract.call_count, 2)
        self.assertIsNone(seen[1][0], "A failed compiled query must not survive into recompilation")
        self.assertIn("Unknown column nonexistent_name", seen[1][1])
        self.assertEqual([call.args[0] for call in db.execute_sql.call_args_list], [bad_sql, good_sql])

    def test_denial_is_returned_without_retry_even_when_it_contains_error_text(self):
        for extra in ({}, {"error": "permission denied"}):
            with self.subTest(extra=extra):
                db = self.make_db()
                db.semantic_catalog = {}
                denied = {"status": "denied", "Access_check": False, "message": "没有权限", **extra}
                db.execute_sql.return_value = denied
                result = self.query_successfully(db, "员工姓名")
                self.assertEqual(result, denied)
                db.select_table.assert_called_once()
                db.generate_sql.assert_called_once()
                db.execute_sql.assert_called_once()


if __name__ == "__main__":
    unittest.main()
