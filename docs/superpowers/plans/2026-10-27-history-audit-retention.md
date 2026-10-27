# 对话审计留存实施计划

**Goal:** 保持接口契约，将用户删除改为个人隐藏，平台继续保留原文。

**Architecture:** 原有 MinIO 历史 JSON 不变，增加按服务器用户身份隔离的隐藏标记。仅个人查询过滤标记，平台保持原文读取。

**Tech Stack:** Python 3.11、FastAPI、现有 MinIO、unittest/httpx；不新增依赖。

## 约束

- 不改任何后端接口路径、参数及响应结构。
- 不改凭据，不重构认证、知识库、SQL 或图谱逻辑。
- 不删除生产业务记录。上线前备份，记录 Git 提交和回滚方法。

## 执行

- [x] 在 `tests/timeout_regressions/test_history_audit_retention.py` 写内存接口回归，先在旧实现上确认目标用例失败。
- [x] 在 `backend/app.py` 增加隔离标记、用户查询过滤，修改用户单/批删除，拆开平台删除实现。
- [x] 运行新回归，覆盖存储失败、跨身份隔离及聊天保存后仍隐藏。
- [x] 比较路由装饰器和参数 AST，运行既有回归；独立评审改动。
- [ ] 提交本次文件，备份生产原文件，检查 SHA 后应用；将修复分支导入原仓库，不重置原工作区。
- [ ] 通过 dlx 重启后端，健康检查与只读检查；记录回滚路径、Git 提交和测试结果。

验证命令使用现有 `/data2/dlx/projects/xty/.pixi/envs/default/bin/python -B`，通过 `XTY_SOURCE_ROOT` 指向隔离代码。测试使用模拟存储并禁止外部网络，不触碰生产 MinIO 对象。
