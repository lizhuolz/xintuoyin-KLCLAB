# api_feedback_list

## success

- status: PASS
- method: GET
- path: /api/feedback/list

### request
```json
{
  "type": "like"
}
```

### response
```json
{
  "code": 0,
  "msg": "获取反馈列表成功",
  "data": {
    "list": [
      {
        "id": "fb_conv-feedback-list_0",
        "conversation_id": "conv-feedback-list",
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
          "record_id": "conv-feedback-list",
          "ip_address": "183.230.12.156"
        },
        "user_id": "UID_20250001",
        "record_id": "conv-feedback-list",
        "time": "1775561469218",
        "update_time": "1775561469218",
        "processed_at": "",
        "createdAt": "2026/04/07 19:31:09",
        "updatedAt": "2026/04/07 19:31:09",
        "processedAt": "",
        "times": {
          "submit_time": "1775561469218",
          "update_time": "1775561469218",
          "processed_at": "",
          "createdAt": "2026/04/07 19:31:09",
          "updatedAt": "2026/04/07 19:31:09",
          "processedAt": ""
        },
        "question": "反馈测试",
        "answer": "模拟回答: 【当前用户问题】\n反馈测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
        "process_status": "未处理",
        "process_result": ""
      }
    ],
    "total": 1,
    "page": 1,
    "size": 10,
    "total_pages": 1
  }
}
```

## filter_no_match

- status: PASS
- method: GET
- path: /api/feedback/list

### request
```json
{
  "enterprise": "不存在企业"
}
```

### response
```json
{
  "code": 0,
  "msg": "获取反馈列表成功",
  "data": {
    "list": [],
    "total": 0,
    "page": 1,
    "size": 10,
    "total_pages": 0
  }
}
```

## invalid_time

- status: PASS
- method: GET
- path: /api/feedback/list

### request
```json
{
  "start_time": "bad-ts"
}
```

### response
```json
{
  "code": 1,
  "msg": "获取反馈列表失败",
  "data": {
    "reason": "start_time 必须是毫秒时间戳字符串或整数"
  }
}
```

## pagination_with_feedback_type_and_user

- status: PASS
- method: GET
- path: /api/feedback/list
- notes: 反馈列表应返回嵌套 user、反馈类型元数据、时间说明字段和分页信息。

### request
```json
{
  "feedback_type": "点赞",
  "page": 1,
  "size": 1
}
```

### response
```json
{
  "code": 0,
  "msg": "获取反馈列表成功",
  "data": {
    "list": [
      {
        "id": "fb_conv-feedback-page_0",
        "conversation_id": "conv-feedback-page",
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
          "record_id": "conv-feedback-page",
          "ip_address": "183.230.12.156"
        },
        "user_id": "UID_20250001",
        "record_id": "conv-feedback-page",
        "time": "1775561475684",
        "update_time": "1775561475684",
        "processed_at": "",
        "createdAt": "2026/04/07 19:31:15",
        "updatedAt": "2026/04/07 19:31:15",
        "processedAt": "",
        "times": {
          "submit_time": "1775561475684",
          "update_time": "1775561475684",
          "processed_at": "",
          "createdAt": "2026/04/07 19:31:15",
          "updatedAt": "2026/04/07 19:31:15",
          "processedAt": ""
        },
        "question": "反馈测试",
        "answer": "模拟回答: 【当前用户问题】\n反馈测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
        "process_status": "未处理",
        "process_result": ""
      }
    ],
    "total": 1,
    "page": 1,
    "size": 1,
    "total_pages": 1
  }
}
```

## report_filter_success

- status: PASS
- method: GET
- path: /api/feedback/list
- notes: 反馈类型筛选应支持 举报，并命中反馈类型标签。

### request
```json
{
  "feedback_type": "举报"
}
```

### response
```json
{
  "code": 0,
  "msg": "获取反馈列表成功",
  "data": {
    "list": [
      {
        "id": "fb_conv-feedback-report_0",
        "conversation_id": "conv-feedback-report",
        "message_index": 0,
        "type": "dislike",
        "state": "dislike",
        "feedback_type": {
          "primary": "点踩",
          "scene": "针对回答效果",
          "labels": [
            "点踩",
            "针对回答效果",
            "举报"
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
          "举报内容违规"
        ],
        "comment": "需要举报处理",
        "pictures": [],
        "pictures_list": [],
        "uploaded_files": [],
        "user": {
          "name": "王颖奇",
          "enterprise": "图湃（北京）医疗科技",
          "phone": "15323720032",
          "user_id": "UID_20250001",
          "record_id": "conv-feedback-report",
          "ip_address": "183.230.12.156"
        },
        "user_id": "UID_20250001",
        "record_id": "conv-feedback-report",
        "time": "1775561478907",
        "update_time": "1775561478907",
        "processed_at": "",
        "createdAt": "2026/04/07 19:31:18",
        "updatedAt": "2026/04/07 19:31:18",
        "processedAt": "",
        "times": {
          "submit_time": "1775561478907",
          "update_time": "1775561478907",
          "processed_at": "",
          "createdAt": "2026/04/07 19:31:18",
          "updatedAt": "2026/04/07 19:31:18",
          "processedAt": ""
        },
        "question": "举报测试",
        "answer": "模拟回答: 【当前用户问题】\n举报测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
        "process_status": "未处理",
        "process_result": ""
      }
    ],
    "total": 1,
    "page": 1,
    "size": 10,
    "total_pages": 1
  }
}
```
