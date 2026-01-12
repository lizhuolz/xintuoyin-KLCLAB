from __future__ import annotations
from typing import  Literal
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from agent.messagestate import GraphState
from langchain_core.messages import ToolMessage


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
    last = state["messages"][-1]
    messages = state["messages"]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools_local"
    if len(messages) > 1 and isinstance(messages[-2], ToolMessage):
        return "end"
    return "should_sql"


def route_after_chatbot_web(state: GraphState) -> Literal["tools_web", "should_sql"]:
    messages = state["messages"]
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools_web"
    if len(messages) > 1 and isinstance(messages[-2], ToolMessage):
        return "end"
    return "should_sql"