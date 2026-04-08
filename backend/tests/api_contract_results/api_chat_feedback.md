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
    "feedback_type": {
      "primary": "点踩",
      "scene": "针对回答效果",
      "labels": [
        "点踩",
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
    "reasons": [
      "答案不完整"
    ],
    "comment": "需要更具体",
    "pictures": [],
    "pictures_list": [],
    "uploaded_files": [],
    "user": {
      "name": "王颖奇",
      "enterprise": "图湃（北京）医疗科技",
      "phone": "15323720032",
      "user_id": "UID_20250001",
      "record_id": "conv-feedback-ok",
      "ip_address": "183.230.12.156"
    },
    "user_id": "UID_20250001",
    "record_id": "conv-feedback-ok",
    "time": "1775561415624",
    "update_time": "1775561415624",
    "processed_at": "",
    "createdAt": "2026/04/07 19:30:15",
    "updatedAt": "2026/04/07 19:30:15",
    "processedAt": "",
    "times": {
      "submit_time": "1775561415624",
      "update_time": "1775561415624",
      "processed_at": "",
      "createdAt": "2026/04/07 19:30:15",
      "updatedAt": "2026/04/07 19:30:15",
      "processedAt": ""
    },
    "question": "有效点踩",
    "answer": "模拟回答: 【当前用户问题】\n有效点踩\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
    "process_status": "未处理",
    "process_result": ""
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
    "uploaded_files": [],
    "user": {
      "name": "王颖奇",
      "enterprise": "图湃（北京）医疗科技",
      "phone": "15323720032",
      "user_id": "UID_20250001",
      "record_id": "conv-feedback",
      "ip_address": "183.230.12.156"
    },
    "user_id": "UID_20250001",
    "record_id": "conv-feedback",
    "time": "1775561422032",
    "update_time": "1775561422032",
    "processed_at": "",
    "createdAt": "2026/04/07 19:30:22",
    "updatedAt": "2026/04/07 19:30:22",
    "processedAt": "",
    "times": {
      "submit_time": "1775561422032",
      "update_time": "1775561422032",
      "processed_at": "",
      "createdAt": "2026/04/07 19:30:22",
      "updatedAt": "2026/04/07 19:30:22",
      "processedAt": ""
    },
    "question": "点赞测试",
    "answer": "模拟回答: 【当前用户问题】\n点赞测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
    "process_status": "未处理",
    "process_result": ""
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
    "uploaded_files": [],
    "user": {
      "name": "王颖奇",
      "enterprise": "图湃（北京）医疗科技",
      "phone": "15323720032",
      "user_id": "UID_20250001",
      "record_id": "conv-feedback-toggle",
      "ip_address": "183.230.12.156"
    },
    "user_id": "UID_20250001",
    "record_id": "conv-feedback-toggle",
    "time": "1775561428413",
    "update_time": "1775561428446",
    "processed_at": "",
    "createdAt": "2026/04/07 19:30:28",
    "updatedAt": "2026/04/07 19:30:28",
    "processedAt": "",
    "times": {
      "submit_time": "1775561428413",
      "update_time": "1775561428446",
      "processed_at": "",
      "createdAt": "2026/04/07 19:30:28",
      "updatedAt": "2026/04/07 19:30:28",
      "processedAt": ""
    },
    "question": "重复点赞",
    "answer": "模拟回答: 【当前用户问题】\n重复点赞\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
    "process_status": "未处理",
    "process_result": ""
  }
}
```
