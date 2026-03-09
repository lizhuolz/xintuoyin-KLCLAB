from typing_extensions import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt import ToolNode, tools_condition
import os
import sys
import tempfile
import subprocess
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent

# 你可以换成别的模型，这里用 OpenAI 举例
from langchain_openai import ChatOpenAI
SYS_prompt = '''
举水流域（有经纬度生成地图）
柳子港水文站断面	61612400	水文站，几十米-几百米

关联降雨：
黄土岗	61640800
明山	61613010
西张店	61643200
麻城	61612200
浮桥河	61614200
尾斗山	61614410
三河口	61612610

水库：	泄洪放水到柳子港
明山	61613010
三河口	61612610
尾斗山	61614410
浮桥河	61614200
碧绿河	61612700
芭茅河	61612580
大河铺	61612560
大坳	61612750
大旗山	61612300
从/home/lyq/xintuoyin-KLCLAB/hongdian文件夹下面读取csv文件并且处理，写代码并且运行代码之后再回答问题
1.你可以多次调用代码工具，将你想返回的内容进行print[重要!!!]
2.为完成目的一步一步进行,可以先从获得文件目录开始,再读取文件,最后处理文件
3.注意文件中存在中文，编码方式需要你进行指定gbk） 
4.使用中文进行回答[重要!!!]
\n问题如下'''

@tool
def run_python(code: str) -> str:
    """
    Execute Python code and return stdout/stderr.
    Notes:
    - Runs in a temporary working directory
    - Has a hard timeout
    - Still NOT a perfect sandbox (do not expose to untrusted users)
    """
    print("============[CODE]============")
    print(code)
    print("==============================")
    code = code.strip()
    if not code:
        return "No code provided."

    # （可选）非常粗糙的拦截：防止明显危险关键词
    # blocked = ["os.system", "subprocess", "socket", "requests", "shutil.rmtree", "pathlib.Path("]
    # if any(b in code for b in blocked):
    #     return "Blocked: code contains potentially dangerous operations."

    with tempfile.TemporaryDirectory() as td:
        try:
            # -I: isolate mode（忽略用户 site-packages / PYTHON* 环境变量等）
            # 注意：这不是安全沙箱，只是降低污染
            proc = subprocess.run(
                [sys.executable, "-I", "-c", code],
                cwd=td,
                capture_output=True,
                text=True,
                timeout=3,   # 超时秒数可调
                env={
                    "PYTHONNOUSERSITE": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PATH": os.environ.get("PATH", ""),
                },
            )
            out = proc.stdout.strip()
            
            err = proc.stderr.strip()
            print("============[OUT]============")
            print("out:", out)
            print("============[ERR]============")
            print("err:", err)
            print("=============================")
            
            if proc.returncode != 0:
                return f"ExitCode={proc.returncode}\nSTDOUT:\n{out}\n\nSTDERR:\n{err}"
            return out if out else "(no stdout)"
        except subprocess.TimeoutExpired:
            return "Timeout: code execution exceeded 3 seconds."

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

model = ChatOpenAI(model="gpt-4o", temperature=0.5).bind_tools([run_python])

def call_model(state: AgentState):
    # 让模型基于当前 messages 决定是否要 tool_calls
    resp = model.invoke(state["messages"])
    return {"messages": [resp]}

builder = StateGraph(AgentState)
builder.add_node("llm", call_model)
builder.add_node("tools", ToolNode([run_python]))

builder.add_edge(START, "llm")

# 如果 llm 产出了 tool_calls → tools；否则结束
builder.add_conditional_edges("llm", tools_condition, {"tools": "tools", "__end__": END})

# tools 执行完把 ToolMessage 加回 messages，然后回到 llm 继续
builder.add_edge("tools", "llm")

graph = builder.compile()

out = graph.invoke({"messages": [("user", 
                                  f'''{SYS_prompt}:查询统计明山水库2024年度水位极值。''')]} )
print(out["messages"][-1].content)
print("\n\n===================[Next Question]===================")
out = graph.invoke({"messages": [("user", 
                                  f'''{SYS_prompt}:查询统计三河口水库2024年度水位极值''')]} )
print(out["messages"][-1].content)


