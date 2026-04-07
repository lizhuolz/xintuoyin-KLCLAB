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
        "file_id": "file_1775216099025_0",
        "filename": "note_16.txt",
        "url": "http://127.0.0.1:9000/xintuoyin-data/chat/2026-04-03/conv-upload/0/note_16.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260403%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260403T113459Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=4e21326715dab7efc3f983f93a827634c2e07473455e520330b4d6b007895140",
        "relative_path": "chat/2026-04-03/conv-upload/0/note_16.txt",
        "object_name": "chat/2026-04-03/conv-upload/0/note_16.txt"
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
        "file_id": "file_1775216099053_0",
        "filename": "note_16.txt",
        "url": "http://127.0.0.1:9000/xintuoyin-data/chat/2026-04-03/conv-upload-gap/99/note_16.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260403%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260403T113459Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=70527cd357c3626099b058882a8bc013c21250e16fc4e670d318ec8ffcca16db",
        "relative_path": "chat/2026-04-03/conv-upload-gap/99/note_16.txt",
        "object_name": "chat/2026-04-03/conv-upload-gap/99/note_16.txt"
      }
    ]
  }
}
```
