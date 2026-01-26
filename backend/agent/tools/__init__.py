from .calculate import calculator,echo
from .search import search_tool
from .db_operator import sql_tool
from .rag_tool import rag_tool

# 所有的tool需要进行注册
WEB_TOOLS = [calculator, echo,search_tool,sql_tool,rag_tool]
LOCAL_TOOLS = [calculator, echo,sql_tool,rag_tool]

__All__ = ['calculator','echo','search_tool','sql_tool','rag_tool']



# =============================
#  配置：你的 SQL 工具名
# =============================
SQL_TOOL_NAME = "sql_tool"  # <<< 改成你项目里 SQL 工具的 name（必须在 TOOLS 里）
# =============================
#  SQL 工具节点：只放 SQL 工具
# =============================
SQL_TOOLS = [t for t in LOCAL_TOOLS if getattr(t, "name", None) == SQL_TOOL_NAME]
if not SQL_TOOLS:
    raise ValueError(
        f"没有在 TOOLS 中找到 name={SQL_TOOL_NAME} 的 SQL 工具。"
        f"请检查 SQL_TOOL_NAME 或 TOOLS 配置。当前 TOOLS: {[getattr(t, 'name', None) for t in LOCAL_TOOLS]}"
    )