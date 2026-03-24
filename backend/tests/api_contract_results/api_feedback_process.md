# api_feedback_process

## success

- status: PASS
- method: POST
- path: /api/feedback/process

### request
```json
{
  "id": "fb_conv-feedback-process_0",
  "processor": "tester",
  "is_collect": true
}
```

### response
```json
{
  "code": 0,
  "msg": "处理反馈成功",
  "data": {
    "id": "fb_conv-feedback-process_0",
    "conversation_id": "conv-feedback-process",
    "message_index": 0,
    "type": "like",
    "state": "like",
    "time": "1774367355133",
    "update_time": "1774367355133",
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
    "process_status": "已处理",
    "processor": "tester",
    "processed_at": "1774367355137",
    "processedAt": "2026/03/24 23:49:15",
    "process_result": "已收录"
  }
}
```

## missing_id

- status: PASS
- method: POST
- path: /api/feedback/process

### request
```json
{
  "processor": "tester"
}
```

### response
```json
{
  "code": 1,
  "msg": "处理反馈失败",
  "data": {
    "reason": "id 不能为空"
  }
}
```

## not_found

- status: PASS
- method: POST
- path: /api/feedback/process

### request
```json
{
  "id": "fb_missing_0",
  "processor": "tester"
}
```

### response
```json
{
  "code": 1,
  "msg": "处理反馈失败",
  "data": {
    "id": "fb_missing_0"
  }
}
```
