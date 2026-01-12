# agent_cli.py
import operator as op
from typing import Any, Dict

# 引入必要的类型判断
from langchain_core.messages import AIMessageChunk
from langgraph.checkpoint.memory import MemorySaver
from agent.build_graph import graph_builder

# -----------------------------
# 编译
# -----------------------------
checkpointer = MemorySaver()
app = graph_builder.compile(checkpointer=checkpointer)

# -----------------------------
#  命令行对话循环 (同步流式版)
# -----------------------------
def main():
    print("LangGraph 对话 Agent 已启动 (Stream Mode: Messages)。输入 exit 退出。")
    thread_id = "demo-thread"

    while True:
        try:
            user_text = input("\nYou: ").strip()
        except EOFError:
            break

        if not user_text:
            continue
        if user_text.lower() in ("exit", "quit"):
            break

        # 配置
        config = {"configurable": {"thread_id": thread_id}}
        inputs = {
            "messages": [("user", user_text)],
            "enable_web": True,
            "select_model": "gpt-4o"
        }

        print("Agent: ", end="", flush=True)

        # ---------------------------------------------------------
        # 核心修改：使用 stream_mode="messages"
        # ---------------------------------------------------------
        # 这会自动提取 Graph 中所有 ChatModel 的输出片段
        # event 格式为: (message_chunk, metadata)
        for msg, metadata in app.stream(inputs, config, stream_mode="messages"):
            
            # 1. 获取生成该消息的节点名称 (例如 "agent", "tools", "researcher")
            # 这是你在 graph_builder.add_node("名字", ...) 时定义的名字
            node_name = metadata.get("langgraph_node", "unknown")
            
            # 2. (可选) 获取具体的模型名称 (例如 "gpt-4o")
            # 注意：流式传输时，只有部分 chunk 的 response_metadata 包含 model_name
            # model_name = msg.response_metadata.get("model_name", "")

            if isinstance(msg, AIMessageChunk) and msg.content and node_name in ["chatbot_web","chatbot_local"]:
                print(msg.content, end="", flush=True)

        print("") # 对话结束后换行

if __name__ == "__main__":
    main()