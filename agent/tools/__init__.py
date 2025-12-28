from .calculate import calculator,echo
from .search import search_tool
from .db_operator import sql_tool

# 所有的tool需要进行注册
TOOLS = [calculator, echo,search_tool,sql_tool]
__All__ = ['calculator','echo','search_tool','sql_tool']
