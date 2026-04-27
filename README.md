# 研发猫 AI 系统

企业 AI 助手平台，集成对话问答、知识库检索、知识图谱、反馈管理等能力。

---

## 功能特性

- **AI 对话**：支持多轮对话、流式输出、思考过程展示、联网搜索、用户主动中断、并发控制（同会话不可并发请求）
- **知识库（RAG）**：基于 Milvus + bge-small-zh 的语义检索；按租户隔离；支持创建者保护、使用人授权
- **知识图谱**：文件上传 → 实体/关系自动抽取 → 可视化展示 + 编辑；图谱 ID 可绑定到对话上下文
- **多模态文件**：对话/知识库支持 `.pdf .doc .docx .ppt .pptx .xls .xlsx .txt .md .csv .png .jpg .jpeg .bmp .gif`
  - 旧版 Office 自动通过 LibreOffice 转换
  - 图片走 Qwen3.5 原生多模态识别
- **反馈管理**：点赞/点踩、原因分类、截图上传、管理端审核处理、批量删除
- **对话日志**：历史搜索（含 question/answer 全文）、命中跳转、xlsx 导出
- **管理端**：独立 `/api/admin/*` 路由（无 Token），数据库连接管理、知识库全租户视图、反馈/日志管理
- **多租户**：基于甲方 `t_staff.TENANT_ID` 自动隔离知识库、对话、反馈

---

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11、FastAPI、uvicorn、LangGraph、LangChain |
| 知识图谱后端 | Flask 3（通过 a2wsgi 挂载到 FastAPI 同进程） |
| 前端 | Vue 3 + Vite |
| 大模型 | Qwen3.5-27B（vLLM 部署，端口 62272，原生多模态） |
| 向量库 | milvus-lite（嵌入式）+ bge-small-zh-v1.5 |
| 对象存储 | MinIO |
| 业务数据库 | MySQL（甲方提供） |
| 用户认证 | Redis（甲方提供，token 存储） |
| 文件解析 | docling、pypdf、openpyxl、LibreOffice headless |
| 依赖管理 | pixi（conda-forge + pypi 混合） |

---

## 系统要求

- **OS**：Linux x86_64
- **Python**：3.11（pixi 自动管理，不用手装）
- **GPU**：CUDA 设备（运行 vLLM、embedding、安全检查所需）
- **系统包**（部署目标机器需要）：
  ```bash
  apt install libreoffice-core libreoffice-writer libreoffice-impress libreoffice-calc
  ```
- **外部服务**：vLLM 服务（默认 `http://127.0.0.1:62272/v1`）、甲方 MySQL/Redis

---

## 快速开始

### 1. 克隆并安装依赖

```bash
git clone <repo-url> xty
cd xty
pixi install        # 装好所有 conda + pypi 依赖
```

### 2. 配置环境变量

主要配置在 `backend/script/setting.sh`，按需修改：

```bash
# 关键变量
export DB_MYSQL_HOST="183.69.138.62"        # 甲方 MySQL
export DB_MYSQL_PORT=33666
export DB_MYSQL_USER="hagongda"
export DB_MYSQL_PASSWORD="..."
export DB_MYSQL_NAME="r_d_test"

export PARTNER_REDIS_HOST="183.69.138.62"   # 甲方 Redis（用户认证）
export PARTNER_REDIS_PORT=6800
export PARTNER_REDIS_PASSWORD="..."
export PARTNER_REDIS_DB=1

export OPENAI_API_BASE="http://127.0.0.1:62272/v1"  # vLLM
export CHAT_MODEL_NAME="Qwen3.5-27B"

export KL_MILVUS_URI="${PROJECT_ROOT}/data/milvus/klclab_milvus.db"
export RAG_EMBED_MODEL="BAAI/bge-small-zh-v1.5"
export MILVUS_EMBED_DIM=512
```

### 3. 一键启动

```bash
bash scripts/start.sh
```

会依次启动：

| 服务 | 端口 | 说明 |
|---|---|---|
| MinIO | 9000 / 9001 | 对象存储 + Web 控制台 |
| 后端（FastAPI + Flask 图谱）| 8000 | 业务 API + 图谱接口 |
| 前端（Vite dev）| 5173 | Vue 应用 |

启动成功提示：

```
=============================
启动完成！
前端: http://localhost:5173
后端: http://localhost:8000
日志: tail -f data/logs/backend.log
=============================
```

### 4. 验证

```bash
curl -s http://127.0.0.1:8000/api/config/enums         # xty 后端
curl -s http://127.0.0.1:8000/api/health               # 图谱（同端口）
curl -s http://127.0.0.1:9000/minio/health/live        # MinIO
curl -s http://127.0.0.1:5173                          # 前端
```

浏览器打开：`http://localhost:5173`

### 5. 停止服务

```bash
bash scripts/stop_all.sh
```

---

## 单独启动 / 调试

`pixi.toml` 里定义了多个独立 task：

```bash
pixi run start            # 一键启动（同 scripts/start.sh）
pixi run stop             # 一键停止
pixi run start-backend    # 仅启动后端 8000
pixi run start-minio      # 仅启动 MinIO
pixi run dev-frontend     # 仅启动前端 dev server
pixi run build-frontend   # 前端打包

# 调试
pixi run graph-standalone # 单独启动图谱 Flask 5002（已挂到 8000，平时不用）
pixi run check-soffice    # 验证系统已装 LibreOffice
```

---

## 项目结构

```
xty/
├── backend/                      # FastAPI 后端
│   ├── app.py                    # 主应用入口（含 WSGI 挂载图谱、3000+ 行业务路由）
│   ├── agent/                    # LangGraph Agent 实现（chat/RAG/SQL/web 工具）
│   ├── services/                 # 服务层
│   │   ├── kb_service.py         # 知识库
│   │   ├── milvus_service.py     # 向量检索
│   │   ├── storage_service.py    # MinIO 封装
│   │   ├── kb_file_parser.py     # 文件解析（含 LibreOffice、Qwen3.5 多模态）
│   │   ├── user_auth.py          # Redis token + MySQL 部门
│   │   └── db_registry.py        # 业务数据库连接池
│   ├── utils/                    # 工具：DB、prompt、规范化
│   ├── config.py                 # 全局配置
│   └── script/setting.sh         # 环境变量入口
├── frontend/                     # Vue 3 前端
│   ├── src/api/ai.js             # 与后端的接口封装
│   ├── src/components/           # 组件
│   └── vite.config.js            # /api 代理到后端 8000
├── graph/                        # 知识图谱子项目（Flask，已挂载到主后端）
│   ├── app.py                    # 图谱 Flask 入口（含 /upload、/get_graph、/graph/* 等）
│   ├── modules/Graph/            # 系统内 SQL 图谱
│   ├── modules/xintuoyin/        # 系统外文件抽取图谱
│   └── runtime/                  # 图谱数据存储
├── scripts/                      # 启动脚本
│   ├── start.sh                  # 一键启动（MinIO + 后端 + 前端）
│   ├── start_minio.sh            # MinIO 单独启动
│   └── stop_all.sh               # 停止
├── data/                         # 运行时数据（已 .gitignore）
│   ├── databases.json            # 业务数据库连接清单
│   ├── kb_metadata.json          # 知识库元数据
│   ├── milvus/klclab_milvus.db   # milvus-lite 嵌入式向量库
│   ├── minio/                    # MinIO 数据 + bin
│   └── logs/                     # 服务日志
├── pixi.toml                     # 依赖 + tasks 定义
└── README.md
```

---

## 数据存储说明

| 业务 | 存储 |
|---|---|
| 历史对话 | MinIO `history/<日期>/<conversation_id>.json` |
| 反馈（含 JSON 元数据 + 截图）| MinIO `feedback/<日期>/<feedback_id>/` |
| 知识库文件 | MinIO `kb/<日期>/<kb_name>/` |
| 知识库元数据 | 本地 `data/kb_metadata.json`（内含 tenant_id、creator、users） |
| 知识库向量 | milvus-lite 本地 `data/milvus/*.db` |
| 图谱 JSON | 本地 `graph/runtime/external_workspace/<graphId>.json` |
| 业务数据连接 | 本地 `data/databases.json` |

部署到新机器时只需保留代码 + `data/databases.json`、`data/kb_metadata.json`，运行后会自动初始化其他空目录。

---

## API 入口

- **企业端**：`/api/*`（需要 `accessToken` header，对应甲方 Redis 中的 token）
- **管理端**：`/api/admin/*`（无 Token，独立路由）
- **知识图谱**：`/upload`、`/get_graph`、`/graph/*`、`/external/*`、`/internal-binding/*`（直接走 Flask，前端原路径不变）
- **OpenAPI**：`http://localhost:8000/docs` 自动文档（仅含 FastAPI 部分）
- **Apipost / 接口管理**：导入 `/openapi.json` 即可

---

## 部署到生产环境

### 1. 系统包

```bash
sudo apt update
sudo apt install -y libreoffice-core libreoffice-writer libreoffice-impress libreoffice-calc
```

### 2. 装 pixi（若未安装）

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

### 3. 拉代码 + 装依赖

```bash
git clone <repo-url> /opt/xty
cd /opt/xty
pixi install   # 自动装到 .pixi/，约 11G（含 cuda/torch/onnx）
```

### 4. 配置生产环境变量

修改 `backend/script/setting.sh` 中的 MySQL/Redis/vLLM 地址。

### 5. 启动

```bash
bash scripts/start.sh
```

建议用 `systemd` 管理进程（参考 `scripts/start.sh` 内的命令）。

### 6. 反向代理（可选）

如果生产机器对外只开放一个 80/443 端口，前面挂个 nginx：

```nginx
server {
    listen 80;
    location /api/ { proxy_pass http://127.0.0.1:8000; }
    location /upload { proxy_pass http://127.0.0.1:8000; }
    location /get_graph { proxy_pass http://127.0.0.1:8000; }
    location /graph/ { proxy_pass http://127.0.0.1:8000; }
    location /external/ { proxy_pass http://127.0.0.1:8000; }
    location / { proxy_pass http://127.0.0.1:5173; }   # 或前端 build 后的静态文件
}
```

---

## 常见问题

### 后端起来但文件上传失败

检查 MinIO：

```bash
curl -i http://127.0.0.1:9000/minio/health/live
```

### 知识库检索没结果

可能向量库未初始化。新建一个知识库并上传文件即可触发自动建表。

### 图片识别失败 / 旧版 Office 解析失败

```bash
pixi run check-soffice          # 验证 LibreOffice 装好
curl http://127.0.0.1:62272/v1/models   # 验证 vLLM 跑着
```

### 反馈数据保存在哪

全部在 MinIO `feedback/` 前缀下，包括 JSON 元数据和截图。本地 `data/feedbacks/` 已废弃。

### 切换 vLLM 模型

修改 `backend/script/setting.sh` 的 `CHAT_MODEL_NAME` 和 `OPENAI_API_BASE`，重启后端即可。

### 多个进程占了 8000 端口

```bash
lsof -i :8000 -t | xargs -r kill -9
bash scripts/start.sh
```

### 看日志

```bash
tail -f data/logs/backend.log
tail -f data/logs/frontend.log
```

---

## 与甲方系统的对接

| 对接点 | 说明 |
|---|---|
| 用户认证 | 甲方 Redis (`183.69.138.62:6800` db=1)，key 模式 `system:LOGIN_ENTERPRISE_USER_TOKEN:LOGIN_ENTERPRISE_USER_TOKEN_{token}` |
| 部门/员工 | 甲方 MySQL `t_dept`（树）+ `t_staff` |
| 业务数据查询 | 通过 `/api/admin/db/*` 接口管理多数据库连接，对话 SQL 工具自动选当前激活的 |
| 角色 | 三层：游客（无 token）/ 普通用户 / 企业管理员（roleName="超级管理员"）；管理端走独立路由不验 token |

完整数据结构和对接细节见 `backend/services/user_auth.py` 顶部注释。
