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
    "feedback_type": {
      "primary": "点赞",
      "scene": "针对回答效果",
      "labels": [
        "点赞",
        "针对回答效果"
      ],
      "options": [
        "全部",
        "针对问题",
        "针对回答效果",
        "举报",
        "点赞",
        "点踩"
      ]
    },
    "reasons": [],
    "comment": "",
    "pictures": [],
    "pictures_list": [],
    "user": {
      "name": "王颖奇",
      "enterprise": "图湃（北京）医疗科技",
      "phone": "15323720032",
      "record_id": "UID_20250001",
      "ip_address": "183.230.12.156"
    },
    "time": "1775048848414",
    "update_time": "1775048848414",
    "processed_at": "1775048848419",
    "createdAt": "2026/04/01 21:07:28",
    "updatedAt": "2026/04/01 21:07:28",
    "processedAt": "2026/04/01 21:07:28",
    "times": {
      "submit_time": "1775048848414",
      "update_time": "1775048848414",
      "processed_at": "1775048848419",
      "createdAt": "2026/04/01 21:07:28",
      "updatedAt": "2026/04/01 21:07:28",
      "processedAt": "2026/04/01 21:07:28"
    },
    "question": "反馈测试",
    "answer": "模拟回答: 【当前用户问题】\n反馈测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
    "process_status": "已处理",
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
