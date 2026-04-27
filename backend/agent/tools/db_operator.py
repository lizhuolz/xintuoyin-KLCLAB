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
    """
    【数据库查询工具】
    仅当问题明确需要从数据库表中查询结构化数据时使用，例如：
    - 统计/聚合（发票总额、员工人数、考勤汇总等）
    - 筛选/排行（按条件查询记录、排名等）
    - 数据表中的具体字段值
    如果问题涉及项目信息、企业政策、制度文件等知识性内容，请优先使用 rag_tool 而非本工具。
    """
    from services.user_auth import current_role, ROLE_GUEST
    if current_role() == ROLE_GUEST:
        return "数据库查询功能需要登录后使用，请先登录。"
    try:
        answer = get_db_instance().query_db(text_query=question)
        print("answer",answer)
        return answer
    except Exception as e:
        return  f"Error:{e} 数据库查询错误。"
    
