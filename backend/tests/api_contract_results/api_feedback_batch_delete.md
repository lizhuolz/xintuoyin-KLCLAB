# api_feedback_batch_delete

## success

- status: PASS
- method: POST
- path: /api/feedback/batch_delete

### request
```json
{
  "ids": [
    "fb_conv-feedback-batch_0"
  ]
}
```

### response
```json
{
  "code": 0,
  "msg": "批量删除反馈成功",
  "data": {
    "deleted_ids": [
      "fb_conv-feedback-batch_0"
    ]
  }
}
```

## invalid_ids_type

- status: PASS
- method: POST
- path: /api/feedback/batch_delete

### request
```json
{
  "ids": "fb_missing_0"
}
```

### response
```json
{
  "code": 1,
  "msg": "批量删除反馈失败",
  "data": {
    "reason": "ids 必须是列表"
  }
}
```
