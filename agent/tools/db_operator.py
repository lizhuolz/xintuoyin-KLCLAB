import ast
import operator as op
from typing import Any, Dict
from langchain_core.tools import tool

@tool
def sql_tool(sql: str,param:str) -> str:
    """执行SQL查询。{SQL:sql查询代码,Param:sql查询参数 }"""
    return "这是sql 查询demo，返回测试"