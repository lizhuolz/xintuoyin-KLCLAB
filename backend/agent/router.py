from __future__ import annotations
from typing import  Literal
from langchain_core.messages import AIMessage, HumanMessage
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
_SQL_FAIL_INDICATORS = ("error", "错误", "未找到", "no result", "empty", "不存在", "no data")


def _last_tool_msg_failed_for(messages, tool_name: str) -> bool:
    """从后往前找最后一个该工具的 ToolMessage，判断它是否失败/空结果。"""
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage) and (msg.name or "") == tool_name:
            content = (msg.content or "").lower()
            return any(k in content for k in _SQL_FAIL_INDICATORS)
    return False


def route_after_chatbot_local(state: GraphState) -> Literal["tools_local", "should_sql", "sql_rag_fallback", "end"]:
    messages = state["messages"]
    # sql_tool 已执行过且失败 → 走 fallback 让模型改用 rag_tool
    if not state.get("sql_fallback_done") and _last_tool_msg_failed_for(messages, "sql_tool"):
        return "sql_rag_fallback"
    has_tool_result = any(isinstance(m, ToolMessage) for m in messages)
    last = messages[-1]
    has_tool_calls = bool(isinstance(last, AIMessage) and getattr(last, "tool_calls", None))
    if has_tool_calls:
        return "tools_local"
    if has_tool_result:
        # 已调过 rag/web 工具，但用户问题看起来像 SQL 类且 should_sql 还没尝试 → 再补一次 SQL 路径
        if not state.get("sql_attempted") and _looks_like_sql_query(extract_current_user_question(messages)):
            return "should_sql"
        return "end"
    # 没用过工具：常规路径
    if _looks_like_sql_query(extract_current_user_question(messages)):
        return "should_sql"
    return "end"


def route_after_chatbot_web(state: GraphState) -> Literal["tools_web", "should_sql", "sql_rag_fallback", "end"]:
    messages = state["messages"]
    if not state.get("sql_fallback_done") and _last_tool_msg_failed_for(messages, "sql_tool"):
        return "sql_rag_fallback"
    has_tool_result = any(isinstance(m, ToolMessage) for m in messages)
    last = messages[-1]
    has_tool_calls = bool(isinstance(last, AIMessage) and getattr(last, "tool_calls", None))
    if has_tool_calls:
        return "tools_web"
    if has_tool_result:
        # 调过 web/rag 后，如果是 SQL 类问题且 should_sql 还没尝试过 → 补一次 SQL 路径
        if not state.get("sql_attempted") and _looks_like_sql_query(extract_current_user_question(messages)):
            return "should_sql"
        return "end"
    return "should_sql"

    # 注意：web_chatbot_node 的 system prompt 已强制要求调用 tavily_search，
    # 如果模型仍然不调用，node.py 的 _should_force_tool_retry 会触发重试。


def _sql_result_is_empty(state: GraphState) -> bool:
    """检查 SQL 查询结果是否为空/无结果。"""
    messages = state.get("messages", [])
    # 从后往前找最后一个 sql_tool 的 ToolMessage
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage) and (msg.name or "") == "sql_tool":
            content = (msg.content or "").lower()
            empty_indicators = ("没有", "未找到", "无结果", "no result", "empty", "error", "错误", "不存在")
            return any(indicator in content for indicator in empty_indicators)
    return False


def route_after_sql_answer(state: GraphState) -> Literal["sql_rag_fallback", "end"]:
    """SQL 回答后检查是否需要回退到 RAG。"""
    if state.get("sql_fallback_done"):
        return "end"
    if _sql_result_is_empty(state):
        return "sql_rag_fallback"
    return "end"


def sql_rag_fallback_node(state: GraphState):
    """SQL 查询无结果时，清理 SQL 相关消息，提示模型用 rag_tool 重试。"""
    messages = list(state["messages"])
    # 移除 SQL 子流程产生的消息（ToolMessage + 相关 AIMessage）
    cleaned = []
    skip_tool_ids = set()
    for msg in messages:
        if isinstance(msg, ToolMessage) and (msg.name or "") == "sql_tool":
            skip_tool_ids.add(getattr(msg, "tool_call_id", None))
            continue
        if isinstance(msg, AIMessage):
            tool_calls = getattr(msg, "tool_calls", None) or []
            if any(tc.get("name") == "sql_tool" for tc in tool_calls):
                continue
        cleaned.append(msg)
    # 添加提示
    cleaned.append(HumanMessage(
        content="数据库中未查询到相关数据，请尝试调用 rag_tool 从知识库中检索回答。"
    ))
    return {"messages": cleaned, "sql_fallback_done": True}
