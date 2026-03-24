from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import tiktoken
from fastapi import UploadFile
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage, ToolMessage, trim_messages

from core.files import extract_file_text


@dataclass
class ChatExecutionResult:
    full_text: str = ""
    events: List[Dict[str, Any]] = field(default_factory=list)
    search_results: List[Dict[str, Any]] = field(default_factory=list)


def get_token_encoder():
    try:
        return tiktoken.encoding_for_model("gpt-4o")
    except Exception:
        return tiktoken.get_encoding("cl100k_base")


def count_message_tokens(messages) -> int:
    enc = get_token_encoder()
    total = 0
    for msg in messages:
        content = getattr(msg, "content", "")
        total += len(enc.encode(content if isinstance(content, str) else str(content)))
        total += 8
    return total


def trim_input_messages(messages, max_tokens: int):
    try:
        return trim_messages(
            messages,
            max_tokens=max_tokens,
            token_counter=count_message_tokens,
            strategy="last",
            include_system=True,
            start_on="human",
            allow_partial=False,
        )
    except Exception as exc:
        print(f"[Trim messages failed] {exc}")
        return messages


def extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                text_part = item.get("text")
                if isinstance(text_part, str):
                    parts.append(text_part)
            else:
                parts.append(str(item))
        return "".join(parts)
    if content is None:
        return ""
    return str(content)


async def fallback_invoke_response(agent_app: Any, inputs: Dict[str, Any]) -> str:
    try:
        result = await agent_app.ainvoke(inputs)
    except Exception as exc:
        print(f"[Chat fallback error] {exc}")
        return ""

    messages = result.get("messages", []) if isinstance(result, dict) else []
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            text = extract_text_content(getattr(message, "content", "")).strip()
            if text:
                return text
    return ""


async def build_agent_inputs(
    *,
    message: str,
    files: Optional[Sequence[UploadFile]],
    system_prompt: str,
    db_version: Optional[str],
    kb_category: Optional[str],
    user_identity: str,
    web_search: bool,
    select_model: str,
    max_input_tokens: int,
    max_file_prompt_chars: int,
    file_context_tail_chars: int,
) -> Dict[str, Any]:
    file_context = await extract_file_text(
        files,
        max_chars=max_file_prompt_chars,
        tail_chars=file_context_tail_chars,
    )

    full_user_content = message
    if db_version:
        full_user_content = f"从数据库{db_version}中 {full_user_content}"
    if file_context:
        full_user_content += f"\n\n--- 附件内容 ---\n{file_context}"

    current_system_prompt = system_prompt
    current_system_prompt += "\n\n【重要上下文】"
    current_system_prompt += f"\n- 当前用户身份: {user_identity}"
    current_system_prompt += (
        "\n- 你的任务: 优先通过调用 `rag_tool` 检索内部知识库。"
        "如果检索到内容，请务必【直接引用原文】或基于原文精准回答，严禁产生幻觉。"
        "如果未搜到内容，请如实告知。"
    )
    if kb_category:
        current_system_prompt += (
            f"\n- 用户偏好: 已指定分类 '{kb_category}'。"
            "请在调用 `rag_tool` 时参考此分类。"
        )

    raw_messages = [
        SystemMessage(content=current_system_prompt),
        HumanMessage(content=full_user_content),
    ]
    trimmed_messages = trim_input_messages(raw_messages, max_input_tokens)

    return {
        "messages": trimmed_messages,
        "enable_web": web_search,
        "select_model": select_model,
        "user_identity": user_identity,
        "full_user_content": full_user_content,
        "raw_messages": raw_messages,
        "trimmed_messages": trimmed_messages,
    }


def _build_tool_call_events(message: Any, node_name: str) -> List[Dict[str, Any]]:
    events = []
    tool_calls = getattr(message, "tool_calls", None) or []
    for tool_call in tool_calls:
        events.append(
            {
                "type": "tool.call",
                "node": node_name,
                "tool_name": tool_call.get("name", ""),
                "tool_call_id": tool_call.get("id", ""),
                "arguments": tool_call.get("args", {}),
            }
        )
    return events


def _summarize_tool_result(message: ToolMessage, node_name: str) -> Dict[str, Any]:
    content = message.content if isinstance(message.content, str) else str(message.content)
    event = {
        "type": "tool.result",
        "node": node_name,
        "tool_name": getattr(message, "name", ""),
        "tool_call_id": getattr(message, "tool_call_id", ""),
        "preview": content[:500],
    }
    if getattr(message, "name", "") == "sql_tool":
        event["type"] = "sql.result"
    return event


def _parse_search_results(tool_message: ToolMessage) -> List[Dict[str, Any]]:
    if getattr(tool_message, "name", "") != "tavily_search_with_summary":
        return []
    try:
        payload = json.loads(tool_message.content)
        results = payload.get("results", [])
        return results if isinstance(results, list) else []
    except Exception:
        return []


async def execute_agent(*, agent_app: Any, inputs: Dict[str, Any], include_text_deltas: bool) -> ChatExecutionResult:
    result = ChatExecutionResult()
    current_node = None

    async for msg, metadata in agent_app.astream(inputs, stream_mode="messages"):
        node_name = metadata.get("langgraph_node", "unknown")
        if node_name != current_node:
            current_node = node_name
            result.events.append({"type": "node.enter", "node": node_name})

        if getattr(msg, "tool_calls", None):
            result.events.extend(_build_tool_call_events(msg, node_name))

        if isinstance(msg, ToolMessage):
            tool_event = _summarize_tool_result(msg, node_name)
            result.events.append(tool_event)
            search_results = _parse_search_results(msg)
            if search_results:
                result.search_results = search_results
                result.events.append(
                    {
                        "type": "search.results",
                        "node": node_name,
                        "tool_name": getattr(msg, "name", ""),
                        "count": len(search_results),
                        "results": search_results,
                    }
                )
            continue

        if isinstance(msg, AIMessageChunk):
            delta = extract_text_content(msg.content)
            if delta and node_name in {"chatbot_web", "chatbot_local", "sql_answer"}:
                result.full_text += delta
                if include_text_deltas:
                    result.events.append({"type": "answer.delta", "node": node_name, "delta": delta})

    if not result.full_text:
        fallback_text = (await fallback_invoke_response(agent_app, inputs)).strip()
        if fallback_text:
            result.full_text = fallback_text
            if include_text_deltas:
                result.events.append({"type": "answer.delta", "node": "fallback", "delta": fallback_text})

    result.events.append(
        {
            "type": "run.completed",
            "answer_length": len(result.full_text),
            "search_result_count": len(result.search_results),
        }
    )
    return result
