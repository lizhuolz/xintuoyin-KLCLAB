import os
from pathlib import Path
from typing import Dict, Optional
from langchain_core.tools import tool
from llama_index.core import (
    VectorStoreIndex, 
    SimpleDirectoryReader, 
    StorageContext, 
    load_index_from_storage,
    Settings
)
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
BASE_STORAGE_DIR = Path(__file__).parent.parent.parent / "storage"

# 缓存所有加载的 Engines: {"contracts": engine, "projects": engine, ...}
_ENGINES: Dict[str, any] = {}

VALID_CATEGORIES = ["contracts", "projects", "research"]

def get_query_engine(category: str = "default"):
    global _ENGINES
    
    # 如果请求的 category 不存在，回退到默认或报错，这里做简单映射
    # 假设前端传的是英文目录名
    target_dir = BASE_DOCS_DIR / category
    storage_dir = BASE_STORAGE_DIR / category
    
    if category in _ENGINES:
        return _ENGINES[category]

    # 1. 检查目录是否存在
    if not target_dir.exists():
        # 如果是 default 且没有子目录，尝试读根目录（兼容旧逻辑）
        if category == "default":
             target_dir = BASE_DOCS_DIR
             storage_dir = BASE_STORAGE_DIR / "default"
        else:
             raise ValueError(f"知识库分类 '{category}' 不存在")

    # 2. 加载或构建索引
    if storage_dir.exists() and any(storage_dir.iterdir()):
        print(f"Loading RAG index for [{category}] from {storage_dir}...")
        storage_context = StorageContext.from_defaults(persist_dir=str(storage_dir))
        index = load_index_from_storage(storage_context)
    else:
        print(f"Building RAG index for [{category}] from {target_dir}...")
        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
            
        documents = SimpleDirectoryReader(input_dir=str(target_dir), recursive=True).load_data()
        if not documents:
             # 空目录处理
             return None
             
        index = VectorStoreIndex.from_documents(documents)
        storage_dir.mkdir(parents=True, exist_ok=True)
        index.storage_context.persist(persist_dir=str(storage_dir))

    engine = index.as_query_engine(streaming=False)
    _ENGINES[category] = engine
    return engine

@tool
def rag_tool(question: str, category: str = "default") -> str:
    """
    检索公司内部知识库。
    输入参数:
    - question: 用户的问题。
    - category: 知识库分类ID，必须是以下之一: ['contracts', 'projects', 'research']。如果不确定，使用 'default'。
      contracts: 合同管理 (委托合同, 费用明细等)
      projects: 项目资料 (立项, 验收, 论证等)
      research: 调研检索 (调研记录, 检索记录)
    """
    try:
        # 简单清洗 category 参数
        if category not in VALID_CATEGORIES:
            category = "default"
            
        engine = get_query_engine(category)
        if not engine:
            return f"知识库 [{category}] 为空或未初始化。"
            
        response = engine.query(question)
        return str(response)
    except Exception as e:
        return f"知识库查询失败: {str(e)}"