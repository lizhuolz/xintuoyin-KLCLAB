# api_kb_create

## success

- status: PASS
- method: POST
- path: /api/kb/create

### request
```json
{
  "name": "新知识库",
  "model": "openai"
}
```

### response
```json
{
  "code": 0,
  "msg": "创建知识库成功",
  "data": {
    "id": "kb_1",
    "name": "新知识库",
    "category": "知识库",
    "model": "openai",
    "remark": "",
    "enabled": true,
    "users": [],
    "fileCount": 0,
    "url": "知识库/新知识库",
    "physical_path": "知识库/新知识库",
    "owner_info": "",
    "created_at": "1",
    "updated_at": "1",
    "createdAt": "2026/03/24 00:00:00",
    "updatedAt": "2026/03/24 00:00:00"
  }
}
```
