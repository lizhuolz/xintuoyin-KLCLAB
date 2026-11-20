"""Offline regressions for production SQL routing, context and accepted SSE output."""
import ast
import asyncio
import json
import os
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import AsyncIterator, List, Optional
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from agent.node import make_chatbot_node, make_should_sql_node
from agent.router import route_after_chatbot_local
from agent.sql_planner import make_sql_planner_node
from agent.utils import extract_current_user_question


BACKEND = Path(__file__).resolve().parents[1]


def app_functions(*names, **extras):
    """Run real pure/event functions without importing app startup or services."""
    tree = ast.parse((BACKEND / 'app.py').read_text())
    selected = [node for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    namespace = dict(re=re, json=json, os=os, List=List, Optional=Optional,
                     AsyncIterator=AsyncIterator, AIMessage=AIMessage,
                     AIMessageChunk=AIMessageChunk, HumanMessage=HumanMessage,
                     ToolMessage=ToolMessage, MAX_FILE_TEXT_CHARS=12000,
                     MAX_HISTORY_ROUNDS=6, FILE_HISTORY_SNIPPET_CHARS=3000,
                     now_ms=lambda: 1)
    namespace.update(extras)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(BACKEND / 'app.py'), 'exec'), namespace)
    return namespace


def production_prompt(question):
    namespace = app_functions('_compact_text', '_strip_rag_sources', 'compose_chat_prompt')
    return namespace['compose_chat_prompt'](
        question, {'messages': [{'question': '项目ID 17的名称是什么？', 'answer': '项目甲'}]},
        [{'filename': '范围.txt', 'kind': 'text', 'text': '项目甲的普通编号为0006。'}])


class SQLQuestionFlowTests(unittest.TestCase):
    def test_actual_production_wrapper_extracts_only_current_question(self):
        question = '该项目的成员有几个？'
        self.assertEqual(extract_current_user_question([HumanMessage(content=production_prompt(question))]), question)

    def test_should_sql_then_planner_retains_exact_question_with_history_and_files(self):
        question = '该项目的成员有几个？'
        state = {'messages': [HumanMessage(content=production_prompt(question)), AIMessage(content='初稿')],
                 'select_model': 'offline', 'current_question': question,
                 'query_context': '项目ID 17；附件普通编号0006'}
        judge = Mock()
        judge.invoke.return_value = AIMessage(content='{"sql_needed":true,"reason":"需要取数"}')
        with patch('langchain_openai.ChatOpenAI', return_value=judge):
            update = make_should_sql_node('sql_tool')(state)
        state.update(update)
        result = make_sql_planner_node()(state)
        self.assertEqual(result['messages'][-1].tool_calls[0]['args'], {'question': question})
        self.assertEqual(judge.invoke.call_args.args[0][-1].content, '用户问题：' + question)
        self.assertFalse(any('系统补充要求' in str(message.content) for message in state['messages']))
        self.assertEqual(state['query_context'], '项目ID 17；附件普通编号0006')

    def test_entity_count_question_still_enters_sql_after_history_is_removed(self):
        state = {'messages': [HumanMessage(content='项目成员有几个？'), AIMessage(content='待查询')],
                 'current_question': '项目成员有几个？'}
        self.assertEqual(route_after_chatbot_local(state), 'should_sql')

    def test_project_list_requests_enter_sql_without_history_keywords(self):
        questions = [
            '我目前能查看哪些研发项目？列出项目名称、负责人、起止时间和当前状态。',
            '列出当前可访问项目的名称和状态。',
            '给我当前研发项目列表。',
            '返回当前可访问项目清单。',
        ]
        for question in questions:
            with self.subTest(question=question):
                state = {'messages': [HumanMessage(content=question), AIMessage(content='待处理')],
                         'current_question': question}
                self.assertEqual(route_after_chatbot_local(state), 'should_sql')

    def test_project_instructions_and_explanations_do_not_enter_sql(self):
        questions = ['如何查看项目？', '如何查看项目列表？', '列出项目管理的常见方法。',
                     '项目管理有几个步骤？', '研发项目是什么？', '项目负责人通常承担什么职责？']
        for question in questions:
            with self.subTest(question=question):
                state = {'messages': [HumanMessage(content=question), AIMessage(content='说明')],
                         'current_question': question}
                self.assertEqual(route_after_chatbot_local(state), 'end')

    def test_machine_document_turns_thinking_off(self):
        model = Mock()
        model.bind.return_value = model
        model.invoke.return_value = AIMessage(content='{"calculations":[]}')
        with patch('langchain_openai.ChatOpenAI', return_value=model) as factory:
            make_chatbot_node(0, [], machine_output=True, stream_answer=False)(
                {'messages': [HumanMessage(content='查询项目')], 'select_model': 'offline', 'enable_thinking': True})
        self.assertEqual(factory.call_args.kwargs['model_kwargs'],
                         {'extra_body': {'chat_template_kwargs': {'enable_thinking': False}}})


class SQLStreamFlowTests(unittest.TestCase):
    def test_graph_messages_publish_only_accepted_sql_answer(self):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        from langgraph.constants import TAG_NOSTREAM
        from langgraph.graph import StateGraph, START, END
        from agent.messagestate import GraphState
        from agent.sql_answer import make_sql_answer_node

        bad = '可能有成员未返回，建议重新查询核实名单。'
        accepted = '员工51：4.00小时。'
        model = FakeListChatModel(responses=[bad, accepted], disable_streaming=True, tags=[TAG_NOSTREAM])

        def factory(*args, **kwargs):
            self.assertFalse(kwargs['stream_answer'])
            self.assertIn(TAG_NOSTREAM, kwargs['model_tags'])
            return lambda state: {'messages': [model.invoke(state['messages'])]}

        payload = {'status': 'ok', 'truncated': False, 'fields': ['staff', 'hours'],
                   'data': [{'staff': 51, 'hours': '4.00'}]}
        state = {'current_question': '列出各成员登记小时，无记录也保留。',
                 'messages': [HumanMessage(content='历史背景与当前问题'),
                              ToolMessage(content=json.dumps(payload), name='sql_tool', tool_call_id='q')]}
        with patch('agent.sql_answer.make_chatbot_node', side_effect=factory):
            graph = StateGraph(GraphState)
            graph.add_node('sql_answer', make_sql_answer_node())
            graph.add_edge(START, 'sql_answer')
            graph.add_edge('sql_answer', END)
            events = list(graph.compile().stream(state, stream_mode='messages'))
        self.assertEqual(''.join(message.content for message, _ in events), accepted)
        self.assertTrue(all(metadata['langgraph_node'] == 'sql_answer' for _, metadata in events))

    def test_endpoint_snapshots_raw_question_and_context_and_replaces_preliminary_answer(self):
        question = '该项目的成员有几个？'
        prompt = production_prompt(question)
        accepted = '| 名称 |\n| --- |\n| 项目甲 |\n'

        class Graph:
            async def astream(self, inputs, config, stream_mode):
                self.inputs, self.config = inputs, config
                yield AIMessage(content='未查询的初稿'), {'langgraph_node': 'chatbot_local'}
                yield ToolMessage(content='{"status":"ok","data":[]}', name='sql_tool', tool_call_id='q'), {'langgraph_node': 'sql_tools'}
                yield AIMessage(content=accepted), {'langgraph_node': 'sql_answer'}

        graph = Graph()
        namespace = app_functions('_compact_preview', '_format_tool_result_preview', '_tool_trace_event',
                                  '_tool_trace_thinking_delta', '_strip_think_blocks', 'iterate_chat_events',
                                  agent_app=graph)
        user = {'tenant_id': 6, 'staff_id': 51, 'role': 'user'}

        async def collect():
            return [event async for event in namespace['iterate_chat_events'](
                [{'type': 'text', 'text': prompt}, {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,PRIVATE'}}],
                'offline', False, 'ignored', raw_user_message=question)]

        with patch.dict('sys.modules', {'services.user_auth': SimpleNamespace(get_current_user=lambda: user)}):
            events = asyncio.run(collect())
        self.assertEqual(graph.inputs.get('current_question'), question)
        context = graph.inputs.get('query_context', '')
        self.assertIn('项目ID 17', context)
        self.assertIn('普通编号为0006', context)
        self.assertNotIn('PRIVATE', context)
        self.assertEqual(graph.config['configurable']['sql_query_context'], context)
        self.assertEqual(graph.config['configurable']['sql_user'], user)
        self.assertIn({'type': 'answer_replace', 'content': ''}, events)
        visible = ''
        for event in events:
            if event['type'] == 'answer_replace':
                visible = event['content']
            elif event['type'] == 'answer_delta':
                visible += event['delta']
        self.assertEqual(visible, accepted)
        self.assertEqual(events[-1]['result']['answer'], accepted.strip())


if __name__ == '__main__':
    unittest.main()
