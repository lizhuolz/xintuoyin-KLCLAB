import json
import os
from pydantic import BaseModel, Field
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_core.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

summary_model = os.getenv("RESEARCH_SUMMARY_MODEL", "gpt-4o")
max_results = int(os.getenv("RESEARCH_MAX_RESULTS", 5))

# --- 1. 修改模型输出结构 (从 List 改为单个 Item，因为每个线程只处理一个) ---
class SearchResultItem(BaseModel):
    url: str = Field(description="原网页的来源链接，用于精确匹配")
    main_title: str = Field(description="原网页的大标题")
    sub_title: str = Field(description="根据网页内容提炼的核心词或小标题")
    summary: str = Field(description="一两句话的核心内容摘要")

# --- 2. 初始化工具和模型 ---
base_search = TavilySearchResults(
    max_results=max_results,
    include_answer=True,
    include_raw_content=True,
)

# 注意这里强制要求模型每次只输出一个 SearchResultItem 结构
summary_llm = ChatOpenAI(model=summary_model, temperature=0).with_structured_output(SearchResultItem)


# --- 3. 定义单个网页的处理任务 (供多线程调用) ---
def process_single_result(raw_result: dict) -> dict:
    """处理单个搜索结果：调用 LLM 生成摘要并拼接原文"""
    url = raw_result.get("url", "")
    title = raw_result.get("title", "")
    snippet = raw_result.get("content", "")
    raw_content = raw_result.get("raw_content", "未获取到原文")
    
    prompt = (
        "请作为信息提取员，为以下网页片段提取大标题、提炼小标题并总结摘要。\n\n"
        f"【URL】: {url}\n"
        f"【原标题】: {title}\n"
        f"【网页片段】: {snippet}"
    )
    
    try:
        # 调用大模型提取结构化数据
        structured_data = summary_llm.invoke([HumanMessage(content=prompt)])
        
        # 将 Pydantic 对象转为字典
        item_dict = structured_data.model_dump()
        
        # 强制覆盖 url 确保与原文绝对匹配（防止大模型幻觉改写 URL）
        item_dict["url"] = url 
        # 拼接长篇原文
        item_dict["raw_content"] = raw_content 
        
        return item_dict
        
    except Exception as e:
        # 如果当前线程的大模型调用失败，优雅降级，不影响其他线程
        return {
            "url": url,
            "main_title": title or "标题提取失败",
            "sub_title": "解析错误",
            "summary": f"大模型解析失败: {str(e)}",
            "raw_content": raw_content
        }


# --- 4. 封装多线程工具 ---
@tool("tavily_search_with_summary")
def search_tool(query: str) -> str:
    """当需要查询互联网信息时使用此工具。它会返回包含大标题、小标题、摘要以及完整原始网页内容的 JSON 数据。"""
    try:
        # 1. 一次性获取所有原始搜索结果 (API限制，通常单次调用即可)
        raw_results = base_search.invoke({"query": query})
        
        # 如果没搜到东西，直接返回空
        if not raw_results:
             return json.dumps({"results": []}, ensure_ascii=False)

        final_results = []
        
        # 2. 【核心优化】使用多线程并发调用大模型处理每个网页片段
        # max_workers 设为 max_results 即可，保证每个网页分配一个线程
        with ThreadPoolExecutor(max_workers=max_results) as executor:
            # 提交所有任务
            future_to_url = {executor.submit(process_single_result, r): r.get("url") for r in raw_results}
            
            # as_completed 会在某个线程完成时立刻 yield，不用等所有人都完成才开始聚合
            for future in as_completed(future_to_url):
                try:
                    result_dict = future.result()
                    final_results.append(result_dict)
                except Exception as exc:
                    url = future_to_url[future]
                    print(f"[后台告警] 提取 {url} 时发生未知致命异常: {exc}")

        # 3. 返回最终聚合的 JSON
        return json.dumps({"results": final_results}, ensure_ascii=False)
        
    except Exception as e:
        error_json = {"results": [{"main_title": "搜索工具整体崩溃", "sub_title": "Error", "summary": str(e), "url": "", "raw_content": ""}]}
        return json.dumps(error_json, ensure_ascii=False)