# Backend Refactor Report

生成时间: 2026-03-24

## 1. 上传文件功能完善
状态: 已完成

实现内容:
- `/api/kb/{id}/upload` 改为支持一次上传多个文件。
- 支持扩展名白名单: `pdf`, `txt`, `csv`, `doc`, `docx`, `xls`, `xlsx`。
- 对空文件名和不支持类型返回标准化业务错误码。
- 对聊天附件解析补充了 `csv`、`doc`、多工作表 Excel 的处理。

主要实现文件:
- `backend/app.py`
- `backend/core/files.py`
- `backend/services/kb_service.py`

测试覆盖:
- `test_upload_kb_file_success`
- `test_upload_kb_multiple_files_success`
- `test_upload_kb_file_empty_filename`
- `test_upload_kb_file_unsupported_type`
- `test_upload_kb_file_internal_failure`
- `test_upload_kb_file_refresh_failure_is_reported`
- `test_chat_large_file_keeps_tail_context`
- `test_chat_file_parse_error_is_ignored`

结论:
- 多文件上传、类型校验、异常归一化已通过。
- `.doc` 为 best-effort 解析: 优先 `textract`，缺失时降级为文本解码。

## 2. 新增后台 AI 搜索与网页抓取 API
状态: 已完成

新增 API:
- `POST /api/chat/search-artifacts`

返回内容:
- `conversation_id`
- `search_results`
- `result_count`
- `final_answer`

实现说明:
- 从 LangGraph 工具消息 `tavily_search_with_summary` 中提取结构化抓取结果。
- 返回 `main_title`、`sub_title`、`summary`、`url`、`raw_content`。

主要实现文件:
- `backend/app.py`
- `backend/services/chat_service.py`

测试覆盖:
- `test_chat_search_artifacts_returns_search_payload`

结论:
- 新 API 可稳定返回 `core_agt` 中原本只打印在控制台的搜索抓取结构化结果。

## 3. LangGraph 思考过程/工具调用/SQL 过程输出方案
状态: 已完成基础方案

决策:
- 采用多个 API，而不是把主回答流和调试/过程信息强行混在一个接口里。

当前落地:
- `POST /api/chat`: 主回答流，保持 `text/plain` 输出。
- `POST /api/chat/events`: 返回结构化事件列表，包括节点进入、工具结果、搜索结果、回答增量。
- `POST /api/chat/search-artifacts`: 专门返回后台联网抓取结果。

事件类型示例:
- `node.enter`
- `tool.call`
- `tool.result`
- `sql.result`
- `search.results`
- `answer.delta`
- `run.completed`

主要实现文件:
- `backend/app.py`
- `backend/services/chat_service.py`

测试覆盖:
- `test_chat_events_returns_structured_trace`

结论:
- 已形成“主回答接口 + 过程接口 + 搜索产物接口”的后端分层。
- 这比单接口混流更适合工业前后端解耦。

## 4. app.py 重构
状态: 已完成

重构结果:
- 将环境加载、HTTP 响应、文件处理、聊天执行、历史存储拆出独立模块。
- `app.py` 保留为应用装配和路由协调层。

新增模块:
- `backend/core/env.py`
- `backend/core/http.py`
- `backend/core/files.py`
- `backend/services/chat_service.py`
- `backend/services/history_service.py`

结论:
- 主入口职责明显收敛，后续继续拆分 router 会更容易。

## 5. 测试与结果
状态: 已完成

执行命令:
```bash
python3 -m py_compile backend/app.py backend/core/http.py backend/core/files.py backend/services/chat_service.py backend/services/history_service.py backend/services/kb_service.py backend/tests/test_api.py
python3 -m unittest backend.tests.test_api -v
```

结果:
- 静态编译: 通过
- API 单测: 43/43 通过

说明:
- 测试中对 `utils.security` 做了 stub，避免 GPU 安全模型加载影响后端 API 回归。
- PDF 破损场景仍按预期忽略解析错误，不中断聊天流程。
