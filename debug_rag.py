import os
import sys
from pathlib import Path

from llama_index.core import StorageContext, load_index_from_storage, Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.vector_stores.types import MetadataFilters, ExactMatchFilter

# --- 配置 ---
os.environ["OPENAI_API_KEY"] = "sk-pMyKRA0l2LRns2k0BuBipp1gDmI2HG98ZXATEyOS0MMAJNJH"
os.environ["OPENAI_API_BASE"] = "https://api.claudeshop.top/v1"

Settings.embed_model = OpenAIEmbedding(
    model="text-embedding-3-small",
    api_key=os.environ["OPENAI_API_KEY"],
    api_base=os.environ["OPENAI_API_BASE"]
)

STORAGE_DIR = Path("backend/storage_global")

def get_hierarchical_categories_local(user_identity: str):
    if user_identity == "admin":
        return [["基础知识库", "企业知识库", "部门知识库/技术部", "部门知识库/财务部", "个人知识库/员工A1", "个人知识库/员工B1"]]
    if user_identity == "user_a1":
        return [["个人知识库/员工A1"], ["部门知识库/技术部"], ["企业知识库"], ["基础知识库"]]
    elif user_identity == "user_a2":
        return [["部门知识库/技术部"], ["企业知识库"], ["基础知识库"]]
    elif user_identity == "dept_a_manager":
        return [["部门知识库/技术部"], ["企业知识库"], ["基础知识库"]]
    elif user_identity == "user_b1":
        return [["个人知识库/员工B1"], ["部门知识库/财务部"], ["企业知识库"], ["基础知识库"]]
    else:
        return [["基础知识库"]]

def test_rag_cases():
    if not STORAGE_DIR.exists():
        print("❌ 索引不存在")
        return
    
    storage_context = StorageContext.from_defaults(persist_dir=str(STORAGE_DIR))
    index = load_index_from_storage(storage_context)
    
    cases = [
        ("工作面上隅角瓦斯控制指标是多少？", "user_a1"),
        ("项目的主要研发内容有哪些？", "admin"),
        ("实现本项目目标具备什么条件？", "user_a1"),
        ("这个项目的名称是什么？", "dept_a_manager")
    ]

    for q, identity in cases:
        print(f"\n--- 测试 [用户:{identity}] 提问: {q} ---")
        hierarchy = get_hierarchical_categories_local(identity)
        
        found = False
        for level in hierarchy:
            print(f"  正在搜层级: {level}...")
            filters = MetadataFilters(
                filters=[ExactMatchFilter(key="category_path", value=cat) for cat in level],
                condition="or"
            )
            retriever = index.as_retriever(filters=filters, similarity_top_k=2)
            nodes = retriever.retrieve(q)
            
            for node in nodes:
                if node.score > 0.35: # 降低一点门槛看效果
                    print(f"  ✅ 命中! 分数: {node.score:.4f}, 来源: {node.node.metadata.get('category_path')}/{node.node.metadata.get('file_name')}")
                    print(f"  原文片段: {node.node.get_content().replace(chr(10), ' ')[:200]}...")
                    found = True
            if found: break
        
        if not found:
            print("  ❌ 未搜到相关内容")

if __name__ == "__main__":
    test_rag_cases()
