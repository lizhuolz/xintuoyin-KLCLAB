from __future__ import annotations
from agent.node import make_chatbot_node
from agent.tools import LOCAL_TOOLS,WEB_TOOLS,SQL_TOOLS,SQL_TOOL_NAME
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode
from agent.messagestate import GraphState
from agent.node import make_should_sql_node
from agent.router import (
    route_start,
    route_after_chatbot_local,
    route_after_chatbot_web,
    route_after_should_sql,
    route_after_sql_planner,
)


# =============================
# 2) chatbot（你原有）
# =============================
local_chatbot_node = make_chatbot_node( 0, LOCAL_TOOLS)
web_chatbot_node = make_chatbot_node( 0, WEB_TOOLS)
should_sql_node = make_should_sql_node(SQL_TOOL_NAME)
# sql_planner：只允许 SQL 工具调用（产出 tool_calls）
sql_planner_node = make_chatbot_node(0, SQL_TOOLS,system_prompt="你是一个用户问题总结器,你需要精炼用户的问题，后续你的回答将会给sql代码生成器使用，请让你的回答清晰且能完全表述需求。") #SYS prompt 可以不加，已经在路由中加入了
# sql_answer：不允许任何工具调用（只根据 messages 里 ToolMessage 总结）
sql_answer_node = make_chatbot_node( 0, [])


local_tools_node = ToolNode(LOCAL_TOOLS)
web_tools_node = ToolNode(WEB_TOOLS)
sql_tools_node = ToolNode(SQL_TOOLS)


# =============================
# 7) build_graph：完整搭图
# =============================
def build_graph():
    graph_builder = StateGraph(GraphState)

    # 两套 chatbot/tools
    graph_builder.add_node("chatbot_local", local_chatbot_node)
    graph_builder.add_node("tools_local", local_tools_node)

    graph_builder.add_node("chatbot_web", web_chatbot_node)
    graph_builder.add_node("tools_web", web_tools_node)

    # SQL 子流程
    graph_builder.add_node("should_sql",should_sql_node)
    graph_builder.add_node("sql_planner", sql_planner_node)
    graph_builder.add_node("sql_tools", sql_tools_node)
    graph_builder.add_node("sql_answer", sql_answer_node)

    # START -> (local/web)
    graph_builder.add_conditional_edges(
        START,
        route_start,
        {
            "chatbot_local": "chatbot_local",
            "chatbot_web": "chatbot_web",
        },
    )

    # local 分支循环
    graph_builder.add_conditional_edges(
        "chatbot_local",
        route_after_chatbot_local,
        {
            "tools_local": "tools_local",
            "should_sql": "should_sql",
            "end": END, # 添加结束路径
        },
    )
    graph_builder.add_edge("tools_local", "chatbot_local")

    # web 分支循环
    graph_builder.add_conditional_edges(
        "chatbot_web",
        route_after_chatbot_web,
        {
            "tools_web": "tools_web",
            "should_sql": "should_sql",
             "end": END # 添加结束路径
        },
    )
    graph_builder.add_edge("tools_web", "chatbot_web")

    # should_sql -> (sql / end)
    graph_builder.add_conditional_edges(
        "should_sql",
        route_after_should_sql,
        {"sql_planner": "sql_planner", "end": END},
    )

    # sql_planner -> (sql_tools / sql_answer)
    graph_builder.add_conditional_edges(
        "sql_planner",
        route_after_sql_planner,
        {"sql_tools": "sql_tools", "sql_answer": "sql_answer"},
    )
    graph_builder.add_edge("sql_tools", "sql_answer")
    graph_builder.add_edge("sql_answer", END)

    return graph_builder


graph_builder = build_graph()
