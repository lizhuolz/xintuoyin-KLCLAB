"""离线验证权限改写、Text2SQL 生命周期及真实 LangGraph 工具调用。"""

import asyncio
import importlib.util
import json
import sqlite3
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, START, END, MessagesState

from utils.DB_vllm_32B import DB, _extract_sql
from utils.sql_permissions import RESOURCE_DIR, SQLAccessDenied, SQLPermissions, load_table_policy

BACKEND = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sql_operator_under_test", BACKEND / "agent/tools/db_operator.py")
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)


class SQLPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = SQLPermissions(6, 51)
        self.policy.project_ids = (10,)
        self.policy.project_names = ("项目甲",)
        self.columns = {
            "t_project": {"ID", "TENANT_ID", "OPERATER_STATUS", "PROJECT_NAME"},
            "t_project_user": {"ID", "TENANT_ID", "OPERATER_STATUS", "PROJECT_ID", "STAFF_ID"},
            "t_staff": {"ID", "TENANT_ID", "OPERATER_STATUS"},
        }
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE t_project(ID INT, TENANT_ID INT, OPERATER_STATUS INT, PROJECT_NAME TEXT);
            INSERT INTO t_project VALUES (10,6,1,'项目甲'),(11,6,1,'项目甲'),(12,7,1,'其他租户'),(13,6,-1,'已删除');
            CREATE TABLE t_project_user(ID INT, TENANT_ID INT, OPERATER_STATUS INT, PROJECT_ID INT, STAFF_ID INT);
            INSERT INTO t_project_user VALUES (1,6,1,10,51),(2,6,1,11,52),(3,7,1,12,51);
            CREATE TABLE t_staff(ID INT, TENANT_ID INT, OPERATER_STATUS INT);
            INSERT INTO t_staff VALUES (51,6,1),(52,6,1),(53,7,1);
        """)

    def run_query(self, sql):
        return self.db.execute(self.policy.restrict_sql(sql, self.columns)).fetchall()

    def test_tenant_and_project_filter_survives_or_and_same_name(self):
        self.assertEqual(self.run_query("SELECT ID FROM t_project WHERE TENANT_ID=7 OR 1=1"), [(10,)])
        self.assertEqual(self.run_query("SELECT COUNT(*) FROM t_project"), [(1,)])

    def test_join_subquery_cte_union(self):
        queries = [
            "SELECT p.ID FROM t_project p JOIN t_project_user u ON p.ID=u.PROJECT_ID",
            "SELECT ID FROM t_project WHERE ID IN (SELECT PROJECT_ID FROM t_project_user)",
            "WITH permitted AS (SELECT * FROM t_project) SELECT ID FROM permitted",
            "WITH t_project AS (SELECT * FROM t_staff) SELECT ID FROM t_project ORDER BY ID",
            "SELECT ID FROM t_project UNION SELECT PROJECT_ID FROM t_project_user",
            "SELECT p.ID FROM t_project p JOIN t_project q ON p.ID=q.ID",
        ]
        for sql in queries:
            with self.subTest(sql=sql):
                expected = [(51,), (52,)] if "SELECT * FROM t_staff" in sql else [(10,)]
                self.assertEqual(self.run_query(sql), expected)

    def test_all_project_admin_still_tenant_scoped(self):
        self.policy = SQLPermissions(6, None, allow_all_projects=True)
        self.assertEqual(self.run_query("SELECT ID FROM t_project ORDER BY ID"), [(10,), (11,)])

    def test_denied_queries(self):
        queries = [
            "DELETE FROM t_project", "UPDATE t_project SET TENANT_ID=6", "SELECT * FROM t_project; SELECT * FROM t_staff",
            "SELECT * FROM another.t_project", "SELECT * FROM information_schema.tables", "SELECT * FROM not_allowed",
            "SELECT * FROM t_project FOR UPDATE", "SELECT * INTO OUTFILE '/tmp/export' FROM t_project",
            "SELECT LOAD_FILE('/etc/passwd') FROM t_staff", "SELECT SLEEP(2) FROM t_staff",
            "SELECT custom_func(ID) FROM t_staff", "SELECT @@version FROM t_staff", "SELECT @x:=ID FROM t_staff",
            "SELECT * FROM t_project USE INDEX (PRIMARY)",
        ]
        for sql in queries:
            with self.subTest(sql=sql), self.assertRaises(SQLAccessDenied):
                self.policy.restrict_sql(sql, self.columns)

    def test_unknown_project_key_and_missing_tenant_deny(self):
        with self.assertRaises(SQLAccessDenied):
            self.policy.restrict_sql("SELECT * FROM t_project_power_calculate_item_month", {
                "t_project_power_calculate_item_month": {"TENANT_ID", "PROJECT_POWER_CALCULATE_ID"}})
        with self.assertRaises(SQLAccessDenied):
            self.policy.restrict_sql("SELECT * FROM t_staff", {"t_staff": {"ID"}})

    def test_no_projects_does_not_block_non_project_queries(self):
        self.policy.project_ids = ()
        with self.assertRaises(SQLAccessDenied):
            self.run_query("SELECT * FROM t_project")
        self.assertEqual(self.run_query("SELECT COUNT(*) FROM t_staff"), [(2,)])

    def test_invalid_identity(self):
        for tenant, staff in [(None, 51), (0, 51), (True, 51), (6, None), (6, 0), (6, "1 OR 1=1")]:
            with self.subTest(tenant=tenant, staff=staff), self.assertRaises(SQLAccessDenied):
                SQLPermissions(tenant, staff)

    def test_safe_date_case_functions(self):
        for sql in ["SELECT DATE_SUB(CURDATE(), INTERVAL 1 MONTH) FROM t_staff",
                    "SELECT SUM(CASE WHEN ID=51 THEN 1 ELSE 0 END) FROM t_staff"]:
            self.assertIn("`TENANT_ID` = 6", self.policy.restrict_sql(sql, self.columns))

    def test_resources_independent_of_reference(self):
        self.assertNotIn("db_cyn", str(RESOURCE_DIR))
        allowed, project = load_table_policy()
        self.assertEqual((len(allowed), len(project)), (144, 48))
        self.assertIn("operaterStatus", self.policy.type_hint("删除"))

    def test_extraction_preserves_statements_and_refusal(self):
        self.assertIn(";", _extract_sql("SELECT ID FROM t_staff; DELETE FROM t_staff"))
        self.assertEqual(_extract_sql("<think>SELECT 1</think>I do not know"), "I do not know")


class DBIntegrationTests(unittest.TestCase):
    def test_constructor_project_lookup_and_close(self):
        rows = [{"ID": 10, "PROJECT_NAME": "项目甲"}]
        with patch.object(DB, "_init_mysql"), patch.object(DB, "_extract_all_table_detailed_comments", return_value={}), \
                patch.object(DB, "_read_internal", return_value=rows) as read, \
                patch("utils.DB_vllm_32B.OpenAI") as client:
            db = DB(tenant_id="6", staff_id="51")
            self.assertEqual(db.permissions.project_ids, (10,))
            self.assertEqual(read.call_args.args[1], (6, 51))
            self.assertIn("u.OPERATER_STATUS > 0", read.call_args.args[0])
            db.close()
            client.return_value.close.assert_called_once()

    def test_constructor_failure_closes_connection(self):
        conn = MagicMock()
        def init(db):
            db.conn = conn
            db.cur = conn.cursor()
        with patch.object(DB, "_init_mysql", init), \
                patch.object(DB, "_extract_all_table_detailed_comments", side_effect=RuntimeError("schema failed")):
            with self.assertRaises(RuntimeError):
                DB(tenant_id=6, staff_id=51)
        conn.close.assert_called_once()

    def test_denied_sql_never_uses_connection(self):
        db = DB.__new__(DB)
        db.permissions = SQLPermissions(6, 51)
        db.table_columns = {"t_project": {"ID", "TENANT_ID"}}
        db.conn = MagicMock()
        result = db.execute_sql("DELETE FROM t_project")
        self.assertEqual(result["status"], "denied")
        db.conn.ping.assert_not_called()

    def test_project_denial_does_not_generate_or_retry(self):
        db = DB.__new__(DB)
        db.permissions = SQLPermissions(6, 51)
        db.table_columns = {"t_project": {"ID", "TENANT_ID"}}
        db.select_table = MagicMock(return_value=["t_project"])
        db.generate_sql = MagicMock()
        self.assertFalse(db.query_db("项目总数")["Access_check"])
        db.select_table.assert_called_once()
        db.generate_sql.assert_not_called()

    def test_prompt_keeps_permissions_on_retry(self):
        db = DB.__new__(DB)
        db.permissions = SQLPermissions(6, 51)
        db.permissions.project_ids, db.permissions.project_names = (10,), ("项目甲",)
        db.table_columns = {"t_project": {"ID", "TENANT_ID"}}
        db._format_schema = MagicMock(return_value="CREATE TABLE t_project ...")
        db.client = MagicMock()
        db.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="SELECT ID FROM t_project"))])
        db.model_name, db.generate_temperature, db.generate_max_tokens, db.extra_body = "test", 0, 1024, {}
        db.generate_sql(["t_project"], "删除的项目", error_context="previous SQL failed")
        prompt = db.client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        self.assertIn("TENANT_ID = 6", prompt)
        self.assertIn("项目甲", prompt)
        self.assertIn("previous SQL failed", prompt)
        self.assertIn("operaterStatus", prompt)


class RouterTests(unittest.TestCase):
    def test_denied_never_falls_back_and_success_text_not_misclassified(self):
        dependencies = {
            "agent.utils": SimpleNamespace(extract_current_user_question=lambda messages: ""),
            "agent.messagestate": SimpleNamespace(GraphState=MessagesState),
        }
        with patch.dict(sys.modules, dependencies):
            router_spec = importlib.util.spec_from_file_location("sql_router_under_test", BACKEND / "agent/router.py")
            router = importlib.util.module_from_spec(router_spec)
            router_spec.loader.exec_module(router)
        for result, expected in [
            ({"status": "denied", "Access_check": False, "message": "没有权限"}, "end"),
            ({"status": "empty", "data": []}, "sql_rag_fallback"),
            ({"status": "error", "message": "查询失败"}, "sql_rag_fallback"),
            ({"status": "ok", "data": [{"NAME": "错误测试项目"}]}, "end"),
        ]:
            state = {"messages": [ToolMessage(content=json.dumps(result), name="sql_tool", tool_call_id="1")]}
            self.assertEqual(router.route_after_sql_answer(state), expected)
            self.assertEqual(router._last_tool_msg_failed_for(state["messages"], "sql_tool"), expected != "end")


class ToolFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_toolnode_parallel_identity_snapshot(self):
        created = []
        def create(**kwargs):
            db = MagicMock()
            db.query_db.return_value = {"status": "ok", "tenant_id": kwargs["tenant_id"], "staff_id": kwargs["staff_id"]}
            created.append((kwargs, db))
            return db
        builder = StateGraph(MessagesState)
        builder.add_node("tools", ToolNode([operator.sql_tool]))
        builder.add_edge(START, "tools")
        builder.add_edge("tools", END)
        graph = builder.compile()
        async def call(tenant, staff):
            state = {"messages": [AIMessage(content="", tool_calls=[{"name": "sql_tool", "args": {"question": "项目数"}, "id": str(tenant), "type": "tool_call"}])]}
            result = await graph.ainvoke(state, config={"configurable": {"sql_user": {"tenant_id": tenant, "staff_id": staff, "role": "user"}}})
            return json.loads(result["messages"][-1].content)
        with patch.object(operator, "DB", side_effect=create):
            results = await asyncio.gather(call(6, 51), call(7, 52))
        self.assertEqual([(r["tenant_id"], r["staff_id"]) for r in results], [(6, 51), (7, 52)])
        self.assertEqual(len(created), 2)
        for _, db in created:
            db.close.assert_called_once()
        self.assertEqual(set(operator.sql_tool.args), {"question"})

    async def test_guest_and_missing_staff_never_connect(self):
        for user in [{"role": "guest"}, {"role": "user", "tenant_id": 6}, {"role": "enterprise_admin"}]:
            with patch("utils.DB_vllm_32B.pymysql.connect") as connect:
                result = json.loads(await operator.sql_tool.ainvoke({"question": "项目数"}, config={"configurable": {"sql_user": user}}))
                self.assertEqual(result["status"], "denied")
                connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
