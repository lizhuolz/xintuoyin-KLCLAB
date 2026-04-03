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
  "kb_update_request_body_description": "请求体参数"
}
```
