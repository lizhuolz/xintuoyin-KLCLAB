# api_kb_detail

## success

- status: PASS
- method: GET
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
  "msg": "获取知识库详情成功",
  "data": {
    "id": "kb_1",
    "name": "详情库",
    "category": "知识库",
    "model": "openai",
    "remark": "",
    "enabled": true,
    "users": [],
    "fileCount": 0,
    "url": "知识库/详情库",
    "physical_path": "知识库/详情库",
    "owner_info": "",
    "created_at": "1",
    "updated_at": "1",
    "createdAt": "2026/03/24 00:00:00",
    "updatedAt": "2026/03/24 00:00:00",
    "files": []
  }
}
```

## not_found

- status: PASS
- method: GET
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
  "msg": "获取知识库详情失败",
  "data": {
    "id": "kb_missing"
  }
}
```
