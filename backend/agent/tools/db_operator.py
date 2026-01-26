import ast
import operator as op
from typing import Any, Dict
from langchain_core.tools import tool
from utils.DB_vllm_32B import DB

# db = DB() # <--- 移除全局初始化，防止启动时因连接失败导致 Crash

@tool
def sql_tool(question: str) -> str:
    """使用自然语言描述问题，你的问题将会给SQL代码生成器使用，并且返回查询结果给用户"""
    try:
        # 懒加载：按需实例化 DB
        # 如果数据库配置错误或网络不通，这里会抛出异常，但被外层 try-except 捕获
        # 从而保证不会 crash 整个应用
        try:
            db_instance = DB()
        except Exception as init_err:
            return f"系统提示：数据库连接初始化失败，无法执行查询。原因: {str(init_err)}"

        answer = db_instance.query_db(text_query=question)
        return answer
    except Exception as e:
        return f"数据库查询执行失败: {str(e)}。您可以尝试让问题更清晰明确一点。"
