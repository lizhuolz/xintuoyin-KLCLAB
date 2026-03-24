# api_kb_delete_file

## success

- status: PASS
- method: POST
- path: /api/kb/{id}/delete_file

### request
```json
{
  "id": "kb_1",
  "filename": "a.txt"
}
```

### response
```json
{
  "code": 0,
  "msg": "删除知识库文档成功",
  "data": {
    "id": "kb_1",
    "deleted_files": [
      "a.txt"
    ]
  }
}
```

## kb_not_found

- status: PASS
- method: POST
- path: /api/kb/{id}/delete_file

### request
```json
{
  "id": "kb_missing",
  "filename": "a.txt"
}
```

### response
```json
{
  "code": 1,
  "msg": "删除知识库文档失败",
  "data": {
    "id": "kb_missing"
  }
}
```
