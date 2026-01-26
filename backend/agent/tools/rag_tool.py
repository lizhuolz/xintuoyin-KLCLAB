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

def get_hierarchical_categories(user_identity: str) -> List[List[str]]:
    """
    返回一个分层的分类列表。
    """
    # 路径映射，确保和磁盘 ls 出来的完全一致
    if user_identity == "admin":
        # 超级管理员：一层直接搜所有
        return [["基础知识库", "企业知识库", "部门知识库/技术部", "部门知识库/财务部", "个人知识库/员工A1", "个人知识库/员工B1"]]
    
    # 普通员工：分层检索 [个人 -> 部门 -> 企业 -> 基础]
    if user_identity == "user_a1":
        return [["个人知识库/员工A1"], ["部门知识库/技术部"], ["企业知识库"], ["基础知识库"]]
    elif user_identity == "user_a2": # 假设 a2 没个人库或还没创建
        return [["部门知识库/技术部"], ["企业知识库"], ["基础知识库"]]
    elif user_identity == "dept_a_manager":
        return [["部门知识库/技术部"], ["企业知识库"], ["基础知识库"]]
    elif user_identity == "user_b1":
        return [["个人知识库/员工B1"], ["部门知识库/财务部"], ["企业知识库"], ["基础知识库"]]
    else:
        return [["基础知识库"]]

_GLOBAL_INDEX = None

def force_refresh_index():
    """强制刷新索引"""
    global _GLOBAL_INDEX
    _GLOBAL_INDEX = None
    import shutil
    if GLOBAL_STORAGE_DIR.exists():
        shutil.rmtree(GLOBAL_STORAGE_DIR)

def get_global_index():
    global _GLOBAL_INDEX
    if _GLOBAL_INDEX:
        return _GLOBAL_INDEX

    if GLOBAL_STORAGE_DIR.exists() and any(GLOBAL_STORAGE_DIR.iterdir()):
        storage_context = StorageContext.from_defaults(persist_dir=str(GLOBAL_STORAGE_DIR))
        _GLOBAL_INDEX = load_index_from_storage(storage_context)
    else:
        def get_meta(file_path):
            try:
                # 计算相对 documents 的路径
                rel_path = Path(file_path).relative_to(BASE_DOCS_DIR)
                parts = rel_path.parts
                # 逻辑：
                # 1. 基础知识库/xxx.txt -> 基础知识库
                # 2. 企业知识库/xxx.txt -> 企业知识库
                # 3. 部门知识库/技术部/xxx.txt -> 部门知识库/技术部
                # 4. 个人知识库/员工A1/xxx.txt -> 个人知识库/员工A1
                if parts[0] in ["部门知识库", "个人知识库"] and len(parts) >= 2:
                    category = f"{parts[0]}/{parts[1]}"
                else:
                    category = parts[0]
                return {"category_path": category}
            except Exception:
                return {"category_path": "unknown"}

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
    【权威知识库检索工具】
    当你需要回答涉及企业内部政策、技术指标、项目计划或个人笔记等专业问题时，必须调用此工具。
    它会根据你的身份权限，按照[个人->部门->企业->基础]的优先级搜索最相关的原始文档片段。
    
    返回结果是文档的【原文】，你应该优先直接引用这些原文来回答用户，以确保准确性。
    """
    try:
        index = get_global_index()
        hierarchy = get_hierarchical_categories(user_identity)
        
        final_results = []
        for level_categories in hierarchy:
            print(f"Level search in: {level_categories} (User: {user_identity})")
            filters = MetadataFilters(
                filters=[ExactMatchFilter(key="category_path", value=cat) for cat in level_categories],
                condition="or"
            )
            
            retriever = index.as_retriever(filters=filters, similarity_top_k=3)
            nodes = retriever.retrieve(question)
            
            for node in nodes:
                # 相似度阈值放低一点 (0.3)，确保能搜到东西
                if node.score > 0.3: 
                    content = node.node.get_content()
                    meta = node.node.metadata
                    source = f"{meta.get('category_path', '')}/{meta.get('file_name', '')}"
                    final_results.append(f"【来源: {source}】\n{content}")
            
            # 如果是超级管理员，我们不中断，让他看完所有层级
            # 如果是普通用户，找到匹配度高的就中断，体现优先级
            if final_results and user_identity != "admin":
                break 

        if not final_results:
            return "未找到相关内容。"

        return "\n\n---\n\n".join(final_results)

    except Exception as e:
        return f"检索异常: {str(e)}"