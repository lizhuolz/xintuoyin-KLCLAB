import unittest

from langchain_core.messages import AIMessage, HumanMessage

from agent.node import _dedupe_tool_calls, _should_force_tool_retry
from agent.router import route_after_chatbot_local
from agent.utils import extract_current_user_question


class ToolRetryHeuristicsTestCase(unittest.TestCase):
    def test_force_retry_for_meta_tool_reasoning_without_structured_tool_call(self):
        message = AIMessage(
            content='用户要求我使用 calculator 工具计算 88+12，并且只返回结果。我需要调用 calculator 工具，表达式是 "88+12"。\n</think>\n\n'
        )
        should_retry = _should_force_tool_retry(
            message,
            "请使用 calculator 计算 88+12，只返回结果",
            False,
            tools=[type("Tool", (), {"name": "calculator"})()],
        )
        self.assertTrue(should_retry)

    def test_dedupe_tool_calls_by_name_and_args(self):
        message = AIMessage(
            content="",
            tool_calls=[
                {"name": "calculator", "args": {"expression": "88+12"}, "id": "call-1", "type": "tool_call"},
                {"name": "calculator", "args": {"expression": "88+12"}, "id": "call-2", "type": "tool_call"},
                {"name": "echo", "args": {"text": "ok"}, "id": "call-3", "type": "tool_call"},
            ],
        )

        deduped = _dedupe_tool_calls(message)

        self.assertEqual(len(deduped.tool_calls), 2)
        self.assertEqual(deduped.tool_calls[0]["name"], "calculator")
        self.assertEqual(deduped.tool_calls[1]["name"], "echo")

    def test_extract_current_user_question_from_composed_prompt(self):
        composed = (
            "【当前用户问题】\n请使用 calculator 计算 88+12，只返回结果\n\n"
            "【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。"
        )
        extracted = extract_current_user_question([HumanMessage(content=composed)])
        self.assertEqual(extracted, "请使用 calculator 计算 88+12，只返回结果")

    def test_route_after_chatbot_local_does_not_misclassify_composed_prompt_as_sql(self):
        composed = (
            "【当前用户问题】\n请使用 calculator 计算 88+12，只返回结果\n\n"
            "【回答要求】\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。"
        )
        state = {
            "messages": [
                HumanMessage(content=composed),
                AIMessage(
                    content="我需要调用 calculator。",
                    tool_calls=[
                        {"name": "calculator", "args": {"expression": "88+12"}, "id": "call-1", "type": "tool_call"}
                    ],
                ),
            ]
        }
        self.assertEqual(route_after_chatbot_local(state), "tools_local")


if __name__ == "__main__":
    unittest.main()
