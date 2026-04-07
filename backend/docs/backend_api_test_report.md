# 后端 API 测试报告

> 维护时间：2026-04-03
>
> 契约结果来源：[SUMMARY.md](/home/lyq/xintuoyin-KLCLAB/backend/tests/api_contract_results/SUMMARY.md)
>
> 对齐实现：[app.py](/home/lyq/xintuoyin-KLCLAB/backend/app.py)

## 1. 测试范围

本轮测试分为两部分：

- 契约测试：`backend/tests/test_api_contract.py`
- 真实服务烟测：已启动后端 `8000` 和前端 `5173` 后，通过 HTTP 直接访问核心接口、页面入口和知识库预览更新链路

说明：

- 这是接口契约和联机烟测，不是高并发压测
- 本轮额外覆盖了 `/api/chat` 与 `/api/chat/{conversation_id}/thinking` 的纯流式契约和边界行为

## 2. 契约测试结果

汇总结果：

- 总接口数：`28`
- 总用例数：`76`
- 通过：`76`
- 失败：`0`

主要覆盖：

- OpenAPI 参数描述补齐
- `/api/chat` 固定 SSE，且回答流剥离 `<think>...</think>`
- `/api/chat/{conversation_id}/thinking` 固定文本流，优先返回工具调用过程，其次回退到 `<think>` 内容
- `/api/chat/{conversation_id}/thinking` 在无工具过程且无 `<think>` 时返回空文本流
- `/api/chat/{conversation_id}/thinking` 在会话或轮次不存在时返回统一 `404`
- 无文件的 `/api/chat`、`/api/chat/feedback`、`/api/kb/create`、`/api/kb/{id}/delete_file` 已切到 JSON 主路径
- 带文件的对话、反馈和知识库更新仍保留 multipart 兼容
- 历史记录分页、MinIO 存储与字段补充
- 反馈列表重构与筛选
- 知识库创建去掉 `category`
- 知识库更新预览/确认、同次删除与上传
- 数据库显式选择接口

详细结果见：

- [SUMMARY.md](/home/lyq/xintuoyin-KLCLAB/backend/tests/api_contract_results/SUMMARY.md)
- [api_history_list.md](/home/lyq/xintuoyin-KLCLAB/backend/tests/api_contract_results/api_history_list.md)
- [api_feedback_list.md](/home/lyq/xintuoyin-KLCLAB/backend/tests/api_contract_results/api_feedback_list.md)
- [api_kb_update.md](/home/lyq/xintuoyin-KLCLAB/backend/tests/api_contract_results/api_kb_update.md)
- [api_db_select_options.md](/home/lyq/xintuoyin-KLCLAB/backend/tests/api_contract_results/api_db_select_options.md)
- [openapi_schema.md](/home/lyq/xintuoyin-KLCLAB/backend/tests/api_contract_results/openapi_schema.md)

## 3. 真实服务烟测结果

测试环境：

- 后端：`http://127.0.0.1:8000`
- 前端：`http://127.0.0.1:5173`
- 启动脚本：[restart_services.sh](/home/lyq/xintuoyin-KLCLAB/restart_services.sh)

### 3.1 后端核心接口

本次实测通过的接口：

| 接口 | 结果 | 备注 |
| --- | --- | --- |
| `GET /openapi.json` | `200` | OpenAPI 可访问 |
| `GET /api/history/list?page=1&size=10` | `200` | 返回新分页结构 |
| `GET /api/chat/{conversation_id}/thinking?message_index=0` | `200/404` | 成功时返回文本流，不存在时返回统一错误结构 |
| `GET /api/feedback/list?feedback_type=点赞&page=1&size=10` | `200` | 返回新反馈结构 |
| `GET /api/kb/list?page=1&size=10` | `200` | 返回分页知识库列表 |
| `GET /api/db/select_options?question=我们公司的总员工是多少` | `200` | 返回显式候选表 |
| `POST /api/kb/create` | `200` | 成功创建联调用测试知识库 |
| `POST /api/kb/{id}/upload` | `200` | 成功上传 `old.txt` |
| `POST /api/kb/update (confirm=false)` | `200` | 成功返回预览结果，且未提前改动真实文件 |
| `GET /api/kb/{id}/files` | `200` | 预览后仍仅返回 `old.txt` |
| `POST /api/kb/update (confirm=true)` | `200` | 成功完成删除旧文件并上传 `new.txt` |
| `DELETE /api/kb/{id}` | `200` | 成功清理联调测试库 |

### 3.2 前端页面入口

本次实测通过的页面：

| 页面 | 结果 | 备注 |
| --- | --- | --- |
| `/` | `200` | 首页壳正常 |
| `/ai/chat` | `200` | AI 聊天页面入口正常 |

### 3.3 知识库联调结果

本次额外验证了前端知识库管理页最关键的“预览后确认提交”链路：

- 创建知识库成功
- 上传 `old.txt` 成功
- 调用 `confirm=false` 预览时，返回 `preview: true` 和 `pending.confirm_required: true`
- 预览后再次读取文件列表，真实文件仍只有 `old.txt`
- 调用 `confirm=true` 后，文件列表切换为 `new.txt`
- 最后删除测试知识库成功

### 3.4 前端构建

命令：

```bash
cd /home/lyq/xintuoyin-KLCLAB/frontend
npm run build
```

结果：

- 构建通过
- 无编译错误
- 仅存在 Vite chunk size 警告，不影响交付

## 4. 本轮重点验证项

### 4.1 TODO 改造点回归

| 项目 | 结论 |
| --- | --- |
| OpenAPI 参数描述 | 已补齐 |
| 历史/反馈/知识库列表分页 | 已生效 |
| 创建知识库移除 `category` | 已生效 |
| 更新知识库支持预览、同次上传和删除 | 已生效 |
| 历史列表补充最后一轮问答和用户 `record_id/user_id/ip_address` | 已生效 |
| 反馈列表改为 `user`、`feedback_type`、`times` 嵌套结构 | 已生效 |
| 数据库显式选择接口 | 已上线 |

### 4.2 对话与思考流式契约回归

| 项目 | 结论 |
| --- | --- |
| `/api/chat` 仅支持 SSE | 已生效 |
| `/api/chat` 不再输出 `thinking` 事件 | 已生效 |
| `/api/chat` 回答流剥离 `<think>...</think>` | 已生效 |
| `/api/chat/{conversation_id}/thinking` 仅支持文本流 | 已生效 |
| 思考接口优先返回工具调用过程 | 已生效 |
| 无工具过程时回退到 `<think>` 内容 | 已生效 |
| 无工具过程且无 `<think>` 时返回空文本流 | 已生效 |
| 会话/轮次不存在时返回 `404` | 已生效 |

### 4.3 JSON 请求体规范回归

| 项目 | 结论 |
| --- | --- |
| 无文件 `/api/chat` 支持 JSON 请求体 | 已生效 |
| 无截图 `/api/chat/feedback` 支持 JSON 请求体 | 已生效 |
| `/api/kb/create` 支持 JSON 请求体 | 已生效 |
| 无文件 `/api/kb/update` 支持 JSON 请求体 | 已生效 |
| `/api/kb/{id}/delete_file` 支持 JSON 请求体 | 已生效 |
| 带文件链路仍兼容 multipart | 已生效 |
| `/api/kb/{id}/delete_file` 在文件不存在时返回 `404` | 已生效 |

### 4.4 数据库显式选择接口说明

`/api/db/select_options` 当前已满足前端显式选表需要：

- 返回 `selected_tables`
- 返回全部 `options`
- 每项带 `table_comment`
- 每项带 `column_comments`
- 当模型选表失败时，会回退到关键词匹配逻辑，避免前端拿到空推荐

## 5. 风险与说明

- `/api/chat` 的最终回答质量仍取决于你当前部署的模型服务，这部分不属于本轮前端管理页烟测重点
- 前端生产构建体积仍偏大，后续可以再做按页拆包
- 数据库显式选表接口已经具备兜底，但在超大库场景下，推荐精度仍受模型和表注释质量影响

## 6. 结论

当前后端文档、接口契约和前端依赖的核心管理功能已对齐。就本轮维护范围而言：

- 后端文档已更新到当前实现
- 契约测试 `76/76` 全通过
- 前端构建通过
- 前后端真实联机烟测通过
- 知识库“预览更新 -> 确认提交”流程通过

可继续用于前端联调和文档交付。
