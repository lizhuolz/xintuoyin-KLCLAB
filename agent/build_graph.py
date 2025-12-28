"""
LangGraph: chatbot(普通工具调用) + LLM判断是否需要SQL + SQL工具调用 + 基于SQL结果生成最终回答

流程：
START -> chatbot
chatbot 若有 tool_calls -> tools(普通工具) -> chatbot 循环
chatbot 若无 tool_calls -> should_sql(LLM判断)
  - sql_needed = False -> END
  - sql_needed = True  -> sql_planner(仅允许SQL工具的LLM生成SQL tool_call)
        -> sql_tools(执行SQL工具)
        -> sql_answer(根据ToolMessage里的SQL结果生成最终回答)
        -> END
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Literal, TypedDict

from agent.node import make_chatbot_node
from agent.tools import TOOLS

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode


# =============================
# 0) 配置：你的 SQL 工具名
# =============================
SQL_TOOL_NAME = "sql_tool"  # <<< 改成你项目里 SQL 工具的 name（必须在 TOOLS 里）
# =============================
# 3) SQL 工具节点：只放 SQL 工具
# =============================
SQL_TOOLS = [t for t in TOOLS if getattr(t, "name", None) == SQL_TOOL_NAME]
if not SQL_TOOLS:
    raise ValueError(
        f"没有在 TOOLS 中找到 name={SQL_TOOL_NAME} 的 SQL 工具。"
        f"请检查 SQL_TOOL_NAME 或 TOOLS 配置。当前 TOOLS: {[getattr(t, 'name', None) for t in TOOLS]}"
    )

# =============================
# 1) State：继承 MessagesState（关键：不要重定义 messages）
# =============================
class GraphState(MessagesState, total=False):
    sql_needed: bool
    sql_reason: str


# =============================
# 2) chatbot（你原有）
# =============================
chatbot_node = make_chatbot_node("gpt-4o", 0, TOOLS)
tools_node = ToolNode(TOOLS)

sql_tools_node = ToolNode(SQL_TOOLS)
# sql_planner：只允许 SQL 工具调用（产出 tool_calls）
sql_planner_node = make_chatbot_node("gpt-4o", 0, SQL_TOOLS)
# sql_answer：不允许任何工具调用（只根据 messages 里 ToolMessage 总结）
sql_answer_node = make_chatbot_node("gpt-4o", 0, [])


# =============================
# 4) 路由：chatbot 输出是否包含 tool_calls？
# =============================
def route_after_chatbot(state: GraphState) -> Literal["tools", "should_sql"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools"
    return "should_sql"


# =============================
# 5) LLM 判断：是否需要 SQL
# =============================
judge_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def _extract_last_user_text(messages: List[BaseMessage]) -> str:
    for m in reversed(messages):
        if getattr(m, "type", None) == "human":
            return getattr(m, "content", "") or ""
        if isinstance(m, dict) and m.get("role") == "user":
            return m.get("content", "") or ""
    return ""


def _safe_json_load(s: str) -> Dict[str, Any]:
    s = (s or "").strip()
    s = re.sub(r"^```json\s*", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"^```\s*", "", s).strip()
    s = re.sub(r"\s*```$", "", s).strip()

    if not (s.startswith("{") and s.endswith("}")):
        m = re.search(r"\{.*\}", s, flags=re.DOTALL)
        if m:
            s = m.group(0)

    return json.loads(s)


def should_sql_node(state: GraphState) -> GraphState:
    user_text = _extract_last_user_text(state["messages"])

    system = SystemMessage(
        content=(
            "你是一个路由分类器。任务：判断用户问题是否必须通过数据库(SQL)查询才能回答。\n"
            "只有当需要从数据库取数/统计/列表/筛选/聚合/排行/时间范围数据等，才返回 sql_needed=true。\n"
            "如果仅靠常识、解释、建议、写作、代码示例即可回答，返回 sql_needed=false。\n"
            "你必须只输出严格 JSON，不要输出任何多余文字。\n"
            '输出格式：{"sql_needed": true/false, "reason": "一句话原因"}'
        )
    )
    human = HumanMessage(content=f"用户问题：{user_text}")

    resp = judge_llm.invoke([system, human])
    content = getattr(resp, "content", "") or ""

    try:
        obj = _safe_json_load(content)
        sql_needed = bool(obj.get("sql_needed", False))
        reason = str(obj.get("reason", "") or "")
    except Exception:
        sql_needed = False
        reason = "LLM 输出解析失败，默认不走 SQL。"

    state["sql_needed"] = sql_needed
    state["sql_reason"] = reason

    # 若需要SQL：删掉 chatbot 刚刚可能生成的“最终回答”，避免两段回复
    if sql_needed:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and not getattr(last, "tool_calls", None):
            state["messages"] = state["messages"][:-1]

        # 追加 system 指令引导 sql_planner 只调用 SQL 工具
        state["messages"].append(
            SystemMessage(
                content=(
                    f"需要通过数据库查询来回答。你只能调用工具 `{SQL_TOOL_NAME}` 获取数据。"
                    "请先发起一次工具调用获取结果，然后再基于工具返回结果回答用户。"
                )
            )
        )

    return state


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
# 7) build_graph：完整搭图
# =============================
def build_graph():
    graph_builder = StateGraph(GraphState)

    graph_builder.add_node("chatbot", chatbot_node)
    graph_builder.add_node("tools", tools_node)

    graph_builder.add_node("should_sql", should_sql_node)
    graph_builder.add_node("sql_planner", sql_planner_node)
    graph_builder.add_node("sql_tools", sql_tools_node)
    graph_builder.add_node("sql_answer", sql_answer_node)

    graph_builder.add_edge(START, "chatbot")

    graph_builder.add_conditional_edges(
        "chatbot",
        route_after_chatbot,
        {
            "tools": "tools",
            "should_sql": "should_sql",
        },
    )

    graph_builder.add_edge("tools", "chatbot")

    graph_builder.add_conditional_edges(
        "should_sql",
        route_after_should_sql,
        {
            "sql_planner": "sql_planner",
            "end": END,
        },
    )

    graph_builder.add_conditional_edges(
        "sql_planner",
        route_after_sql_planner,
        {
            "sql_tools": "sql_tools",
            "sql_answer": "sql_answer",
        },
    )

    graph_builder.add_edge("sql_tools", "sql_answer")
    graph_builder.add_edge("sql_answer", END)

    return graph_builder


graph_builder = build_graph()
