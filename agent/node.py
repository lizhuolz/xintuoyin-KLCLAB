from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState


# 获得一个chatbot节点
def make_chatbot_node(model: str, temperature: float, tools, system_prompt: str = "你是一个有用的人工智能助手，你可以使用工具来回答问题。"):
    llm = ChatOpenAI(model=model, temperature=temperature).bind_tools(tools)
    sys_msg = SystemMessage(content=system_prompt)

    def chatbot_node(state: MessagesState):
        response = llm.invoke([sys_msg, *state["messages"]])
        return {"messages": [response]}

    return chatbot_node
