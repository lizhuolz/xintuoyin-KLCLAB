# 后端基础设施企业级升级指南 (MinIO & Milvus)

## 1. 架构变更说明

为了满足甲方“企业级管理”及“分布式扩展”的需求，系统存储层已完成从本地文件系统向专业中间件的迁移。

### 1.1 文件存储：本地磁盘 -> MinIO
*   **逻辑变更**：
    *   原本直接操作 `uploads/`, `feedbacks/`, `documents/` 物理目录的逻辑，现统一收口至 `backend/services/storage_service.p1y`。
    *   **上传**：使用流式上传（Streaming Upload）直接将文件推送到 MinIO 桶 `xintuoyin-data` 中。
    *   **下载/预览**：不再使用 FastAPI 静态挂载，改为生成 **预签名 URL (Pre-signed URL)**，提供带时效的安全访问链接。
    *   **解析**：附件解析逻辑改为“下载至临时目录 -> 提取文本 -> 自动清理”，确保宿主机磁盘整洁。

### 1.2 向量检索：FAISS/本地索引 -> Milvus Standalone
*   **逻辑变更**：
    *   **推荐模块**：原本的 FAISS 本地文件替换为 Milvus Lite 接口连接的独立服务（19530 端口）。
    *   **RAG 模块**：LlamaIndex 默认索引替换为 `MilvusVectorStore`。
*   **权限简化逻辑**：
    *   取消了原有的“企业-部门-个人”复杂层级。
    *   **扁平化**：除“基础知识库”外，所有库统一存放在 `用户知识库/` 目录下。
    *   **授权模型**：检索时仅根据 `allowed_users`（使用人）列表进行精确过滤。基础知识库全员可见。

---

## 2. 服务启动指南

所有数据和服务二进制文件均存放在 `/data1/dlx/projects/xintuoyin/` 目录下，与代码分离。

### 2.1 启动 MinIO (对象存储)
*   **启动命令**：
    ```bash
    # 在项目根目录执行
    export MINIO_STORAGE_FULL_THRESHOLD=0
    bash /data1/dlx/projects/xintuoyin/minio/start_minio.sh
    ```
*   **管理后台**：`http://服务器IP:9001` (minioadmin / minioadmin)
*   **API 地址**：`http://127.0.0.1:9000`

### 2.2 启动 Milvus (向量数据库)
*   **启动命令**：
    ```bash
    # 在项目根目录执行
    bash start_milvus_standalone.sh
    ```
*   **API 地址**：`http://127.0.0.1:19530`
*   **日志路径**：`/data1/dlx/projects/xintuoyin/milvus/milvus_server.log`

---

## 3. 开发环境适配
在 `pixi` 环境下，请确保已添加以下关键依赖：
*   `minio`: 对象存储驱动
*   `pymilvus`: Milvus 客户端
*   `langchain-milvus` & `llama-index-vector-stores-milvus`: 框架集成插件
*   `setuptools`: 提供 `pkg_resources` 运行时支持

---

## 4. 剩余待办项 (TODO)

- [ ] **全量索引重构**：由于 Milvus 数据库目前是空的，需要运行一次全量扫描脚本，将 MinIO 中的文档重新向量化并灌入 Milvus。
- [ ] **前端 URL 对接**：检查前端 Vue 组件，确保其能正确解析并渲染 MinIO 返回的绝对路径预签名链接（原本是相对路径）。
- [ ] **磁盘清理**：在确认 MinIO 和 Milvus 运行稳定且数据已完成同步后，手动删除项目根目录下的旧文件夹：`uploads/`, `feedbacks/`, `documents/` 以释放空间。
- [ ] **环境变量统一**：将脚本中硬编码的 `MINIO_ENDPOINT` 和 `MILVUS_URI` 整理到项目的标准 `.env` 或 `env.sh` 中。
- [ ] **安全加固**：修改 MinIO 和 Milvus 的默认管理员密码（目前均为 minioadmin）。
