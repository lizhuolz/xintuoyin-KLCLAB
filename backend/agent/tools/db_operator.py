import json
import logging
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from utils.DB_vllm_32B import DB
from utils.sql_permissions import SQLAccessDenied

logger = logging.getLogger(__name__)


def get_db_instance(user):
    from services.user_auth import ROLE_USER, ROLE_ENTERPRISE_ADMIN
    role = user.get("role")
    if role not in {ROLE_USER, ROLE_ENTERPRISE_ADMIN}:
        raise SQLAccessDenied("数据库查询功能需要登录后使用，请先登录。")
    return DB(
        tenant_id=user.get("tenant_id"),
        staff_id=user.get("staff_id"),
        allow_all_projects=role == ROLE_ENTERPRISE_ADMIN,
    )


@tool
def sql_tool(question: str, config: RunnableConfig) -> str:
    """
    【数据库查询工具】
    仅当问题明确需要从数据库表中查询结构化数据时使用，例如：
    - 统计/聚合（发票总额、员工人数、考勤汇总等）
    - 筛选/排行（按条件查询记录、排名等）
    - 数据表中的具体字段值
    如果问题涉及项目信息、企业政策、制度文件等知识性内容，请优先使用 rag_tool 而非本工具。
    """
    from services.user_auth import get_current_user
    configurable = (config or {}).get("configurable", {})
    user = configurable["sql_user"] if "sql_user" in configurable else get_current_user()
    db = None
    try:
        db = get_db_instance(user)
        answer = db.query_db(text_query=question)
    except SQLAccessDenied as exc:
        answer = {"status": "denied", "Access_check": False, "message": str(exc)}
    except Exception:
        logger.exception("SQL tool query failed")
        answer = {"status": "error", "message": "数据库查询失败，请稍后重试。"}
    finally:
        if db is not None:
            db.close()
    return json.dumps(answer, ensure_ascii=False, default=str)
    
