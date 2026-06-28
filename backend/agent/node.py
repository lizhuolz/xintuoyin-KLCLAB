from __future__ import annotations

import os
import uuid

from langchain_core.messages import SystemMessage
from langgraph.graph import MessagesState


from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode
from .messagestate import GraphState
import json
import re
from typing import Any, Dict, List, Literal, TypedDict
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from agent.utils import extract_current_user_question, extract_last_user_text, safe_json_load

# 获得一个chatbot节点
def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _chat_model_kwargs(enable_thinking: bool = True) -> dict:
    """根据 enable_thinking 控制是否启用模型思考。"""
    if enable_thinking:
        return {}
    return {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}


def _coerce_xml_tool_calls(message: AIMessage) -> AIMessage:
    existing_tool_calls = getattr(message, "tool_calls", None) or []
    if existing_tool_calls:
        valid_existing = [
            tc for tc in existing_tool_calls
            if str(tc.get("name") or "").strip() and str(tc.get("name") or "").strip() != "unknown_tool"
        ]
        if valid_existing:
            return message
    content = getattr(message, "content", "") or ""
    matches = re.findall(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", content, flags=re.DOTALL | re.IGNORECASE)
    tool_calls = []
    for raw in matches:
        try:
            parsed = safe_json_load(raw)
        except Exception:
            continue
        name = str(parsed.get("name") or "").strip()
        args = parsed.get("arguments") or parsed.get("args") or {}
        if not name:
            continue
        if not isinstance(args, dict):
            args = {}
        tool_calls.append({
            "name": name,
            "args": args,
            "id": f"call_{uuid.uuid4().hex[:16]}",
            "type": "tool_call",
        })

    if not tool_calls:
        xml_blocks = re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", content, flags=re.DOTALL | re.IGNORECASE)
        for block in xml_blocks:
            fn_match = re.search(r"<function=([a-zA-Z0-9_\-]+)>\s*(.*?)\s*</function>", block, flags=re.DOTALL | re.IGNORECASE)
            if not fn_match:
                continue
            name = str(fn_match.group(1) or "").strip()
            inner = fn_match.group(2) or ""
            args = {}
            for param_name, param_value in re.findall(
                r"<parameter=([a-zA-Z0-9_\-]+)>\s*(.*?)\s*</parameter>",
                inner,
                flags=re.DOTALL | re.IGNORECASE,
            ):
                args[str(param_name).strip()] = str(param_value).strip()
            if not name:
                continue
            tool_calls.append({
                "name": name,
                "args": args,
                "id": f"call_{uuid.uuid4().hex[:16]}",
                "type": "tool_call",
            })

    if not tool_calls:
        return message

    cleaned_content = re.sub(r"<tool_call>\s*.*?\s*</tool_call>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()
    return AIMessage(
        content=cleaned_content,
        tool_calls=tool_calls,
        additional_kwargs=getattr(message, "additional_kwargs", {}),
        response_metadata=getattr(message, "response_metadata", {}),
        id=getattr(message, "id", None),
        name=getattr(message, "name", None),
    )


def _has_invalid_or_missing_tool_name(message: AIMessage) -> bool:
    tool_calls = getattr(message, "tool_calls", None) or []
    if not tool_calls:
        return False
    return any(not str(call.get("name") or "").strip() for call in tool_calls)


def _looks_like_sql_query(text: str) -> bool:
    lowered = (text or "").lower()
    keywords = ("数据库", "sql", "表", "字段", "统计", "发票", "员工", "总数", "总额", "查询", "人数", "多少", "汇总", "排行")
    return any(keyword in lowered for keyword in keywords)


def _looks_like_rag_query(text: str) -> bool:
    lowered = (text or "").lower()
    keywords = ("知识库", "rag", "文档", "附件", "文件", "资料", "根据知识库", "根据文档", "根据资料", "口令", "负责人", "上线日期")
    return any(keyword in lowered for keyword in keywords)


def _dedupe_tool_calls(message: AIMessage) -> AIMessage:
    tool_calls = getattr(message, "tool_calls", None) or []
    if len(tool_calls) <= 1:
        return message

    deduped = []
    seen = set()
    for call in tool_calls:
        key = (
            str(call.get("name") or "").strip(),
            json.dumps(call.get("args") or {}, ensure_ascii=False, sort_keys=True),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(call)

    if len(deduped) == len(tool_calls):
        return message

    return AIMessage(
        content=getattr(message, "content", "") or "",
        tool_calls=deduped,
        additional_kwargs=getattr(message, "additional_kwargs", {}),
        response_metadata=getattr(message, "response_metadata", {}),
        id=getattr(message, "id", None),
        name=getattr(message, "name", None),
    )


def _filter_tool_calls_for_intent(message: AIMessage, user_text: str, enable_web: bool) -> AIMessage:
    tool_calls = getattr(message, "tool_calls", None) or []
    if not tool_calls:
        return message

    preferred_names = None
    if _looks_like_sql_query(user_text):
        preferred_names = {"sql_tool"}
    elif _looks_like_rag_query(user_text):
        preferred_names = {"rag_tool"}
    elif enable_web:
        preferred_names = {"tavily_search_with_summary"}

    if not preferred_names:
        return message

    filtered_tool_calls = [
        call for call in tool_calls
        if str(call.get("name") or "").strip() in preferred_names
    ]
    if not filtered_tool_calls:
        return message
    if len(filtered_tool_calls) == len(tool_calls):
        return message

    return AIMessage(
        content=getattr(message, "content", "") or "",
        tool_calls=filtered_tool_calls,
        additional_kwargs=getattr(message, "additional_kwargs", {}),
        response_metadata=getattr(message, "response_metadata", {}),
        id=getattr(message, "id", None),
        name=getattr(message, "name", None),
    )


def _should_force_tool_retry(message: AIMessage, user_text: str, enable_web: bool, tools) -> bool:
    """只在 coerce 后仍无 tool_calls 且内容有残留工具标记时才重试。"""
    if not tools or not isinstance(message, AIMessage):
        return False
    if getattr(message, "tool_calls", None):
        return False
    content = getattr(message, "content", "") or ""
    lower = content.lower()
    # 内容中有工具调用标记但没被 coerce 解析出来——需要重试
    has_markup = any(token in lower for token in ("<tool_call>", "</tool_call>", "<function="))
    return has_markup


def make_chatbot_node(
    temperature: float,
    tools,
    system_prompt: str = "你是一个专业的人工智能助手。",
):
    def chatbot_node(state: GraphState):
        from langchain_openai import ChatOpenAI

        model = state["select_model"]
        user_text = extract_current_user_question(state["messages"])
        enable_thinking = bool(state.get("enable_thinking", False))
        base_llm = ChatOpenAI(
            model=model,
            temperature=_env_float("CHAT_MODEL_TEMPERATURE", temperature),
            streaming=not tools,
            max_tokens=_env_int("CHAT_MODEL_MAX_TOKENS", 4096),
            timeout=_env_float("CHAT_MODEL_TIMEOUT", 120),
            model_kwargs=_chat_model_kwargs(enable_thinking),
        )
        llm = base_llm
        if tools:
            llm = llm.bind_tools(tools)
        
        # 强化指令：要求 AI 尊重原文
        instruction = (
            "\n\n【行为准则】"
            "\n1. 你必须始终针对【当前用户提问】进行回答。历史对话仅作参考背景，不要重复回答历史问题。"
            "\n2. 如果当前输入是不完整的文字、单个标点符号或无意义字符，请直接回复'请输入完整的问题，我会为您解答'，不要基于历史上下文猜测并回答。"
            "\n3. 如果你调用了知识库检索工具 `rag_tool`，请务必直接使用返回的原文进行回答。"
            "\n4. 严禁对原文进行过度总结或润色，必须保留原文的关键指标、数据和术语。"
            "\n5. 回答时请注明来源（如：根据[XXX文件]记载...）。"
            "\n6. 如果需要输出 <think>，请只保留关键决策，避免长篇复述问题。"
            "\n7. 涉及知识库内容的问题，你必须调用 `rag_tool` 检索最新内容后再回答，不要直接引用历史对话中的知识库相关回答，因为知识库可能已更新或关闭。"
        )
        
        full_system_prompt = system_prompt + instruction
        sys_msg = SystemMessage(content=full_system_prompt)
        response = llm.invoke([sys_msg, *state["messages"]])
        if isinstance(response, AIMessage):
            response = _coerce_xml_tool_calls(response)
            response = _dedupe_tool_calls(response)
            if tools and (_has_invalid_or_missing_tool_name(response) or _should_force_tool_retry(response, user_text, bool(state.get("enable_web")), tools)):
                strict_tool_prompt = full_system_prompt + (
                    "\n\n【工具调用格式要求】"
                    "\n如果当前问题需要工具，你必须发起工具调用，不能只输出思考过程。"
                    "\n优先使用如下 XML 结构之一，不要输出额外解释："
                    "\n方案1："
                    "\n<tool_call>"
                    '\n{"name":"工具名","arguments":{"参数名":"参数值"}}'
                    "\n</tool_call>"
                    "\n方案2："
                    "\n<tool_call>"
                    "\n<function=工具名>"
                    "\n<parameter=参数名>参数值</parameter>"
                    "\n</function>"
                    "\n</tool_call>"
                    "\n不要输出空工具名，不要输出 unknown_tool。"
                )
                retry_llm = ChatOpenAI(
                    model=model,
                    temperature=_env_float("CHAT_MODEL_TEMPERATURE", temperature),
                    streaming=False,
                    max_tokens=_env_int("CHAT_MODEL_MAX_TOKENS", 4096),
                    timeout=_env_float("CHAT_MODEL_TIMEOUT", 120),
                    model_kwargs=_chat_model_kwargs(enable_thinking),
                )
                if tools:
                    retry_llm = retry_llm.bind_tools(tools)
                retry_response = retry_llm.invoke([SystemMessage(content=strict_tool_prompt), *state["messages"]])
                if isinstance(retry_response, AIMessage):
                    response = _coerce_xml_tool_calls(retry_response)
                    response = _dedupe_tool_calls(response)
        return {"messages": [response]}

    return chatbot_node

def make_should_sql_node(SQL_TOOL_NAME) -> GraphState:
    
    def res(state: GraphState):
        from langchain_openai import ChatOpenAI

        judge_llm = ChatOpenAI(
            model=state["select_model"],
            temperature=_env_float("SQL_ROUTE_TEMPERATURE", 0.0),
            max_tokens=_env_int("CHAT_MODEL_MAX_TOKENS", 4096),
            timeout=_env_float("CHAT_MODEL_TIMEOUT", 120),
            model_kwargs=_chat_model_kwargs(False),
        )
        user_text = extract_last_user_text(state["messages"])
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
            obj = safe_json_load(content)
            sql_needed = bool(obj.get("sql_needed", False))
            reason = str(obj.get("reason", "") or "")
        except Exception:
            sql_needed = False
            reason = "LLM 输出解析失败，默认不走 SQL。"

        updates = {
            "sql_needed": sql_needed,
            "sql_reason": reason,
            "sql_attempted": True,   # 标记已判断过，避免 chatbot 兜底再次进入
        }

        if sql_needed:
            new_messages = list(state["messages"])
            last = new_messages[-1] if new_messages else None
            if isinstance(last, AIMessage) and not getattr(last, "tool_calls", None):
                new_messages = new_messages[:-1]

            new_messages.append(
                HumanMessage(
                    content=(
                        f"系统补充要求：这个问题必须通过数据库查询来回答。你只能调用工具 `{SQL_TOOL_NAME}` 获取数据，"
                        "请先发起一次工具调用获取结果，然后再基于工具返回结果回答用户。"
                    )
                )
            )
            updates["messages"] = new_messages

        return updates
    return res
