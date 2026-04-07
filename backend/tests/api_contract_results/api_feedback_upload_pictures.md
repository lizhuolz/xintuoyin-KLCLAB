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
        "file_id": "pic_1775216098647_0",
        "filename": "a.png",
        "object_name": "feedback/2026-04-03/fb_conv-pic_0/a.png",
        "url": "http://127.0.0.1:9000/xintuoyin-data/feedback/2026-04-03/fb_conv-pic_0/a.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260403%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260403T113458Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=fa57f402e9cdd37a9544efa36d9e3dd43b5da5a13908db8d16b47cfcd4ea92bd"
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
        "file_id": "pic_1775216098663_0",
        "filename": "a.png",
        "object_name": "feedback/2026-04-03/fb_conv-pic-dup_0/a.png",
        "url": "http://127.0.0.1:9000/xintuoyin-data/feedback/2026-04-03/fb_conv-pic-dup_0/a.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260403%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260403T113458Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=0ded52a299efac6c6ed35f83c6e382a581d3ef2d1d39d6ead33750f2e0d02943"
      },
      {
        "file_id": "pic_1775216098672_1",
        "filename": "a_1.png",
        "object_name": "feedback/2026-04-03/fb_conv-pic-dup_0/a_1.png",
        "url": "http://127.0.0.1:9000/xintuoyin-data/feedback/2026-04-03/fb_conv-pic-dup_0/a_1.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260403%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260403T113458Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=d6257e4b20b22bf0d3fff9186c6bfdedae0b274db4ef7e848806caf1e1e709d6"
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
