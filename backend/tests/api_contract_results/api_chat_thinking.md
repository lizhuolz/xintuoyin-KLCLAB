# api_chat_thinking

## success

- status: PASS
- method: GET
- path: /api/chat/{conversation_id}/thinking

### request
```json
{
  "conversation_id": "conv-think",
  "message_index": 0
}
```

### response
```json
{
  "text": "在正式回答前，我先做了几步准备：\n1. 我调用了 mock_tool，输入大致是：{}。\n整理完这些信息后，我再把最终答案组织成对你更自然的回复。"
}
```

## default_stream_success

- status: PASS
- method: GET
- path: /api/chat/{conversation_id}/thinking
- notes: 不传 stream 时默认返回思考过程文本流。

### request
```json
{
  "conversation_id": "conv-think-stream",
  "message_index": 0
}
```

### response
```json
{
  "content_type": "text/plain; charset=utf-8",
  "text": "在正式回答前，我先做了几步准备：\n1. 我调用了 mock_tool，输入大致是：{}。\n整理完这些信息后，我再把最终答案组织成对你更自然的回复。"
}
```

## not_found

- status: PASS
- method: GET
- path: /api/chat/{conversation_id}/thinking

### request
```json
{
  "conversation_id": "missing-thinking",
  "message_index": 0
}
```

### response
```json
{
  "code": 1,
  "msg": "获取思考过程失败",
  "data": {
    "conversation_id": "missing-thinking"
  }
}
```
