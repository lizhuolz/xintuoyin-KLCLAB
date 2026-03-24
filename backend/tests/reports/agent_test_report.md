# Agent Capability Test Report

## Backend Probe

- Base URL: `http://127.0.0.1:8069`
- Health check: `200`
- Reachable: `True`

## Extracted Requirements

- `REQ-THINKING` | 企业端-思考过程 | 思考过程展示与开关 | not_testable_via_current_api
  Scope: Agent 在推理时输出思考过程，并支持开关。
  Source rows: 43-53
  Note: /api/chat 当前仅返回 text/plain 最终回答，不返回独立思考过程流或开关状态。
- `REQ-WEB` | 企业端-联网功能 | 联网实时检索 | partially_testable
  Scope: 根据 web_search 开关进行实时信息检索。
  Source rows: 54-61
  Note: 当前 /api/chat 仅暴露 web_search 布尔开关，不返回检索来源或执行细节，结果受外部网络与模型行为影响。
- `REQ-SOURCE` | 参考来源 | 参考来源展示与合规过滤 | not_testable_via_current_api
  Scope: 回答带来源标注、来源卡片与合规过滤。
  Source rows: 62-72
  Note: /api/chat 当前不返回引用来源结构化字段，也不返回来源卡片元数据。
- `REQ-DB` | 链接数据库 | 自然语言转 SQL 与数据库查询 | partially_testable
  Scope: 按选定数据库执行查询并返回结果。
  Source rows: 73-83
  Note: 当前公开接口仅暴露 db_version 提示词注入能力，未暴露 SQL、权限判断、结果集或数据库选择列表。
- `REQ-FILE` | 上传文件--解析文件 | 文件解析、结构提取与基于附件问答 | live_testable
  Scope: 解析上传文件并将内容注入对话上下文。
  Source rows: 86-100
  Note: 当前 /api/chat 支持 files 上传，并在后端解析 txt/pdf/docx/xlsx/xls。
- `REQ-KB` | 企业端-动态知识库 | 动态知识库问答 | live_testable
  Scope: 上传知识库文件后，按分类进行检索问答。
  Source rows: 195-213
  Note: 当前后端提供 KB 创建、上传、删除与 /api/chat 的 kb_category 检索入口。
- `REQ-HISTORY` | 企业端-历史对话 | 历史对话落盘、删除与新会话隔离 | partially_testable
  Scope: 对话持久化、删除以及不同会话的上下文隔离。
  Source rows: 221-230
  Note: 当前后端支持落盘与删除，但未提供列表、搜索、批量删除等公开 API。

## Executed Cases Summary

- Total live cases: `6`
- Passed: `4`
- Failed: `2`
- Errors: `0`

## Case Details

### CASE-FILE-TXT TXT 附件解析与引用

- Requirement: `REQ-FILE`
- Status: `passed`
- Prompt: `我上传了一个文件。请告诉我里面的项目代号和上线日期。`
- Expected all: `['北极星', '2026年4月15日']`

```text
根据您提供的文件内容：

- 项目代号是：北极星
- 上线日期是：2026年4月15日
```

- expected_all `北极星` -> `True`
- expected_all `2026年4月15日` -> `True`

### CASE-FILE-MULTI 多文件联合解析

- Requirement: `REQ-FILE`
- Status: `passed`
- Prompt: `请根据我上传的两个文件，分别告诉我研发负责人和测试负责人是谁。`
- Expected all: `['张敏', '李卓']`

```text
根据您提供的文件内容：

- 研发负责人是张敏。
- 测试负责人是李卓。
```

- expected_all `张敏` -> `True`
- expected_all `李卓` -> `True`

### CASE-FILE-XLSX Excel 解析能力

- Requirement: `REQ-FILE`
- Status: `failed`
- Prompt: `我上传了一个Excel文件。请告诉我它包含哪些工作表名称。`
- Expected all: `['Sheet1', 'Sheet3']`
- Failure reason: `content check failed`

```text
请提供该Excel文件，我将帮助你查看其中包含的工作表名称。
```

- expected_all `Sheet1` -> `False`
- expected_all `Sheet3` -> `False`

### CASE-KB-BASIC 动态知识库问答

- Requirement: `REQ-KB`
- Status: `failed`
- Prompt: `知识库里提到的报销审批时限是多久？`
- Expected any: `['3个工作日']`
- Failure reason: `content check failed`

```text
知识库检索工具出现异常，无法获取相关信息。请稍后再试或联系技术支持以解决此问题。
```

- expected_any `['3个工作日']` -> `False`

### CASE-HISTORY-PERSIST 历史对话落盘

- Requirement: `REQ-HISTORY`
- Status: `passed`
- Prompt: `请回复一句：历史记录测试成功。`
- Expected any: `['历史记录测试成功']`

```text
历史记录测试成功。
```

- expected_any `['历史记录测试成功']` -> `True`
- history_file_created -> `True`

### CASE-HISTORY-ISOLATION 新会话不继承旧上下文

- Requirement: `REQ-HISTORY`
- Status: `passed`
- Prompt: `上一轮会话里我说过什么暗号？如果你不知道，请直接说不知道。`
- Expected any: `['不知道', '无法确定', '不清楚']`

```text
不知道。
```

- expected_any `['不知道', '无法确定', '不清楚']` -> `True`
- history_isolation -> `True`

## Unmet Or Untestable Requirements

- `REQ-THINKING` | 思考过程展示/关闭 | 当前 API 不返回思考过程流，无法通过 /api/chat 自动核对。
  Suggestion: 如需测试，需后端新增结构化字段或单独流通道。
- `REQ-WEB` | 联网实时数据与时效性 | 结果依赖外部网络与模型调用，且当前接口不返回来源元数据，自动断言稳定性差。
  Suggestion: 建议增加引用来源、抓取时间戳与是否走联网链路的结构化字段。
- `REQ-SOURCE` | 参考来源弹窗/来源卡片/合规过滤 | 当前 API 不返回来源列表、来源标题、副标题、过滤原因。
  Suggestion: 建议新增 sources 字段与过滤日志。
- `REQ-DB` | NL2SQL、权限判断、无数据和断链处理 | 公开接口未返回 SQL、结果集、错误码或数据库元信息，无法对需求逐项自动核验。
  Suggestion: 建议提供数据库查询专用接口或调试字段。
- `REQ-FILE` | Excel 解析能力 | content check failed
  Suggestion: See case details and actual response above.
- `REQ-KB` | 动态知识库问答 | content check failed
  Suggestion: See case details and actual response above.

