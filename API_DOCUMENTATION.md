# 研发猫 AI 系统 - 接口对接文档 (演示版)

本文档旨在为甲方对接提供系统核心接口说明。系统采用 FastAPI 构建后端，支持流式对话、全文检索及历史记录维护。

---

## 1. 历史对话记录管理

### 1.1 获取历史记录列表
用于管理后台展示所有用户的对话摘要。

- **URL**: `/api/history/list`
- **Method**: `GET`
- **Query Parameters**:
  | 参数名 | 类型 | 必选 | 说明 |
  | :--- | :--- | :--- | :--- |
  | `search` | string | 否 | 搜索关键词（支持匹配标题及对话内容正文） |
  | `start_time` | float | 否 | 开始时间戳 (Unix Timestamp, 秒) |
  | `end_time` | float | 否 | 结束时间戳 (Unix Timestamp, 秒) |

- **Response** (Array of Objects):
  ```json
  [
    {
      "id": "1741681234",
      "title": "关于研发加计扣除的咨询",
      "updatedAt": 1741681234.56,
      "messageCount": 4
    }
  ]
  ```

### 1.2 获取对话详情
查看某次对话的完整历史记录。

- **URL**: `/api/history/{conversation_id}`
- **Method**: `GET`
- **Response**:
  ```json
  [
    { "role": "user", "content": "你好" },
    { "role": "assistant", "content": "您好！有什么可以帮您？" }
  ]
  ```

### 1.3 删除/批量删除对话
- **单条删除**: `DELETE /api/chat/{conversation_id}`
- **批量删除**: `POST /api/history/batch_delete`
  - Body: `{"ids": ["id1", "id2"]}`

---

## 2. AI 对话核心接口

### 2.1 流式对话
支持附件上传、联网搜索及知识库检索。

- **URL**: `/api/chat`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **Parameters**:
  | 字段名 | 说明 |
  | :--- | :--- |
  | `message` | 用户输入的文本内容 |
  | `conversation_id` | 唯一对话ID（前端生成或使用时间戳） |
  | `user_identity` | 用户身份标识（如 admin, user_a1 等） |
  | `files` | (可选) 文件附件列表 |
  | `web_search` | (可选) 是否开启联网搜索 (true/false) |
  | `rag_enabled` | (可选) 是否开启知识库检索 (true/false) |

- **Response**: `text/plain` 流式输出。
  - 特殊标签说明：
    - `[SOURCES_JSON]:[...]` : 包含参考链接的 JSON 数组
    - `[RECOMMENDATIONS]:[...]` : AI 预测的追问建议

---

## 3. 反馈与审计

### 3.1 提交意见反馈
当用户对回答不满意（点踩）时触发。

- **URL**: `/api/chat/feedback`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **Response**: `{"status": "success", "id": "feedback_id"}`

### 3.2 获取反馈列表
用于后台审计用户反馈。

- **URL**: `/api/feedback/list`
- **Method**: `GET`
- **Response**: 包含反馈人、企业、不满意原因及关联对话ID的列表。

---

## 4. 扩展说明 (预留)

### 4.1 导出功能
系统前端已集成导出 CSV 功能，逻辑如下：
1. 前端获取当前过滤后的列表数据。
2. 构造带 `UTF-8 BOM` 的 CSV 字符串以支持 Excel 直接打开。
3. 触发浏览器下载。

### 4.2 用户信息关联
目前系统假定用户已登录。在后续维护中，可通过 `user_identity` 字段在 `HistoryManagement.vue` 的表格中映射真实的 `IP地址`、`用户名` 等元数据。
