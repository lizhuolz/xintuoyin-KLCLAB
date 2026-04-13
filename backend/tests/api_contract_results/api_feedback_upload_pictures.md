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
        "file_id": "pic_1775712267581_0",
        "filename": "a.png",
        "object_name": "feedback/2026-04-09/fb_conv-pic_0/a.png",
        "url": "http://127.0.0.1:9000/xintuoyin-data/feedback/2026-04-09/fb_conv-pic_0/a.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260409%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260409T052427Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=b95333c07c860570b992c9b0d7073a622ef6263e92feede8a034b622197e0def"
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
        "file_id": "pic_1775712267598_0",
        "filename": "a.png",
        "object_name": "feedback/2026-04-09/fb_conv-pic-dup_0/a.png",
        "url": "http://127.0.0.1:9000/xintuoyin-data/feedback/2026-04-09/fb_conv-pic-dup_0/a.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260409%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260409T052427Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=ab9a901a883e28a3ac775472390d3b8776d30b4dacb8259e6c566f9fe3fe2209"
      },
      {
        "file_id": "pic_1775712267606_1",
        "filename": "a_1.png",
        "object_name": "feedback/2026-04-09/fb_conv-pic-dup_0/a_1.png",
        "url": "http://127.0.0.1:9000/xintuoyin-data/feedback/2026-04-09/fb_conv-pic-dup_0/a_1.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260409%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260409T052427Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=601992c32d7aa40d9d972258bfd0ee7dc342f7f5e7dba94fc18dd1a7a7871837"
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
