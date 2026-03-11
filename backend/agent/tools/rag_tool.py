import os
import json
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
from llama_index.core.vector_stores.types import MetadataFilters, ExactMatchFilter, MetadataFilter
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding

# --- 路径配置 ---
BASE_DIR = Path(__file__).parent.parent.parent.parent
BASE_DOCS_DIR = BASE_DIR / "documents"
GLOBAL_STORAGE_DIR = BASE_DIR / "backend" / "storage_global"
METADATA_FILE = BASE_DIR / "backend" / "data" / "kb_metadata.json"
USER_JSON_FILE = BASE_DIR / "user.json"

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

def get_current_user_profile():
    """从 user.json 读取当前登录用户信息"""
    if USER_JSON_FILE.exists():
        try:
            with open(USER_JSON_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"name": "未知用户", "company": "未知公司", "department": "未知部门"}

def get_kb_metadata_map():
    """将 metadata 数组转为以物理路径为 key 的字典，方便索引时查询"""
    if not METADATA_FILE.exists(): return {}
    try:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            all_kb = json.load(f)
            # key: 物理路径 (不含 documents/), value: 权限与状态
            return {kb["physical_path"]: kb for kb in all_kb}
    except: return {}

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
    if _GLOBAL_INDEX: return _GLOBAL_INDEX

    if GLOBAL_STORAGE_DIR.exists() and any(GLOBAL_STORAGE_DIR.iterdir()):
        storage_context = StorageContext.from_defaults(persist_dir=str(GLOBAL_STORAGE_DIR))
        _GLOBAL_INDEX = load_index_from_storage(storage_context)
    else:
        kb_map = get_kb_metadata_map()
        
        def get_meta(file_path):
            try:
                rel_path = Path(file_path).relative_to(BASE_DOCS_DIR)
                # 检查文件所属的知识库目录
                # documents/基础知识库/xxx.txt
                # documents/企业知识库/公司名/KB名/xxx.txt
                parts = rel_path.parts
                
                # 寻找匹配的 KB 元数据
                kb_info = None
                for i in range(len(parts), 0, -1):
                    test_path = "/".join(parts[:i])
                    if test_path in kb_map:
                        kb_info = kb_map[test_path]
                        break
                
                meta = {
                    "file_name": parts[-1],
                    "rel_path": str(rel_path),
                    "is_base": "true" if parts[0] == "基础知识库" else "false",
                    "enabled": "true",
                    "allowed_users": "all",
                    "scope": parts[0]
                }
                
                if kb_info:
                    meta["kb_name"] = kb_info["name"]
                    meta["enabled"] = "true" if kb_info.get("enabled", True) else "false"
                    meta["allowed_users"] = ",".join(kb_info.get("users", []))
                    # 归属实体 (公司名/部门名/用户名)
                    meta["belong_to"] = parts[1] if len(parts) > 1 else ""
                
                return meta
            except: return {"enabled": "false"}

        reader = SimpleDirectoryReader(input_dir=str(BASE_DOCS_DIR), recursive=True, file_metadata=get_meta)
        documents = reader.load_data()
        # 过滤掉属于已禁用 KB 的文档（或者在检索时过滤）
        _GLOBAL_INDEX = VectorStoreIndex.from_documents(documents)
        GLOBAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        _GLOBAL_INDEX.storage_context.persist(persist_dir=str(GLOBAL_STORAGE_DIR))
    
    return _GLOBAL_INDEX

@tool
def rag_tool(question: str, user_identity: str = "guest") -> str:
    """
    【核心知识库检索工具】
    调用此工具回答涉及企业政策、部门规约、个人笔记或基础常识等专业问题。
    系统会自动根据你的身份权限在允许访问的知识库中检索原文。
    """
    try:
        index = get_global_index()
        user = get_current_user_profile()
        
        # 构建动态复合过滤器 (LlamaIndex 的 MetadataFilters)
        # 1. 基础库全员共享
        # 2. 属于用户所在企业的库
        # 3. 属于用户所在部门的库
        # 4. 用户在 allowed_users 列表中的库
        # 5. 必须是 enabled == 'true'
        
        # 注意：Simple Vector Store 的过滤器功能有限，这里我们采用多条件组合
        # 实际上，通过逻辑 OR 匹配 scope 和 belong_to 即可
        
        filters = MetadataFilters(filters=[
            MetadataFilter(key="enabled", value="true"),
            # 基础库 OR (所属公司匹配) OR (所属部门匹配) OR (用户名匹配)
            MetadataFilters(filters=[
                ExactMatchFilter(key="is_base", value="true"),
                ExactMatchFilter(key="belong_to", value=user["company"]),
                ExactMatchFilter(key="belong_to", value=user["department"]),
                MetadataFilter(key="allowed_users", value=user["name"], operator="contains")
            ], condition="or")
        ], condition="and")

        retriever = index.as_retriever(filters=filters, similarity_top_k=5)
        nodes = retriever.retrieve(question)
        
        final_results = []
        for node in nodes:
            if node.score > 0.35:
                content = node.node.get_content()
                meta = node.node.metadata
                source = f"{meta.get('scope','未知')}/{meta.get('belong_to','')}/{meta.get('kb_name','')}/{meta.get('file_name','')}"
                final_results.append(f"【来源: {source}】\n{content}")

        if not final_results: return "在您的权限范围内未找到相关企业知识内容。"
        return "\n\n---\n\n".join(final_results)

    except Exception as e:
        return f"检索异常: {str(e)}"
