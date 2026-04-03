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

## filename_not_found

- status: PASS
- method: POST
- path: /api/kb/{id}/delete_file
- notes: 单文件删除在目标文件不存在时应返回 404，而不是返回空成功。

### request
```json
{
  "id": "kb_1",
  "filename": "missing.txt"
}
```

### response
```json
{
  "code": 1,
  "msg": "删除知识库文档失败",
  "data": {
    "id": "kb_1",
    "filename": "missing.txt"
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
