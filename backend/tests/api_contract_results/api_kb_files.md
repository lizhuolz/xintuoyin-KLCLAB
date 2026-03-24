# api_kb_files

## success

- status: PASS
- method: GET
- path: /api/kb/{id}/files

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
  "msg": "获取知识库文件成功",
  "data": {
    "id": "kb_1",
    "url": "企业知识库/文件库",
    "files": [
      {
        "file_id": "kb_1:doc.txt",
        "name": "doc.txt",
        "url": "企业知识库/文件库/doc.txt",
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
- method: GET
- path: /api/kb/{id}/files

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
  "msg": "获取知识库文件失败",
  "data": {
    "id": "kb_missing"
  }
}
```
