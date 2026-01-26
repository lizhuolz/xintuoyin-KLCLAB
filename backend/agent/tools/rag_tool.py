import os
from pathlib import Path
from typing import List, Optional
from langchain_core.tools import tool
from llama_index.core import (
    VectorStoreIndex, 
    SimpleDirectoryReader, 
    StorageContext, 
    load_index_from_storage,
    Settings
)
from llama_index.core.vector_stores.types import MetadataFilters, ExactMatchFilter
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding

# --- 配置 LlamaIndex ---
Settings.llm = OpenAI(
    model="gpt-4o",
    api_key=os.environ.get("OPENAI_API_KEY"),
    api_base=os.environ.get("OPENAI_API_BASE"),
    temperature=0.1
)
Settings.embed_model = OpenAIEmbedding(
    model="text-embedding-3-small",
    api_key=os.environ.get("OPENAI_API_KEY"),
    api_base=os.environ.get("OPENAI_API_BASE"),
)

# --- 路径配置 ---
BASE_DOCS_DIR = Path(__file__).parent.parent.parent.parent / "documents"
GLOBAL_STORAGE_DIR = Path(__file__).parent.parent.parent / "storage_global"

# 模拟权限控制 (基于概念图分层)
# 键为用户身份标识，值为允许访问的 category_path 列表
USER_ACCESS_MAP = {
    "admin": ["base", "org", "depts/dept_a", "depts/dept_b", "users/user_a1", "users/user_b1", "users/user_a2"],
    "dept_a_manager": ["base", "org", "depts/dept_a"],
    "user_a1": ["base", "org", "depts/dept_a", "users/user_a1"],
    "user_a2": ["base", "org", "depts/dept_a", "users/user_a2"],
    "dept_b_manager": ["base", "org", "depts/dept_b"],
    "user_b1": ["base", "org", "depts/dept_b", "users/user_b1"],
    "guest": ["base"]
}

_GLOBAL_INDEX = None

def force_refresh_index():
    """强制刷新索引：清除内存单例并物理删除磁盘缓存"""
    global _GLOBAL_INDEX
    _GLOBAL_INDEX = None
    import shutil
    if GLOBAL_STORAGE_DIR.exists():
        print(f"Refreshing RAG Index: deleting {GLOBAL_STORAGE_DIR}")
        shutil.rmtree(GLOBAL_STORAGE_DIR)

def get_global_index():
    """获取或初始化全局索引"""
    global _GLOBAL_INDEX
    if _GLOBAL_INDEX:
        return _GLOBAL_INDEX

    if GLOBAL_STORAGE_DIR.exists() and any(GLOBAL_STORAGE_DIR.iterdir()):
        print("Loading Global Scalable Index...")
        storage_context = StorageContext.from_defaults(persist_dir=str(GLOBAL_STORAGE_DIR))
        _GLOBAL_INDEX = load_index_from_storage(storage_context)
    else:
        print("Building Global Scalable Index from scratch...")
        # 定义元数据提取函数，将文件所在的相对路径存入元数据
        def get_meta(file_path):
            rel_path = Path(file_path).relative_to(BASE_DOCS_DIR)
            # 我们只需要存第一层或前两层目录作为标识
            parts = rel_path.parts
            if len(parts) >= 2:
                category = f"{parts[0]}/{parts[1]}"
            else:
                category = parts[0]
            return {"category_path": category}

        reader = SimpleDirectoryReader(
            input_dir=str(BASE_DOCS_DIR), 
            recursive=True,
            file_metadata=get_meta
        )
        documents = reader.load_data()
        
        _GLOBAL_INDEX = VectorStoreIndex.from_documents(documents)
        GLOBAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        _GLOBAL_INDEX.storage_context.persist(persist_dir=str(GLOBAL_STORAGE_DIR))
    
    return _GLOBAL_INDEX

@tool
def rag_tool(question: str, user_identity: str = "guest") -> str:
    """
    分层知识库检索工具。高性能版：使用元数据过滤在全局索引中进行检索。
    
    参数:
    - question: 用户的问题
    - user_identity: 用户身份标识 (例如: 'user_a1', 'user_a2', 'dept_a_manager', 'admin')
    """
    try:
        index = get_global_index()
        
        # 1. 计算当前用户有权访问的类别
        authorized_categories = USER_ACCESS_MAP.get(user_identity, ["base"])
        print(f"User [{user_identity}] query filtering by: {authorized_categories}")

        # 2. 构建元数据过滤器 (OR 逻辑)
        filters = MetadataFilters(
            filters=[
                ExactMatchFilter(key="category_path", value=cat) 
                for cat in authorized_categories
            ],
            condition="or"
        )

        # 3. 创建带过滤器的查询引擎
        query_engine = index.as_query_engine(
            filters=filters,
            similarity_top_k=5,
            streaming=False
        )

        response = query_engine.query(question)
        return str(response)

    except Exception as e:
        return f"知识库检索异常: {str(e)}"
