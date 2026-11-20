"""The selected SQL route must execute the original question and retain valid empties."""
import json
import unittest

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from agent.sql_planner import make_sql_planner_node
from agent.router import route_after_sql_planner, route_after_sql_answer


class SQLDispatchTests(unittest.TestCase):
    def test_forwards_full_question_without_rewriting_or_identity_arguments(self):
        question = '普通编号0006的项目成员按工时降序，并列按员工ID升序；负责人不额外计入。'
        result = make_sql_planner_node()({'messages': [HumanMessage(content=question)]})
        calls = result['messages'][0].tool_calls
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['name'], 'sql_tool')
        self.assertEqual(calls[0]['args'], {'question': question})
        self.assertEqual(route_after_sql_planner(result), 'sql_tools')

    def test_uses_current_question_from_the_production_wrapper(self):
        question = '哪些未删除项目没有成员？空结果不能补造。'
        wrapped = '历史背景\n【当前用户问题】\n' + question + '\n【回答要求】不得改题'
        result = make_sql_planner_node()({'messages': [HumanMessage(content=wrapped)]})
        self.assertEqual(result['messages'][0].tool_calls[0]['args']['question'], question)

    def test_uses_latest_user_question_not_previous_summary(self):
        messages = [HumanMessage(content='旧问题'), AIMessage(content='错误的改写'),
                    HumanMessage(content='最新问题：当前租户的全部未删除项目')]
        result = make_sql_planner_node()({'messages': messages})
        self.assertEqual(result['messages'][0].tool_calls[0]['args']['question'], messages[-1].content)

    def test_no_question_does_not_create_database_call(self):
        result = make_sql_planner_node()({'messages': []})
        self.assertFalse(result['messages'][0].tool_calls)

    def test_valid_empty_and_denial_end_but_execution_error_can_use_existing_fallback(self):
        cases = [({'status': 'empty', 'data': []}, 'end'),
                 ({'data': []}, 'end'),
                 ({'status': 'denied', 'Access_check': False}, 'end'),
                 ({'status': 'ok', 'data': [{'NAME': 'error plan'}]}, 'end'),
                 ({'status': 'error', 'message': 'query failed'}, 'sql_rag_fallback')]
        for payload, expected in cases:
            with self.subTest(payload=payload):
                state = {'messages': [ToolMessage(content=json.dumps(payload), name='sql_tool', tool_call_id='x'),
                                      AIMessage(content='查询结果说明')]}
                self.assertEqual(route_after_sql_answer(state), expected)


if __name__ == '__main__':
    unittest.main()
