"""Valid authorized SQL executes without a model-based semantic veto."""
import unittest
from unittest.mock import Mock, MagicMock
from utils.DB_vllm_32B import DB
from utils.sql_permissions import SQLPermissions


class EvidenceExecutionTests(unittest.TestCase):
    def test_guarded_business_outputs_do_not_require_a_second_model_opinion(self):
        db=DB.__new__(DB)
        db.permissions=SQLPermissions(17,None,allow_all_projects=True)
        db.table_columns={'t_project_milestone':{'ID','NAME','TIME','TYPE_NAME','TENANT_ID','OPERATER_STATUS','PROJECT_ID'}}
        db.client=Mock();db.conn=Mock()
        cursor=Mock();cursor.description=[('NAME',),('TIME',),('TYPE_NAME',)]
        cursor.fetchmany.return_value=[('示例里程碑','2025-03-02','样例阶段')]
        manager=MagicMock();manager.__enter__.return_value=cursor;db.conn.cursor.return_value=manager
        result=db.execute_sql('SELECT NAME,TIME,TYPE_NAME FROM t_project_milestone WHERE PROJECT_ID=91 ORDER BY TIME DESC LIMIT 3',
                              validate_generated=True,source_question='项目91最近三个里程碑的名称、时间和阶段类型是什么？')
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['data'][0]['TYPE_NAME'],'样例阶段')
        self.assertIn('17',result['executed_sql'])
        cursor.execute.assert_called_once_with(result['executed_sql'])
        db.client.chat.completions.create.assert_not_called()

if __name__=='__main__':unittest.main()
