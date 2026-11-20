"""Offline regressions for literal identity grounding and numeric provenance."""

import copy
import unittest

from utils.typed_facts import FactError, describe_result, render_plan
from utils.typed_query import ContractError, compile_contract


class TypedSafetyTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {
            "entities": {
                "staff": {
                    "table": "t_staff", "key": ["ID"], "label": "员工",
                    "attributes": {
                        "ID": {"type": "int", "label": "员工ID"},
                        "NAME": {"type": "text", "label": "姓名"},
                        "AMOUNT": {"type": "decimal", "label": "金额"},
                    },
                },
                "project": {
                    "table": "t_project", "key": ["ID"], "label": "项目",
                    "attributes": {"ID": {"type": "int", "label": "项目ID"}},
                },
            },
            "relations": {
                "membership": {
                    "kind": "association", "table": "t_project_user",
                    "left": "staff", "right": "project",
                    "left_columns": ["STAFF_ID"], "right_columns": ["PROJECT_ID"],
                    "label": "项目成员",
                },
            },
        }

    def contract(self, value, evidence):
        return {
            "bindings": {"b": {"entity": "staff", "key": [{"value": value, "evidence": evidence}]}},
            "facts": [{"op": "attribute", "subject": "b", "property": "NAME"}],
        }

    def result(self, sql, field="value", values=(11, 12)):
        result = {"fields": [field], "data": [{field: value} for value in values], "executed_sql": sql}
        result["typed_evidence"] = describe_result(result, self.catalog, type_codes={field: 3})
        return result

    def sum_plan(self):
        return {"calculations": [{"operation": "sum", "arguments": ["column:0"], "requested_by": "合计"}]}

    def test_numeric_key_cannot_drop_a_sign_or_use_a_date_component(self):
        for evidence in ("-11", "+11", "2026-11-20"):
            with self.subTest(evidence=evidence), self.assertRaises(ContractError):
                compile_contract(self.contract("11", evidence), self.catalog, "员工ID " + evidence + "的姓名")

    def test_exact_negative_and_unsigned_numeric_keys_remain_valid(self):
        for value in ("-11", "11"):
            compiled = compile_contract(self.contract(value, value), self.catalog, "员工ID " + value + "的姓名")
            self.assertIn("`ID` = " + value, compiled["sql"])

    def test_independent_object_attributes_fall_back_without_missing_first_anchor_suppression(self):
        contract = self.contract("11", "11")
        contract["bindings"]["present"] = {"entity": "staff", "key": [{"value": "37", "evidence": "37"}]}
        contract["facts"].append({"op": "attribute", "subject": "present", "property": "NAME"})
        # A single anchor on ID 11 would also hide the valid fact about ID 37
        # whenever 11 is absent. Ordinary SQL must handle these independently.
        self.assertIsNone(compile_contract(contract, self.catalog, "查询员工11和37的姓名"))

    def test_equivalent_numeric_keys_under_different_binding_names_share_one_anchor(self):
        contract = self.contract("11", "11")
        contract["bindings"]["same"] = {"entity": "staff", "key": [{"value": "11.0", "evidence": "11.0"}]}
        contract["facts"].append({"op": "attribute", "subject": "same", "property": "AMOUNT"})
        compiled = compile_contract(contract, self.catalog, "员工11和11.0为同一对象，查询姓名与金额")
        self.assertIsNotNone(compiled)
        self.assertEqual(len(compiled["fields"]), 2)

    def test_attribute_and_relation_with_different_left_object_fall_back(self):
        contract = self.contract("11", "11")
        contract["bindings"].update({
            "other": {"entity": "staff", "key": [{"value": "37", "evidence": "37"}]},
            "project": {"entity": "project", "key": [{"value": "50", "evidence": "50"}]},
        })
        contract["facts"].append({"op": "relation_exists", "relation": "membership", "left": "other", "right": "project"})
        question = "查询员工11的姓名，以及员工37是否参与项目50"
        self.assertIsNone(compile_contract(contract, self.catalog, question))
        # Validation still covers later operations before multiple roots cause
        # fallback; a malformed contract must not silently become valid SQL.
        invalid = copy.deepcopy(contract)
        invalid["facts"].append({"op": "raw_sql"})
        with self.assertRaises(ContractError):
            compile_contract(invalid, self.catalog, question)

    def test_attribute_and_relation_with_same_left_object_keep_compilation(self):
        contract = self.contract("11", "11")
        contract["bindings"]["project"] = {"entity": "project", "key": [{"value": "50", "evidence": "50"}]}
        contract["facts"].append({"op": "relation_exists", "relation": "membership", "left": "b", "right": "project"})
        self.assertIsNotNone(compile_contract(contract, self.catalog, "查询员工11的姓名，以及其是否参与项目50"))

    def test_unqualified_join_reference_is_an_identifier_and_cannot_be_summed(self):
        result = self.result("SELECT STAFF_ID AS value FROM t_project_user m JOIN t_staff s ON s.ID=m.STAFF_ID")
        self.assertEqual(result["typed_evidence"]["fields"][0]["type"], "identifier")
        with self.assertRaises(FactError):
            render_plan(result, self.sum_plan(), "ID合计")

    def test_unqualified_measure_resolves_to_its_only_schema_source(self):
        result = self.result("SELECT AMOUNT AS value FROM t_project_user m JOIN t_staff s ON s.ID=m.STAFF_ID")
        field = result["typed_evidence"]["fields"][0]
        self.assertEqual(field["origin"], ("t_staff", "AMOUNT"))
        self.assertEqual(field["type"], "number")
        self.assertIn("value合计：23", render_plan(result, self.sum_plan(), "金额合计")[0])

    def test_ambiguous_or_computed_numeric_lineage_cannot_be_used_for_arithmetic(self):
        for sql in ("SELECT ID AS value FROM t_staff s JOIN t_project p ON p.ID=s.ID",
                    "SELECT s.ID + 0 AS value FROM t_staff s"):
            with self.subTest(sql=sql):
                result = self.result(sql)
                with self.assertRaises(FactError):
                    render_plan(result, self.sum_plan(), "数值合计")

    def test_compiled_attribute_proof_preserves_measure_and_identifier_types(self):
        for column, expected in (("AMOUNT", "number"), ("ID", "identifier")):
            result = {"fields": ["fact_0"], "data": [{"fact_0": 11}],
                      "executed_sql": "SELECT (SELECT " + column + " FROM t_staff LIMIT 1) AS fact_0 FROM t_staff"}
            compiled = {"fields": [{"field": "fact_0", "kind": "attribute", "source_columns": [["t_staff", column]]}]}
            meta = describe_result(result, self.catalog, compiled=compiled, type_codes={"fact_0": 3})
            self.assertEqual(meta["fields"][0]["type"], expected)


if __name__ == "__main__":
    unittest.main()
