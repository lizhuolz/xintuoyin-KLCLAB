"""Real relational null semantics, with no model output or testcase answers mocked."""
import sqlite3
import unittest
from unittest.mock import Mock

from utils.sql_generation_checks import SQLGenerationError, validate_optional_scope_filters, validate_independent_staff_metrics, validate_requested_literals, validate_optional_time_filters, nonexistent_generated_tables, validate_project_absence_grain
from utils.sql_generation_checks import validate_entity_identity_projection


class EntityIdentityProjectionTests(unittest.TestCase):
    columns = {
        't_project': {'ID','PROJECT_NAME','START_DATE','PROJECT_RESEARCH_YEAR','TENANT_ID','RESEARCH_CONTENTS'},
        't_staff': {'ID','FULL_NAME','WORK_NUM','ENTRY_TIME','TENANT_ID'},
    }

    def validate(self, sql, question='未删除项目中，开始日期在2021年的有哪些？请同时列开始日期和研发年度。'):
        return validate_entity_identity_projection(sql, question, self.columns)

    def test_attribute_only_rows_cannot_identify_requested_projects(self):
        with self.assertRaisesRegex(SQLGenerationError, '最终SELECT'):
            self.validate('SELECT START_DATE, PROJECT_RESEARCH_YEAR FROM t_project WHERE YEAR(START_DATE)=2021')

    def test_id_or_name_can_identify_objects_with_aliases_or_concatenation(self):
        for sql in ['SELECT p.ID AS 编号,p.START_DATE FROM t_project p',
                    'SELECT p.PROJECT_NAME AS 名称 FROM t_project p',
                    "SELECT CONCAT(p.ID,':',p.PROJECT_NAME) AS 对象 FROM t_project p",
                    'SELECT * FROM t_project', 'SELECT p.* FROM t_project p']:
            self.validate(sql)

    def test_predicate_count_and_condition_ids_are_not_projected_identities(self):
        for sql in ['SELECT START_DATE FROM t_project WHERE ID>3',
                    'SELECT COUNT(ID) AS 项目ID FROM t_project',
                    "SELECT CASE WHEN ID>3 THEN '新' ELSE '旧' END AS 分类 FROM t_project"]:
            with self.assertRaises(SQLGenerationError):self.validate(sql)

    def test_cte_identity_must_reach_the_outer_projection(self):
        prefix='WITH p AS (SELECT ID,PROJECT_NAME,START_DATE FROM t_project) '
        with self.assertRaises(SQLGenerationError):self.validate(prefix+'SELECT START_DATE FROM p')
        self.validate(prefix+'SELECT p.PROJECT_NAME,START_DATE FROM p')
        self.validate('WITH unused AS (SELECT ID FROM t_staff),p AS (SELECT * FROM t_project) SELECT ID FROM p')

    def test_union_object_branches_keep_identity_and_subtotals_are_allowed(self):
        self.validate('SELECT ID FROM t_project UNION ALL SELECT ID FROM t_project')
        self.validate('SELECT ID FROM t_project UNION ALL SELECT COUNT(*) FROM t_project')
        with self.assertRaises(SQLGenerationError):
            self.validate('SELECT START_DATE FROM t_project UNION ALL SELECT START_DATE FROM t_project')

    def test_employee_identity_is_not_a_joined_project_identity(self):
        question='哪些员工没有参与项目？列出入职日期。'
        with self.assertRaises(SQLGenerationError):
            self.validate('SELECT p.ID,s.ENTRY_TIME FROM t_staff s LEFT JOIN t_project p ON p.ID=s.ID',question)
        self.validate('SELECT s.WORK_NUM,s.ENTRY_TIME FROM t_staff s',question)

    def test_aggregate_attributes_and_explicit_only_fields_do_not_gain_id_columns(self):
        for question in ['当前项目预算总数是多少？',
                         '按年份统计项目数量。',
                         '哪些月份有项目？只列月份。',
                         '项目中开始在2021年的有哪些？只返回开始日期和研发年度。',
                         '项目ID7的开始日期是什么？']:
            self.validate('SELECT START_DATE FROM t_project',question)

    def test_named_entity_content_enumeration_is_not_an_entity_listing(self):
        self.validate('SELECT RESEARCH_CONTENTS FROM t_project WHERE ID=7',
                      '项目ID7已登记的主要研究内容有哪些？请概括其中的六项内容。')

    def test_authorization_denial_precedes_generation_diagnostics(self):
        from utils.DB_vllm_32B import DB
        from utils.sql_permissions import SQLAccessDenied
        db=DB.__new__(DB);db.permissions=Mock();db.table_columns=self.columns;db.conn=Mock()
        db.permissions.restrict_sql.side_effect=SQLAccessDenied('查询包含未授权数据库或表')
        db._known_database_tables={'t_project'};db.permissions.allowed_tables=set()
        result=db.execute_sql('SELECT START_DATE FROM t_project',validate_generated=True,
                              source_question='哪些项目在2021年开始？')
        self.assertEqual(result['status'],'denied')
        self.assertNotIn('executed_sql',result)
        db.conn.ping.assert_not_called()

    def test_missing_identity_enters_bounded_generation_retry_before_database_execution(self):
        from utils.DB_vllm_32B import DB
        db=DB.__new__(DB);db.permissions=Mock();db.table_columns=self.columns;db.conn=Mock()
        db.permissions.tenant_id=9;db.permissions.allow_all_projects=True
        db.permissions.restrict_sql.side_effect=lambda query,columns:query
        db.select_table=Mock(return_value=['t_project'])
        bad='SELECT START_DATE FROM t_project WHERE TENANT_ID=9'
        good='SELECT ID,PROJECT_NAME,START_DATE FROM t_project WHERE TENANT_ID=9'
        db.generate_sql=Mock(side_effect=[bad,good])
        cursor=Mock();cursor.description=[('ID',),('PROJECT_NAME',),('START_DATE',)]
        cursor.fetchmany.return_value=[(8,'样例甲','2021-02-01')]
        manager=__import__('unittest.mock',fromlist=['MagicMock']).MagicMock()
        manager.__enter__.return_value=cursor;db.conn.cursor.return_value=manager
        result=db.query_db('未删除项目中，开始于2021年的有哪些？同时列开始日期。')
        self.assertEqual(result['data'][0]['PROJECT_NAME'],'样例甲')
        self.assertEqual(result['executed_sql'],good)
        self.assertIn('最终SELECT',db.generate_sql.call_args_list[1].kwargs['error_context'])
        self.assertEqual(db.permissions.restrict_sql.call_count,2)
        cursor.execute.assert_called_once_with(good)


class OptionalJoinScopeTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.executescript('''
            CREATE TABLE members(ID INTEGER, TENANT_ID INTEGER);
            CREATE TABLE hours(STAFF_ID INTEGER, TENANT_ID INTEGER, OPERATER_STATUS INTEGER, VALUE INTEGER);
            INSERT INTO members VALUES(11,1),(12,1),(13,1);
            INSERT INTO hours VALUES(13,1,1,5);
        ''')
        self.prefix = ('SELECT m.ID, COALESCE(SUM(h.VALUE),0) FROM members m '
                       'LEFT JOIN hours h ON h.STAFF_ID=m.ID ')
        self.suffix = ' GROUP BY m.ID HAVING COALESCE(SUM(h.VALUE),0)=0 ORDER BY m.ID'

    def tearDown(self):
        self.conn.close()

    def test_where_scope_drops_no_record_members_but_on_scope_retains_them(self):
        broken = self.prefix + 'WHERE m.TENANT_ID=1 AND h.TENANT_ID=1' + self.suffix
        corrected = self.prefix + 'AND h.TENANT_ID=1 WHERE m.TENANT_ID=1' + self.suffix
        self.assertEqual(self.conn.execute(broken).fetchall(), [])
        self.assertEqual(self.conn.execute(corrected).fetchall(), [(11,0),(12,0)])
        with self.assertRaisesRegex(SQLGenerationError, '可空侧'):
            validate_optional_scope_filters(broken, 1)
        validate_optional_scope_filters(corrected, 1)

    def test_soft_delete_check_also_belongs_in_optional_join(self):
        with self.assertRaises(SQLGenerationError):
            validate_optional_scope_filters(self.prefix+'WHERE h.OPERATER_STATUS>0'+self.suffix, 1)

    def test_time_where_or_null_still_loses_members_with_only_other_months(self):
        self.conn.execute('ALTER TABLE hours ADD COLUMN MONTHS INTEGER')
        self.conn.execute('UPDATE hours SET MONTHS=7')
        self.conn.execute('INSERT INTO hours VALUES(11,1,1,7,6)')
        self.conn.execute('INSERT INTO hours VALUES(12,1,1,9,6)')
        broken=self.prefix+'WHERE (h.MONTHS=7 OR h.STAFF_ID IS NULL)'+self.suffix
        corrected=self.prefix+'AND h.MONTHS=7 WHERE m.TENANT_ID=1'+self.suffix
        self.assertEqual(self.conn.execute(broken).fetchall(),[])
        self.assertEqual(self.conn.execute(corrected).fetchall(),[(11,0),(12,0)])
        with self.assertRaises(SQLGenerationError):validate_optional_time_filters(broken)
        validate_optional_time_filters(corrected)

    def test_inner_time_filters_and_nested_alias_scopes_are_allowed(self):
        validate_optional_time_filters('SELECT m.ID FROM members m JOIN hours h ON h.STAFF_ID=m.ID WHERE h.MONTHS=7')
        validate_optional_time_filters(self.prefix+'WHERE EXISTS (SELECT 1 FROM hours h WHERE h.MONTHS=7)'+self.suffix)

    def test_null_preserving_or_and_explicit_inner_join_are_allowed(self):
        validate_optional_scope_filters(self.prefix+'WHERE h.TENANT_ID=1 OR h.STAFF_ID IS NULL'+self.suffix,1)
        validate_optional_scope_filters('SELECT m.ID FROM members m JOIN hours h ON h.STAFF_ID=m.ID WHERE h.TENANT_ID=1',1)

    def test_cte_where_is_checked_without_confusing_shadowed_aliases(self):
        with self.assertRaises(SQLGenerationError):
            validate_optional_scope_filters('WITH c AS ('+self.prefix+'WHERE (h.TENANT_ID=1)) SELECT * FROM c',1)
        validate_optional_scope_filters(self.prefix+'WHERE EXISTS (SELECT 1 FROM hours h WHERE h.TENANT_ID=1)'+self.suffix,1)

    def test_other_tenant_predicates_and_business_fields_are_not_silently_changed(self):
        validate_optional_scope_filters(self.prefix+'WHERE h.TENANT_ID=2'+self.suffix,1)
        validate_optional_scope_filters(self.prefix+'WHERE h.VALUE=0'+self.suffix,1)


class ProjectAbsenceGrainTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.conn.executescript('''
          CREATE TABLE t_project(ID INTEGER,PROJECT_NAME TEXT);
          CREATE TABLE t_project_user(PROJECT_ID INTEGER,STAFF_ID INTEGER);
          CREATE TABLE t_project_user_r_d_time(ID INTEGER,PROJECT_ID INTEGER,STAFF_ID INTEGER);
          INSERT INTO t_project VALUES(1,'has_hours'),(2,'no_hours');
          INSERT INTO t_project_user VALUES(1,11),(1,12),(2,13);
          INSERT INTO t_project_user_r_d_time VALUES(101,1,11);
        ''')
        self.broken=('SELECT DISTINCT p.ID FROM t_project p JOIN t_project_user u ON u.PROJECT_ID=p.ID '
                     'LEFT JOIN t_project_user_r_d_time h ON h.PROJECT_ID=p.ID AND h.STAFF_ID=u.STAFF_ID '
                     'WHERE h.ID IS NULL')

    def tearDown(self):self.conn.close()

    def test_one_unmatched_member_does_not_make_the_project_empty(self):
        self.assertEqual(self.conn.execute(self.broken).fetchall(),[(1,),(2,)])
        with self.assertRaises(SQLGenerationError):validate_project_absence_grain(self.broken)

    def test_project_level_absence_keeps_member_existence_independent(self):
        correct=('SELECT p.ID FROM t_project p WHERE EXISTS '
                 '(SELECT 1 FROM t_project_user u WHERE u.PROJECT_ID=p.ID) AND NOT EXISTS '
                 '(SELECT 1 FROM t_project_user_r_d_time h WHERE h.PROJECT_ID=p.ID)')
        self.assertEqual(self.conn.execute(correct).fetchall(),[(2,)])
        validate_project_absence_grain(correct)

    def test_member_results_and_explicit_member_quantifier_are_supported(self):
        validate_project_absence_grain(self.broken.replace('DISTINCT p.ID','p.ID,u.STAFF_ID'))
        validate_project_absence_grain('SELECT p.ID FROM t_project p WHERE EXISTS '
            '(SELECT 1 FROM t_project_user u WHERE u.PROJECT_ID=p.ID AND NOT EXISTS '
            '(SELECT 1 FROM t_project_user_r_d_time h WHERE h.PROJECT_ID=p.ID AND h.STAFF_ID=u.STAFF_ID))')


class GeneratedTableNameTests(unittest.TestCase):
    def setUp(self):
        self.known={'t_project','t_project_budget','t_private'}
        self.allowed={'t_project','t_project_budget'}

    def test_missing_physical_table_is_a_generation_diagnostic(self):
        self.assertEqual(nonexistent_generated_tables('SELECT * FROM t_project_monthly_budget',self.known,self.allowed),['t_project_monthly_budget'])

    def test_existing_forbidden_tables_foreign_schemas_and_unknown_catalog_stay_denied(self):
        for query in ['SELECT * FROM t_private','SELECT * FROM other_db.t_missing',
                      'SELECT * FROM t_private JOIN t_missing ON 1=1']:
            self.assertEqual(nonexistent_generated_tables(query,self.known,self.allowed),[])
        self.assertEqual(nonexistent_generated_tables('SELECT * FROM t_missing',None,self.allowed),[])

    def test_cte_names_are_not_mistaken_for_missing_or_forbidden_physical_tables(self):
        query='WITH t_private AS (SELECT * FROM t_project) SELECT * FROM t_private'
        self.assertEqual(nonexistent_generated_tables(query,self.known,self.allowed),[])

    def test_guard_runs_first_and_only_generated_missing_table_denials_retry(self):
        from utils.DB_vllm_32B import DB
        from utils.sql_permissions import SQLAccessDenied
        db=DB.__new__(DB);db.permissions=Mock();db.permissions.allowed_tables=self.allowed
        db.table_columns={}
        db.permissions.restrict_sql.side_effect=SQLAccessDenied('查询包含未授权数据库或表')
        db._known_database_tables=self.known;db.detailed_comments={name:{} for name in self.allowed}
        db.conn=Mock()
        query='SELECT * FROM t_project_monthly_budget'
        self.assertEqual(db.execute_sql(query)['status'],'denied')
        self.assertEqual(db.execute_sql(query,validate_generated=True)['error_type'],'unknown_generated_table')
        self.assertEqual(db.execute_sql('SELECT * FROM t_private',validate_generated=True)['status'],'denied')
        db.permissions.restrict_sql.side_effect=SQLAccessDenied('SQL 函数 SLEEP 未获准使用')
        self.assertEqual(db.execute_sql(query,validate_generated=True)['status'],'denied')
        db.conn.ping.assert_not_called()


class RequestedLiteralTests(unittest.TestCase):
    def test_inserting_or_removing_whitespace_in_a_quoted_name_is_rejected(self):
        for query,question in [("SELECT * FROM t WHERE NAME='示例 项目'",'读取“示例项目”的登记字段'),
                               ("SELECT * FROM t WHERE NAME='研发组'",'名称精确为“研发 组”的员工')]:
            with self.assertRaises(SQLGenerationError):validate_requested_literals(query,question)

    def test_exact_values_and_unrelated_date_or_label_literals_are_allowed(self):
        validate_requested_literals("SELECT * FROM t WHERE NAME='示例项目'",'读取“示例项目”的登记字段')
        validate_requested_literals("SELECT * FROM t WHERE DATE>='2026-01-01 00:00:00'",'查询“示例项目”在2026年的数据')
        validate_requested_literals("SELECT * FROM t WHERE NAME='研发'",'研发部门员工')


class IndependentStaffMetricTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.conn.executescript('''
          CREATE TABLE t_staff(ID INTEGER);
          CREATE TABLE t_project_user(STAFF_ID INTEGER, PROJECT_ID INTEGER);
          CREATE TABLE t_project_user_r_d_time(ID INTEGER, STAFF_ID INTEGER, PROJECT_ID INTEGER, R_D_HOUR INTEGER);
          INSERT INTO t_staff VALUES(1);
          INSERT INTO t_project_user VALUES(1,10),(1,20);
          INSERT INTO t_project_user_r_d_time VALUES(101,1,10,2),(102,1,30,7);
        ''')
        self.prefix=('SELECT s.ID,COUNT(DISTINCT u.PROJECT_ID),SUM(h.R_D_HOUR) FROM t_staff s '
                     'LEFT JOIN t_project_user u ON u.STAFF_ID=s.ID '
                     'LEFT JOIN t_project_user_r_d_time h ON h.STAFF_ID=s.ID ')

    def tearDown(self):
        self.conn.close()

    def test_join_fanout_and_membership_limited_hours_are_detected(self):
        fanout=self.prefix+'GROUP BY s.ID'
        limited=self.prefix+'AND h.PROJECT_ID=u.PROJECT_ID GROUP BY s.ID'
        self.assertEqual(self.conn.execute(fanout).fetchall(),[(1,2,18)])
        self.assertEqual(self.conn.execute(limited).fetchall(),[(1,2,2)])
        for query in [fanout,limited]:
            with self.assertRaises(SQLGenerationError):
                validate_independent_staff_metrics(query)

    def test_independent_metrics_keep_unassigned_hours_and_do_not_multiply_records(self):
        query=('SELECT s.ID,p.n,h.hours FROM t_staff s LEFT JOIN '
               '(SELECT STAFF_ID,COUNT(DISTINCT PROJECT_ID) AS n FROM t_project_user GROUP BY STAFF_ID) p '
               'ON p.STAFF_ID=s.ID LEFT JOIN '
               '(SELECT STAFF_ID,SUM(R_D_HOUR) AS hours FROM t_project_user_r_d_time GROUP BY STAFF_ID) h '
               'ON h.STAFF_ID=s.ID')
        self.assertEqual(self.conn.execute(query).fetchall(),[(1,2,9)])
        validate_independent_staff_metrics(query)

    def test_count_and_sum_of_the_same_hours_fact_are_allowed(self):
        query=self.prefix.replace('COUNT(DISTINCT u.PROJECT_ID)','COUNT(h.ID)')+'GROUP BY s.ID'
        validate_independent_staff_metrics(query)


if __name__=='__main__':
    unittest.main()
