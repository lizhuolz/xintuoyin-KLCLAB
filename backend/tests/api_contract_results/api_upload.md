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
        "file_id": "file_1775048848716_0",
        "filename": "note_5.txt",
        "url": "http://127.0.0.1:9000/xintuoyin-data/chat/2026-04-01/conv-upload/0/note_5.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260401%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260401T130728Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=0cec2ef4f54d1a71689f0a1c06468119e28f0ec49d57e580016963996cae5e1e",
        "relative_path": "chat/2026-04-01/conv-upload/0/note_5.txt",
        "object_name": "chat/2026-04-01/conv-upload/0/note_5.txt"
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
        "file_id": "file_1775048848737_0",
        "filename": "note_3.txt",
        "url": "http://127.0.0.1:9000/xintuoyin-data/chat/2026-04-01/conv-upload-gap/99/note_3.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260401%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260401T130728Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=5c45c74511d4d94588730e9448a4c0ff12010eb2d8dc6c66d408ecb6f6fda788",
        "relative_path": "chat/2026-04-01/conv-upload-gap/99/note_3.txt",
        "object_name": "chat/2026-04-01/conv-upload-gap/99/note_3.txt"
      }
    ]
  }
}
```
