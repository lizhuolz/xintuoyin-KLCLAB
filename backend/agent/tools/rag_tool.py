from langchain_core.tools import tool

from config import get_user_profile
from services.milvus_service import MilvusNotReadyError, build_milvus_service_from_env

_MILVUS_SERVICE = None


def _get_milvus_service():
    global _MILVUS_SERVICE
    if _MILVUS_SERVICE is None:
        _MILVUS_SERVICE = build_milvus_service_from_env()
    return _MILVUS_SERVICE


@tool
def rag_tool(question: str, user_identity: str = "guest") -> str:
    """
    【核心知识库检索工具】
    调用此工具回答涉及企业知识的问题，包括但不限于：
    - 项目信息（项目编号、负责人、上线日期、口令等）
    - 企业政策、部门规约、制度文件
    - 个人笔记或基础常识文档
    优先使用此工具检索，而非 sql_tool，除非问题明确需要数据库统计/聚合。
    系统会自动根据你的授权范围在允许访问的知识库中检索原文。
    """
    try:
        user = get_user_profile()
        service = _get_milvus_service()
        results = service.search(question=question, user=user)
        final_results = []
        for item in results:
            source = f"【来源: {item.get('scope', '未知')}/{item.get('belong_to', '')}/{item.get('kb_name', '')}/{item.get('file_name', '')}】"
            final_results.append(f"{source}\n{item.get('content', '')}")
        if not final_results:
            return "在您的权限范围内未找到相关企业知识内容。"
        return "\n\n---\n\n".join(final_results)
    except MilvusNotReadyError as exc:
        return f"检索异常: {str(exc)}"
    except Exception as exc:
        return f"检索异常: {str(exc)}"
