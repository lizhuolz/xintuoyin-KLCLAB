"""Schema grounding regressions; live model replays remain the acceptance test."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from utils.DB_vllm_32B import DB
from utils.sql_permissions import SQLPermissions


class GenerationContextTests(unittest.TestCase):
    def setUp(self):
        self.db = object.__new__(DB)
        self.db.table_columns = {'t_staff': {'ID', 'TENANT_ID', 'DEPT_NAME', 'FULL_NAME'}}
        self.db.detailed_comments = {'t_staff': {'table_comment': '员工', 'columns': [
            {'COLUMN_NAME': 'TENANT_ID', 'COLUMN_COMMENT': '租户编号'},
            {'COLUMN_NAME': 'DEPT_NAME', 'COLUMN_COMMENT': '部门名称'},
            {'COLUMN_NAME': 'FULL_NAME', 'COLUMN_COMMENT': '姓名'},
        ]}}
        self.db.permissions = Mock()
        self.db.permissions.type_hint.return_value = 'N/A'
        self.db.permissions.access_hint.return_value = 'tenant-only'
        self.db.permissions.is_project_table.return_value = False
        self.db._format_schema = Mock(return_value='CREATE TABLE t_staff (DEPT_NAME varchar(255));')
        self.db._read_internal = Mock(return_value=[{'DEPT_NAME': '业务一部'}])
        self.db.client = SimpleNamespace(chat=SimpleNamespace(completions=Mock()))
        self.db.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='SELECT DEPT_NAME FROM t_staff'))])
        self.db.model_name = 'test-model'
        self.db.generate_temperature = 0
        self.db.generate_max_tokens = 1024
        self.db.extra_body = {}

    def test_selector_catalogue_keeps_real_column_names_without_duplicate_audit_fields(self):
        catalogue = self.db.get_database_comments()
        self.assertIn('DEPT_NAME:部门名称', catalogue)
        self.assertIn('FULL_NAME:姓名', catalogue)
        self.assertNotIn('TENANT_ID:租户编号', catalogue)
        self.assertIn('TENANT_ID=租户', catalogue)

    def test_generation_sees_actual_column_index_and_original_literals(self):
        self.db.generate_sql(['t_staff'], '部门名称为“研发”的员工', error_context='Unknown column s.DEPARTMENT_NAME')
        request = self.db.client.chat.completions.create.call_args.kwargs
        system, user = [m['content'] for m in request['messages']]
        self.assertIn('DEPT_NAME:部门名称', user)
        self.assertIn('部门名称为“研发”的员工', user)
        self.assertIn('Unknown column s.DEPARTMENT_NAME', user)
        self.assertIn('Do not add ENABLE_STATUS', system)

    def test_unknown_column_retry_lists_real_candidates_only(self):
        hint = self.db._retry_column_hint(['t_staff'], "(1054, Unknown column 's.DEPARTMENT_NAME' in 'field list')")
        self.assertIn('t_staff.DEPT_NAME', hint)
        self.assertIn('does not exist', hint)
        self.assertEqual(self.db._retry_column_hint(['t_staff'], '(1267, Illegal mix of collations)'), '')

    def test_semantic_hints_require_their_real_schema_fields(self):
        self.assertIn('员工登记部门名称字段是 DEPT_NAME', self.db._schema_semantics(['t_staff']))
        self.db.table_columns['t_staff'].remove('DEPT_NAME')
        self.assertNotIn('员工登记部门名称字段是 DEPT_NAME', self.db._schema_semantics(['t_staff']))

    def test_department_value_hints_use_the_same_tenant_guard(self):
        self.db.permissions = SQLPermissions(6, 51)
        hint = self.db._database_value_hints(['t_staff'], '某部门员工')
        executed = self.db._read_internal.call_args.args[0]
        self.assertIn('`TENANT_ID` = 6', executed)
        self.assertIn('LIMIT 51', executed)
        self.assertIn('业务一部', hint)
        self.db._read_internal.reset_mock()
        self.assertEqual(self.db._database_value_hints(['t_staff'], '员工人数'), 'N/A')
        self.db._read_internal.assert_not_called()

    def test_parser_failure_retries_without_executing_or_claiming_auth_failure(self):
        self.db.permissions = SQLPermissions(6, 51)
        self.db.conn = Mock()
        result = self.db.execute_sql('SELECT a.b.ID FROM t_staff AS a.b')
        self.assertEqual(result.get('error_type'), 'sql_syntax')
        self.assertIn('error', result)
        self.db.conn.ping.assert_not_called()
        denied = self.db.execute_sql('DELETE FROM t_staff')
        self.assertEqual(denied['status'], 'denied')
        self.db.conn.ping.assert_not_called()

    def test_manager_examples_keep_ordinary_users_project_scope(self):
        self.db.permissions = SQLPermissions(6, 51)
        self.db.permissions.project_ids = (10,)
        self.db.table_columns['t_project'] = {'ID', 'TENANT_ID', 'OPERATER_STATUS',
                                             'PROJECT_MANAGER_IDS', 'PROJECT_MANAGER_NAMES'}
        self.db._read_internal.return_value = [{'PROJECT_MANAGER_IDS': '["42"]',
                                               'PROJECT_MANAGER_NAMES': '["负责人甲"]'}]
        hint = self.db._database_value_hints(['t_project'], '登记负责人列表')
        executed = self.db._read_internal.call_args.args[0]
        self.assertIn('`TENANT_ID` = 6', executed)
        self.assertIn('`ID` IN (10)', executed)
        self.assertIn('LIMIT 3', executed)
        self.assertIn('负责人甲', hint)


if __name__ == '__main__':
    unittest.main()
