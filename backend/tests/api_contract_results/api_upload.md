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
        "file_id": "file_1775712463364_0",
        "filename": "note_2.txt",
        "url": "http://127.0.0.1:9000/xintuoyin-data/chat/2026-04-09/conv-upload/0/note_2.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260409%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260409T052743Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=50652497bebe91b3e90b52bb0cb6beef45ac351a68e786db2d0e5cb4771ac979",
        "relative_path": "chat/2026-04-09/conv-upload/0/note_2.txt",
        "object_name": "chat/2026-04-09/conv-upload/0/note_2.txt"
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
        "file_id": "file_1775712463420_0",
        "filename": "note_2.txt",
        "url": "http://127.0.0.1:9000/xintuoyin-data/chat/2026-04-09/conv-upload-gap/99/note_2.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260409%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260409T052743Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=a7e70188c92e48d50788e2ec8f4c760e09abd6dbb6b76da1b4c91d3523f32e66",
        "relative_path": "chat/2026-04-09/conv-upload-gap/99/note_2.txt",
        "object_name": "chat/2026-04-09/conv-upload-gap/99/note_2.txt"
      }
    ]
  }
}
```
