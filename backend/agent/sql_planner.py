"""Dispatch an already selected SQL route without lossy question rewriting."""
from uuid import uuid4

from langchain_core.messages import AIMessage
from agent.utils import extract_current_user_question


def make_sql_planner_node(tool_name="sql_tool"):
    def sql_planner_node(state):
        question = state.get("current_question") or extract_current_user_question(state.get("messages", []))
        if not question.strip():
            return {"messages": [AIMessage(content="请输入完整的数据库查询问题。")]}
        return {"messages": [AIMessage(content="", tool_calls=[{
            "name": tool_name,
            "args": {"question": question},
            "id": "call_sql_" + uuid4().hex,
        }])]}
    return sql_planner_node
