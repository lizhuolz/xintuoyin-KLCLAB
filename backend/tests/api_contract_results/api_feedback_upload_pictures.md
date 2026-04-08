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
        "file_id": "pic_1775561482222_0",
        "filename": "a.png",
        "object_name": "feedback/2026-04-07/fb_conv-pic_0/a.png",
        "url": "http://127.0.0.1:9000/xintuoyin-data/feedback/2026-04-07/fb_conv-pic_0/a.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260407%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260407T113122Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=b3e9f58471a0c9ca3b80d703516ee6c2a36b3a0e63d63a7bcfaf95263c62178b"
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
        "file_id": "pic_1775561482239_0",
        "filename": "a.png",
        "object_name": "feedback/2026-04-07/fb_conv-pic-dup_0/a.png",
        "url": "http://127.0.0.1:9000/xintuoyin-data/feedback/2026-04-07/fb_conv-pic-dup_0/a.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260407%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260407T113122Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=f0e1b9d7e32043e8092d8e79353c742ed99e7148d0d0d62e45636ae85ec22b52"
      },
      {
        "file_id": "pic_1775561482248_1",
        "filename": "a_1.png",
        "object_name": "feedback/2026-04-07/fb_conv-pic-dup_0/a_1.png",
        "url": "http://127.0.0.1:9000/xintuoyin-data/feedback/2026-04-07/fb_conv-pic-dup_0/a_1.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260407%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260407T113122Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=f2598f35facc6901e12362911a6ba81f46303b6538c8b17fcb0c243cac1787cc"
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
