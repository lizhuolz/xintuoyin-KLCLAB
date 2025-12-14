# agent_cli.py
import ast
import operator as op
from typing import Any, Dict

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
import os



# -----------------------------
# 1) 定义工具（Tools）
# -----------------------------
# 一个“安全版四则运算”工具（避免直接 eval）
_ALLOWED_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.USub: op.neg,
    ast.Pow: op.pow,
    ast.Mod: op.mod,
}

def _safe_eval(expr: str) -> float:
    def _eval(node):
        if isinstance(node, ast.Num):  # py<3.8
            return node.n
        if isinstance(node, ast.Constant):  # py>=3.8
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Only int/float constants are allowed")
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](_eval(node.operand))
        raise ValueError("Unsupported expression")

    tree = ast.parse(expr, mode="eval")
    return float(_eval(tree.body))


@tool
def calculator(expression: str) -> str:
    """做四则运算/乘方/取模等数学计算。输入例如：'2 + 3*4'、'(1+2)**3'。"""
    try:
        return str(_safe_eval(expression))
    except Exception as e:
        return f"计算失败：{e}"


@tool
def echo(text: str) -> str:
    """原样复述（用于演示工具调用）。"""
    return text


TOOLS = [calculator, echo]


# -----------------------------
# 2) 定义“模型节点”（LLM）
# -----------------------------
# 关键点：把 tools 绑定给模型，让模型能产生 tool_calls
llm = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(TOOLS)

def chatbot_node(state: MessagesState) -> Dict[str, Any]:
    """
    state['messages'] 是一串对话消息（人类、AI、工具消息等）。
    返回值用 {'messages': ...} 的形式更新消息列表。
    """
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


# -----------------------------
# 3) 搭图：chatbot -> (tools?) -> chatbot 循环，直到 END
# -----------------------------
graph_builder = StateGraph(MessagesState)

graph_builder.add_node("chatbot", chatbot_node)
graph_builder.add_node("tools", ToolNode(TOOLS))

graph_builder.add_edge(START, "chatbot")

# tools_condition：如果模型输出包含 tool calls，则走到 tools；否则走 END
graph_builder.add_conditional_edges("chatbot", tools_condition)

# tools 执行完，把工具结果消息加回 state，再回到 chatbot 继续
graph_builder.add_edge("tools", "chatbot")

# -----------------------------
# 4) 编译 + 记忆（Checkpointer）
# -----------------------------
# MemorySaver：把每一步 state checkpoint 存起来，用 thread_id 实现“多轮记忆”
checkpointer = MemorySaver()
app = graph_builder.compile(checkpointer=checkpointer)


# -----------------------------
# 5) 命令行对话循环
# -----------------------------
def main():
    print("LangGraph 对话 Agent 已启动。输入 exit 退出。")
    thread_id = "demo-thread"  # 你也可以换成用户ID/会话ID

    while True:
        user_text = input("\nYou: ").strip()
        if not user_text:
            continue
        if user_text.lower() in ("exit", "quit"):
            break

        result = app.invoke(
            {"messages": [("user", user_text)]},
            config={"configurable": {"thread_id": thread_id}},
        )

        # result["messages"] 是整个线程的消息列表，取最后一条 AI 消息输出
        last = result["messages"][-1]
        print(f"Agent: {last.content}")


if __name__ == "__main__":
    main()
