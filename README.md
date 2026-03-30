# xintuoyin-KLCLAB

## 启动说明

当前项目的运行依赖主要有 3 部分：

- `Conda` 环境：后端运行在 `xtyAgent`
- `MinIO`：对象存储，负责聊天附件、反馈图片、知识库文件
- 业务服务：后端 `FastAPI` + 前端 `Vite`

说明：

- 当前知识库向量存储使用的是 `milvus-lite` 本地数据库文件
- 不需要单独启动 `19530` 的独立 Milvus 服务
- 但必须保证 `MinIO` 已启动，否则文件上传、知识库文件管理、反馈图片等功能会异常

## 1. 进入项目

```bash
cd /home/lyq/xintuoyin-KLCLAB
conda activate xtyAgent
```

## 2. 启动 MinIO

如果机器上还没有准备过 MinIO，可先执行一次：

```bash
./setup_minio_env.sh
```

默认情况下，MinIO 运行目录会放在项目内的：

```bash
/home/lyq/xintuoyin-KLCLAB/.runtime/minio
```

启动 MinIO：

```bash
export MINIO_STORAGE_FULL_THRESHOLD=0
./start_minio.sh
```

如果你不想把运行数据放在项目目录内，可以改环境变量：

```bash
export XTY_RUNTIME_ROOT=/your/runtime/root
./setup_minio_env.sh
./start_minio.sh
```

启动成功后默认地址：

- MinIO API: `http://127.0.0.1:9000`
- MinIO Console: `http://127.0.0.1:9001`
- 默认账号: `minioadmin`
- 默认密码: `minioadmin`

如果 `9000/9001` 已经在监听，说明 MinIO 大概率已经启动：

```bash
ss -ltnp | rg ':(9000|9001)\b'
```

也可以直接检查：

```bash
curl -i http://127.0.0.1:9000/minio/health/live
curl -I http://127.0.0.1:9001
```

## 3. 启动项目

项目主启动命令仍然是：

```bash
./restart_services.sh
```

这个脚本会做两件事：

- 启动后端：`0.0.0.0:8000`
- 启动前端开发服务：通常是 `0.0.0.0:5173`

脚本内部会自动：

- 加载 `conda activate xtyAgent`
- 加载后端配置：
  - [backend/script/setting.sh](/home/lyq/xintuoyin-KLCLAB/backend/script/setting.sh)
  - [backend/script/env.sh](/home/lyq/xintuoyin-KLCLAB/backend/script/env.sh)
- 自动查找 Conda 安装路径，不再强依赖 `/home/lyq/anaconda3/...`

如果默认环境名不是 `xtyAgent`，可以这样启动：

```bash
export XTY_CONDA_ENV_NAME=你的环境名
./restart_services.sh
```

## 4. 启动后验证

### 后端接口

```bash
curl -sS http://127.0.0.1:8000/api/chat/new_session
curl -sS http://127.0.0.1:8000/api/kb/list
```

### 前端页面

浏览器打开：

- `http://127.0.0.1:5173`

如果前端已经启动，还可以验证前端代理到后端是否正常：

```bash
curl -sS http://127.0.0.1:5173/api/chat/new_session
curl -sS http://127.0.0.1:5173/api/kb/list
```

说明：

- 前端默认走 `/api`
- 代理配置在 [frontend/vite.config.js](/home/lyq/xintuoyin-KLCLAB/frontend/vite.config.js)
- 前端 AI 接口封装在 [frontend/src/api/ai.js](/home/lyq/xintuoyin-KLCLAB/frontend/src/api/ai.js)

## 5. 日志位置

- 后端日志：`logs/backend.log`
- 前端日志：`logs/frontend.log`
- 进程记录：`pids.server`

实时查看：

```bash
tail -f logs/backend.log
tail -f logs/frontend.log
```

## 6. 停止服务

`restart_services.sh` 会先杀掉旧的前后端进程再重新拉起。

如果只想手动停止，可参考：

```bash
cat pids.server
kill -9 <backend_pid>
kill -9 <frontend_pid>
```

## 7. 测试命令

### API 合同测试

```bash
cd backend
python tests/run_api_contract_tests.py
```

测试报告：

- [backend/tests/api_contract_results/SUMMARY.json](/home/lyq/xintuoyin-KLCLAB/backend/tests/api_contract_results/SUMMARY.json)

### 轻量系统联调/压测

```bash
cd /home/lyq/xintuoyin-KLCLAB
python backend/tests/light_system_probe.py
```

输出报告：

- [backend/tests/artifacts/light_system_probe_report.json](/home/lyq/xintuoyin-KLCLAB/backend/tests/artifacts/light_system_probe_report.json)
- [backend/tests/artifacts/light_system_probe_report.md](/home/lyq/xintuoyin-KLCLAB/backend/tests/artifacts/light_system_probe_report.md)

这个脚本会覆盖：

- `8000` 后端端口
- `9000/9001` MinIO
- `5173/5174` 前端开发服务
- 前端 `/api` 代理到后端
- 知识库创建、上传、列表、删除闭环

说明：

- 测试报告输出到当前仓库的 `backend/tests/artifacts`
- `5173` 是默认前端端口，`5174` 只作为额外 dev server 探测目标，不是必需实例
- 知识库删除接口使用 `DELETE /api/kb/{id}`，不是 `POST /api/kb/{id}/delete`
- 对话附件上传会优先保留原始文件名；只有同一条消息内出现重名文件时才会追加 `_1`、`_2`

## 8. 常见问题

### 1. 后端起来了，但文件上传失败

优先检查 MinIO：

```bash
curl -i http://127.0.0.1:9000/minio/health/live
```

### 2. 前端能打开，但调用后端失败

检查：

- 前端 dev server 是否启动
- `5173` 是否可访问
- [frontend/vite.config.js](/home/lyq/xintuoyin-KLCLAB/frontend/vite.config.js) 中 `/api` 代理是否指向 `http://127.0.0.1:8000`

### 3. 需要单独启动 Milvus 吗

当前默认不需要。

项目现在使用的是 `milvus-lite` 本地数据库文件，默认路径由 [backend/script/setting.sh](/home/lyq/xintuoyin-KLCLAB/backend/script/setting.sh) 中的 `KL_MILVUS_URI` 控制。

## 9. 路径配置

为了避免强依赖固定机器路径，项目新增了 [runtime_paths.sh](/home/lyq/xintuoyin-KLCLAB/runtime_paths.sh)。

默认规则：

- 运行时根目录：`$PROJECT_ROOT/.runtime`
- MinIO 根目录：`$XTY_RUNTIME_ROOT/minio`
- Milvus Standalone 根目录：`$XTY_RUNTIME_ROOT/milvus`
- Conda 环境名：`xtyAgent`

可覆盖环境变量：

```bash
export XTY_RUNTIME_ROOT=/your/runtime/root
export XTY_MINIO_ROOT=/your/minio/root
export XTY_MILVUS_ROOT=/your/milvus/root
export XTY_CONDA_ENV_NAME=xtyAgent
```

## 最小启动流程

如果只看最短版本，按下面执行：

```bash
cd /home/lyq/xintuoyin-KLCLAB
conda activate xtyAgent
export MINIO_STORAGE_FULL_THRESHOLD=0
./setup_minio_env.sh
./start_minio.sh
./restart_services.sh
curl -sS http://127.0.0.1:8000/api/chat/new_session
curl -sS http://127.0.0.1:5173/api/chat/new_session
```

## 本次回归结果

截至 `2026-03-30`，已在 `main` 分支完成一轮完整回归：

- API 合同测试：`66/66` 通过
- 轻量系统联调/压测：`10/10` critical checks 通过
- 已验证前端首页加载、前端 `/api` 代理、聊天主链路、知识库上传/删除闭环
