# api_kb_list

## success

- status: PASS
- method: GET
- path: /api/kb/list

### request
```json
{}
```

### response
```json
{
  "code": 0,
  "msg": "获取知识库列表成功",
  "data": {
    "list": [
      {
        "id": "kb_1",
        "name": "测试库",
        "category": "企业知识库",
        "model": "openai",
        "remark": "",
        "enabled": true,
        "users": [],
        "fileCount": 0,
        "url": "企业知识库/测试库",
        "physical_path": "企业知识库/测试库",
        "owner_info": "",
        "created_at": "1",
        "updated_at": "1",
        "createdAt": "2026/03/24 00:00:00",
        "updatedAt": "2026/03/24 00:00:00",
        "files": []
      }
    ],
    "total": 1
  }
}
```
