import json
import re
from typing import Any, Dict, List, Literal, TypedDict
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
import os
from langchain_milvus import Milvus

# Milvus Standalone 配置
MILVUS_URI = os.getenv("MILVUS_HISTORY_URI", "http://127.0.0.1:19530")
EMBEDDING_MODEL = os.getenv("QUERY_EMBEDDING_MODEL", "BAAI/bge-base-zh-v1.5")


_embeddings = None
_vector_db = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
    return _embeddings


def load_or_init_db():
    """加载或初始化 Milvus Lite 历史题库"""
    embeddings = get_embeddings()
    collection_name = "user_query_history"
    
    # 初始化 Milvus 向量库
    vector_db = Milvus(
        embedding_function=embeddings,
        connection_args={"uri": MILVUS_URI},
        collection_name=collection_name,
        auto_id=True,
        drop_old=False # 保持持久化
    )
    
    # 检查是否需要初始化种子数据 (通过简单的相似度搜索判断是否为空)
    try:
        count_res = vector_db.similarity_search("test", k=1)
        if not count_res:
            raise ValueError("Empty collection")
    except Exception:
        seed_queries = [
            "人工智能未来会取代哪些工作？",
            "帮我解释一下量子计算的核心原理",
            "如何零基础学习 Python 编程？",
            "近期美联储降息对股市有什么影响？",
            "推荐几本提升底层认知的好书",
            "LangGraph 的多 Agent 协作怎么实现？"
        ]
        vector_db.add_texts(seed_queries)
        
    return vector_db


def get_vector_db():
    global _vector_db
    if _vector_db is None:
        _vector_db = load_or_init_db()
    return _vector_db


def get_semantic_recommendations(user_query: str) -> list[str]:
    """
    接收用户提问，返回 3 个语义最相近的历史问题，并将当前问题存入 Milvus。
    """
    try:
        vector_db = get_vector_db()
        # k=4 为了容错，防命中当前一模一样的问题
        results = vector_db.similarity_search(user_query, k=4)
    except Exception as e:
        print(f"[后台提示] Milvus 语义检索失败: {e}")
        return ["有什么我可以帮您的吗？", "最新的科技资讯？"]
    
    recommendations = []
    for doc in results:
        text = doc.page_content
        if text != user_query and text not in recommendations:
            recommendations.append(text)
        
        if len(recommendations) == 3:
            break
            
    if not recommendations:
        recommendations = ["我想了解关于这个话题的其他细节"]

    # 入库阶段：Milvus 会自动持久化到 .db 文件，无需手动 save
    if len(user_query.strip()) >= 4:
        try:
            vector_db.add_texts([user_query.strip()])
        except Exception as e:
            print(f"[后台提示] 写入历史提问失败: {e}")
        
    return recommendations



def extract_last_user_text(messages: List[BaseMessage]) -> str:
    for m in reversed(messages):
        if getattr(m, "type", None) == "human":
            return getattr(m, "content", "") or ""
        if isinstance(m, dict) and m.get("role") == "user":
            return m.get("content", "") or ""
    return ""


def safe_json_load(s: str) -> Dict[str, Any]:
    s = (s or "").strip()
    s = re.sub(r"^```json\s*", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"^```\s*", "", s).strip()
    s = re.sub(r"\s*```$", "", s).strip()

    if not (s.startswith("{") and s.endswith("}")):
        m = re.search(r"\{.*\}", s, flags=re.DOTALL)
        if m:
            s = m.group(0)

    return json.loads(s)

