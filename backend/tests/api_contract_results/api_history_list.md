# api_history_list

## success

- status: PASS
- method: GET
- path: /api/history/list

### request
```json
{
  "search": "历史测试"
}
```

### response
```json
{
  "code": 0,
  "msg": "获取历史记录成功",
  "data": {
    "list": [
      {
        "conversation_id": "conv-history",
        "title": "历史测试",
        "updated_at": "1775048848509",
        "updatedAt": "2026/04/01 21:07:28",
        "message_count": 1,
        "last_user_input": "历史测试",
        "last_answer": "模拟回答: 【当前用户问题】\n历史测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
        "user": {
          "name": "王颖奇",
          "phone": "15323720032",
          "categoryName": "图湃（北京）医疗科技",
          "record_id": "UID_20250001",
          "ip_address": "183.230.12.156"
        }
      }
    ],
    "total": 1,
    "page": 1,
    "size": 10,
    "total_pages": 1
  }
}
```

## case_insensitive_search

- status: PASS
- method: GET
- path: /api/history/list

### request
```json
{
  "search": "alpha"
}
```

### response
```json
{
  "code": 0,
  "msg": "获取历史记录成功",
  "data": {
    "list": [
      {
        "conversation_id": "conv-case",
        "title": "Alpha Beta",
        "updated_at": "1775048848520",
        "updatedAt": "2026/04/01 21:07:28",
        "message_count": 1,
        "last_user_input": "Alpha Beta",
        "last_answer": "模拟回答: 【当前用户问题】\nAlpha Beta\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
        "user": {
          "name": "王颖奇",
          "phone": "15323720032",
          "categoryName": "图湃（北京）医疗科技",
          "record_id": "UID_20250001",
          "ip_address": "183.230.12.156"
        }
      }
    ],
    "total": 1,
    "page": 1,
    "size": 10,
    "total_pages": 1
  }
}
```

## invalid_time

- status: PASS
- method: GET
- path: /api/history/list

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
  "msg": "获取历史记录失败",
  "data": {
    "reason": "start_time 必须是毫秒时间戳字符串或整数"
  }
}
```

## pagination_with_last_round_fields

- status: PASS
- method: GET
- path: /api/history/list
- notes: 历史列表应返回分页信息，以及最近一轮用户输入、回答和用户 RecordID/IP。

### request
```json
{
  "page": 1,
  "size": 1
}
```

### response
```json
{
  "code": 0,
  "msg": "获取历史记录成功",
  "data": {
    "list": [
      {
        "conversation_id": "conv-history-page-2",
        "title": "分页问题2",
        "updated_at": "1775048848536",
        "updatedAt": "2026/04/01 21:07:28",
        "message_count": 1,
        "last_user_input": "分页问题2",
        "last_answer": "模拟回答: 【当前用户问题】\n分页问题2\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
        "user": {
          "name": "王颖奇",
          "phone": "15323720032",
          "categoryName": "图湃（北京）医疗科技",
          "record_id": "UID_20250001",
          "ip_address": "183.230.12.156"
        }
      }
    ],
    "total": 2,
    "page": 1,
    "size": 1,
    "total_pages": 2
  }
}
```
