import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from utils.sql_semantics import validate_aggregate_shape
from utils.sql_generation_checks import SQLGenerationError
from utils.sql_permissions import SQLPermissions, SQLAccessDenied
from utils.DB_vllm_32B import DB


class AggregateShapeTests(unittest.TestCase):
    columns={'orders':{'ID','NAME','PRICE','BUYER_ID','CREATED'},
             'buyers':{'ID','NAME','JOINED'}}
    def test_detail_with_global_aggregation_is_rejected_at_any_query_scope(self):
        for sql in ['SELECT NAME,SUM(PRICE) FROM orders',
                    'SELECT ID,COUNT(*) FROM orders',
                    'WITH x AS (SELECT NAME,MAX(PRICE) FROM orders) SELECT * FROM x',
                    'SELECT x.* FROM (SELECT NAME,AVG(PRICE) FROM orders) x']:
            with self.subTest(sql=sql),self.assertRaises(SQLGenerationError):
                validate_aggregate_shape(sql,self.columns)

    def test_valid_shapes_preserve_requested_grain(self):
        for sql in ['SELECT NAME,SUM(PRICE) OVER () FROM orders',
                    'SELECT NAME,SUM(PRICE) FROM orders GROUP BY NAME',
                    'SELECT ID,NAME,SUM(PRICE) FROM orders GROUP BY ID',
                    'SELECT SUM(PRICE),COUNT(*) FROM orders',
                    'SELECT YEAR(CREATED) y,SUM(PRICE) FROM orders GROUP BY y',
                    'SELECT ROUND(SUM(PRICE),2) FROM orders',
                    'SELECT NAME,SUM(PRICE) FROM orders WHERE ID=47',
                    'SELECT SUM(o.PRICE),b.PRICE/SUM(o.PRICE) FROM orders o CROSS JOIN (SELECT PRICE FROM orders WHERE ID=47) b',
                    'SELECT b.JOINED,MIN(o.CREATED) FROM orders o JOIN buyers b ON b.ID=o.BUYER_ID WHERE o.BUYER_ID=47',
                    'SELECT (SELECT SUM(PRICE) FROM orders) AS total FROM buyers WHERE ID=47']:
            with self.subTest(sql=sql):validate_aggregate_shape(sql,self.columns)

    def test_window_inside_an_expression_is_not_a_global_aggregate(self):
        validate_aggregate_shape('SELECT NAME,COALESCE(SUM(PRICE) OVER(),0) FROM orders',self.columns)

    def test_or_and_nullable_join_do_not_prove_a_single_detail_value(self):
        for sql in ['SELECT NAME,COUNT(*) FROM orders WHERE ID=47 OR ID=48',
                    'SELECT b.NAME,COUNT(*) FROM orders o LEFT JOIN buyers b ON b.ID=o.BUYER_ID WHERE o.ID=47']:
            with self.assertRaises(SQLGenerationError):validate_aggregate_shape(sql,self.columns)
        with self.assertRaises(SQLGenerationError):
            validate_aggregate_shape('SELECT SUM(o.PRICE),b.PRICE FROM orders o CROSS JOIN (SELECT PRICE FROM orders WHERE ID=47 OR ID=48) b',self.columns)

    def test_rollup_requires_an_explicit_grouping_marker(self):
        with self.assertRaises(SQLGenerationError):
            validate_aggregate_shape('SELECT NAME,COUNT(*) FROM orders GROUP BY NAME WITH ROLLUP',self.columns)
        validate_aggregate_shape('SELECT NAME,COUNT(*),GROUPING(NAME) AS summary_flag FROM orders GROUP BY NAME WITH ROLLUP',self.columns)


class DummySourceAndFunctionTests(unittest.TestCase):
    columns={'t_staff':{'ID','TENANT_ID','OPERATER_STATUS','FULL_NAME'}}
    def setUp(self):self.guard=SQLPermissions(17,None,allow_all_projects=True)
    def test_bare_dummy_source_is_removed_but_subquery_is_still_tenant_guarded(self):
        sql=self.guard.restrict_sql('SELECT (SELECT COUNT(*) FROM t_staff) AS n FROM DUAL',self.columns)
        self.assertNotIn('DUAL',sql);self.assertIn('`TENANT_ID` = 17',sql)

    def test_dummy_source_does_not_authorize_constant_only_queries_or_foreign_tables(self):
        for sql in ['SELECT 1 FROM DUAL','SELECT 1 FROM private.dual',
                    'SELECT 1 FROM `dual`','SELECT (SELECT COUNT(*) FROM private.t_staff) FROM DUAL',
                    'SELECT s.ID FROM t_staff s JOIN DUAL ON 1=1']:
            with self.subTest(sql=sql),self.assertRaises(SQLAccessDenied):self.guard.restrict_sql(sql,self.columns)

    def test_cte_called_dual_is_not_treated_as_a_dummy_source(self):
        sql=self.guard.restrict_sql('WITH dual AS (SELECT ID FROM t_staff) SELECT ID FROM dual',self.columns)
        self.assertIn('FROM `dual`',sql);self.assertIn('`TENANT_ID` = 17',sql)

    def test_grouping_is_a_read_only_allowed_function(self):
        sql=self.guard.restrict_sql('SELECT FULL_NAME,COUNT(*),GROUPING(FULL_NAME) FROM t_staff GROUP BY FULL_NAME WITH ROLLUP',self.columns)
        self.assertIn('GROUPING',sql)

    def test_near_miss_function_is_retryable_without_being_executed_or_allowed(self):
        db=object.__new__(DB);db.permissions=self.guard;db.table_columns=self.columns;db.conn=Mock()
        result=db.execute_sql('SELECT SUMM(ID) FROM t_staff',validate_generated=True)
        self.assertEqual(result['error_type'],'unknown_generated_function')
        self.assertIn('SUM',result['error']);db.conn.ping.assert_not_called()
        with self.assertRaises(SQLAccessDenied):self.guard.restrict_sql('SELECT SUMM(ID) FROM t_staff',self.columns)

    def test_side_effect_function_and_non_generated_requests_keep_denial(self):
        db=object.__new__(DB);db.permissions=self.guard;db.table_columns=self.columns;db.conn=Mock()
        for sql,generated in [('SELECT SLEEP(9) FROM t_staff',True),('SELECT SUMM(ID) FROM t_staff',False)]:
            self.assertEqual(db.execute_sql(sql,validate_generated=generated)['status'],'denied')
        db.conn.ping.assert_not_called()

    def test_hallucinated_suffix_can_retry_within_a_read_only_function_family(self):
        db=object.__new__(DB);db.permissions=self.guard;db.table_columns=self.columns;db.conn=Mock()
        result=db.execute_sql('SELECT DATEDATE(ID,ID) FROM t_staff',validate_generated=True)
        self.assertEqual(result['error_type'],'unknown_generated_function')
        self.assertIn('DATEDIFF',result['error']);db.conn.ping.assert_not_called()


if __name__=='__main__':unittest.main()
