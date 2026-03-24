# 后端 API 详细文档

> 文档基于 [backend/app.py](/home/lyq/xintuoyin-KLCLAB/backend/app.py) 实现、运行中的 `http://127.0.0.1:8000/openapi.json` 以及 2026-03-25 实测结果整理。

## 1. 文档范围

本文覆盖当前后端全部公开接口：

- 对话与会话
- 文件上传
- 历史记录
- 思考过程
- 反馈处理
- 知识库管理

## 2. 通用规范

### 2.1 Base URL

- 本地开发：`http://127.0.0.1:8000`

### 2.2 通用返回结构

业务成功时：

```json
{
  "code": 0,
  "msg": "成功描述",
  "data": {}
}
```

业务失败时：

```json
{
  "code": 1,
  "msg": "失败描述",
  "data": {
    "reason": "失败原因"
  }
}
```

框架参数校验失败时：

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "message"],
      "msg": "Field required"
    }
  ]
}
```

### 2.3 状态码约定

- `200`：调用成功
- `400`：业务参数不合法
- `404`：目标资源不存在
- `422`：FastAPI 请求参数校验失败
- `500`：服务内部异常，常见于模型调用或文件处理失败

### 2.4 前端接入总原则

- 首次进入聊天页先调用 `GET /api/chat/new_session` 获取 `conversation_id`
- 发送消息优先走 `POST /api/chat`；有附件时可直接随消息提交，也可先走 `/api/upload`
- 聊天流式模式必须按事件类型处理 `answer_delta`、`thinking`、`done`、`error`
- 反馈、思考过程、附件补传都依赖 `conversation_id + message_index`
- 删除类接口仅对已持久化资源生效，新建但从未写入磁盘的资源可能返回 `404`

## 3. 对话与会话接口

### 3.1 `GET /api/chat/new_session`

作用：创建新的会话 ID，用于后续聊天、上传、反馈和历史记录查询。

请求规范：

- Method：`GET`
- Content-Type：无要求
- 鉴权：当前实现未强制要求

成功返回 `data` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `conversation_id` | string | 毫秒时间戳格式的会话 ID |

特殊情况：

- 该接口只分配 ID，不会立即落盘历史文件
- 因此如果前端只调了这个接口、没有发生聊天，后续直接删除该 ID 可能返回 `404`

前端参考逻辑：

1. 进入新会话页立即拉取一个 `conversation_id`
2. 本地缓存到页面状态或路由参数
3. 真正发送第一条消息前不要重新生成，避免附件、反馈与历史错绑

测试用例：

- 成功：正常获取 `conversation_id`
- 压力：20 次请求全部成功，`p50=9.73ms`，`max=11.74ms`

### 3.2 `POST /api/chat`

作用：发送用户消息并得到助手回答，支持附件、流式输出、联网搜索和上下文拼装。

请求规范：

- Method：`POST`
- Content-Type：`multipart/form-data`
- Header：`accessToken` 可选

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `message` | string | 是 | 用户本轮输入 |
| `conversation_id` | string | 是 | 会话 ID |
| `files` | file[] | 否 | 本轮附件 |
| `system_prompt` | string | 否 | 默认 `You are a helpful assistant` |
| `web_search` | bool | 否 | 是否启用联网搜索，默认 `false` |
| `db_version` | string | 否 | 数据库版本标记，当前仅透传存档 |
| `user_identity` | string | 否 | 默认 `guest` |
| `stream` | bool | 否 | 默认 `true` |

非流式成功返回 `data` 主要字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `message_index` | int | 当前轮次编号 |
| `question` | string | 经过安全校验后的问题 |
| `files` | string[] | 附件文件名列表 |
| `uploaded_files` | object[] | 已保存附件元信息 |
| `file_contexts` | object[] | 后端解析出的附件正文摘要 |
| `web_search` | bool | 是否启用联网搜索 |
| `db_version` | string/null | 数据库版本标记 |
| `answer` | string | 最终回答 |
| `resource` | object[] | 外部资源列表，联网检索时有值 |
| `recommend_answer` | string[] | 推荐追问 |
| `feedback` | string/null | 初始为 `null` |
| `thinking_text` | string | 思考过程文本 |
| `thinking_steps` | object[] | 工具调用轨迹 |
| `created_at` | string | 毫秒时间戳 |
| `updated_at` | string | 毫秒时间戳 |
| `createdAt` | string | 展示时间 |
| `updatedAt` | string | 展示时间 |

`uploaded_files` 元素字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `file_id` | string | 文件唯一标识 |
| `filename` | string | 文件名，重名时自动加后缀 |
| `url` | string | 静态访问路径 |
| `relative_path` | string | 相对上传根目录路径 |

`file_contexts` 元素字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `filename` | string | 文件名 |
| `text` | string | 抽取出的正文或错误提示 |

流式模式返回：`text/event-stream`

事件类型：

- `answer_delta`：追加回答文本
- `answer_replace`：安全拦截后整体替换回答
- `thinking`：更新思考文本与工具轨迹
- `done`：最终完成事件，`data` 结构与非流式一致
- `error`：流式处理异常

特殊情况：

- `message` 缺失会触发 `422`
- 输入命中安全策略会返回 `400`，例如 `ignore previous instructions`
- 附件会被保存并尝试抽取正文；旧版 Office 二进制格式会返回“不支持直接抽取正文”的提示
- `stream=true` 时前端必须等待 `done` 才能认定消息入库完成
- 回答会自动写入历史文件，因此这也是让会话真正“持久化”的入口

前端参考逻辑：

1. 第一次发言前确保已有 `conversation_id`
2. 优先直接通过 `POST /api/chat` 一次性提交文本和附件
3. 如果选择流式：
   - `answer_delta` 逐段拼接到消息气泡
   - `thinking` 用于“思考中”面板
   - `done.data` 覆盖最终消息对象并拿到 `message_index`
4. 如果非流式：直接用 `data` 渲染消息
5. 拿到 `message_index` 后，后续 `/thinking`、`/feedback`、`/upload` 都依赖它

测试用例：

- 成功：带文本附件的非流式问答返回 200，实测回答正确抽取了 `probe.txt`
- 边界：缺少 `message` 返回 422；命中安全词返回 400
- 压力：轻量串行 2 次，全部成功，`p50=7748.60ms`，`max=7748.60ms`
- 流式：实测存在 `done` 事件，耗时约 `8864.23ms`

### 3.3 `GET /api/chat/{conversation_id}/title`

作用：获取会话标题，当前实现直接取第一轮 `question`。

请求规范：

- Method：`GET`
- Path：`conversation_id`

成功返回 `data` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `conversation_id` | string | 会话 ID |
| `title` | string | 标题 |
| `question` | string | 与 `title` 相同 |

特殊情况：

- 如果该会话没有任何消息，返回 `404`

前端参考逻辑：

- 历史列表可以直接用 `/api/history/list` 返回的 `title`
- 详情页如需懒加载标题，可调用本接口

测试用例：

- 边界：不存在的会话返回 `404`
- 压力：15 次全部成功，`p50=9.36ms`

## 4. 文件上传接口

### 4.1 `POST /api/upload`

作用：给指定会话和指定消息轮次补传附件。

请求规范：

- Method：`POST`
- Content-Type：`multipart/form-data`

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `conversation_id` | string | 是 | 会话 ID |
| `message_index` | int | 否 | 不填时默认追加到当前消息尾部索引 |
| `files` | file[] | 是 | 上传文件列表 |

成功返回 `data` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `conversation_id` | string | 会话 ID |
| `message_index` | int | 文件挂载的轮次 |
| `files` | object[] | 与聊天接口 `uploaded_files` 结构相同 |

特殊情况：

- `message_index < 0` 返回 `400`
- 如果 `message_index` 对应的消息不存在，文件仍会保存，但不会回填到历史消息对象

前端参考逻辑：

- 推荐优先直接使用 `/api/chat` 上传附件
- 本接口适合“先发消息，后补附件”场景
- 上传成功后如果目标轮次已存在，前端应刷新当前消息详情

测试用例：

- 边界：`message_index=-1` 返回 `400`
- 压力：5 次全部成功，`p50=12.02ms`

## 5. 历史记录接口

### 5.1 `GET /api/history/list`

作用：查询会话历史列表，支持关键字和时间范围筛选。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `search` | string | 否 | 标题与问答全文模糊匹配 |
| `start_time` | string | 否 | 起始毫秒时间戳 |
| `end_time` | string | 否 | 截止毫秒时间戳 |

成功返回 `data` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `list` | object[] | 历史项列表 |
| `total` | int | 总数 |

`list` 元素字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `conversation_id` | string | 会话 ID |
| `title` | string | 标题 |
| `updated_at` | string | 毫秒时间戳 |
| `updatedAt` | string | 展示时间 |
| `message_count` | int | 消息轮次数 |
| `user` | object | 用户简要信息 |

特殊情况：

- `start_time` 或 `end_time` 不是毫秒时间戳会返回 `400`
- 搜索是大小写不敏感的全文匹配

前端参考逻辑：

- 历史页列表直接依赖本接口
- 搜索框和时间筛选栏可以直接映射到查询参数
- 结果已按 `updated_at` 倒序排序

测试用例：

- 边界：非法 `start_time=abc` 返回 `400`
- 检索：命中和未命中均验证通过
- 压力：20 次全部成功，`p50=32.76ms`

### 5.2 `GET /api/history/{conversation_id}`

作用：获取单个会话完整历史内容。

成功返回：完整历史记录对象，包括 `messages` 数组。

历史记录主要字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `conversation_id` | string | 会话 ID |
| `title` | string | 标题 |
| `created_at` | string | 毫秒时间戳 |
| `updated_at` | string | 毫秒时间戳 |
| `createdAt` | string | 展示时间 |
| `updatedAt` | string | 展示时间 |
| `message_count` | int | 轮次数 |
| `user` | object | 用户简要信息 |
| `messages` | object[] | 所有轮次消息 |

`messages` 元素结构与 `/api/chat` 成功返回的 `data` 基本一致。

特殊情况：

- 会话不存在或没有消息返回 `404`

前端参考逻辑：

- 进入历史详情页时调用本接口恢复整段对话
- 如需渲染附件、思考过程、反馈状态，直接读取 `messages[n]`

测试用例：

- 边界：不存在会话返回 `404`
- 压力：15 次全部成功，`p50=9.45ms`

### 5.3 `DELETE /api/chat/{conversation_id}`

作用：删除单个会话历史文件。

成功返回 `data` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `conversation_id` | string | 已删除的会话 ID |

特殊情况：

- 如果只是调用了 `/api/chat/new_session` 但从未发消息，该会话没有历史文件，删除会返回 `404`
- 删除后会尝试清理空目录

前端参考逻辑：

- 删除前建议先确认该会话至少已有一轮消息
- 删除成功后前端应把当前详情页跳回列表或新建页

测试用例：

- 成功：对已持久化会话删除返回 `200`
- 边界：不存在会话返回 `404`
- 备注：探针中对“未持久化新会话”删除返回 `404`，属于符合当前实现的特殊行为

### 5.4 `POST /api/history/batch_delete`

作用：批量删除多个会话历史。

请求体：

```json
{
  "ids": ["conversation_id_1", "conversation_id_2"]
}
```

兼容字段：`conversation_ids`

成功返回 `data` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `deleted_ids` | string[] | 实际删除成功的 ID 列表 |

特殊情况：

- `ids` 或 `conversation_ids` 不是数组时返回 `400`
- 对不存在的会话不会报错，只是不出现在 `deleted_ids` 中

前端参考逻辑：

- 适合历史管理页的多选删除
- 建议根据 `deleted_ids` 做局部刷新，而不是盲删全部勾选项

测试用例：

- 边界：`ids` 为字符串返回 `400`
- 压力：5 次全部成功，`p50=10.81ms`

## 6. 思考过程接口

### 6.1 `GET /api/chat/{conversation_id}/thinking`

作用：获取某个回答的思考文本，支持纯文本和流式文本。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `message_index` | int | 否 | 不传时默认取最后一轮 |
| `stream` | bool | 否 | 默认 `true`，返回 `text/plain` 流 |

返回规范：

- `stream=true`：`StreamingResponse(text/plain)`
- `stream=false`：`PlainTextResponse`

特殊情况：

- 会话不存在返回 `404`
- 指定 `message_index` 不存在返回 `404`
- 若没有工具调用，会返回默认说明文本

前端参考逻辑：

- 历史消息卡片上可增加“查看思考过程”按钮
- `stream=false` 适合弹窗一次性加载
- `stream=true` 适合渐进式渲染长思考文本

测试用例：

- 边界：不存在会话、不存在消息轮次均返回 `404`
- 压力：10 次全部成功，`p50=10.13ms`

## 7. 反馈接口

### 7.1 `POST /api/chat/feedback`

作用：对指定消息提交点赞或点踩反馈，可附原因、描述和截图。

请求规范：

- Method：`POST`
- Content-Type：`multipart/form-data`
- Header：`accessToken` 可选

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `conversation_id` | string | 是 | 会话 ID |
| `message_index` | int | 是 | 消息轮次 |
| `type` | string | 是 | 仅支持 `like` / `dislike` |
| `reasons` | string | 否 | 可传 JSON 数组、JSON 对象或普通字符串 |
| `comment` | string | 否 | 文字反馈 |
| `pictures` | file[] | 否 | 截图 |
| `files` | file[] | 否 | 与 `pictures` 兼容的上传字段 |

成功返回 `data` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 反馈 ID，格式 `fb_{conversation_id}_{message_index}` |
| `conversation_id` | string | 会话 ID |
| `message_index` | int | 消息轮次 |
| `type` | string | 本次提交的类型 |
| `state` | string/null | 当前状态；重复点同一 `like` 会切换为 `null` |
| `reasons` | string[] | 原因列表 |
| `comment` | string | 文字说明 |
| `pictures` | string[] | 截图文件名 |
| `name` | string | 用户名 |
| `enterprise` | string | 企业名称 |
| `phone` | string | 手机号 |
| `time` | string | 首次创建时间 |
| `update_time` | string | 最近更新时间 |
| `createdAt` | string | 展示时间 |
| `updatedAt` | string | 展示时间 |
| `process_status` | string | 默认 `未处理` |

特殊情况：

- `type` 非 `like/dislike` 返回 `400`
- `message_index < 0` 返回 `400`
- 指向不存在的消息返回 `404`
- 点踩时如果没有 `reasons/comment/图片` 任一项，会返回 `400`
- 重复提交同一 `like` 会清空状态，属于“toggle off”行为

前端参考逻辑：

- 点赞按钮可直接调用 `type=like`
- 点踩按钮建议先弹出原因选择框，至少要求用户填写原因、评论或截图之一
- 前端状态不要只依赖 `type`，而要看返回的 `state`
- 成功后可联动刷新消息卡片中的 `feedback`

测试用例：

- 成功：点赞、点踩带评论和截图都验证通过
- 边界：非法类型、负索引、空点踩均返回 `400`
- 压力：4 次切换点赞全部成功，`p50=15.52ms`

### 7.2 `POST /api/feedback/upload_pictures`

作用：给某条反馈单独补传图片。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `conversation_id` | string | 是 | 会话 ID |
| `message_index` | int | 是 | 消息轮次 |
| `pictures` | file[] | 是 | 图片列表 |

成功返回 `data` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `conversation_id` | string | 会话 ID |
| `message_index` | int | 消息轮次 |
| `pictures` | object[] | 新增图片元信息 |

`pictures` 元素字段：`file_id`、`filename`、`url`

特殊情况：

- `message_index < 0` 返回 `400`
- 当前实现主要根据文件名与字节流保存，未对图片内容做强校验

前端参考逻辑：

- 适合“先提交点踩，再追加截图”的交互
- 成功后可把返回的 `pictures` 追加到反馈详情页中

测试用例：

- 边界：负索引返回 `400`
- 压力：3 次全部成功，`p50=15.54ms`

### 7.3 `GET /api/feedback/list`

作用：查询反馈列表。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 否 | 按姓名过滤 |
| `enterprise` | string | 否 | 按企业过滤 |
| `type` | string | 否 | 反馈类型过滤 |
| `start_time` | string | 否 | 起始毫秒时间戳 |
| `end_time` | string | 否 | 截止毫秒时间戳 |

成功返回 `data`：

- `list`：反馈摘要数组
- `total`：总数

反馈摘要结构与 `/api/chat/feedback` 返回的 `data` 基本一致。

特殊情况：

- 非法时间戳返回 `400`

前端参考逻辑：

- 管理后台列表页直接使用
- 处理状态可从 `process_status` 判断是否已处理

测试用例：

- 边界：`start_time=abc` 返回 `400`
- 压力：10 次全部成功，`p50=16.37ms`

### 7.4 `GET /api/feedback/{feedback_id}`

作用：按反馈 ID 读取反馈详情。

特殊情况：

- 反馈不存在返回 `404`

前端参考逻辑：

- 适合通过列表项点击后直达详情

测试用例：

- 边界：不存在 ID 返回 `404`
- 压力：10 次全部成功，`p50=9.04ms`

### 7.5 `GET /api/feedback/detail/{date}/{id}`

作用：按日期分区和反馈 ID 读取详情。

特殊情况：

- 目标目录不存在返回 `404`

前端参考逻辑：

- 如果后台列表中已经携带日期分区，可直接走该接口减少二次检索

测试用例：

- 边界：不存在记录返回 `404`
- 压力：10 次全部成功，`p50=10.23ms`

### 7.6 `POST /api/feedback/process`

作用：处理反馈，并可选择将问答样本收录到优秀答案或负向问答目录。

请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 反馈 ID |
| `date_path` | string | 否 | 日期目录；不传时自动搜索 |
| `processor` | string | 否 | 默认 `系统管理员` |
| `is_collect` | bool | 否 | 是否收录样本，默认 `false` |

成功返回：完整 `feedback.json` 内容，并新增以下字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `processor` | string | 处理人 |
| `processed_at` | string | 处理时间戳 |
| `processedAt` | string | 展示时间 |
| `process_result` | string | `已收录` 或 `已处理(未收录)` |
| `process_status` | string | `已处理` |

特殊情况：

- `id` 为空返回 `400`
- 找不到反馈记录返回 `404`
- `is_collect=true` 时：
  - `like` 会进入优秀答案目录
  - `dislike` 会进入负向问答目录

前端参考逻辑：

- 反馈管理后台处理按钮调用本接口
- 建议前端显式展示“仅处理”和“处理并收录”两个动作

测试用例：

- 成功：普通处理、收录处理均验证通过
- 边界：缺失 `id` 返回 `400`
- 压力：3 次全部成功，`p50=10.69ms`

### 7.7 `POST /api/feedback/batch_delete`

作用：批量删除反馈目录。

请求体：

```json
{
  "ids": ["fb_xxx_0", "fb_xxx_1"]
}
```

成功返回：`deleted_ids`

特殊情况：

- `ids` 不是数组返回 `400`
- 不存在的反馈会被静默忽略

前端参考逻辑：

- 适用于反馈管理页多选删除

测试用例：

- 边界：`ids` 非数组返回 `400`
- 压力：5 次全部成功，`p50=11.05ms`

### 7.8 `DELETE /api/feedback/{date}/{id}`

作用：按日期目录删除单条反馈。

特殊情况：

- 不存在则返回 `404`
- 删除后会尝试清理空父目录

前端参考逻辑：

- 后台删除时若手头只有 `feedback_id`，更推荐先用 `/api/feedback/{feedback_id}` 获取详情后再删

测试用例：

- 成功：已创建反馈删除返回 `200`
- 边界：不存在记录返回 `404`
- 说明：探针压力用例针对 `404` 边界执行，目的是验证幂等与错误路径稳定性

## 8. 知识库接口

### 8.1 `GET /api/kb/list`

作用：获取知识库列表。

成功返回 `data`：

- `list`：知识库数组
- `total`：总数

知识库摘要字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 知识库 ID |
| `name` | string | 名称 |
| `category` | string | 分类 |
| `model` | string | 关联模型 |
| `remark` | string | 备注 |
| `enabled` | bool | 是否启用 |
| `users` | object[] | 用户可见范围 |
| `fileCount` | int | 文件数 |
| `url` | string | 相对物理路径 |
| `physical_path` | string | 相对物理路径 |
| `owner_info` | string | 所属公司/部门 |
| `created_at` | string | 创建时间戳 |
| `updated_at` | string | 更新时间戳 |
| `createdAt` | string | 展示时间 |
| `updatedAt` | string | 展示时间 |

前端参考逻辑：

- 知识库首页和下拉选择器直接使用本接口

测试用例：

- 压力：15 次全部成功，`p50=14.07ms`

### 8.2 `GET /api/kb/{id}`

作用：获取知识库详情，包括文件列表。

额外返回字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `files` | object[] | 文件列表 |

文件元素字段：`file_id`、`name`、`url`、`size`、`uploaded_at`、`uploadedAt`

特殊情况：

- 知识库不存在返回 `404`

前端参考逻辑：

- 详情页进入时调用，避免列表页携带过大文件信息

测试用例：

- 边界：不存在 ID 返回 `404`
- 压力：10 次全部成功，`p50=10.38ms`

### 8.3 `POST /api/kb/create`

作用：创建知识库元数据和存储目录。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 是 | 知识库名称 |
| `category` | string | 是 | 如个人/部门/企业知识库 |
| `model` | string | 否 | 默认 `openai` |

特殊情况：

- 缺少必填字段触发 `422`
- 同名目录已存在时会自动在目录名后追加时间后缀避免冲突

前端参考逻辑：

- 新建后应使用返回的 `id` 继续走上传和详情接口

测试用例：

- 边界：缺少 `name` 返回 `422`
- 压力：3 次全部成功，`p50=11.63ms`

### 8.4 `POST /api/kb/update`

作用：更新知识库名称、备注、启用状态和用户列表。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 知识库 ID |
| `name` | string | 否 | 名称 |
| `remark` | string | 否 | 备注 |
| `enabled` | string | 否 | 字符串 `true/false` |
| `users` | string | 否 | JSON 字符串数组 |

特殊情况：

- `users` 不是合法 JSON 返回 `400`
- 目标知识库不存在返回 `404`
- `enabled` 的解析是 `enabled.lower() == "true"`

前端参考逻辑：

- 用户列表要先序列化成 JSON 字符串再提交
- `enabled` 不要传布尔值对象，统一传字符串

测试用例：

- 边界：非法 JSON 返回 `400`，不存在 ID 返回 `404`
- 压力：5 次全部成功，`p50=12.03ms`

### 8.5 `POST /api/kb/{id}/upload`

作用：上传知识库文档。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `files` | file[] | 是 | 文档列表 |

成功返回：`files` 为当前知识库全部文件列表，而不是仅新增文件名。

特殊情况：

- 知识库不存在返回 `404`
- 文件重名会自动追加 `_1`、`_2` 等后缀

前端参考逻辑：

- 上传完成后无需额外调 `/files` 也能直接刷新列表，但推荐在复杂场景仍做一次刷新

测试用例：

- 边界：不存在知识库返回 `404`
- 压力：3 次全部成功，`p50=15.38ms`

### 8.6 `GET /api/kb/{id}/files`

作用：单独获取知识库文件列表。

成功返回 `data`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 知识库 ID |
| `url` | string | 知识库目录 |
| `files` | object[] | 文件列表 |

特殊情况：

- 知识库不存在返回 `404`

前端参考逻辑：

- 文件管理页建议直接调本接口，避免依赖详情页结构变更

测试用例：

- 边界：不存在知识库返回 `404`
- 压力：10 次全部成功，`p50=13.00ms`

### 8.7 `POST /api/kb/{id}/delete_files`

作用：批量删除知识库文件。

请求体：

```json
{
  "filenames": ["a.txt", "b.pdf"]
}
```

兼容字段：`files`

成功返回：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 知识库 ID |
| `deleted_files` | string[] | 实际删除成功的文件名 |

特殊情况：

- `filenames` 不是数组返回 `400`
- 知识库不存在返回 `404`
- 对不存在的文件名会被静默忽略

前端参考逻辑：

- 多选删除优先走该接口
- 删除后可根据 `deleted_files` 局部更新文件列表

测试用例：

- 边界：`filenames` 非数组返回 `400`；不存在知识库返回 `404`
- 压力：5 次全部成功，`p50=10.13ms`

### 8.8 `POST /api/kb/{id}/delete_file`

作用：删除单个知识库文件。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `filename` | string | 是 | 文件名 |

特殊情况：

- 知识库不存在返回 `404`
- 文件不存在时返回 `200`，但 `deleted_files` 可能为空

前端参考逻辑：

- 单文件行内删除优先走该接口
- 删除后判断 `deleted_files` 是否为空，以确认是否真正删掉文件

测试用例：

- 边界：不存在知识库返回 `404`
- 压力：5 次全部成功，`p50=11.24ms`

### 8.9 `DELETE /api/kb/{id}`

作用：删除知识库及其文档目录。

特殊情况：

- 知识库不存在返回 `404`
- 删除会同时删除目录与元数据

前端参考逻辑：

- 删除成功后应从列表中移除并跳出详情页

测试用例：

- 成功：已创建知识库删除返回 `200`
- 边界：不存在知识库返回 `404`
- 说明：探针压力用例针对 `404` 边界路径执行，用于验证重复删除时的稳定性

## 9. 推荐的前端调用时序

### 9.1 聊天页

1. `GET /api/chat/new_session`
2. `POST /api/chat` 发送首轮消息
3. 如需查看思考过程：`GET /api/chat/{conversation_id}/thinking`
4. 如需反馈：`POST /api/chat/feedback`
5. 历史恢复：`GET /api/history/{conversation_id}`

### 9.2 历史页

1. `GET /api/history/list`
2. 点击某项：`GET /api/history/{conversation_id}`
3. 删除单项：`DELETE /api/chat/{conversation_id}`
4. 批量删除：`POST /api/history/batch_delete`

### 9.3 反馈后台

1. `GET /api/feedback/list`
2. 查看详情：`GET /api/feedback/{feedback_id}` 或 `GET /api/feedback/detail/{date}/{id}`
3. 补传截图：`POST /api/feedback/upload_pictures`
4. 处理：`POST /api/feedback/process`
5. 删除：`DELETE /api/feedback/{date}/{id}` 或 `POST /api/feedback/batch_delete`

### 9.4 知识库后台

1. `GET /api/kb/list`
2. `POST /api/kb/create`
3. `POST /api/kb/{id}/upload`
4. `GET /api/kb/{id}` 或 `GET /api/kb/{id}/files`
5. `POST /api/kb/update`
6. `POST /api/kb/{id}/delete_file` 或 `POST /api/kb/{id}/delete_files`
7. `DELETE /api/kb/{id}`

## 10. 发现的实现特点与风险

- `DELETE /api/chat/{conversation_id}` 对“仅生成 ID、未落历史文件”的会话会返回 `404`，前端要区分“空会话”和“已有会话”。
- `POST /api/chat/feedback` 的点赞是可切换的，重复点击同一 `like` 会把 `state` 清空。
- `POST /api/feedback/upload_pictures` 当前主要做文件保存，不校验真实图片内容类型。
- `POST /api/kb/update` 的 `enabled` 是字符串解析，不是标准 JSON 布尔解析。
- `/api/chat` 的耗时远高于其他接口，前端需要明确 loading、超时与重试策略。
- 聊天、反馈、知识库接口都存在落盘副作用，生产环境建议补充幂等键、权限校验和审计日志。

## 11. 相关文件

- API 实现：[backend/app.py](/home/lyq/xintuoyin-KLCLAB/backend/app.py)
- 知识库服务：[backend/services/kb_service.py](/home/lyq/xintuoyin-KLCLAB/backend/services/kb_service.py)
- 安全校验：[backend/utils/security.py](/home/lyq/xintuoyin-KLCLAB/backend/utils/security.py)
- 测试探针：[backend/tests/api_stress_probe.py](/home/lyq/xintuoyin-KLCLAB/backend/tests/api_stress_probe.py)
- 原始测试报告：[backend/tests/artifacts/api_stress_report.json](/home/lyq/xintuoyin-KLCLAB/backend/tests/artifacts/api_stress_report.json)
