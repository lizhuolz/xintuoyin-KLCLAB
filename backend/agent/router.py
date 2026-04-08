from __future__ import annotations
from typing import  Literal
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from agent.messagestate import GraphState
from langchain_core.messages import ToolMessage
from agent.utils import extract_current_user_question


def _looks_like_sql_query(text: str) -> bool:
    lowered = (text or "").lower()
    keywords = ("数据库", "sql", "字段", "统计", "发票", "员工", "总数", "总额", "查询", "人数", "多少", "汇总", "排行", "数据表")
    return any(keyword in lowered for keyword in keywords)


def route_start(state: GraphState) -> Literal["chatbot_local", "chatbot_web"]:
    return "chatbot_web" if state.get("enable_web") else "chatbot_local"


def route_after_should_sql(state: GraphState) -> Literal["sql_planner", "end"]:
    return "sql_planner" if state.get("sql_needed") else "end"


# =============================
# 6) 路由：sql_planner 是否产生 tool_calls？
# =============================
def route_after_sql_planner(state: GraphState) -> Literal["sql_tools", "sql_answer"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "sql_tools"
    return "sql_answer"


# =============================
# 5) chatbot 后路由：有 tool_calls -> 对应 tools；无 -> should_sql
# =============================
def route_after_chatbot_local(state: GraphState) -> Literal["tools_local", "should_sql","end"]:
    messages = state["messages"]
    if len(messages) > 1 and isinstance(messages[-2], ToolMessage):
        return "end"
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        tool_names = {str(call.get("name") or "").strip() for call in (last.tool_calls or [])}
        if _looks_like_sql_query(extract_current_user_question(messages)) and "sql_tool" not in tool_names:
            return "should_sql"
        return "tools_local"
    return "should_sql"


def route_after_chatbot_web(state: GraphState) -> Literal["tools_web", "should_sql"]:
    messages = state["messages"]
    if len(messages) > 1 and isinstance(messages[-2], ToolMessage):
        return "end"
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools_web"
    return "should_sql"
