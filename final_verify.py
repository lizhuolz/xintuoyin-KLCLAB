import os
import sys
import json
from pathlib import Path

# 设置环境
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

def test_system():
    print("--- 1. 测试 MinIO 连通性 ---")
    try:
        from services.storage_service import storage_service
        files = storage_service.list_files("chat/")
        print(f"MinIO 状态正常，检测到已迁移文件: {len(files)}")
    except Exception as e:
        print(f"MinIO 失败: {e}")

    print("\n--- 2. 测试 Milvus Standalone (19530) ---")
    try:
        from agent.utils import get_semantic_recommendations
        recs = get_semantic_recommendations("如何高效管理企业知识库？")
        print(f"Milvus 推荐测试成功: {recs}")
    except Exception as e:
        print(f"Milvus 推荐失败: {e}")

    print("\n--- 3. 测试 扁平化权限逻辑 (RAG) ---")
    try:
        from agent.tools.rag_tool import rag_tool
        print("模拟身份: 创始人 (dlx)")
        # 这里尝试触发 RAG 初始化，如果 Milvus 没数据会尝试扫描 documents 并灌入
        res = rag_tool.invoke({"question": "测试知识库中有什么内容", "user_identity": "dlx"})
        print(f"RAG 运行结果: {res[:150]}...")
    except Exception as e:
        print(f"RAG 逻辑执行失败: {e}")

if __name__ == "__main__":
    test_system()
