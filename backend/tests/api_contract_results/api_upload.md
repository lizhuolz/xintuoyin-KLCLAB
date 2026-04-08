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
        "file_id": "file_1775561505358_0",
        "filename": "note.txt",
        "url": "http://127.0.0.1:9000/xintuoyin-data/chat/2026-04-07/conv-upload/0/note.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260407%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260407T113145Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=1d454bf1e50ef6775f5dab86dee9625b336ef09a9a949673df52a159cbd09a67",
        "relative_path": "chat/2026-04-07/conv-upload/0/note.txt",
        "object_name": "chat/2026-04-07/conv-upload/0/note.txt"
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
        "file_id": "file_1775561505405_0",
        "filename": "note.txt",
        "url": "http://127.0.0.1:9000/xintuoyin-data/chat/2026-04-07/conv-upload-gap/99/note.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260407%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260407T113145Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=3261085f770c149d5a2ac3335f4fd0179e963a17cd0a7b634bd7109fc186a971",
        "relative_path": "chat/2026-04-07/conv-upload-gap/99/note.txt",
        "object_name": "chat/2026-04-07/conv-upload-gap/99/note.txt"
      }
    ]
  }
}
```
