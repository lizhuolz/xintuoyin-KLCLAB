# api_kb_delete_files

## success

- status: PASS
- method: POST
- path: /api/kb/{id}/delete_files

### request
```json
{
  "id": "kb_1",
  "filenames": [
    "a.txt",
    "b.txt"
  ]
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
      "a.txt",
      "b.txt"
    ]
  }
}
```

## invalid_filenames_type

- status: PASS
- method: POST
- path: /api/kb/{id}/delete_files

### request
```json
{
  "id": "kb_1",
  "filenames": "a.txt"
}
```

### response
```json
{
  "code": 1,
  "msg": "删除知识库文档失败",
  "data": {
    "reason": "filenames 必须是列表"
  }
}
```

## kb_not_found

- status: PASS
- method: POST
- path: /api/kb/{id}/delete_files

### request
```json
{
  "id": "kb_missing",
  "filenames": [
    "a.txt"
  ]
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
