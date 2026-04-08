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
  "body": ": stream-open\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"模\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"拟\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"回\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"答\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \":\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \" \"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"【\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"当\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"前\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"用\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"户\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"问\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"题\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"】\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"你\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"好\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"【\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"回\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"答\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"要\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"求\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"】\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"1\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \".\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \" \"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"必\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"须\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"同\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"时\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"结\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"合\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"历\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"史\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"对\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"话\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"、\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"本\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"轮\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"问\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"题\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"和\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"上\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"传\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"内\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"容\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"进\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"行\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"回\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"答\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"。\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"2\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \".\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \" \"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"如\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"果\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"上\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"面\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"已\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"经\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"给\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"出\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"了\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"上\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"传\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"正\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"或\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"摘\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"要\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"，\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"说\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"明\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"系\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"统\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"已\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"经\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"成\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"功\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"读\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"取\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"；\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"此\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"时\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"不\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"要\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"再\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"说\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"“\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"无\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"法\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"读\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"取\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"附\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"”\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"或\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"类\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"似\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"表\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"述\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"。\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"3\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \".\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \" \"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"如\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"果\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"上\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"传\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"中\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"有\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"可\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"用\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"信\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"息\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"，\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"优\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"先\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"基\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"于\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"内\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"容\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"回\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"答\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"，\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"并\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"明\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"确\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"提\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"到\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"名\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"。\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"4\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \".\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \" \"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"如\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"果\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"未\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"解\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"析\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"成\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"功\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"或\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"内\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"容\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"不\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"足\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"，\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"请\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"明\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"确\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"说\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"明\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"，\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"不\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"要\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"假\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"装\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"已\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"经\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"读\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"到\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"。\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"5\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \".\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \" \"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"不\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"要\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"忽\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"略\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"用\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"户\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"本\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"轮\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"输\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"入\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"的\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"字\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"问\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"题\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"。\"}\n\ndata: {\"type\": \"done\", \"data\": {\"message_index\": 0, \"question\": \"你好\", \"files\": [], \"uploaded_files\": [], \"file_contexts\": [], \"web_search\": true, \"db_version\": null, \"answer\": \"模拟回答: 【当前用户问题】\\n你好\\n\\n【回答要求】\\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\\n5. 不要忽略用户本轮输入的文字问题。\", \"resource\": [{\"link\": \"https://example.com\", \"title\": \"示例来源\", \"content\": \"示例摘要\"}], \"recommend_answer\": [\"追问1\", \"追问2\", \"追问3\"], \"feedback\": null, \"created_at\": \"1775561402801\", \"updated_at\": \"1775561402801\", \"createdAt\": \"2026/04/07 19:30:02\", \"updatedAt\": \"2026/04/07 19:30:02\"}}\n\n",
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
      "created_at": "1775561402801",
      "updated_at": "1775561402801",
      "createdAt": "2026/04/07 19:30:02",
      "updatedAt": "2026/04/07 19:30:02"
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
  "body": ": stream-open\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"模\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"拟\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"回\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"答\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \":\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \" \"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"【\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"当\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"前\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"用\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"户\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"问\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"题\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"】\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"默\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"认\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"流\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"式\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"【\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"回\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"答\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"要\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"求\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"】\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"1\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \".\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \" \"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"必\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"须\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"同\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"时\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"结\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"合\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"历\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"史\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"对\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"话\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"、\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"本\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"轮\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"问\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"题\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"和\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"上\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"传\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"内\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"容\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"进\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"行\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"回\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"答\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"。\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"2\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \".\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \" \"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"如\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"果\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"上\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"面\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"已\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"经\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"给\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"出\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"了\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"上\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"传\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"正\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"或\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"摘\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"要\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"，\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"说\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"明\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"系\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"统\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"已\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"经\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"成\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"功\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"读\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"取\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"；\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"此\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"时\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"不\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"要\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"再\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"说\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"“\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"无\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"法\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"读\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"取\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"附\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"”\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"或\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"类\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"似\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"表\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"述\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"。\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"3\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \".\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \" \"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"如\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"果\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"上\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"传\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"中\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"有\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"可\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"用\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"信\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"息\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"，\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"优\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"先\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"基\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"于\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"内\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"容\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"回\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"答\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"，\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"并\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"明\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"确\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"提\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"到\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"名\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"。\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"4\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \".\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \" \"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"如\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"果\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"件\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"未\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"解\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"析\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"成\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"功\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"或\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"内\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"容\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"不\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"足\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"，\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"请\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"明\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"确\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"说\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"明\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"，\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"不\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"要\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"假\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"装\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"已\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"经\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"读\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"到\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"。\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"\\n\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"5\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \".\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \" \"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"不\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"要\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"忽\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"略\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"用\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"户\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"本\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"轮\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"输\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"入\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"的\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"文\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"字\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"问\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"题\"}\n\ndata: {\"type\": \"answer_delta\", \"delta\": \"。\"}\n\ndata: {\"type\": \"done\", \"data\": {\"message_index\": 0, \"question\": \"默认流式\", \"files\": [], \"uploaded_files\": [], \"file_contexts\": [], \"web_search\": false, \"db_version\": null, \"answer\": \"模拟回答: 【当前用户问题】\\n默认流式\\n\\n【回答要求】\\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\\n5. 不要忽略用户本轮输入的文字问题。\", \"resource\": [], \"recommend_answer\": [\"追问1\", \"追问2\", \"追问3\"], \"feedback\": null, \"created_at\": \"1775561405984\", \"updated_at\": \"1775561405984\", \"createdAt\": \"2026/04/07 19:30:05\", \"updatedAt\": \"2026/04/07 19:30:05\"}}\n\n"
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
      "context.txt"
    ],
    "uploaded_files": [
      {
        "file_id": "file_1775561428482_0",
        "filename": "context.txt",
        "url": "http://127.0.0.1:9000/xintuoyin-data/chat/2026-04-07/conv-file-context/0/context.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260407%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260407T113028Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=4172da793f8e7c7e5487fd3165557856e4419aea667d965cff208cb33a561780",
        "relative_path": "chat/2026-04-07/conv-file-context/0/context.txt",
        "object_name": "chat/2026-04-07/conv-file-context/0/context.txt"
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
    "answer": "模拟回答: 【本轮上传文件内容】\n文件1：context.txt\n附件里写着项目代号是北极星。\n\n【当前用户问题】\n请根据附件内容回答\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
    "resource": [],
    "recommend_answer": [
      "追问1",
      "追问2",
      "追问3"
    ],
    "feedback": null,
    "created_at": "1775561432391",
    "updated_at": "1775561432391",
    "createdAt": "2026/04/07 19:30:32",
    "updatedAt": "2026/04/07 19:30:32"
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
    "created_at": "1775561442439",
    "updated_at": "1775561442439",
    "createdAt": "2026/04/07 19:30:42",
    "updatedAt": "2026/04/07 19:30:42"
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
      "same.txt",
      "same_1.txt"
    ],
    "uploaded_files": [
      {
        "file_id": "file_1775561449219_0",
        "filename": "same.txt",
        "url": "http://127.0.0.1:9000/xintuoyin-data/chat/2026-04-07/conv-files/0/same.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260407%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260407T113049Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=c22834fc1e249678f23ab2bfa3c8c4b864f646162b71ca3486ad2cf7f9cf9911",
        "relative_path": "chat/2026-04-07/conv-files/0/same.txt",
        "object_name": "chat/2026-04-07/conv-files/0/same.txt"
      },
      {
        "file_id": "file_1775561449226_1",
        "filename": "same_1.txt",
        "url": "http://127.0.0.1:9000/xintuoyin-data/chat/2026-04-07/conv-files/0/same_1.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260407%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260407T113049Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=f9623d765ed3aaae2c4f61347e74a92129b81ca982b22c4cb54de2be22045c56",
        "relative_path": "chat/2026-04-07/conv-files/0/same_1.txt",
        "object_name": "chat/2026-04-07/conv-files/0/same_1.txt"
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
    "answer": "模拟回答: 【本轮上传文件内容】\n文件1：same.txt\na\n文件2：same_1.txt\nb\n\n【当前用户问题】\n带附件\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。",
    "resource": [],
    "recommend_answer": [
      "追问1",
      "追问2",
      "追问3"
    ],
    "feedback": null,
    "created_at": "1775561453052",
    "updated_at": "1775561453052",
    "createdAt": "2026/04/07 19:30:53",
    "updatedAt": "2026/04/07 19:30:53"
  }
}
```
