# api_history_batch_delete

## success

- status: PASS
- method: POST
- path: /api/history/batch_delete

### request
```json
{
  "ids": [
    "conv-b1",
    "conv-b2"
  ]
}
```

### response
```json
{
  "code": 0,
  "msg": "批量删除历史对话成功",
  "data": {
    "deleted_ids": [
      "conv-b1",
      "conv-b2"
    ]
  }
}
```

## invalid_ids_type

- status: PASS
- method: POST
- path: /api/history/batch_delete

### request
```json
{
  "ids": "conv-bad"
}
```

### response
```json
{
  "code": 1,
  "msg": "批量删除历史对话失败",
  "data": {
    "reason": "ids 必须是列表"
  }
}
```
