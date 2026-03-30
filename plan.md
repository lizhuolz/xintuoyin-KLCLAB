# 企业级对象存储 (MinIO) 迁移计划

## 1. 背景与目标
当前系统（对话附件、反馈截图、知识库文档）均通过本地文件系统（根目录下的 `uploads/`, `feedbacks/`, `documents/`）进行管理。这种方式不利于分布式部署、扩容以及企业级数据管理。
甲方需求：引入企业级对象存储服务（如 MinIO，兼容 AWS S3 协议）来全面替换本地文件存储。

## 2. 影响范围
本次改造主要涉及后端文件 I/O 逻辑的替换，具体模块包括：
1. **对话模块 (`backend/app.py`)**：
   - 附件上传 (`save_chat_uploads`)
   - 附件解析 (`extract_uploaded_file_text`)
2. **反馈模块 (`backend/app.py`)**：
   - 截图与附件上传 (`save_feedback`, `upload_feedback_pictures`)
3. **知识库模块 (`backend/services/kb_service.py`)**：
   - 文档的上传、列表查询、删除 (`save_files`, `list_files`, `delete_files`)
   - 知识库元数据（如文件数量计算 `_format_kb`）
4. **静态文件代理**：
   - 原有 FastAPI 挂载的本地静态代理 (`StaticFiles`) 将废弃或重定向，统一改为返回 MinIO 对象的预签名 URL（Pre-signed URL）或直接可通过 MinIO 网关访问的公开 URL。

## 3. 改造方案

### 阶段一：环境与基础设施准备
1. **依赖引入**：在 `backend/requirements.txt` 中添加 `minio`（官方 SDK）或 `boto3`（通用 S3 SDK）。
2. **配置管理**：在 `env.sh` 中新增环境变量：
   - `MINIO_ENDPOINT` (例如: `127.0.0.1:9000`)
   - `MINIO_ACCESS_KEY`
   - `MINIO_SECRET_KEY`
   - `MINIO_SECURE` (是否启用 HTTPS，默认 False)
   - `MINIO_BUCKET_NAME` (例如: `xintuoyin-data`)

### 阶段二：封装通用存储服务 (Storage Service)
创建 `backend/services/storage_service.py`，将所有文件操作收口。提供以下标准接口：
- `upload_file(file_obj, object_name: str)`：将 FastAPI 的 `UploadFile` 流式写入 MinIO。
- `download_file(object_name: str, local_path: str)`：用于附件解析时，如果需要将文件拉取到本地临时目录交给如 `PdfReader` 解析。
- `read_file_bytes(object_name: str) -> bytes`：直接在内存中读取文件流（适合较小的 txt/md/json 等）。
- `delete_file(object_name: str)` / `delete_files(prefix: str)`：删除单个文件或基于前缀批量删除。
- `list_files(prefix: str)`：列出某前缀下的所有对象。
- `get_presigned_url(object_name: str)`：生成前端可直接访问的带签名的图片/附件地址。

### 阶段三：业务逻辑重构
1. **重构 Chat 与 Feedback 存储 (`app.py`)**：
   - `save_chat_uploads` 逻辑中不再使用 `shutil.copyfileobj` 写本地，而是调用 `StorageService.upload_file`，对象路径如 `chat/2026-03-28/{conv_id}/{msg_index}/filename`。
   - `extract_uploaded_file_text` 解析前，对于无法在内存处理的大文件（如 pdf, docx, xlsx），先下载到系统的 `/tmp` 目录，解析完成后立刻清理。
   - 反馈的截图和附件按照类似逻辑存入 MinIO `feedback/{date}/{fb_id}/filename`，记录其网络 URL。
2. **重构知识库存储 (`kb_service.py`)**：
   - `DOCS_DIR / physical_path` 替换为 MinIO Bucket 下的 `documents/physical_path` 前缀。
   - `list_files` 改为调用 MinIO 的 `list_objects` 接口拉取对象元信息。
   - 知识库元数据 `kb_metadata.json` 依然可以保留在本地（或迁移到数据库），仅替换文件本身的存储载体。

### 阶段四：存量数据迁移与测试
- 编写一份简单的 `migrate_local_to_minio.py` 脚本，遍历现有的 `uploads`, `feedbacks`, `documents` 目录并将文件全量推送到 MinIO。
- 进行接口回归测试，确保文件上传、预览、删除及解析抽取的准确性。

## 4. 前端联调考量
- 前端之前依赖的是相对路径（如 `/api/static/chat_uploads/...`）。改为 MinIO 后，后端将直接返回绝对 URL（如 `http://minio-server:9000/bucket/...`）。前端在渲染图片或下载文件时需确保跨域 (CORS) 配置已在 MinIO 端正确开启。