"""Offline date-function compatibility and permission-isolation regressions."""

import sqlite3
import unittest
from datetime import datetime

import sqlglot
from sqlglot import exp

from utils.sql_permissions import SQLAccessDenied, SQLPermissions


class SQLDateFunctionTests(unittest.TestCase):
    def setUp(self):
        self.columns = {
            "t_project": {"ID", "TENANT_ID", "OPERATER_STATUS", "CREATE_TIME"},
            "t_project_user": {"ID", "TENANT_ID", "OPERATER_STATUS", "PROJECT_ID", "CREATE_TIME"},
        }
        self.user = SQLPermissions(6, 51)
        self.user.project_ids = (10,)
        self.admin = SQLPermissions(6, None, allow_all_projects=True)
        self.policies = (("user", self.user), ("admin", self.admin))
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        # sqlglot preserves YEAR in SQLite output; supply only its pure date
        # operation so these tests can execute the actual permission rewrite.
        self.db.create_function("YEAR", 1, lambda value: datetime.fromisoformat(value).year,
                                deterministic=True)
        self.db.executescript("""
            CREATE TABLE t_project(ID INT, TENANT_ID INT, OPERATER_STATUS INT, CREATE_TIME TEXT);
            INSERT INTO t_project VALUES
                (10,6,1,'2025-03-04 12:34:56'),
                (11,6,1,'2025-07-08 09:10:11'),
                (12,7,1,'2025-03-04 12:34:56'),
                (13,6,-1,'2025-03-04 12:34:56'),
                (14,6,1,'2024-03-04 12:34:56');
            CREATE TABLE t_project_user(ID INT, TENANT_ID INT, OPERATER_STATUS INT, PROJECT_ID INT, CREATE_TIME TEXT);
            INSERT INTO t_project_user VALUES
                (1,6,1,10,'2025-03-04 12:34:56'),
                (2,6,1,11,'2025-03-04 12:34:56'),
                (3,7,1,10,'2025-03-04 12:34:56'),
                (4,6,-1,10,'2025-03-04 12:34:56');
        """)

    def rewrite_allowed(self, policy, sql):
        try:
            return policy.restrict_sql(sql, self.columns)
        except SQLAccessDenied as exc:
            self.fail(f"An approved date expression was denied: {exc}; SQL: {sql}")

    def run_query(self, policy, sql):
        rewritten = self.rewrite_allowed(policy, sql)
        sqlite_sql = sqlglot.transpile(rewritten, read="mysql", write="sqlite")[0]
        return self.db.execute(sqlite_sql).fetchall()

    def assert_table_filters(self, rewritten, policy):
        tree = sqlglot.parse_one(rewritten, read="mysql")
        tables = list(tree.find_all(exp.Table))
        self.assertTrue(tables)
        for table in tables:
            filtered = table.find_ancestor(exp.Select)
            where = filtered.args.get("where")
            self.assertIsNotNone(where)
            conditions = where.sql(dialect="mysql")
            self.assertIn("`TENANT_ID` = 6", conditions)
            self.assertIn("`OPERATER_STATUS` > 0", conditions)
            if not policy.allow_all_projects:
                key = "ID" if table.name == "t_project" else "PROJECT_ID"
                self.assertIn(f"`{key}` IN (10)", conditions)
        return tree

    def test_year_filter_returns_only_visible_2025_projects(self):
        sql = "SELECT ID FROM t_project WHERE YEAR(CREATE_TIME) = 2025 ORDER BY ID"
        for role, policy in self.policies:
            with self.subTest(role=role):
                expected = [(10,)] if role == "user" else [(10,), (11,)]
                self.assertEqual(self.run_query(policy, sql), expected)

    def test_date_filter_ignores_time_and_preserves_isolation(self):
        sql = "SELECT ID FROM t_project WHERE DATE(CREATE_TIME) = '2025-03-04' ORDER BY ID"
        for role, policy in self.policies:
            with self.subTest(role=role):
                self.assertEqual(self.run_query(policy, sql), [(10,)])

    def test_original_approved_date_function_family_remains_allowed(self):
        expressions = [
            "YEAR(CREATE_TIME)", "MONTH(CREATE_TIME)", "DAY(CREATE_TIME)",
            "DAYOFMONTH(CREATE_TIME)", "DAYOFWEEK(CREATE_TIME)", "DAYOFYEAR(CREATE_TIME)",
            "WEEK(CREATE_TIME)", "WEEKDAY(CREATE_TIME)", "WEEKOFYEAR(CREATE_TIME)",
            "YEARWEEK(CREATE_TIME)", "DATE(CREATE_TIME)", "TIME(CREATE_TIME)",
            "TIMESTAMP(CREATE_TIME)", "DATE_ADD(CREATE_TIME, INTERVAL 1 DAY)",
            "DATE_SUB(CREATE_TIME, INTERVAL 1 MONTH)", "ADDDATE(CREATE_TIME, INTERVAL 1 DAY)",
            "DATEDIFF(CREATE_TIME, '2025-01-01')",
            "TIMESTAMPDIFF(DAY, '2025-01-01', CREATE_TIME)",
            "DATE_FORMAT(CREATE_TIME, '%Y-%m')", "MONTHNAME(CREATE_TIME)",
            "STR_TO_DATE('2025-03-04', '%Y-%m-%d')",
            "STR_TO_DATE('2025-03-04 12:34:56', '%Y-%m-%d %H:%i:%s')",
            "LAST_DAY(CREATE_TIME)", "HOUR(CREATE_TIME)", "MINUTE(CREATE_TIME)",
            "EXTRACT(YEAR FROM CREATE_TIME)", "CURDATE()", "CURRENT_DATE",
            "NOW()", "CURRENT_TIMESTAMP",
        ]
        for role, policy in self.policies:
            for expression in expressions:
                with self.subTest(role=role, expression=expression):
                    sql = f"SELECT {expression} AS value FROM t_project"
                    before = sqlglot.parse_one(sql, read="mysql")
                    after = self.assert_table_filters(self.rewrite_allowed(policy, sql), policy)
                    self.assertEqual(after.expressions[0].sql(dialect="mysql"),
                                     before.expressions[0].sql(dialect="mysql"))

    def test_nested_date_and_format_expressions_remain_allowed(self):
        expressions = [
            "YEAR(DATE_SUB(CREATE_TIME, INTERVAL 1 MONTH))",
            "DATE_FORMAT(DATE_ADD(CREATE_TIME, INTERVAL 1 DAY), '%Y-%m-%d')",
            "STR_TO_DATE(CONCAT(YEAR(CREATE_TIME), '-01-01'), '%Y-%m-%d')",
            "CASE WHEN YEAR(CREATE_TIME)=2025 THEN MONTHNAME(CREATE_TIME) "
            "ELSE DATE_FORMAT(CREATE_TIME, '%Y') END",
        ]
        for role, policy in self.policies:
            for expression in expressions:
                with self.subTest(role=role, expression=expression):
                    self.assert_table_filters(self.rewrite_allowed(
                        policy, f"SELECT {expression} FROM t_project"), policy)

    def test_date_predicates_cannot_bypass_filters_with_or(self):
        sql = ("SELECT ID FROM t_project WHERE YEAR(CREATE_TIME)=2025 "
               "OR TENANT_ID=7 OR OPERATER_STATUS=-1 OR ID=11 ORDER BY ID")
        for role, policy in self.policies:
            with self.subTest(role=role):
                expected = [(10,)] if role == "user" else [(10,), (11,)]
                self.assertEqual(self.run_query(policy, sql), expected)

    def test_date_queries_keep_cte_join_and_union_scopes(self):
        queries = [
            "WITH p AS (SELECT ID, CREATE_TIME FROM t_project) "
            "SELECT ID FROM p WHERE YEAR(CREATE_TIME)=2025 ORDER BY ID",
            "SELECT p.ID FROM t_project p JOIN t_project_user u ON p.ID=u.PROJECT_ID "
            "WHERE YEAR(p.CREATE_TIME)=2025 AND DATE(u.CREATE_TIME)='2025-03-04' ORDER BY p.ID",
            "SELECT ID FROM t_project WHERE YEAR(CREATE_TIME)=2025 UNION "
            "SELECT PROJECT_ID FROM t_project_user WHERE DATE(CREATE_TIME)='2025-03-04' ORDER BY ID",
        ]
        for role, policy in self.policies:
            for sql in queries:
                with self.subTest(role=role, sql=sql):
                    expected = [(10,)] if role == "user" else [(10,), (11,)]
                    self.assertEqual(self.run_query(policy, sql), expected)

    def test_date_queries_keep_project_detail_id_filter(self):
        sql = "SELECT ID FROM t_project_user WHERE YEAR(CREATE_TIME)=2025 ORDER BY ID"
        for role, policy in self.policies:
            with self.subTest(role=role):
                self.assert_table_filters(self.rewrite_allowed(policy, sql), policy)
                expected = [(1,)] if role == "user" else [(1,), (2,)]
                self.assertEqual(self.run_query(policy, sql), expected)

    def test_safe_dates_do_not_grant_projects_to_unassigned_user(self):
        self.user.project_ids = ()
        for sql in ["SELECT YEAR(CREATE_TIME) FROM t_project",
                    "SELECT DATE(CREATE_TIME) FROM t_project_user"]:
            with self.subTest(sql=sql), self.assertRaises(SQLAccessDenied):
                self.user.restrict_sql(sql, self.columns)

    def test_unsafe_functions_nested_in_date_arguments_are_denied(self):
        unsafe_calls = ["SLEEP(1)", "LOAD_FILE('/etc/passwd')", "BENCHMARK(1, 1)",
                        "GET_LOCK('date-test', 1)", "unapproved_udf(CREATE_TIME)"]
        for role, policy in self.policies:
            for call in unsafe_calls:
                for expression in [f"YEAR({call})", f"DATE({call})", f"MONTHNAME({call})",
                                   f"DAYOFMONTH({call})", f"DAYOFWEEK({call})",
                                   f"DAYOFYEAR({call})", f"WEEKOFYEAR({call})"]:
                    with self.subTest(role=role, expression=expression), self.assertRaises(SQLAccessDenied):
                        policy.restrict_sql(f"SELECT {expression} FROM t_project", self.columns)

    def test_unsafe_functions_nested_in_format_arguments_are_denied(self):
        unsafe_calls = ["SLEEP(1)", "LOAD_FILE('/etc/passwd')", "BENCHMARK(1, 1)",
                        "GET_LOCK('date-test', 1)", "unapproved_udf(CREATE_TIME)"]
        for role, policy in self.policies:
            for call in unsafe_calls:
                expressions = [f"DATE_FORMAT(CREATE_TIME, {call})",
                               f"STR_TO_DATE(CREATE_TIME, {call})",
                               f"STR_TO_DATE({call}, '%Y-%m-%d %H:%i:%s')"]
                for expression in expressions:
                    with self.subTest(role=role, expression=expression), self.assertRaises(SQLAccessDenied):
                        policy.restrict_sql(f"SELECT {expression} FROM t_project", self.columns)

    def test_unsafe_functions_nested_in_interval_arguments_are_denied(self):
        unsafe_calls = ["SLEEP(1)", "LOAD_FILE('/etc/passwd')", "BENCHMARK(1, 1)",
                        "GET_LOCK('date-test', 1)", "unapproved_udf(CREATE_TIME)"]
        for role, policy in self.policies:
            for call in unsafe_calls:
                for name in ["DATE_ADD", "DATE_SUB", "ADDDATE"]:
                    sql = f"SELECT {name}(CREATE_TIME, INTERVAL {call} DAY) FROM t_project"
                    with self.subTest(role=role, sql=sql), self.assertRaises(SQLAccessDenied):
                        policy.restrict_sql(sql, self.columns)

    def test_safe_date_functions_do_not_allow_cross_schema_access(self):
        queries = [
            "SELECT YEAR(CREATE_TIME) FROM another_schema.t_project",
            "SELECT DATE(CREATE_TIME) FROM information_schema.tables",
            "SELECT YEAR(CREATE_TIME) FROM t_project WHERE ID IN "
            "(SELECT ID FROM another_schema.t_project)",
        ]
        for role, policy in self.policies:
            for sql in queries:
                with self.subTest(role=role, sql=sql), self.assertRaises(SQLAccessDenied):
                    policy.restrict_sql(sql, self.columns)

    def test_safe_date_functions_do_not_allow_multiple_statements(self):
        queries = [
            "SELECT YEAR(CREATE_TIME) FROM t_project; SELECT DATE(CREATE_TIME) FROM t_project",
            "SELECT DATE(CREATE_TIME) FROM t_project; DELETE FROM t_project",
        ]
        for role, policy in self.policies:
            for sql in queries:
                with self.subTest(role=role, sql=sql), self.assertRaises(SQLAccessDenied):
                    policy.restrict_sql(sql, self.columns)


if __name__ == "__main__":
    unittest.main()
