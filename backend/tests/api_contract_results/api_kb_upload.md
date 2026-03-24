# api_kb_upload

## success

- status: PASS
- method: POST
- path: /api/kb/{id}/upload

### request
```json
{
  "id": "kb_1",
  "files": [
    "doc.txt"
  ]
}
```

### response
```json
{
  "code": 0,
  "msg": "上传知识库文档成功",
  "data": {
    "id": "kb_1",
    "files": [
      {
        "file_id": "kb_1:doc.txt",
        "name": "doc.txt",
        "url": "企业知识库/上传库/doc.txt",
        "size": 7,
        "uploaded_at": "3",
        "uploadedAt": "2026/03/24 00:00:02"
      }
    ]
  }
}
```

## not_found

- status: PASS
- method: POST
- path: /api/kb/{id}/upload

### request
```json
{
  "id": "kb_missing",
  "files": [
    "doc.txt"
  ]
}
```

### response
```json
{
  "code": 1,
  "msg": "上传知识库文档失败",
  "data": {
    "id": "kb_missing"
  }
}
```
