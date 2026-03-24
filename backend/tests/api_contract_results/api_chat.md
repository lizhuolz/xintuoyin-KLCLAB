# api_chat

## success

- status: PASS
- method: POST
- path: /api/chat

### request
```json
{
  "message": "你好",
  "conversation_id": "conv1",
  "web_search": true
}
```

### response
```json
{
  "code": 0,
  "msg": "发送对话成功",
  "data": {
    "message_index": 0,
    "question": "你好",
    "files": [],
    "uploaded_files": [],
    "file_contexts": [],
    "web_search": true,
    "db_version": null,
    "answer": "模拟回答: 【当前用户问题】\n你好\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n3. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n4. 不要忽略用户本轮输入的文字问题。",
    "resource": [
      {
        "link": "https://example.com",
        "title": "示例来源",
        "content": "示例摘要"
      }
    ],
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
    "created_at": "1774367344770",
    "updated_at": "1774367344770",
    "createdAt": "2026/03/24 23:49:04",
    "updatedAt": "2026/03/24 23:49:04"
  }
}
```

## default_stream_success

- status: PASS
- method: POST
- path: /api/chat
- notes: 不传 stream 时默认返回 SSE 事件流。

### request
```json
{
  "conversation_id": "conv-stream",
  "message": "默认流式"
}
```

### response
```json
{
  "content_type": "text/event-stream; charset=utf-8",
  "body": "data: {\"type\": \"answer_delta\", \"delta\": \"请您提供相关的文件，以便我可以根据文件内容为您提供更准确的回答。如果文件未能成功解析或内容不足，我会明确告知您。请继续提供您的问题或文件。\"}\n\ndata: {\"type\": \"done\", \"data\": {\"message_index\": 0, \"question\": \"默认流式\", \"files\": [], \"uploaded_files\": [], \"file_contexts\": [], \"web_search\": false, \"db_version\": null, \"answer\": \"请您提供相关的文件，以便我可以根据文件内容为您提供更准确的回答。如果文件未能成功解析或内容不足，我会明确告知您。请继续提供您的问题或文件。\", \"resource\": [], \"recommend_answer\": [\"追问1\", \"追问2\", \"追问3\"], \"feedback\": null, \"thinking_text\": \"这次回答没有额外调用工具，我直接根据已有上下文完成了回复。\", \"thinking_steps\": [], \"created_at\": \"1774367354859\", \"updated_at\": \"1774367354859\", \"createdAt\": \"2026/03/24 23:49:14\", \"updatedAt\": \"2026/03/24 23:49:14\"}}\n\n"
}
```

## file_content_context

- status: PASS
- method: POST
- path: /api/chat
- notes: 上传附件后，模型上下文应同时包含附件正文和本轮文字问题。

### request
```json
{
  "conversation_id": "conv-file-context",
  "message": "请根据附件内容回答",
  "files": [
    "context.txt"
  ]
}
```

### response
```json
{
  "code": 0,
  "msg": "发送对话成功",
  "data": {
    "message_index": 0,
    "question": "请根据附件内容回答",
    "files": [
      "context.txt"
    ],
    "uploaded_files": [
      {
        "file_id": "file_1774367354952_0",
        "filename": "context.txt",
        "url": "/api/static/chat_uploads/2026-03-24/conv-file-context/0/context.txt",
        "relative_path": "2026-03-24/conv-file-context/0/context.txt"
      }
    ],
    "file_contexts": [
      {
        "filename": "context.txt",
        "text": "附件里写着项目代号是北极星。"
      }
    ],
    "web_search": false,
    "db_version": null,
    "answer": "模拟回答: 【本轮上传文件内容】\n文件1：context.txt\n附件里写着项目代号是北极星。\n\n【当前用户问题】\n请根据附件内容回答\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n3. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n4. 不要忽略用户本轮输入的文字问题。",
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
    "created_at": "1774367354952",
    "updated_at": "1774367354952",
    "createdAt": "2026/03/24 23:49:14",
    "updatedAt": "2026/03/24 23:49:14"
  }
}
```

## history_context

- status: PASS
- method: POST
- path: /api/chat
- notes: 同一会话的后续轮次应带上前序问答上下文。

### request
```json
{
  "conversation_id": "conv-history-context",
  "message": "第二轮继续追问"
}
```

### response
```json
{
  "code": 0,
  "msg": "发送对话成功",
  "data": {
    "message_index": 1,
    "question": "第二轮继续追问",
    "files": [],
    "uploaded_files": [],
    "file_contexts": [],
    "web_search": false,
    "db_version": null,
    "answer": "模拟回答: 【历史对话上下文】\n第1轮用户：第一轮问题\n第1轮助手：模拟回答: 【当前用户问题】\n第一轮问题\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n3. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n4. 不要忽略用户本轮输入的文字问题。\n\n【当前用户问题】\n第二轮继续追问\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n3. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n4. 不要忽略用户本轮输入的文字问题。",
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
    "created_at": "1774367354962",
    "updated_at": "1774367354962",
    "createdAt": "2026/03/24 23:49:14",
    "updatedAt": "2026/03/24 23:49:14"
  }
}
```

## run_chat_exception

- status: PASS
- method: POST
- path: /api/chat
- notes: 模拟模型执行异常，确认接口返回统一 500 错误结构。

### request
```json
{
  "conversation_id": "conv-error",
  "message": "失败分支"
}
```

### response
```json
{
  "code": 1,
  "msg": "发送对话失败",
  "data": {
    "reason": "mock run_chat failed"
  }
}
```

## duplicate_upload_names

- status: PASS
- method: POST
- path: /api/chat
- notes: 同名上传文件应自动重命名，避免覆盖历史附件。

### request
```json
{
  "conversation_id": "conv-files",
  "message": "带附件",
  "files": [
    "same.txt",
    "same.txt"
  ]
}
```

### response
```json
{
  "code": 0,
  "msg": "发送对话成功",
  "data": {
    "message_index": 0,
    "question": "带附件",
    "files": [
      "same.txt",
      "same_1.txt"
    ],
    "uploaded_files": [
      {
        "file_id": "file_1774367355010_0",
        "filename": "same.txt",
        "url": "/api/static/chat_uploads/2026-03-24/conv-files/0/same.txt",
        "relative_path": "2026-03-24/conv-files/0/same.txt"
      },
      {
        "file_id": "file_1774367355010_1",
        "filename": "same_1.txt",
        "url": "/api/static/chat_uploads/2026-03-24/conv-files/0/same_1.txt",
        "relative_path": "2026-03-24/conv-files/0/same_1.txt"
      }
    ],
    "file_contexts": [
      {
        "filename": "same.txt",
        "text": "a"
      },
      {
        "filename": "same_1.txt",
        "text": "b"
      }
    ],
    "web_search": false,
    "db_version": null,
    "answer": "模拟回答: 【本轮上传文件内容】\n文件1：same.txt\na\n文件2：same_1.txt\nb\n\n【当前用户问题】\n带附件\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n3. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n4. 不要忽略用户本轮输入的文字问题。",
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
    "created_at": "1774367355010",
    "updated_at": "1774367355010",
    "createdAt": "2026/03/24 23:49:15",
    "updatedAt": "2026/03/24 23:49:15"
  }
}
```
