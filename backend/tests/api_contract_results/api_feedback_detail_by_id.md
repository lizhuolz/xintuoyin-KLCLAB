# api_feedback_detail_by_id

## success

- status: PASS
- method: GET
- path: /api/feedback/{feedback_id}

### request
```json
{
  "feedback_id": "fb_conv-feedback-detail_0"
}
```

### response
```json
{
  "code": 0,
  "msg": "获取反馈详情成功",
  "data": {
    "id": "fb_conv-feedback-detail_0",
    "conversation_id": "conv-feedback-detail",
    "message_index": 0,
    "type": "like",
    "state": "like",
    "time": "1774367355072",
    "update_time": "1774367355072",
    "createdAt": "2026/03/24 23:49:15",
    "updatedAt": "2026/03/24 23:49:15",
    "reasons": [],
    "comment": "",
    "pictures": [],
    "name": "王颖奇",
    "enterprise": "图湃（北京）医疗科技",
    "phone": "15323720032",
    "question": "反馈测试",
    "answer": "模拟回答: 【当前用户问题】\n反馈测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n3. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n4. 不要忽略用户本轮输入的文字问题。",
    "process_status": "未处理"
  }
}
```

## not_found

- status: PASS
- method: GET
- path: /api/feedback/{feedback_id}

### request
```json
{
  "feedback_id": "fb_missing_0"
}
```

### response
```json
{
  "code": 1,
  "msg": "获取反馈详情失败",
  "data": {
    "id": "fb_missing_0"
  }
}
```
