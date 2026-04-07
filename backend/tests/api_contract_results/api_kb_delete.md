# api_kb_delete

## success

- status: PASS
- method: DELETE
- path: /api/kb/{id}

### request
```json
{
  "id": "kb_1"
}
```

### response
```json
{
  "code": 0,
  "msg": "删除知识库成功",
  "data": {
    "id": "kb_1",
    "name": "删除库",
    "category": "知识库",
    "model": "openai",
    "remark": "",
    "enabled": true,
    "users": [],
    "fileCount": 0,
    "url": "知识库/删除库",
    "physical_path": "知识库/删除库",
    "owner_info": "",
    "created_at": "1",
    "updated_at": "1",
    "createdAt": "2026/03/24 00:00:00",
    "updatedAt": "2026/03/24 00:00:00"
  }
}
```

## not_found

- status: PASS
- method: DELETE
- path: /api/kb/{id}

### request
```json
{
  "id": "kb_missing"
}
```

### response
```json
{
  "code": 1,
  "msg": "删除知识库失败",
  "data": {
    "id": "kb_missing"
  }
}
```
