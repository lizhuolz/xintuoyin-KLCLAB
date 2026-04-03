# api_feedback_detail_by_date

## success

- status: PASS
- method: GET
- path: /api/feedback/detail/{date}/{id}

### request
```json
{
  "date": "2026-04-01",
  "id": "fb_conv-feedback-date_0"
}
```

### response
```json
{
  "code": 0,
  "msg": "获取反馈详情成功",
  "data": {
    "id": "fb_conv-feedback-date_0",
    "conversation_id": "conv-feedback-date",
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
    "time": "1775048848314",
    "update_time": "1775048848314",
    "processed_at": "",
    "createdAt": "2026/04/01 21:07:28",
    "updatedAt": "2026/04/01 21:07:28",
    "processedAt": "",
    "times": {
      "submit_time": "1775048848314",
      "update_time": "1775048848314",
      "processed_at": "",
      "createdAt": "2026/04/01 21:07:28",
      "updatedAt": "2026/04/01 21:07:28",
      "processedAt": ""
    },
    "question": "反馈测试",
    "answer": "模拟回答: 【当前用户问题】\n反馈测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
    "process_status": "未处理",
    "process_result": ""
  }
}
```

## not_found

- status: PASS
- method: GET
- path: /api/feedback/detail/{date}/{id}

### request
```json
{
  "date": "2099-01-01",
  "id": "fb_missing_0"
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
