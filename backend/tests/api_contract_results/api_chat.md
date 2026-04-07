# api_chat

## success

- status: PASS
- method: POST
- path: /api/chat

### request
```json
{
  "content_type": "application/json",
  "message": "你好",
  "conversation_id": "conv1",
  "web_search": true
}
```

### response
```json
{
  "content_type": "text/event-stream; charset=utf-8",
  "body": ": stream-open\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"模拟回答: \"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"【当前用户问题】\\n你好\\n\\n【回答要求】\\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\\n5. 不要忽略用户本轮输入的文字问题。\"}\n\ndata: {\"type\": \"done\", \"data\": {\"message_index\": 0, \"question\": \"你好\", \"files\": [], \"uploaded_files\": [], \"file_contexts\": [], \"web_search\": true, \"db_version\": null, \"answer\": \"模拟回答: 【当前用户问题】\\n你好\\n\\n【回答要求】\\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\\n5. 不要忽略用户本轮输入的文字问题。\", \"resource\": [{\"link\": \"https://example.com\", \"title\": \"示例来源\", \"content\": \"示例摘要\"}], \"recommend_answer\": [\"追问1\", \"追问2\", \"追问3\"], \"feedback\": null, \"created_at\": \"1775216098203\", \"updated_at\": \"1775216098203\", \"createdAt\": \"2026/04/03 19:34:58\", \"updatedAt\": \"2026/04/03 19:34:58\"}}\n\n",
  "done": {
    "type": "done",
    "data": {
      "message_index": 0,
      "question": "你好",
      "files": [],
      "uploaded_files": [],
      "file_contexts": [],
      "web_search": true,
      "db_version": null,
      "answer": "模拟回答: 【当前用户问题】\n你好\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
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
      "created_at": "1775216098203",
      "updated_at": "1775216098203",
      "createdAt": "2026/04/03 19:34:58",
      "updatedAt": "2026/04/03 19:34:58"
    }
  }
}
```

## default_stream_success

- status: PASS
- method: POST
- path: /api/chat
- notes: 无文件对话默认使用 JSON 请求，接口固定返回 SSE，且不再推送思考过程事件。

### request
```json
{
  "content_type": "application/json",
  "conversation_id": "conv-stream",
  "message": "默认流式"
}
```

### response
```json
{
  "content_type": "text/event-stream; charset=utf-8",
  "body": ": stream-open\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"模拟回答: \"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"【当前用户问题】\\n默认流式\\n\\n【回答要求】\\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\\n5. 不要忽略用户本轮输入的文字问题。\"}\n\ndata: {\"type\": \"done\", \"data\": {\"message_index\": 0, \"question\": \"默认流式\", \"files\": [], \"uploaded_files\": [], \"file_contexts\": [], \"web_search\": false, \"db_version\": null, \"answer\": \"模拟回答: 【当前用户问题】\\n默认流式\\n\\n【回答要求】\\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\\n5. 不要忽略用户本轮输入的文字问题。\", \"resource\": [], \"recommend_answer\": [\"追问1\", \"追问2\", \"追问3\"], \"feedback\": null, \"created_at\": \"1775216098209\", \"updated_at\": \"1775216098209\", \"createdAt\": \"2026/04/03 19:34:58\", \"updatedAt\": \"2026/04/03 19:34:58\"}}\n\n"
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
  "type": "done",
  "data": {
    "message_index": 0,
    "question": "请根据附件内容回答",
    "files": [
      "context_15.txt"
    ],
    "uploaded_files": [
      {
        "file_id": "file_1775216098307_0",
        "filename": "context_15.txt",
        "url": "http://127.0.0.1:9000/xintuoyin-data/chat/2026-04-03/conv-file-context/0/context_15.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260403%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260403T113458Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=33813a59b17d28207d99ae3205e71c41fef27a38c9c22378808f7ff3afc3fe60",
        "relative_path": "chat/2026-04-03/conv-file-context/0/context_15.txt",
        "object_name": "chat/2026-04-03/conv-file-context/0/context_15.txt"
      }
    ],
    "file_contexts": [
      {
        "filename": "context_15.txt",
        "text": "附件里写着项目代号是北极星。"
      }
    ],
    "web_search": false,
    "db_version": null,
    "answer": "模拟回答: 【本轮上传文件内容】\n文件1：context_15.txt\n附件里写着项目代号是北极星。\n\n【当前用户问题】\n请根据附件内容回答\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
    "resource": [],
    "recommend_answer": [
      "追问1",
      "追问2",
      "追问3"
    ],
    "feedback": null,
    "created_at": "1775216098317",
    "updated_at": "1775216098317",
    "createdAt": "2026/04/03 19:34:58",
    "updatedAt": "2026/04/03 19:34:58"
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
  "type": "done",
  "data": {
    "message_index": 1,
    "question": "第二轮继续追问",
    "files": [],
    "uploaded_files": [],
    "file_contexts": [],
    "web_search": false,
    "db_version": null,
    "answer": "模拟回答: 【历史对话上下文】\n第1轮用户：第一轮问题\n第1轮助手：模拟回答: 【当前用户问题】\n第一轮问题\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。\n\n【当前用户问题】\n第二轮继续追问\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
    "resource": [],
    "recommend_answer": [
      "追问1",
      "追问2",
      "追问3"
    ],
    "feedback": null,
    "created_at": "1775216098329",
    "updated_at": "1775216098329",
    "createdAt": "2026/04/03 19:34:58",
    "updatedAt": "2026/04/03 19:34:58"
  }
}
```

## stream_exception

- status: PASS
- method: POST
- path: /api/chat
- notes: 聊天接口固定为 SSE；执行异常时应返回 error 事件而不是切换到非流式 JSON。

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
  "content_type": "text/event-stream; charset=utf-8",
  "body": ": stream-open\n\ndata: {\"type\": \"error\", \"message\": \"mock stream failed\"}\n\n"
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
  "type": "done",
  "data": {
    "message_index": 0,
    "question": "带附件",
    "files": [
      "same_30.txt",
      "same_31.txt"
    ],
    "uploaded_files": [
      {
        "file_id": "file_1775216098407_0",
        "filename": "same_30.txt",
        "url": "http://127.0.0.1:9000/xintuoyin-data/chat/2026-04-03/conv-files/0/same_30.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260403%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260403T113458Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=e62d3bb437ea2dfdb9a195862412c3196ffb8563663b9993a442b549b709592f",
        "relative_path": "chat/2026-04-03/conv-files/0/same_30.txt",
        "object_name": "chat/2026-04-03/conv-files/0/same_30.txt"
      },
      {
        "file_id": "file_1775216098415_1",
        "filename": "same_31.txt",
        "url": "http://127.0.0.1:9000/xintuoyin-data/chat/2026-04-03/conv-files/0/same_31.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260403%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260403T113458Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=b0ee177b79e0e0d599cd9c0d43ffcc34cf1de59dc8155c57ad08cf8f6e8328b9",
        "relative_path": "chat/2026-04-03/conv-files/0/same_31.txt",
        "object_name": "chat/2026-04-03/conv-files/0/same_31.txt"
      }
    ],
    "file_contexts": [
      {
        "filename": "same_30.txt",
        "text": "a"
      },
      {
        "filename": "same_31.txt",
        "text": "b"
      }
    ],
    "web_search": false,
    "db_version": null,
    "answer": "模拟回答: 【本轮上传文件内容】\n文件1：same_30.txt\na\n文件2：same_31.txt\nb\n\n【当前用户问题】\n带附件\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
    "resource": [],
    "recommend_answer": [
      "追问1",
      "追问2",
      "追问3"
    ],
    "feedback": null,
    "created_at": "1775216098430",
    "updated_at": "1775216098430",
    "createdAt": "2026/04/03 19:34:58",
    "updatedAt": "2026/04/03 19:34:58"
  }
}
```
