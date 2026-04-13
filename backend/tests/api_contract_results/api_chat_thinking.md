# api_chat_thinking

## success

- status: PASS
- method: GET
- path: /api/chat/{conversation_id}/thinking

### request
```json
{
  "conversation_id": "conv-think",
  "message_index": 2
}
```

### response
```json
{
  "content_type": "text/plain; charset=utf-8",
  "text": "内部思考：先分析“【历史对话上下文】\n第1轮用户：思考测试\n第1轮助手：模拟回答: 【当前用户问题】\n思考测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。\n第2轮用户：思考测试\n第2轮助手：模拟回答: 【历史对话上下文】\n第1轮用户：思考测试\n第1轮助手：模拟回答: 【当前用户问题】\n思考测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。\n\n【当前用户问题】\n思考测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。\n\n【当前用户问题】\n思考测试\n\n【回答要求】\n1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n5. 不要忽略用户本轮输入的文字问题。”"
}
```

## default_stream_success

- status: PASS
- method: GET
- path: /api/chat/{conversation_id}/thinking
- notes: 思考过程接口固定返回文本流，优先输出工具调用过程。

### request
```json
{
  "conversation_id": "conv-think-stream",
  "message_index": 3
}
```

### response
```json
{
  "content_type": "text/plain; charset=utf-8",
  "text": "在正式回答前，我先做了几步准备：\n1. 我调用了 mock_tool，输入大致是：{\"q\":\"工具思考\"}。\n对应上面第 1 步，mock_tool 返回了这样的关键信息：检索到 1 条结果。\n整理完这些信息后，我再把最终答案组织成对你更自然的回复。"
}
```

## empty_when_no_tool_and_no_think

- status: PASS
- method: GET
- path: /api/chat/{conversation_id}/thinking
- notes: 没有工具过程且模型回答不含 <think> 时，应返回空文本流。

### request
```json
{
  "conversation_id": "conv-think-empty",
  "message_index": 0
}
```

### response
```json
{
  "content_type": "text/plain; charset=utf-8",
  "text": ""
}
```

## not_found

- status: PASS
- method: GET
- path: /api/chat/{conversation_id}/thinking

### request
```json
{
  "conversation_id": "missing-thinking",
  "message_index": 0
}
```

### response
```json
{
  "code": 1,
  "msg": "获取思考过程失败",
  "data": {
    "conversation_id": "missing-thinking"
  }
}
```
