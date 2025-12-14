from agent.node import make_chatbot_node
from agent.tools import TOOLS
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition

# get node
chatbot_node = make_chatbot_node("gpt-4o", 0, TOOLS)

# -----------------------------
# 搭图：chatbot -> (tools?) -> chatbot 循环，直到 END
# -----------------------------
def build_graph():
    graph_builder = StateGraph(MessagesState)
    graph_builder.add_node("chatbot", chatbot_node)
    graph_builder.add_node("tools", ToolNode(TOOLS))
    graph_builder.add_edge(START, "chatbot")
    # tools_condition：如果模型输出包含 tool calls，则走到 tools；否则走 END
    graph_builder.add_conditional_edges("chatbot", tools_condition)
    # tools 执行完，把工具结果消息加回 state，再回到 chatbot 继续
    graph_builder.add_edge("tools", "chatbot")
    return graph_builder

graph_builder = build_graph()