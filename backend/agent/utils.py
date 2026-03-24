import json
import re
from typing import Any, Dict, List, Literal, TypedDict
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# 向量库本地持久化路径
FAISS_INDEX_PATH = os.getenv("QUERY_DB_PATH", "./data/local_db_query")
EMBEDDING_MODEL = os.getenv("QUERY_EMBEDDING_MODEL", "BAAI/bge-base-zh-v1.5")


_embeddings = None
_vector_db = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        # 延迟加载 embedding 模型，避免服务启动阶段阻塞。
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
    return _embeddings


def load_or_init_db():
    """加载本地历史题库，如果不存在则使用种子数据初始化"""
    embeddings = get_embeddings()
    if os.path.exists(FAISS_INDEX_PATH):
        # 允许加载本地文件
        return FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    else:
        # 冷启动时的“种子数据” 
        seed_queries = [
            "人工智能未来会取代哪些工作？",
            "帮我解释一下量子计算的核心原理",
            "如何零基础学习 Python 编程？",
            "近期美联储降息对股市有什么影响？",
            "推荐几本提升底层认知的好书",
            "LangGraph 的多 Agent 协作怎么实现？"
        ]
        # 初始化并保存到本地
        db = FAISS.from_texts(seed_queries, embeddings)
        db.save_local(FAISS_INDEX_PATH)
        return db


def get_vector_db():
    global _vector_db
    if _vector_db is None:
        _vector_db = load_or_init_db()
    return _vector_db


# 推荐问答函数
def get_semantic_recommendations(user_query: str) -> list[str]:
    """
    接收用户提问，返回 3 个语义最相近的历史问题，并将当前问题存入库中。
    （完全本地运行，无需断网）
    """
    try:
        # k=4 为了容错，防命中当前一模一样的问题
        vector_db = get_vector_db()
        results = vector_db.similarity_search(user_query, k=4)
    except Exception as e:
        print(f"[后台提示] 本地语义检索失败: {e}")
        return ["有什么我可以帮您的吗？", "最新的科技资讯？"]
    
    recommendations = []
    for doc in results:
        text = doc.page_content
        # 过滤掉完全一样的提问
        if text != user_query and text not in recommendations:
            recommendations.append(text)
        
        if len(recommendations) == 3:
            break
            
    # 默认兜底
    if not recommendations:
        recommendations = ["我想了解关于这个话题的其他细节"]

    # 入库阶段：大于等于4个字符的有效提问才入库
    if len(user_query.strip()) >= 4:
        vector_db.add_texts([user_query.strip()])
        # 每次提问后静默覆盖保存到本地，实现题库自生长
        vector_db.save_local(FAISS_INDEX_PATH)
        
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

