import json
from pathlib import Path

from langchain_core.tools import tool

from services.milvus_service import MilvusNotReadyError, build_milvus_service_from_env

BASE_DIR = Path(__file__).parent.parent.parent.parent
USER_JSON_FILE = BASE_DIR / 'user.json'
_MILVUS_SERVICE = None


def _get_milvus_service():
    global _MILVUS_SERVICE
    if _MILVUS_SERVICE is None:
        _MILVUS_SERVICE = build_milvus_service_from_env()
    return _MILVUS_SERVICE


def get_current_user_profile():
    if USER_JSON_FILE.exists():
        try:
            with open(USER_JSON_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {'name': '未知用户', 'company': '未知公司', 'department': '未知部门'}


@tool
def rag_tool(question: str, user_identity: str = 'guest') -> str:
    """
    【核心知识库检索工具】
    调用此工具回答涉及企业政策、部门规约、个人笔记或基础常识等专业问题。
    系统会自动根据你的身份权限在允许访问的知识库中检索原文。
    """
    try:
        user = get_current_user_profile()
        service = _get_milvus_service()
        results = service.search(question=question, user=user)
        threshold = service.settings.score_threshold
        final_results = []
        for item in results:
            score = item.get('score')
            if score is None or score >= threshold:
                source = f"【来源: {item.get('scope', '未知')}/{item.get('belong_to', '')}/{item.get('kb_name', '')}/{item.get('file_name', '')}】"
                final_results.append(f"{source}\n{item.get('content', '')}")
        if not final_results:
            return '在您的权限范围内未找到相关企业知识内容。'
        return '\n\n---\n\n'.join(final_results)
    except MilvusNotReadyError as exc:
        return f'检索异常: {str(exc)}'
    except Exception as exc:
        return f'检索异常: {str(exc)}'
