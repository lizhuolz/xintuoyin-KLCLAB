# 研发猫 AI 系统 - 后端接口对接文档 (演示版)

本系统采用 **FastAPI** 构建后端服务，支持流式对话响应、动态 RAG 权限管理及多维度的历史审计与反馈处理。

---

## 0. 全局配置
- **基础 URL**: `http://<server-ip>:8000`
- **内容编码**: `UTF-8`
- **身份识别**: 演示阶段统一使用根目录 `user.json` 定义的用户信息。

---

## 1. AI 对话核心接口

### 1.1 流式对话检索接口
AI 对话的主入口，支持附件分析、联网搜索及分层知识库检索。

- **URL**: `/api/chat`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **请求参数**:
  | 字段名 | 类型 | 必选 | 说明 |
  | :--- | :--- | :--- | :--- |
  | `message` | string | 是 | 用户输入的提问文本 |
  | `conversation_id` | string | 是 | 前端生成的唯一 ID (推荐时间戳) |
  | `files` | file[] | 否 | 上传的附件列表 |
  | `web_search` | bool | 否 | 是否开启联网搜索 ("true"/"false") |
  | `rag_enabled` | bool | 否 | 是否开启知识库检索 ("true"/"false") |
  | `user_identity` | string | 否 | 用户标识，默认从 `user.json` 读取 |

- **流式响应特殊协议**:
  系统返回 `text/plain` 流，除了正常的文本内容，还会包含以下特殊标记：
  - **参考链接**: `\n[SOURCES_JSON]:[{"main_title": "...", "url": "...", "summary": "..."}]\n`
  - **推荐追问**: `\n[RECOMMENDATIONS]:["问题1", "问题2", "问题3"]\n`
  *前端应拦截这些标签并解析为对应的 UI 组件。*

---

## 2. 知识库管理 (KB Management)

### 2.1 获取知识库列表
- **URL**: `/api/kb/list`
- **Method**: `GET`
- **响应示例**:
  ```json
  [
    {
      "id": "a1b2c3d4",
      "name": "财务制度",
      "fileCount": 5,
      "users": ["王颖奇"],
      "enabled": true,
      "physical_path": "部门知识库/技术部/财务制度"
    }
  ]
  ```

### 2.2 创建知识库
- **URL**: `/api/kb/create`
- **Method**: `POST` (Form Data)
- **参数**: `name` (名称), `category` (企业知识库/部门知识库/个人知识库), `model` (openai)
- **逻辑**: 后端会根据 `user.json` 自动计算物理存储路径。

### 2.3 更新知识库信息 (含开关)
- **URL**: `/api/kb/update`
- **Method**: `POST` (Form Data)
- **参数**: `id` (必填), `name`, `remark`, `enabled` ("true"/"false"), `users` (JSON 数组)

### 2.4 文件操作子接口
- **列表**: `GET /api/kb/{id}/files`
- **上传**: `POST /api/kb/{id}/upload` (字段名 `file`)
- **删除**: `POST /api/kb/{id}/delete_file` (参数 `filename`)

---

## 3. 对话历史维护 (History)

### 3.1 列表检索 (支持全文搜索)
- **URL**: `/api/history/list`
- **Method**: `GET`
- **Query 参数**:
  | 参数名 | 说明 |
  | :--- | :--- |
  | `search` | 关键词 (支持匹配标题及对话全文) |
  | `start_time` | 开始时间戳 (Unix Timestamp) |
  | `end_time` | 结束时间戳 (Unix Timestamp) |

### 3.2 详情查看
- **URL**: `/api/history/{conversation_id}`
- **Method**: `GET`
- **返回**: 完整的对话消息数组 `[{"role": "user", "content": "..."}, ...]`

### 3.3 删除操作
- **单条**: `DELETE /api/chat/{id}`
- **批量**: `POST /api/history/batch_delete` (Body: `{"ids": ["id1", "id2"]}`)

---

## 4. 反馈处理系统 (Feedback)

### 4.1 提交反馈 (点赞/点踩)
- **URL**: `/api/chat/feedback`
- **Method**: `POST` (Form Data)
- **参数**:
  - `conversation_id`, `message_index`: 锁定特定问答对
  - `type`: "like" (正向) 或 "dislike" (负向)
  - `reasons`: 分类原因 JSON (如果是点踩)
  - `comment`: 更多描述文本
  - `files`: 附件图片列表

### 4.2 反馈管理与审计 (后台专用)
- **列表**: `GET /api/feedback/list?type=like|dislike`
- **处理反馈**: `POST /api/feedback/process`
  - **Body**: `{"date_path": "...", "id": "...", "processor": "姓名", "is_collect": bool}`
  - **逻辑**: 若 `is_collect` 为 true，系统自动将该 QA 片段录入优秀/负面知识库。

---

## 5. 辅助功能

### 5.1 获取物理文件树
- **URL**: `/api/test/file_tree`
- **Method**: `GET`
- **用途**: 实时同步展示服务器 `documents/` 目录下的所有真实文件分布情况。

### 5.2 静态资源访问
- **反馈图片**: `/api/static/feedbacks/{date}/{id}/{filename}`

---

## 💡 对接说明事项
1. **RAG 实时性**: 知识库任何状态或文件的变动都会触发后端 `force_refresh_index()`，前端无需手动刷新索引。
2. **权限隔离**: 后端已实现基于 `user.json` 的自动路径映射，前端只需传递基础分类即可完成层级归档。
3. **导出功能**: 前端已实现纯客户端 CSV 导出逻辑（带 UTF-8 BOM），甲方可根据需要选择是否迁移至后端生成。
