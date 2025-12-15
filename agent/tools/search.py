from langchain_community.tools.tavily_search import TavilySearchResults


# 定义搜索工具（tavily）
search_tool = TavilySearchResults(
    max_results=5,
    include_answer=True,
    include_raw_content=False,
)