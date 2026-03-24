# api_kb_update

## success

- status: PASS
- method: POST
- path: /api/kb/update

### request
```json
{
  "id": "kb_1",
  "remark": "新的备注",
  "enabled": "false"
}
```

### response
```json
{
  "code": 0,
  "msg": "更新知识库成功",
  "data": {
    "id": "kb_1",
    "name": "更新库",
    "category": "企业知识库",
    "model": "openai",
    "remark": "新的备注",
    "enabled": false,
    "users": [
      {
        "name": "张三",
        "phone": "1",
        "categoryName": "企业"
      }
    ],
    "fileCount": 0,
    "url": "企业知识库/更新库",
    "physical_path": "企业知识库/更新库",
    "owner_info": "",
    "created_at": "1",
    "updated_at": "2",
    "createdAt": "2026/03/24 00:00:00",
    "updatedAt": "2026/03/24 00:00:01"
  }
}
```

## invalid_users_json

- status: PASS
- method: POST
- path: /api/kb/update

### request
```json
{
  "id": "kb_1",
  "users": "{bad json"
}
```

### response
```json
{
  "code": 1,
  "msg": "更新知识库失败",
  "data": {
    "reason": "users 字段不是合法 JSON"
  }
}
```

## not_found

- status: PASS
- method: POST
- path: /api/kb/update

### request
```json
{
  "id": "kb_missing",
  "remark": "新的备注"
}
```

### response
```json
{
  "code": 1,
  "msg": "更新知识库失败",
  "data": {
    "id": "kb_missing"
  }
}
```
