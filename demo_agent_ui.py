import streamlit as st
import os
import sys
import tempfile
import subprocess
from typing import Annotated, Literal
from typing_extensions import TypedDict
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# ================= 配置页面 =================
st.set_page_config(page_title="水文数据分析助手", layout="wide")
st.title("🌊 举水流域水文数据分析助手")

# ================= 定义工具 (保持你的逻辑不变) =================
@tool
def run_python(code: str) -> str:
    """
    Execute Python code and return stdout/stderr.
    """
    code = code.strip()
    print("============[CODE]============")
    print(code)
    if not code:
        return "No code provided."

    # ================= 修复部分开始 =================
    # 尝试在 Streamlit 界面显示。如果因为线程问题导致上下文丢失，则捕获异常，不影响代码运行。
    try:
        import streamlit as st
        # 检查是否处于 Streamlit 运行环境中
        if st.runtime.exists():
            # 这里如果不使用 with st.status... 这种复杂的上下文管理器，会更稳定
            # 但如果你想保留折叠效果，需要加 try-except
            try:
                container = st.status("正在执行 Python 代码...", expanded=False)
                # 手动管理上下文，防止 status 为 None
                with container as status:
                    st.code(code, language='python')
                    if status: # 再次检查 status 是否存在
                        status.write("代码执行中...")
            except Exception:
                # 如果 st.status 失败，尝试直接打印代码（降级处理）
                st.code(code, language='python')
    except Exception as e:
        # 如果彻底丢失上下文（完全后台运行），则只在终端打印
        print(f"UI Context Lost: {e}")
        
    # ================= 修复部分结束 =================

    with tempfile.TemporaryDirectory() as td:
        try:
            # 这里的路径不需要改，保持你原来的绝对路径逻辑
            proc = subprocess.run(
                [sys.executable, "-I", "-c", code],
                cwd=td,
                capture_output=True,
                text=True,
                timeout=10,
                env={
                    "PYTHONNOUSERSITE": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PATH": os.environ.get("PATH", ""),
                },
            )
            out = proc.stdout.strip()
            err = proc.stderr.strip()
            print("==============out=============")
            print(out)
            print("==============err=============")
            print(err)
            print("==============================")
            if proc.returncode != 0:
                result = f"ExitCode={proc.returncode}\nSTDOUT:\n{out}\n\nSTDERR:\n{err}"
            else:
                result = out if out else "(no stdout)"
            
            # 尝试显示运行结果
            try:
                if st.runtime.exists():
                    with st.expander("代码执行结果", expanded=False):
                        st.text(result)
            except:
                pass
                
            return result

        except subprocess.TimeoutExpired:
            return "Timeout: code execution exceeded 10 seconds."

# ================= 定义图结构 =================

# 系统提示词 (System Prompt)
SYS_PROMPT_TEXT = '''
举水流域（有经纬度生成地图）
柳子港水文站断面    61612400    水文站，几十米-几百米

关联降雨：
黄土岗  61640800
明山    61613010
西张店  61643200
麻城    61612200
浮桥河  61614200
尾斗山  61614410
三河口  61612610

水库：  泄洪放水到柳子港
明山    61613010
三河口  61612610
尾斗山  61614410
浮桥河  61614200
碧绿河  61612700
芭茅河  61612580
大河铺  61612560
大坳    61612750
大旗山  61612300

从 /home/lyq/xintuoyin-KLCLAB/hongdian 文件夹下面读取csv文件并且处理。
1. 你可以多次调用代码工具
2. 为完成目的一步一步进行,可以先从获得文件目录开始,再读取文件,最后处理文件
3. 注意文件中存在中文，编码方式需要你进行指定(gbk)
4. 使用中文进行回答[重要!!!]
5. 读取文件时请务必使用**绝对路径**，你必须先获得文件列表之后再进行其他处理，不许第一次找不到就放弃
6. 将你想返回的内容进行print，最后在回答问题时，只需要根据print的内容进行回答即可(这点非常重要)
'''

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

# 缓存图的构建，避免每次刷新页面都重新编译
@st.cache_resource
def get_graph():
    # 可以在这里替换你的 API Key 或 Base URL
    # os.environ["OPENAI_API_KEY"] = "sk-..." 
    
    model = ChatOpenAI(model="gpt-5", temperature=0).bind_tools([run_python])

    def call_model(state: AgentState):
        resp = model.invoke(state["messages"])
        return {"messages": [resp]}

    builder = StateGraph(AgentState)
    builder.add_node("llm", call_model)
    builder.add_node("tools", ToolNode([run_python]))

    builder.add_edge(START, "llm")
    builder.add_conditional_edges("llm", tools_condition, {"tools": "tools", "__end__": END})
    builder.add_edge("tools", "llm")

    return builder.compile()

graph = get_graph()

# ================= 聊天界面逻辑 =================

# 1. 初始化 Session State (存储聊天记录)
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        SystemMessage(content=SYS_PROMPT_TEXT)
    ]

# 2. 侧边栏：显示说明或重置按钮
with st.sidebar:
    st.write("### 控制面板")
    if st.button("🗑️ 清空对话历史"):
        st.session_state["messages"] = [SystemMessage(content=SYS_PROMPT_TEXT)]
        st.rerun()
    st.info("数据路径: /home/lyq/xintuoyin-KLCLAB/hongdian")

# 3. 渲染历史消息
for msg in st.session_state["messages"]:
    if isinstance(msg, HumanMessage):
        st.chat_message("user").write(msg.content)
    elif isinstance(msg, AIMessage):
        # 如果是工具调用请求，这里可以选择不显示，或者显示“正在思考”
        if msg.content:
            st.chat_message("assistant").write(msg.content)
    elif isinstance(msg, ToolMessage):
        # 工具返回的结果通常比较长（CSV数据等），可以用折叠框显示
        with st.expander(f"工具输出 ({msg.name})"):
            st.text(msg.content[:500] + "..." if len(msg.content) > 500 else msg.content)

# 4. 处理用户输入
if user_input := st.chat_input("请输入查询内容，例如：查询统计明山水库2024年度水位极值"):
    # 显示用户消息
    st.chat_message("user").write(user_input)
    
    # 将用户消息加入状态
    st.session_state["messages"].append(HumanMessage(content=user_input))
    
    # 运行图
    # Streamlit 的运行机制是同步的，为了防止界面卡死，我们显示一个 Spinner
    with st.spinner("Agent 正在分析数据、编写代码..."):
        # Invoke Graph
        # 注意：这里我们传入当前的完整历史
        result = graph.invoke({"messages": st.session_state["messages"]})
        
        # 获取最新的消息（graph 返回的是整个状态，或者我们可以只取增量）
        # LangGraph 的 invoke 返回的是最终状态
        final_messages = result["messages"]
        
        # 找出新产生的消息（比 session_state 里的多出来的部分）
        new_messages = final_messages[len(st.session_state["messages"]):]
        
        # 更新 Session State
        st.session_state["messages"] = final_messages

        # 渲染新消息（Assistant 的回复和工具执行过程）
        for msg in new_messages:
            if isinstance(msg, AIMessage) and msg.content:
                st.chat_message("assistant").write(msg.content)
            # ToolMessage 的即时渲染已经在 tool 函数内部通过 st.status 处理了一部分，
            # 但为了历史记录完整，上面的循环也会渲染它们。
            # 这是一个简单的处理方式。