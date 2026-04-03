# 后端 API 手册

> 维护时间：2026-04-01
>
> 对齐代码：[app.py](/home/lyq/xintuoyin-KLCLAB/backend/app.py)
>
> 对齐契约报告：[SUMMARY.md](/home/lyq/xintuoyin-KLCLAB/backend/tests/api_contract_results/SUMMARY.md)

## 1. 范围

本文覆盖当前后端公开接口，包含：

- 对话与会话
- 历史记录
- 反馈管理
- 知识库管理
- 数据库显式选择
- OpenAPI 导入说明

## 2. 通用约定

### 2.1 Base URL

- 本地开发：`http://127.0.0.1:8000`

### 2.2 返回结构

业务成功：

```json
{
  "code": 0,
  "msg": "成功描述",
  "data": {}
}
```

业务失败：

```json
{
  "code": 1,
  "msg": "失败描述",
  "data": {
    "reason": "失败原因"
  }
}
```

参数校验失败由 FastAPI 返回：

```json
{
  "detail": [
    {
      "loc": ["query", "page"],
      "msg": "Input should be greater than or equal to 1",
      "type": "greater_than_equal"
    }
  ]
}
```

### 2.3 状态码

- `200`：请求成功
- `400`：业务参数错误
- `404`：资源不存在
- `422`：请求参数校验失败
- `500`：服务内部错误

### 2.4 OpenAPI 描述

当前已为 query、path、body、form 字段补充描述。导入 Apipost 时，不应再出现大量 `undefined` 参数说明。

OpenAPI 地址：

- `GET /openapi.json`

## 3. 对话与会话

### 3.1 `GET /api/chat/new_session`

用途：创建会话 ID。

成功返回：

```json
{
  "code": 0,
  "msg": "创建会话成功",
  "data": {
    "conversation_id": "1776150000000"
  }
}
```

说明：

- 该接口只分配会话 ID，不会立即写入历史文件。

### 3.2 `POST /api/chat`

用途：发送消息，支持附件、流式输出、联网搜索和多轮上下文。

请求类型：

- `multipart/form-data`

主要字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `message` | string | 是 | 用户输入 |
| `conversation_id` | string | 是 | 会话 ID |
| `files` | file[] | 否 | 本轮附件 |
| `system_prompt` | string | 否 | 系统提示词 |
| `web_search` | bool | 否 | 是否启用联网搜索 |
| `db_version` | string | 否 | 数据库版本标记 |
| `user_identity` | string | 否 | 用户身份，默认 `guest` |
| `stream` | bool | 否 | 默认 `true`，即默认流式 |

流式返回：

- `Content-Type: text/event-stream`
- 默认开启

事件类型：

- `thinking`
- `answer_delta`
- `answer_replace`
- `done`
- `error`

`done.data` 的核心字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `message_index` | int | 当前轮次索引 |
| `question` | string | 最终问题文本 |
| `files` | string[] | 附件文件名 |
| `uploaded_files` | object[] | 保存后的附件元数据 |
| `file_contexts` | object[] | 抽取后的附件正文摘要 |
| `answer` | string | 最终回答 |
| `resource` | object[] | 工具或联网资源 |
| `recommend_answer` | string[] | 推荐追问 |
| `feedback` | string/null | 当前反馈状态 |
| `thinking_text` | string | 思考过程文本 |
| `thinking_steps` | object[] | 工具调用轨迹 |

注意：

- 旧调用方如果还需要整包 JSON，需显式传 `stream=false`
- 前端应以 `done` 事件作为本轮真正完成标志

### 3.3 `GET /api/chat/{conversation_id}/title`

用途：读取会话标题。当前取首轮 `question`。

### 3.4 `POST /api/upload`

用途：给指定会话、指定轮次补传附件。

主要字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `conversation_id` | string | 是 | 会话 ID |
| `message_index` | int | 否 | 不传时默认追加到当前尾部 |
| `files` | file[] | 是 | 文件列表 |

### 3.5 `GET /api/chat/{conversation_id}/thinking`

用途：查看某一轮消息的思考过程。

查询参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `message_index` | int | 否 | 不传时默认取最后一轮 |
| `stream` | bool | 否 | 默认 `true`，按文本流返回 |

## 4. 历史记录

### 4.1 `GET /api/history/list`

用途：按关键词、时间范围和分页参数查询历史记录。

查询参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `search` | string | 否 | 关键词，匹配标题、问题、回答 |
| `start_time` | string | 否 | 开始时间，毫秒时间戳 |
| `end_time` | string | 否 | 结束时间，毫秒时间戳 |
| `page` | int | 否 | 页码，从 1 开始，默认 `1` |
| `size` | int | 否 | 每页数量，默认 `10` |

返回结构：

```json
{
  "code": 0,
  "msg": "获取历史记录成功",
  "data": {
    "items": [
      {
        "conversation_id": "1776150000000",
        "title": "测试会话",
        "message_count": 2,
        "last_user_input": "最后一轮用户输入",
        "last_answer": "最后一轮模型回答",
        "created_at": "1776150000000",
        "updated_at": "1776150009999",
        "createdAt": "2026/04/01 10:00:00",
        "updatedAt": "2026/04/01 10:00:09",
        "user": {
          "name": "王颖奇",
          "enterprise": "图湃（北京）医疗科技",
          "phone": "15323720032",
          "record_id": "A001",
          "ip_address": "127.0.0.1"
        }
      }
    ],
    "page": 1,
    "size": 10,
    "total": 1
  }
}
```

说明：

- `last_user_input` 和 `last_answer` 已按 TODO 补齐
- `user` 中已包含 `record_id` 和 `ip_address`

### 4.2 `GET /api/history/{conversation_id}`

用途：获取完整历史详情。

### 4.3 `DELETE /api/chat/{conversation_id}`

用途：删除单条历史记录。

### 4.4 `POST /api/history/batch_delete`

用途：批量删除历史记录。

请求体：

```json
{
  "ids": ["1776150000000", "1776150000001"]
}
```

## 5. 反馈管理

### 5.1 `POST /api/chat/feedback`

用途：对指定回答提交点赞或点踩。

请求类型：

- `multipart/form-data`

主要字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `conversation_id` | string | 是 | 会话 ID |
| `message_index` | int | 是 | 消息索引 |
| `type` | string | 是 | `like` 或 `dislike` |
| `reasons` | string | 否 | JSON 数组字符串 |
| `comment` | string | 否 | 补充说明 |
| `pictures` | file[] | 否 | 截图 |

说明：

- 重复点击同一反馈会切换为取消状态
- 点踩时必须提供原因、描述或截图中的至少一种

### 5.2 `POST /api/feedback/upload_pictures`

用途：为反馈补传截图。

### 5.3 `GET /api/feedback/list`

用途：分页查询反馈列表，并支持新的反馈类型筛选。

查询参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 否 | 用户姓名筛选 |
| `enterprise` | string | 否 | 企业筛选 |
| `type` | string | 否 | 兼容旧版 `like/dislike` 筛选 |
| `feedback_type` | string | 否 | 支持 `全部`、`针对问题`、`针对回答效果`、`举报`、`点赞`、`点踩` |
| `start_time` | string | 否 | 开始时间 |
| `end_time` | string | 否 | 结束时间 |
| `page` | int | 否 | 页码，默认 `1` |
| `size` | int | 否 | 每页数量，默认 `10` |

返回的单条摘要已重构为嵌套结构，重点字段如下：

```json
{
  "id": "fb_1776150000000_0",
  "conversation_id": "1776150000000",
  "message_index": 0,
  "type": "like",
  "state": "like",
  "user": {
    "name": "王颖奇",
    "enterprise": "图湃（北京）医疗科技",
    "phone": "15323720032",
    "record_id": "A001",
    "ip_address": "127.0.0.1"
  },
  "feedback_type": {
    "primary": "点赞",
    "scene": "针对回答效果",
    "labels": ["点赞", "针对回答效果"]
  },
  "times": {
    "time": "1776150001000",
    "update_time": "1776150002000",
    "createdAt": "2026/04/01 10:00:01",
    "updatedAt": "2026/04/01 10:00:02"
  },
  "process_status": "未处理"
}
```

时间字段说明：

- `time`：反馈首次创建时间戳
- `update_time`：反馈最近一次变更时间戳
- `createdAt`：首次创建展示时间
- `updatedAt`：最近一次变更展示时间

### 5.4 `GET /api/feedback/{feedback_id}`

用途：按反馈 ID 获取详情。

### 5.5 `GET /api/feedback/detail/{date}/{id}`

用途：按日期目录和 ID 获取详情。

### 5.6 `POST /api/feedback/process`

用途：处理反馈，并可选择是否收录。

请求体：

```json
{
  "id": "fb_1776150000000_0",
  "processor": "api_probe",
  "is_collect": true
}
```

### 5.7 `POST /api/feedback/batch_delete`

用途：批量删除反馈。

### 5.8 `DELETE /api/feedback/{date}/{id}`

用途：删除单条反馈。

## 6. 知识库

### 6.1 `GET /api/kb/list`

用途：分页查询知识库列表。

查询参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `page` | int | 否 | 页码，默认 `1` |
| `size` | int | 否 | 每页数量，默认 `10` |

### 6.2 `GET /api/kb/{id}`

用途：获取知识库详情。

### 6.3 `POST /api/kb/create`

用途：创建知识库。

请求类型：

- `multipart/form-data`

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 是 | 知识库名称 |
| `model` | string | 否 | 模型标识，默认 `openai` |

说明：

- `category` 已废弃，不再区分企业、部门、个人知识库

### 6.4 `POST /api/kb/update`

用途：更新知识库元数据，并在同一次请求中支持删文件、传文件和预览确认。

请求类型：

- `multipart/form-data`

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 知识库 ID |
| `name` | string | 否 | 知识库名称 |
| `remark` | string | 否 | 备注 |
| `enabled` | string | 否 | `true/false` |
| `users` | string | 否 | 授权用户 JSON 字符串 |
| `delete_files` | string | 否 | 待删除文件名 JSON 数组 |
| `confirm` | bool | 否 | 默认 `true`；`false` 表示仅预览 |
| `files` | file[] | 否 | 待上传新文件 |

预览模式特点：

- `confirm=false` 只返回预览结果，不实际写入
- 返回中会包含 `preview: true`
- 返回中会包含 `pending.confirm_required: true`
- 前端可以先本地展示将删除和将上传的文件，再由用户确认

确认提交特点：

- `confirm=true` 才真正执行上传、删除和元数据更新
- 返回中 `preview: false`

### 6.5 `DELETE /api/kb/{id}`

用途：删除知识库。

### 6.6 `GET /api/kb/{id}/files`

用途：获取知识库文件列表。

### 6.7 `POST /api/kb/{id}/upload`

用途：直接给知识库上传文件。

### 6.8 `POST /api/kb/{id}/delete_files`

用途：批量删除知识库文件。

请求体：

```json
{
  "filenames": ["old.txt", "draft.pdf"]
}
```

### 6.9 `POST /api/kb/{id}/delete_file`

用途：删除单个知识库文件。

请求类型：

- `multipart/form-data`

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `filename` | string | 是 | 文件名 |

## 7. 数据库显式选择

### 7.1 `GET /api/db/select_options`

用途：返回数据库候选表、表注释、字段注释，并可结合自然语言问题给出推荐选中表。

查询参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `question` | string | 否 | 用户问题，用于推荐表 |

成功返回：

```json
{
  "code": 0,
  "msg": "获取数据库显式可选字段成功",
  "data": {
    "question": "我们公司的总员工是多少",
    "selected_tables": ["employee"],
    "options": [
      {
        "table_name": "employee",
        "table_comment": "员工信息表",
        "column_comments": [
          "id: 主键",
          "name: 姓名",
          "department: 部门"
        ],
        "selected": true
      }
    ],
    "total": 1
  }
}
```

说明：

- 该接口用于前端显式选表，不直接执行 SQL
- 当模型选表失败时，后端会回退到关键词规则推荐，避免返回空结果

## 8. 前端接入建议

- 历史记录、反馈列表、知识库列表统一按 `page/size` 读写
- 聊天和思考过程默认按流式处理
- 知识库编辑页应先调用 `confirm=false` 预览，再提示用户二次确认
- 反馈列表优先使用新的 `feedback_type`、`times`、`user` 嵌套结构
- 数据库显式选择页或弹窗可直接消费 `/api/db/select_options`

## 9. 参考文件

- [app.py](/home/lyq/xintuoyin-KLCLAB/backend/app.py)
- [kb_service.py](/home/lyq/xintuoyin-KLCLAB/backend/services/kb_service.py)
- [SUMMARY.md](/home/lyq/xintuoyin-KLCLAB/backend/tests/api_contract_results/SUMMARY.md)
- [openapi_schema.md](/home/lyq/xintuoyin-KLCLAB/backend/tests/api_contract_results/openapi_schema.md)
