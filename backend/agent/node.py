from __future__ import annotations

import os

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState

from langchain_openai import ChatOpenAI

from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode
from .messagestate import GraphState
import json
import re
from typing import Any, Dict, List, Literal, TypedDict
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from agent.utils import extract_last_user_text, safe_json_load

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


def make_chatbot_node(temperature: float, tools, system_prompt: str = "你是一个专业的人工智能助手。",streaming=True):
    def chatbot_node(state: GraphState):
        model = state["select_model"]
        llm = ChatOpenAI(
            model=model,
            temperature=_env_float("CHAT_MODEL_TEMPERATURE", temperature),
            streaming=streaming,
            max_tokens=_env_int("CHAT_MODEL_MAX_TOKENS", 4096),
            timeout=_env_float("CHAT_MODEL_TIMEOUT", 120),
        ).bind_tools(tools)
        
        # 强化指令：要求 AI 尊重原文
        instruction = (
            "\n\n【行为准则】"
            "\n1. 如果你调用了知识库检索工具 `rag_tool`，请务必直接使用返回的原文进行回答。"
            "\n2. 严禁对原文进行过度总结或润色，必须保留原文的关键指标、数据和术语。"
            "\n3. 回答时请注明来源（如：根据[XXX文件]记载...）。"
            # "\n4. 如果检索结果中没有相关内容，请直说“知识库中未找到相关信息”，不要尝试编造。"
        )
        
        full_system_prompt = system_prompt + instruction
        sys_msg = SystemMessage(content=full_system_prompt)
        response = llm.invoke([sys_msg, *state["messages"]])
        return {"messages": [response]}

    return chatbot_node

def make_should_sql_node(SQL_TOOL_NAME) -> GraphState:
    
    def res(state: GraphState):
        judge_llm = ChatOpenAI(model=state["select_model"], temperature=_env_float("SQL_ROUTE_TEMPERATURE", 0.0), max_tokens=_env_int("CHAT_MODEL_MAX_TOKENS", 4096), timeout=_env_float("CHAT_MODEL_TIMEOUT", 120))
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
    return res