import ast
import operator as op
from typing import Any, Dict
from langchain_core.tools import tool

@tool
def rag_tool(question: str) -> str:
    "有些关于公司内部的文档信息可以通过这个知识库工具来查询，而不用查询数据库，输入用户的问题，返回参考的上下文。"
    return "研发猫公司"