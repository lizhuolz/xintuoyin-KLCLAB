# api_feedback_upload_pictures

## success

- status: PASS
- method: POST
- path: /api/feedback/upload_pictures

### request
```json
{
  "conversation_id": "conv-pic",
  "message_index": 0,
  "pictures": [
    "a.png"
  ]
}
```

### response
```json
{
  "code": 0,
  "msg": "上传图片成功",
  "data": {
    "conversation_id": "conv-pic",
    "message_index": 0,
    "pictures": [
      {
        "file_id": "pic_1775048848443_0",
        "filename": "a.png",
        "object_name": "feedback/2026-04-01/fb_conv-pic_0/a.png",
        "url": "http://127.0.0.1:9000/xintuoyin-data/feedback/2026-04-01/fb_conv-pic_0/a.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260401%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260401T130728Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=008767fd4c8bdcc26df1a252b7803dc3e97ccdf19b4e9d35c8a139ab5a98aa94"
      }
    ]
  }
}
```

## duplicate_picture_names

- status: PASS
- method: POST
- path: /api/feedback/upload_pictures

### request
```json
{
  "conversation_id": "conv-pic-dup",
  "message_index": 0,
  "pictures": [
    "a.png",
    "a.png"
  ]
}
```

### response
```json
{
  "code": 0,
  "msg": "上传图片成功",
  "data": {
    "conversation_id": "conv-pic-dup",
    "message_index": 0,
    "pictures": [
      {
        "file_id": "pic_1775048848458_0",
        "filename": "a.png",
        "object_name": "feedback/2026-04-01/fb_conv-pic-dup_0/a.png",
        "url": "http://127.0.0.1:9000/xintuoyin-data/feedback/2026-04-01/fb_conv-pic-dup_0/a.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260401%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260401T130728Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=092ce00e61a02934a9ca3138a819ffd6682bf6d3d46af7b7030afb8214366f8f"
      },
      {
        "file_id": "pic_1775048848466_1",
        "filename": "a_1.png",
        "object_name": "feedback/2026-04-01/fb_conv-pic-dup_0/a_1.png",
        "url": "http://127.0.0.1:9000/xintuoyin-data/feedback/2026-04-01/fb_conv-pic-dup_0/a_1.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260401%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260401T130728Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=96a37edf91c11ce31ba8f4933264ec79fdd31ca2f70806beb3ed857e05ef3320"
      }
    ]
  }
}
```

## negative_message_index

- status: PASS
- method: POST
- path: /api/feedback/upload_pictures

### request
```json
{
  "conversation_id": "conv-pic-neg",
  "message_index": -1
}
```

### response
```json
{
  "code": 1,
  "msg": "上传图片失败",
  "data": {
    "reason": "message_index 不能为负数"
  }
}
```
