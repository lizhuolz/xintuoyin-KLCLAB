import os
import json
from pathlib import Path
from langchain_core.tools import tool

# --- 路径配置 ---
BASE_DIR = Path(__file__).parent.parent.parent.parent
BASE_DOCS_DIR = BASE_DIR / "documents"
METADATA_FILE = BASE_DIR / "backend" / "data" / "kb_metadata.json"
USER_JSON_FILE = BASE_DIR / "user.json"
# Milvus Standalone URI
MILVUS_RAG_URI = os.getenv("MILVUS_RAG_URI", "http://127.0.0.1:19530")

_GLOBAL_INDEX = None
_LLAMA_READY = False


def _ensure_llama_runtime():
    global _LLAMA_READY
    if _LLAMA_READY:
        return

    from llama_index.core import (
        VectorStoreIndex,
        SimpleDirectoryReader,
        StorageContext,
        load_index_from_storage,
        Settings,
    )
    from llama_index.core.vector_stores.types import MetadataFilters, ExactMatchFilter, MetadataFilter
    from llama_index.llms.openai import OpenAI
    from llama_index.embeddings.openai import OpenAIEmbedding
    from llama_index.vector_stores.milvus import MilvusVectorStore

    globals().update({
        "VectorStoreIndex": VectorStoreIndex,
        "SimpleDirectoryReader": SimpleDirectoryReader,
        "StorageContext": StorageContext,
        "load_index_from_storage": load_index_from_storage,
        "Settings": Settings,
        "MetadataFilters": MetadataFilters,
        "ExactMatchFilter": ExactMatchFilter,
        "MetadataFilter": MetadataFilter,
        "MilvusVectorStore": MilvusVectorStore
    })

    Settings.llm = OpenAI(
        model=os.environ.get("RAG_LLM_MODEL", "gpt-4o"),
        api_key=os.environ.get("OPENAI_API_KEY"),
        api_base=os.environ.get("OPENAI_API_BASE"),
        temperature=float(os.environ.get("RAG_LLM_TEMPERATURE", 0.1)),
    )
    Settings.embed_model = OpenAIEmbedding(
        model=os.environ.get("RAG_EMBED_MODEL", "text-embedding-3-small"),
        api_key=os.environ.get("OPENAI_API_KEY"),
        api_base=os.environ.get("OPENAI_API_BASE"),
    )
    _LLAMA_READY = True


def get_current_user_profile():
    """从 user.json 读取当前登录用户信息"""
    if USER_JSON_FILE.exists():
        try:
            with open(USER_JSON_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"name": "未知用户", "company": "未知公司", "department": "未知部门"}


def get_kb_metadata_map():
    """将 metadata 数组转为以物理路径为 key 的字典，方便索引时查询"""
    if not METADATA_FILE.exists():
        return {}
    try:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            all_kb = json.load(f)
            return {kb["physical_path"]: kb for kb in all_kb}
    except Exception:
        return {}


def force_refresh_index():
    """强制刷新索引"""
    global _GLOBAL_INDEX
    _GLOBAL_INDEX = None
    # 真正的 Standalone Milvus 刷新通常建议通过 Client 删除 Collection
    # 我们这里依赖后续重新构建时的 overwrite 逻辑


def get_global_index():
    global _GLOBAL_INDEX
    if _GLOBAL_INDEX:
        return _GLOBAL_INDEX

    _ensure_llama_runtime()

    # 初始化 Milvus 向量存储 (网络地址)
    vector_store = MilvusVectorStore(
        uri=MILVUS_RAG_URI,
        collection_name="knowledge_base_collection",
        dim=1536,
        overwrite=False
    )
    
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    # 尝试从 Milvus 加载已有的数据
    try:
        # LlamaIndex 会尝试检查 Collection 是否存在
        _GLOBAL_INDEX = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
        # 这里需要某种方式判断 collection 是否真的有内容
        # 简单策略：如果加载失败或我们要强制刷新，则走构建流程
        return _GLOBAL_INDEX
    except Exception:
        kb_map = get_kb_metadata_map()

        def get_meta(file_path):
            try:
                rel_path = Path(file_path).relative_to(BASE_DOCS_DIR)
                parts = rel_path.parts # 分类 / 知识库名 / 文件名

                kb_info = None
                # 匹配物理路径 (分类/知识库名)
                if len(parts) >= 2:
                    test_path = f"{parts[0]}/{parts[1]}"
                    if test_path in kb_map:
                        kb_info = kb_map[test_path]

                meta = {
                    "file_name": parts[-1],
                    "rel_path": str(rel_path),
                    "is_base": "true" if parts[0] == "基础知识库" else "false",
                    "enabled": "true",
                    "allowed_users": "all",
                    "scope": parts[0],
                }

                if kb_info:
                    meta["kb_name"] = kb_info["name"]
                    meta["enabled"] = "true" if kb_info.get("enabled", True) else "false"
                    # 处理使用人权限
                    users = kb_info.get("users", [])
                    user_names = []
                    for u in users:
                        if isinstance(u, dict): user_names.append(u.get("name", ""))
                        else: user_names.append(str(u))
                    meta["allowed_users"] = ",".join(user_names) if user_names else "none"

                return meta
            except Exception:
                return {"enabled": "false"}

        reader = SimpleDirectoryReader(input_dir=str(BASE_DOCS_DIR), recursive=True, file_metadata=get_meta)
        documents = reader.load_data()
        _GLOBAL_INDEX = VectorStoreIndex.from_documents(documents, storage_context=storage_context)

    return _GLOBAL_INDEX


@tool
def rag_tool(question: str, user_identity: str = "guest") -> str:
    """
    【核心知识库检索工具】
    调用此工具回答涉及企业政策、部门规约、个人笔记或基础常识等专业问题。
    系统会自动根据你的授权范围在允许访问的知识库中检索原文。
    """
    try:
        _ensure_llama_runtime()
        index = get_global_index()
        user = get_current_user_profile()

        # 简化后的权限过滤器
        # 1. 必须启用
        # 2. 基础库 OR 用户被显式授权
        filters = MetadataFilters(filters=[
            MetadataFilter(key="enabled", value="true"),
            MetadataFilters(filters=[
                ExactMatchFilter(key="is_base", value="true"),
                MetadataFilter(key="allowed_users", value=user.get("name", "未知用户"), operator="contains"),
            ], condition="or"),
        ], condition="and")

        retriever = index.as_retriever(filters=filters, similarity_top_k=5)
        nodes = retriever.retrieve(question)

        final_results = []
        for node in nodes:
            if node.score > 0.35:
                content = node.node.get_content()
                meta = node.node.metadata
                source = f"【来源: {meta.get('scope', '未知')}/{meta.get('kb_name', '未命名')}/{meta.get('file_name', '')}】"
                final_results.append(f"{source}\n{content}")

        if not final_results:
            return "在您的权限范围内未找到相关知识内容。"
        return "\n\n---\n\n".join(final_results)

    except Exception as e:
        return f"检索异常: {str(e)}"
