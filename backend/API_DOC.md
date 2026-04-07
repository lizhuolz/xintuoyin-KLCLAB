# Backend API 文档

基于当前 [app.py](/home/lyq/xintuoyin-KLCLAB/backend/app.py) 生成。

## 概览

服务是一个 FastAPI 后端，核心能力包括：

- 流式对话 `/api/chat`
- 分离的思考过程说明 `/api/chat/{conversation_id}/thinking`
- 历史会话管理
- 点赞/点踩反馈管理
- 知识库管理与文件上传

默认服务监听端口是 `8000`，当前通过 `uvicorn app:app` 启动。

## 通用说明

- 基础响应类型：
  - 对话接口多为 `text/plain`
  - 其他管理接口多为 `application/json`
- 历史记录存储位置：MinIO `history/` 前缀
- 历史详情导出接口：`POST /api/history/export`，按选中记录导出单个 TXT 或多个 TXT 的 ZIP
- 原始提问附件下载接口：`GET /api/history/{conversation_id}/messages/{message_index}/files/{file_id}/download`
- 反馈存储目录：`backend/feedbacks`
- 知识库能力由 `KBService` 提供：`backend/services/kb_service.py`

## 1. 对话接口

### `GET /api/chat/new_session`

作用：创建一个新的 `conversation_id`

返回示例：

```json
{
  "conversation_id": "1774360151552"
}
```

### `POST /api/chat`

作用：发起一次流式对话。

请求类型：`multipart/form-data`

字段：

- `message: string` 必填，用户问题
- `conversation_id: string` 必填，会话 ID
- `files: file[]` 可选，附件
- `system_prompt: string` 可选，默认 `"You are a helpful assistant"`
- `web_search: bool` 可选，默认 `false`
- `db_version: string | null` 可选
- `user_identity: string | null` 可选，默认 `"guest"`

返回类型：`text/plain; charset=utf-8`

流内容规则：

- 正文直接以纯文本流式输出
- 如果有联网搜索来源，会插入一段：`[SOURCES_JSON]:[...]`
- 最后可能追加：`[RECOMMENDATIONS]:[...]`

当前特点：

- 已不再返回工具调用轨迹
- 回答生成后会把 `thinking_text` 和 `thinking_steps` 写入历史文件，供单独接口读取

示例：

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat   -F 'message=请使用计算器计算 12*(3+4)'   -F 'conversation_id=test1'   -F 'web_search=false'   -F 'user_identity=admin'
```

### `GET /api/chat/{conversation_id}/thinking`

作用：获取某条 assistant 回答在生成前的思考过程说明。

参数：

- `conversation_id: path` 必填
- `message_index: query` 可选，指定历史数组中的 assistant 消息索引
  - 不传时默认取最后一条 assistant

返回类型：`text/plain; charset=utf-8`

返回内容：

- 自然语言说明文本，不是 JSON

示例返回：

```text
在正式回答前，我先做了几步准备：
1. 我调用了 calculator，输入大致是：{"expression": "88+12"}。
对应上面第 1 步，calculator 返回了这样的关键信息：100.0。
整理完这些信息后，我再把最终答案组织成对你更自然的回复。
```

## 2. 历史记录接口

### `GET /api/history/list`

作用：获取会话摘要列表。

查询参数：

- `search: string` 可选
- `start_time: float` 可选，Unix 秒时间戳
- `end_time: float` 可选，Unix 秒时间戳

返回：数组。

单项字段：

- `id`
- `title`
- `updatedAt`
- `messageCount`
- `ip_address`
- `user_id`
- `record_id`

说明：

- `record_id = conversation_id`
- `user_id = 用户真实 ID`

### `GET /api/history/{conversation_id}`

作用：获取某个会话的完整消息数组。

返回：消息数组。

assistant 消息当前可能包含：

- `content`
- `feedback`
- `thinking_text`
- `thinking_steps`

示例消息结构：

```json
{
  "role": "assistant",
  "content": "计算结果是 84。",
  "thinking_text": "在正式回答前，我先做了几步准备：...",
  "thinking_steps": [
    {
      "kind": "call",
      "node_name": "chatbot_local",
      "tool_name": "calculator",
      "preview": "{"expression": "12*(3+4)"}",
      "tool_call_id": "..."
    }
  ]
}
```

### `DELETE /api/chat/{conversation_id}`

作用：删除单个会话历史文件。

### `POST /api/history/batch_delete`

作用：批量删除历史。

请求体：

```json
{
  "ids": ["conv1", "conv2"]
}
```

## 3. 反馈接口

### `POST /api/chat/feedback`

作用：对某条 assistant 消息点赞或点踩。

请求类型：`multipart/form-data`

字段：

- `conversation_id: string`
- `message_index: int`
- `type: string`，`like` 或 `dislike`
- `reasons: string | null`，JSON 字符串
- `comment: string | null`
- `files: file[] | null`

行为：

- 同一种反馈再次点击会取消
- 不同反馈会覆盖
- 点踩时必须提供原因、评论或图片之一

返回示例：

```json
{
  "status": "success",
  "feedback_state": "dislike",
  "id": "fb_test1_1"
}
```

### `GET /api/feedback/detail/{date}/{id}`

作用：获取单条反馈详情。

### `POST /api/feedback/process`

作用：管理端处理反馈。

请求体字段：

- `date_path`
- `id`
- `processor`
- `is_collect`

行为：

- 更新处理状态
- 可收录到优秀回答库或负面案例库

### `DELETE /api/feedback/{date}/{id}`

作用：删除反馈记录目录。

### `GET /api/feedback/list`

作用：获取反馈列表。

查询参数：

- `name`
- `enterprise`
- `type`

## 4. 知识库接口

### `GET /api/kb/list`

作用：获取知识库列表。

### `POST /api/kb/create`

作用：创建知识库。

表单字段：

- `name`
- `category`
- `model` 默认 `openai`

### `POST /api/kb/update`

作用：更新知识库元数据。

表单字段：

- `id`
- `name`
- `remark`
- `enabled`
- `users`

### `GET /api/kb/{id}/files`

作用：获取某知识库文件列表。

### `POST /api/kb/{id}/upload`

作用：上传文件到知识库并建立索引。

表单字段：

- `file`

### `POST /api/kb/{id}/delete_file`

作用：删除知识库中的指定文件。

表单字段：

- `filename`

## 5. 当前对话链路说明

一次正常前端聊天大致是：

1. 前端先调用 `GET /api/chat/new_session`
2. 前端调用 `POST /api/chat`
3. 后端流式返回正文
4. 后端把 `assistant.content + thinking_text + thinking_steps` 写入历史
5. 前端再调用 `GET /api/chat/{conversation_id}/thinking?message_index=...`
6. 前端展示“回答前，我做了这些准备”卡片

## 6. 关键实现位置

- 主接口定义：`backend/app.py`
- LangGraph 编排：`backend/agent/build_graph.py`
- 路由决策：`backend/agent/router.py`
- 工具注册：`backend/agent/tools/__init__.py`
