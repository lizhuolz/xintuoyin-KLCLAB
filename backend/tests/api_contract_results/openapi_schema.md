# openapi_schema

## descriptions_filled

- status: PASS
- method: GET
- path: /openapi.json
- notes: OpenAPI 文档应为 query/path/body 参数自动补齐描述，避免前端导入 Apipost 时出现 undefined。

### request
```json
{}
```

### response
```json
{
  "history_list_parameter_descriptions": [
    "历史记录关键词，可匹配标题、问题和回答。",
    "开始时间，毫秒时间戳。",
    "结束时间，毫秒时间戳。",
    "页码，从 1 开始。",
    "每页数量，默认 10。"
  ],
  "kb_update_request_body_description": "支持 application/json（无文件）和 multipart/form-data（带文件）的知识库更新请求。",
  "history_export_required": false,
  "feedback_process_properties": [
    "date_path",
    "id",
    "is_collect",
    "process_result",
    "processor"
  ],
  "feedback_list_response_keys": [
    "code",
    "data",
    "msg"
  ],
  "feedback_type_description": "主类型筛选：`dislike` 表示待优化回答，`like` 表示良好回答；不传表示反馈列表全部。",
  "db_options_response_keys": [
    "code",
    "data",
    "msg"
  ],
  "db_select_response_keys": [
    "code",
    "data",
    "msg"
  ]
}
```
