# api_chat_title

## success

- status: PASS
- method: GET
- path: /api/chat/{conversation_id}/title

### request
```json
{
  "conversation_id": "conv-title"
}
```

### response
```json
{
  "code": 0,
  "msg": "获取标题成功",
  "data": {
    "conversation_id": "conv-title",
    "title": "标题测试",
    "question": "标题测试"
  }
}
```

## not_found

- status: PASS
- method: GET
- path: /api/chat/{conversation_id}/title

### request
```json
{
  "conversation_id": "missing-title"
}
```

### response
```json
{
  "code": 1,
  "msg": "获取标题失败",
  "data": {
    "conversation_id": "missing-title"
  }
}
```
