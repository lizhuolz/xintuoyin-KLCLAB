# api_history_detail

## success

- status: PASS
- method: GET
- path: /api/history/{conversation_id}

### request
```json
{
  "conversation_id": "conv-detail"
}
```

### response
```json
{
  "code": 0,
  "msg": "获取历史详情成功",
  "data": {
    "conversation_id": "conv-detail",
    "title": "详情测试",
    "created_at": "1774367355190",
    "updated_at": "1774367355190",
    "createdAt": "2026/03/24 23:49:15",
    "updatedAt": "2026/03/24 23:49:15",
    "message_count": 1,
    "user": {
      "name": "王颖奇",
      "phone": "15323720032",
      "categoryName": "图湃（北京）医疗科技"
    },
    "messages": [
      {
        "message_index": 0,
        "question": "详情测试",
        "files": [],
        "uploaded_files": [],
        "file_contexts": [],
        "web_search": false,
        "db_version": null,
        "answer": "模拟回答: 【当前用户问题】\n详情测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n3. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n4. 不要忽略用户本轮输入的文字问题。",
        "resource": [],
        "recommend_answer": [
          "追问1",
          "追问2",
          "追问3"
        ],
        "feedback": null,
        "thinking_text": "在正式回答前，我先做了几步准备：\n1. 我调用了 mock_tool，输入大致是：{}。\n整理完这些信息后，我再把最终答案组织成对你更自然的回复。",
        "thinking_steps": [
          {
            "kind": "call",
            "node_name": "chatbot_local",
            "tool_name": "mock_tool",
            "preview": "{}",
            "tool_call_id": "tool-1"
          }
        ],
        "created_at": "1774367355190",
        "updated_at": "1774367355190",
        "createdAt": "2026/03/24 23:49:15",
        "updatedAt": "2026/03/24 23:49:15"
      }
    ]
  }
}
```

## not_found

- status: PASS
- method: GET
- path: /api/history/{conversation_id}

### request
```json
{
  "conversation_id": "not-found"
}
```

### response
```json
{
  "code": 1,
  "msg": "获取历史详情失败",
  "data": {
    "conversation_id": "not-found"
  }
}
```
