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
        "file_id": "pic_1774367355152_0",
        "filename": "a.png",
        "url": "/api/static/feedbacks/2026-03-24/fb_conv-pic_0/a.png"
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
        "file_id": "pic_1774367355158_0",
        "filename": "a.png",
        "url": "/api/static/feedbacks/2026-03-24/fb_conv-pic-dup_0/a.png"
      },
      {
        "file_id": "pic_1774367355158_1",
        "filename": "a_1.png",
        "url": "/api/static/feedbacks/2026-03-24/fb_conv-pic-dup_0/a_1.png"
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
