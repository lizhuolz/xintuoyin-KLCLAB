"""Reject ambiguous sources and preserve filtering across valid CTE scopes."""

import sqlite3
import unittest

from utils.sql_permissions import SQLAccessDenied, SQLPermissions


class SQLSourceCoverageTests(unittest.TestCase):
    def setUp(self):
        self.policy = SQLPermissions(6, 51)
        self.policy.project_ids = (10,)
        self.columns = {
            "t_staff": {"ID", "TENANT_ID", "OPERATER_STATUS"},
            "t_project": {"ID", "TENANT_ID", "OPERATER_STATUS"},
        }
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE t_staff(ID INT, TENANT_ID INT, OPERATER_STATUS INT);
            INSERT INTO t_staff VALUES (51,6,1),(52,7,1),(53,6,-1);
            CREATE TABLE t_project(ID INT, TENANT_ID INT, OPERATER_STATUS INT);
            INSERT INTO t_project VALUES (10,6,1),(11,6,1),(12,7,1);
        """)

    def run_query(self, sql):
        rewritten = self.policy.restrict_sql(sql, self.columns)
        return self.db.execute(rewritten).fetchall()

    def test_cte_collision_cannot_hide_physical_table(self):
        sql = (
            "WITH x AS (SELECT * FROM t_staff) "
            "SELECT COUNT(*) FROM forbidden x JOIN x ON 1=1"
        )
        with self.assertRaises(SQLAccessDenied):
            self.policy.restrict_sql(sql, self.columns)

    def test_duplicate_physical_alias_is_denied(self):
        with self.assertRaises(SQLAccessDenied):
            self.policy.restrict_sql(
                "SELECT COUNT(*) FROM t_staff a JOIN t_project a ON 1=1",
                self.columns,
            )

    def test_valid_physical_alias_matching_cte_name_is_filtered(self):
        self.assertEqual(self.run_query(
            "WITH x AS (SELECT ID FROM t_staff) "
            "SELECT x.ID, y.ID FROM t_project x JOIN x y ON 1=1"
        ), [(10, 51)])

    def test_derived_alias_matching_cte_name_is_filtered(self):
        self.assertEqual(self.run_query(
            "WITH x AS (SELECT ID FROM t_staff) "
            "SELECT x.ID, y.ID FROM (SELECT ID FROM t_project) x JOIN x y ON 1=1"
        ), [(10, 51)])

    def test_cte_named_after_business_table_remains_supported(self):
        self.assertEqual(self.run_query(
            "WITH t_project AS (SELECT ID FROM t_staff) SELECT ID FROM t_project"
        ), [(51,)])

    def test_nested_cte_and_union_remain_filtered(self):
        self.assertEqual(self.run_query(
            "WITH staff AS (SELECT ID FROM t_staff), "
            "permitted AS (SELECT ID FROM t_project) "
            "SELECT ID FROM staff UNION SELECT ID FROM permitted ORDER BY ID"
        ), [(10,), (51,)])

    def test_qualified_table_cannot_be_mistaken_for_cte(self):
        with self.assertRaises(SQLAccessDenied):
            self.policy.restrict_sql(
                "WITH x AS (SELECT ID FROM t_staff) SELECT * FROM another_schema.x",
                self.columns,
            )

    def test_exists_subquery_cannot_match_other_tenant_or_project(self):
        for predicate in ("p.TENANT_ID=7", "p.ID=11"):
            with self.subTest(predicate=predicate):
                self.assertEqual(self.run_query(
                    "SELECT s.ID FROM t_staff s WHERE EXISTS "
                    f"(SELECT 1 FROM t_project p WHERE {predicate})"
                ), [])
        self.assertEqual(self.run_query(
            "SELECT s.ID FROM t_staff s WHERE EXISTS "
            "(SELECT 1 FROM t_project p WHERE p.ID=10)"
        ), [(51,)])

    def test_not_exists_subquery_ignores_other_tenant_or_project(self):
        for predicate in ("p.TENANT_ID=7", "p.ID=11"):
            with self.subTest(predicate=predicate):
                self.assertEqual(self.run_query(
                    "SELECT s.ID FROM t_staff s WHERE NOT EXISTS "
                    f"(SELECT 1 FROM t_project p WHERE {predicate})"
                ), [(51,)])
        self.assertEqual(self.run_query(
            "SELECT s.ID FROM t_staff s WHERE NOT EXISTS "
            "(SELECT 1 FROM t_project p WHERE p.ID=10)"
        ), [])


if __name__ == "__main__":
    unittest.main()
