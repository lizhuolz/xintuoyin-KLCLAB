# agent_cli.py
import ast
import operator as op
from typing import Any, Dict

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from agent.build_graph import graph_builder



# -----------------------------
# 编译 + 记忆（Checkpointer）
# -----------------------------
# MemorySaver：把每一步 state checkpoint 存起来，用 thread_id 实现“多轮记忆”
checkpointer = MemorySaver()
app = graph_builder.compile(checkpointer=checkpointer)

# -----------------------------
#  命令行对话循环
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
        print(result["messages"])
        print(f"Agent: {last.content}")


if __name__ == "__main__":
    main()
