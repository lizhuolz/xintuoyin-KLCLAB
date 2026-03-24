# api_chat_delete

## success

- status: PASS
- method: DELETE
- path: /api/chat/{conversation_id}

### request
```json
{
  "conversation_id": "conv-delete"
}
```

### response
```json
{
  "code": 0,
  "msg": "删除历史对话成功",
  "data": {
    "conversation_id": "conv-delete"
  }
}
```

## not_found

- status: PASS
- method: DELETE
- path: /api/chat/{conversation_id}

### request
```json
{
  "conversation_id": "missing-delete"
}
```

### response
```json
{
  "code": 1,
  "msg": "删除历史对话失败",
  "data": {
    "conversation_id": "missing-delete"
  }
}
```
