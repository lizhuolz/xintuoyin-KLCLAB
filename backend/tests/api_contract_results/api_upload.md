# api_upload

## success

- status: PASS
- method: POST
- path: /api/upload

### request
```json
{
  "conversation_id": "conv-upload",
  "message_index": 0,
  "files": [
    "note.txt"
  ]
}
```

### response
```json
{
  "code": 0,
  "msg": "上传文件成功",
  "data": {
    "conversation_id": "conv-upload",
    "message_index": 0,
    "files": [
      {
        "file_id": "file_1774367355343_0",
        "filename": "note.txt",
        "url": "/api/static/chat_uploads/2026-03-24/conv-upload/0/note.txt",
        "relative_path": "2026-03-24/conv-upload/0/note.txt"
      }
    ]
  }
}
```

## negative_message_index

- status: PASS
- method: POST
- path: /api/upload

### request
```json
{
  "conversation_id": "conv-upload",
  "message_index": -1
}
```

### response
```json
{
  "code": 1,
  "msg": "上传文件失败",
  "data": {
    "reason": "message_index 不能为负数"
  }
}
```

## out_of_range_message_index

- status: PASS
- method: POST
- path: /api/upload
- notes: 当前实现允许上传到尚未存在的消息索引，仅返回文件信息，不回填历史消息。

### request
```json
{
  "conversation_id": "conv-upload-gap",
  "message_index": 99,
  "files": [
    "note.txt"
  ]
}
```

### response
```json
{
  "code": 0,
  "msg": "上传文件成功",
  "data": {
    "conversation_id": "conv-upload-gap",
    "message_index": 99,
    "files": [
      {
        "file_id": "file_1774367355354_0",
        "filename": "note.txt",
        "url": "/api/static/chat_uploads/2026-03-24/conv-upload-gap/99/note.txt",
        "relative_path": "2026-03-24/conv-upload-gap/99/note.txt"
      }
    ]
  }
}
```
