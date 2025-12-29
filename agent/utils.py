import json
import re
from typing import Any, Dict, List, Literal, TypedDict
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

def extract_last_user_text(messages: List[BaseMessage]) -> str:
    for m in reversed(messages):
        if getattr(m, "type", None) == "human":
            return getattr(m, "content", "") or ""
        if isinstance(m, dict) and m.get("role") == "user":
            return m.get("content", "") or ""
    return ""


def safe_json_load(s: str) -> Dict[str, Any]:
    s = (s or "").strip()
    s = re.sub(r"^```json\s*", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"^```\s*", "", s).strip()
    s = re.sub(r"\s*```$", "", s).strip()

    if not (s.startswith("{") and s.endswith("}")):
        m = re.search(r"\{.*\}", s, flags=re.DOTALL)
        if m:
            s = m.group(0)

    return json.loads(s)