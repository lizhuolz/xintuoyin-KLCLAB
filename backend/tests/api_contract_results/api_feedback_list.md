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
        "id": "fb_conv-feedback-list_2",
        "conversation_id": "conv-feedback-list",
        "message_index": 2,
        "type": "like",
        "state": "like",
        "feedback_scene": "针对回答效果",
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
        "time": "1775711905021",
        "update_time": "1775711905021",
        "processed_at": "",
        "processor": "",
        "createdAt": "2026/04/09 13:18:25",
        "updatedAt": "2026/04/09 13:18:25",
        "processedAt": "",
        "times": {
          "submit_time": "1775711905021",
          "update_time": "1775711905021",
          "processed_at": "",
          "createdAt": "2026/04/09 13:18:25",
          "updatedAt": "2026/04/09 13:18:25",
          "processedAt": ""
        },
        "question": "反馈测试",
        "answer": "模拟回答: 【历史对话上下文】\n第1轮用户：反馈测试\n第1轮助手：模拟回答: 【当前用户问题】\n反馈测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。\n第2轮用户：反馈测试\n第2轮助手：模拟回答: 【历史对话上下文】\n第1轮用户：反馈测试\n第1轮助手：模拟回答: 【当前用户问题】\n反馈测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。\n\n【当前用户问题】\n反馈测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。\n\n【当前用户问题】\n反馈测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
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

## mode_filters

- status: PASS
- method: GET
- path: /api/feedback/list
- notes: `type=dislike` 对应待优化回答，`type=like` 对应良好回答，不传则是反馈列表全部。

### request
```json
{
  "type": [
    "like",
    "dislike",
    null
  ]
}
```

### response
```json
{
  "like_total": 1,
  "like_types": [
    "like"
  ],
  "dislike_total": 1,
  "dislike_types": [
    "dislike"
  ],
  "all_total": 2,
  "all_types": [
    "dislike",
    "like"
  ]
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
        "id": "fb_conv-feedback-page_2",
        "conversation_id": "conv-feedback-page",
        "message_index": 2,
        "type": "like",
        "state": "like",
        "feedback_scene": "针对回答效果",
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
        "time": "1775712184002",
        "update_time": "1775712184002",
        "processed_at": "",
        "processor": "",
        "createdAt": "2026/04/09 13:23:04",
        "updatedAt": "2026/04/09 13:23:04",
        "processedAt": "",
        "times": {
          "submit_time": "1775712184002",
          "update_time": "1775712184002",
          "processed_at": "",
          "createdAt": "2026/04/09 13:23:04",
          "updatedAt": "2026/04/09 13:23:04",
          "processedAt": ""
        },
        "question": "反馈测试",
        "answer": "模拟回答: 【历史对话上下文】\n第1轮用户：反馈测试\n第1轮助手：模拟回答: 【当前用户问题】\n反馈测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。\n第2轮用户：反馈测试\n第2轮助手：模拟回答: 【历史对话上下文】\n第1轮用户：反馈测试\n第1轮助手：模拟回答: 【当前用户问题】\n反馈测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。\n\n【当前用户问题】\n反馈测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。\n\n【当前用户问题】\n反馈测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
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
        "id": "fb_conv-feedback-report_2",
        "conversation_id": "conv-feedback-report",
        "message_index": 2,
        "type": "dislike",
        "state": "dislike",
        "feedback_scene": "针对回答效果",
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
        "time": "1775712197849",
        "update_time": "1775712197849",
        "processed_at": "",
        "processor": "",
        "createdAt": "2026/04/09 13:23:17",
        "updatedAt": "2026/04/09 13:23:17",
        "processedAt": "",
        "times": {
          "submit_time": "1775712197849",
          "update_time": "1775712197849",
          "processed_at": "",
          "createdAt": "2026/04/09 13:23:17",
          "updatedAt": "2026/04/09 13:23:17",
          "processedAt": ""
        },
        "question": "举报测试",
        "answer": "模拟回答: 【历史对话上下文】\n第1轮用户：举报测试\n第1轮助手：模拟回答: 【当前用户问题】\n举报测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。\n第2轮用户：举报测试\n第2轮助手：模拟回答: 【历史对话上下文】\n第1轮用户：举报测试\n第1轮助手：模拟回答: 【当前用户问题】\n举报测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。\n\n【当前用户问题】\n举报测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。\n\n【当前用户问题】\n举报测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
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
