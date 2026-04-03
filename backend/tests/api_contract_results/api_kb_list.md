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
        "category": "知识库",
        "model": "openai",
        "remark": "",
        "enabled": true,
        "users": [],
        "fileCount": 0,
        "url": "知识库/测试库",
        "physical_path": "知识库/测试库",
        "owner_info": "",
        "created_at": "1",
        "updated_at": "1",
        "createdAt": "2026/03/24 00:00:00",
        "updatedAt": "2026/03/24 00:00:00"
      }
    ],
    "total": 1,
    "page": 1,
    "size": 10,
    "total_pages": 1
  }
}
```

## pagination_success

- status: PASS
- method: GET
- path: /api/kb/list
- notes: 知识库列表应支持 page/size 分页。

### request
```json
{
  "page": 2,
  "size": 1
}
```

### response
```json
{
  "code": 0,
  "msg": "获取知识库列表成功",
  "data": {
    "list": [
      {
        "id": "kb_2",
        "name": "分页库2",
        "category": "知识库",
        "model": "openai",
        "remark": "",
        "enabled": true,
        "users": [],
        "fileCount": 0,
        "url": "知识库/分页库2",
        "physical_path": "知识库/分页库2",
        "owner_info": "",
        "created_at": "1",
        "updated_at": "1",
        "createdAt": "2026/03/24 00:00:00",
        "updatedAt": "2026/03/24 00:00:00"
      }
    ],
    "total": 2,
    "page": 2,
    "size": 1,
    "total_pages": 2
  }
}
```
