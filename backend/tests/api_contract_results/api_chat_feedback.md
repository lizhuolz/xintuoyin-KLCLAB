# api_chat_feedback

## dislike_validation

- status: PASS
- method: POST
- path: /api/chat/feedback

### request
```json
{
  "conversation_id": "conv-feedback-dislike",
  "message_index": 0,
  "type": "dislike"
}
```

### response
```json
{
  "code": 1,
  "msg": "提交反馈失败",
  "data": {
    "reason": "点踩反馈必须填写原因、描述或上传截图"
  }
}
```

## dislike_with_reason

- status: PASS
- method: POST
- path: /api/chat/feedback

### request
```json
{
  "conversation_id": "conv-feedback-ok",
  "message_index": 0,
  "type": "dislike",
  "reasons": [
    "答案不完整"
  ],
  "comment": "需要更具体"
}
```

### response
```json
{
  "code": 0,
  "msg": "提交反馈成功",
  "data": {
    "id": "fb_conv-feedback-ok_0",
    "conversation_id": "conv-feedback-ok",
    "message_index": 0,
    "type": "dislike",
    "state": "dislike",
    "reasons": [
      "答案不完整"
    ],
    "comment": "需要更具体",
    "pictures": [],
    "name": "王颖奇",
    "enterprise": "图湃（北京）医疗科技",
    "phone": "15323720032",
    "time": "1774367354900",
    "update_time": "1774367354900",
    "createdAt": "2026/03/24 23:49:14",
    "updatedAt": "2026/03/24 23:49:14",
    "process_status": "未处理"
  }
}
```

## invalid_type

- status: PASS
- method: POST
- path: /api/chat/feedback

### request
```json
{
  "conversation_id": "conv-feedback-invalid",
  "message_index": 0,
  "type": "bad"
}
```

### response
```json
{
  "code": 1,
  "msg": "提交反馈失败",
  "data": {
    "reason": "type 仅支持 like 或 dislike"
  }
}
```

## like_success

- status: PASS
- method: POST
- path: /api/chat/feedback

### request
```json
{
  "conversation_id": "conv-feedback",
  "message_index": 0,
  "type": "like"
}
```

### response
```json
{
  "code": 0,
  "msg": "提交反馈成功",
  "data": {
    "id": "fb_conv-feedback_0",
    "conversation_id": "conv-feedback",
    "message_index": 0,
    "type": "like",
    "state": "like",
    "reasons": [],
    "comment": "",
    "pictures": [],
    "name": "王颖奇",
    "enterprise": "图湃（北京）医疗科技",
    "phone": "15323720032",
    "time": "1774367354917",
    "update_time": "1774367354917",
    "createdAt": "2026/03/24 23:49:14",
    "updatedAt": "2026/03/24 23:49:14",
    "process_status": "未处理"
  }
}
```

## negative_message_index

- status: PASS
- method: POST
- path: /api/chat/feedback

### request
```json
{
  "conversation_id": "conv-feedback-neg",
  "message_index": -1,
  "type": "like"
}
```

### response
```json
{
  "code": 1,
  "msg": "提交反馈失败",
  "data": {
    "reason": "message_index 不能为负数"
  }
}
```

## conversation_not_found

- status: PASS
- method: POST
- path: /api/chat/feedback

### request
```json
{
  "conversation_id": "missing-feedback",
  "message_index": 0,
  "type": "like"
}
```

### response
```json
{
  "code": 1,
  "msg": "提交反馈失败",
  "data": {
    "conversation_id": "missing-feedback",
    "message_index": 0
  }
}
```

## toggle_like_to_none

- status: PASS
- method: POST
- path: /api/chat/feedback
- notes: 重复提交同一点赞类型时，反馈状态应切换为 None。

### request
```json
{
  "conversation_id": "conv-feedback-toggle",
  "message_index": 0,
  "type": "like"
}
```

### response
```json
{
  "code": 0,
  "msg": "提交反馈成功",
  "data": {
    "id": "fb_conv-feedback-toggle_0",
    "conversation_id": "conv-feedback-toggle",
    "message_index": 0,
    "type": "like",
    "state": null,
    "reasons": [],
    "comment": "",
    "pictures": [],
    "name": "王颖奇",
    "enterprise": "图湃（北京）医疗科技",
    "phone": "15323720032",
    "time": "1774367354940",
    "update_time": "1774367354945",
    "createdAt": "2026/03/24 23:49:14",
    "updatedAt": "2026/03/24 23:49:14",
    "process_status": "未处理"
  }
}
```
