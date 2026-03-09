import json
from pydantic import BaseModel, Field
from typing import List
from langchain_core.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import os
summary_model = os.getenv("RESEARCH_SUMMARY_MODEL", "gpt-4o")
max_results = int(os.getenv("RESEARCH_MAX_RESULTS", 5))

# --- 1. 定义小模型输出的 JSON 结构 (不包含原文，避免让模型消耗过大) ---
class SearchResultItem(BaseModel):
    url: str = Field(description="原网页的来源链接，用于精确匹配")
    main_title: str = Field(description="原网页的大标题")
    sub_title: str = Field(description="根据网页内容提炼的核心词或小标题")
    summary: str = Field(description="一两句话的核心内容摘要")

class SearchResultList(BaseModel):
    results: List[SearchResultItem] = Field(description="搜索结果列表")

# --- 2. 初始化工具和模型 ---
base_search = TavilySearchResults(
    max_results=max_results, # ⚠️ 注意：开启原文后文本量巨大，建议 max_results 调小一点（比如3）防止主Agent上下文超载
    include_answer=True,
    include_raw_content=True, # 开启获取原始网页内容
)


summary_llm = ChatOpenAI(model=summary_model, temperature=0).with_structured_output(SearchResultList)

@tool("tavily_search_with_summary")
def search_tool(query: str) -> str:
    """当需要查询互联网信息时使用此工具。它会返回包含大标题、小标题、摘要以及完整原始网页内容的 JSON 数据。"""
    try:
        # 1. 获取包含原文的原始搜索结果
        raw_results = base_search.invoke({"query": query})
        
        # 2. 为小模型准备精简版数据（只包含普通 snippet，不含超长的 raw_content）
        # 这样处理速度极快，且省 Token
        lite_data_for_llm = [
            {"url": r.get("url"), "title": r.get("title"), "snippet": r.get("content")} 
            for r in raw_results
        ]
        
        # 3. 调用小模型提取标题和摘要
        prompt = f"请作为信息提取员，为以下网页片段提取大标题、提炼小标题并总结摘要。\n\n数据：\n{json.dumps(lite_data_for_llm, ensure_ascii=False)}"
        structured_data = summary_llm.invoke([HumanMessage(content=prompt)])
        
        # 4. 构建映射字典，方便根据 url 查找原文
        raw_content_map = {r.get("url"): r.get("raw_content", "未获取到原文") for r in raw_results}
        
        # 5. 【核心步骤】将原文合并进最终的 JSON 列表
        final_results = []
        for item in structured_data.results:
            item_dict = item.model_dump()
            # 根据 url 把长篇原文塞进字典
            item_dict["raw_content"] = raw_content_map.get(item.url, "未获取到原文") 
            final_results.append(item_dict)
            
        # 6. 返回包含了 大标题、小标题、摘要 和 完整原文 的终极 JSON
        return json.dumps({"results": final_results}, ensure_ascii=False)
        
    except Exception as e:
        error_json = {"results": [{"main_title": "搜索出错", "sub_title": "Error", "summary": str(e), "url": "", "raw_content": ""}]}
        return json.dumps(error_json, ensure_ascii=False)