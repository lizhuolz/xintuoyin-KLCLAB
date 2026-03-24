import ast
import operator as op
from typing import Any, Dict
from langchain_core.tools import tool
from utils.DB_vllm_32B import DB

_db_instance = None


def get_db_instance():
    global _db_instance
    if _db_instance is None:
        _db_instance = DB()
    return _db_instance


@tool
def sql_tool(question: str) -> str:
    """使用自然语言描述问题，你的问题将会给SQL代码生成器使用，并且返回查询结果给用户"""
    try:
        answer = get_db_instance().query_db(text_query=question)
        print("answer",answer)
        return answer
    except Exception as e:
        return  f"Error:{e} 数据库查询错误。"
    
