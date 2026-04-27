from langgraph.graph import StateGraph, START, END, MessagesState

# =============================
# 1) State：继承 MessagesState（关键：不要重定义 messages）
# =============================
class GraphState(MessagesState, total=False):
    sql_needed: bool
    sql_reason: str
    enable_web: bool
    enable_thinking: bool
    select_model: str
    user_identity: str
    sql_fallback_done: bool
