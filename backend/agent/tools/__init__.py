from .calculate import calculator,echo
from .search import search_tool
from .db_operator import sql_tool
from .rag_tool import rag_tool

# chatbot 阶段的工具：故意 *不* 暴露 sql_tool —— SQL 路由由独立的 should_sql/sql_planner 子流程处理，
# 避免模型在 chatbot 阶段误选 sql_tool（或不选 → 错过 SQL 路径）。
# 触发 SQL 的判断由 should_sql_node（LLM 路由分类器）+ _looks_like_sql_query 关键词协同完成。
WEB_TOOLS = [calculator, echo, search_tool, rag_tool]
LOCAL_TOOLS = [calculator, echo, rag_tool]

__All__ = ['calculator','echo','search_tool','sql_tool','rag_tool']


# =============================
#  配置：你的 SQL 工具名
# =============================
SQL_TOOL_NAME = "sql_tool"

# =============================
#  SQL 工具节点：独立给 sql_planner 子流程使用
# =============================
SQL_TOOLS = [sql_tool]