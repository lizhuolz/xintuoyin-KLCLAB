# xty 完整配置与部署指南

核查日期：2026 年 10 月 14 日。当前项目：`/data2/dlx/projects/xty`。适用范围：现有 FastAPI 后端、Vue 前端、集成知识图谱、知识库、MySQL、Redis、MinIO、Milvus，以及独立 vLLM 模型服务。

全项目使用 **Pixi 管理 Python 和 Node.js，vLLM 使用独立的 Pixi 环境**。部署顺序为：确认硬件和已有服务 → 准备环境和模型 → 配置连接 → 启动存储与模型服务 → 启动后端和前端 → 验证业务。文中安装、启动、修改配置的命令是供部署时执行的步骤；本次编写指南没有执行这些操作。

所有 `<…>` 都是需要替换的占位符。真实密码、API Key 和用户 Token 不在本指南中展示。

## 1 项目组成和服务关系

| 模块 | 代码或资源位置 | 用途 |
| --- | --- | --- |
| 主后端 | `backend/app.py` | 对话、历史、反馈、知识库、管理接口 |
| AI Agent | `backend/agent/` | 模型调用、SQL、RAG、联网搜索 |
| Vue 前端 | `frontend/` | 企业端和管理端界面 |
| 集成图谱 | `graph/app.py` | 文件图谱、数据库图谱、可视化 |
| 图谱文件抽取 | `graph/modules/xintuoyin/getgraph/main.py` | OCR、文件读取、实体和关系抽取 |
| 图谱数据库模块 | `graph/modules/Graph/backend/` | MySQL 数据图谱 |
| 应用依赖 | `pixi.toml`、`pixi.lock` | Python、Node.js、Conda 和 PyPI 依赖 |
| 前端依赖 | `frontend/package.json`、`frontend/package-lock.json` | Vue、Vite 和 npm 依赖 |
| 后端环境配置 | `backend/script/setting.sh` | 模型、数据库、Redis、RAG 等参数 |
| 业务数据库注册表 | `data/databases.json` | 多数据库连接和当前激活连接 |
| 独立推理环境 | `/data2/dlx/projects/vllm/` | vLLM 和大模型推理 |

调用关系：浏览器请求 Vue/API；后端调用 vLLM 完成生成，调用 MySQL 查询业务数据，调用 Redis 核验企业用户身份，调用 MinIO 存附件与历史，调用 Milvus 存储和检索向量。Flask 图谱通过 `a2wsgi` 挂载到 FastAPI，同进程使用 8000 端口。

**正常集成部署不需要另开一个图谱 5002 服务。** 5002 用于独立调试。项目也没有必须启动的独立 OCR HTTP 服务，OCR 在本地 Python 中执行。

## 2 本机环境快照和待处理问题

以下是核查时的环境，不是新机器的最低硬件要求。

| 项目 | 2026 年 10 月 14 日核查结果 |
| --- | --- |
| 操作系统 | Ubuntu 22.04.4 LTS，Linux x86_64，glibc 2.35 |
| Pixi | 0.67.0 |
| xty Python | 3.11.15 |
| xty Node.js | 22.22.2 |
| vLLM Python | 3.12.13 |
| GPU | `/proc` 可见 8 张 NVIDIA A800-SXM4-80GB |
| NVIDIA 内核驱动 | 535.104.05 |
| 默认 NVML 用户态库 | `nvidia-smi` 报 580.178，与已加载内核驱动不匹配 |
| xty PyTorch | 2.10.0+cu128，`torch.version.cuda` 为 12.8 |
| vLLM 环境 PyTorch | 2.10.0+cu128，`torch.version.cuda` 为 12.8 |
| vLLM | 独立环境中 0.17.1；xty 环境未安装 vLLM |
| 磁盘 | 核查时 `/data2` 使用率 99%，剩余约 47 GiB |
| MySQL | 当日 `183.69.145.186:33666` 认证连接及 `SELECT 1` 成功；库 `r_d_test`，版本 8.4.2 |
| Redis | 当日北京时间约 17:56，`183.69.145.186:6800` TCP 连接约 5 秒后超时 |

当前有两个环境问题需要单独处理：

1. **常规 `nvidia-smi` 失败**，错误为 `Failed to initialize NVML: Driver/library version mismatch`。管理员需要核对 NVIDIA 内核模块与用户态库的安装状态；部署验收应要求常规 `nvidia-smi` 和实际 CUDA 运算正常。轻量导入 PyTorch 成功不能代替 GPU 运算验证。
2. **Python 依赖检查未通过**。`llama-index-core 0.14.20` 要求 `setuptools>=80.9.0`，但当前 Python 元数据报告 `setuptools 69.5.1`；锁文件和 Conda 元数据记录的是 82.0.1。这说明现有环境发生了漂移。应由维护者核对并按锁文件恢复环境，再执行 `pip check`，不能保证单次普通 `pixi install` 就会修复。

大模型本地权重约 55.56 GB。当前磁盘余量不足以无条件再下载一整套同等权重，同时还要给依赖缓存、上传文件和运行数据留空间。已有模型应复用，不要将模型复制进每个消费者项目。

## 3 系统环境与工具准备

### 3.1 操作系统和账号

根 `pixi.toml` 只声明 `linux-64`。优先按当前 Linux x86_64 环境部署；Windows、macOS 不能直接视为已验证的完整部署目标。

用具有项目读写权限的普通服务账号运行应用。Linux 账号、MySQL 连接账号、Redis 认证账号、网页企业用户是不同身份。不要用 `sudo pip install` 或 root 启动应用来解决环境问题。

在 Ubuntu/Debian 上，由管理员安装系统工具：

```bash
sudo apt update
sudo apt install -y \
  git curl tmux util-linux procps iproute2 ca-certificates \
  libreoffice-core libreoffice-writer libreoffice-impress libreoffice-calc \
  poppler-utils
```

| 系统工具 | 用途 |
| --- | --- |
| Bash、curl | 加载配置、脚本、健康检查 |
| `setsid`、`nohup` | 现有后台启动脚本 |
| `ss`、`ps` | 查看端口和进程归属 |
| tmux | `scripts/start_tun.sh` 的 cpolar 会话 |
| LibreOffice / `soffice` | `.doc`、`.ppt`、`.xls` 转换 |
| `pdftotext` / poppler-utils | PDF 文本提取回退 |

RapidOCR 和 Docling 的依赖由 Python 环境提供。Tesseract 不是当前代码已确认的必需系统依赖。NVIDIA 驱动由系统管理员管理，不属于 Pixi 的 Python 包安装步骤。

### 3.2 Pixi 安装

先检查已有版本：

```bash
command -v pixi
pixi --version
```

新机器缺少 Pixi 时，可按 [Pixi 官方安装说明](https://pixi.prefix.dev/latest/installation/) 安装：

```bash
curl -fsSL https://pixi.sh/install.sh | sh
```

安装后重新打开终端，并检查 `pixi --version`。本项目核查使用 0.67.0；正式部署应记录使用的 Pixi 版本，不把不断变化的最新版当成固定复现依据。

## 4 Python 环境和 requirements

### 4.1 哪个依赖文件是完整入口

| 文件 | 适用范围 | 是否足够安装整个项目 |
| --- | --- | --- |
| 根 `pixi.toml` + `pixi.lock` | 主后端、集成图谱、Python 和 Node.js | **完整应用环境入口**；npm 包、系统工具、模型文件和外部服务另行准备 |
| `graph/requirements.txt` | 图谱子项目的部分 Python 包 | 否，只有 9 项 |
| `graph/modules/Graph/backend/requirements.txt` | 仅列 Flask 3.0.3 | 否 |
| `frontend/package.json` + `package-lock.json` | 前端 npm 依赖 | 仅前端 |
| 独立 vLLM 项目的 `pixi.toml` + `pixi.lock` | 推理服务 | 独立环境，不能代替 xty 环境 |

根目录没有另一份完整的 `requirements.txt` 或 `pyproject.toml`。**不要只运行 `pip install -r graph/requirements.txt` 就认为全项目安装完成。** 全部直接依赖的声明见文末附录。

### 4.2 安装 xty 环境

在新部署目录中安装。下列路径换成实际项目位置：

```bash
cd /data2/dlx/projects/xty
export PROJECT_ROOT="$(pwd)"
pixi install --locked
```

`--locked` 会检查清单和锁文件是否一致；不一致时中止。普通 `pixi install` 可能重新解析并更新锁文件。需要更新依赖时，应由维护者完成更新、验证并保留新的锁文件。`--frozen` 与 `--locked` 的检查语义不同，不应为了绕过不一致而随意替换。[Pixi 安装命令说明](https://pixi.prefix.dev/latest/reference/cli/pixi/install/)

环境解释器位置：

```text
<项目目录>/.pixi/envs/default/bin/python
<项目目录>/.pixi/envs/default/bin/node
```

无需另建或激活 Conda 环境。Pixi 已管理 Conda/PyPI 包及项目环境。当前机器的普通 `python` 来自其他 Conda 环境，普通 `node` 是 24.x；都不应替代本项目的解释器。

### 4.3 检查环境

安装后的检查：

```bash
pixi run --locked python --version
pixi run --locked node --version
pixi run --locked python -m pip check
pixi run --locked check-soffice
```

对已经运行的环境做只读检查时，可直接调用解释器，避免普通 `pixi run` 自动调整环境：

```bash
.pixi/envs/default/bin/python -B -c \
  'import sys; print(sys.executable); print(sys.version)'
.pixi/envs/default/bin/python -B -m pip check
.pixi/envs/default/bin/node --version
```

当前 Pixi 也支持 `pixi run --as-is`，它适合使用已有环境，不替代首次安装或依赖一致性检查。

### 4.4 关键 Python 包版本

下表是本机已安装快照，不是建议另行手装的 requirements。精确复现以锁文件为准。

| 包 | 当前安装版本 | 用途 |
| --- | --- | --- |
| FastAPI | 0.135.3 | 主 API |
| Uvicorn | 0.44.0 | ASGI 服务 |
| Flask | 3.0.3 | 图谱 WSGI 应用 |
| a2wsgi | 见锁文件 | Flask 集成 |
| PyMySQL | 1.1.2 | MySQL |
| redis-py | 7.4.0 | Token 查询 |
| OpenAI SDK | 2.31.0 | OpenAI 兼容模型接口 |
| LangChain | 1.2.15 | 模型和工具 |
| LangGraph | 1.1.6 | Agent 工作流 |
| sentence-transformers | 5.4.0 | 本地 embedding |
| Transformers | 4.51.3 | 应用侧模型依赖 |
| PyTorch | 2.10.0+cu128 | 应用侧计算依赖 |
| Docling | 2.91.0 | 文档解析 |
| RapidOCR ONNXRuntime | 1.4.4 | OCR |
| pymilvus | 2.6.12 | 向量库客户端 |
| milvus-lite | 2.5.1 | 本地向量数据库 |
| MinIO Python SDK | 7.2.20 | 对象存储客户端 |
| Pillow | 11.3.0 | 图片处理 |
| Typer | 0.21.2 | 文档解析相关 CLI 依赖 |

`pixi.toml` 对 Pillow、Typer 有明确版本上界，以适配图谱/Docling。不要在已有环境中执行全量 `pip install --upgrade`，也不要把 vLLM 安装到 xty 环境来覆盖 Torch、Transformers。

## 5 CUDA 和 GPU 配置

### 5.1 三层 CUDA 环境

| 层 | 查看方法 | 含义 |
| --- | --- | --- |
| 系统 NVIDIA 驱动 | `nvidia-smi`、`/proc/driver/nvidia/version` | 系统与 GPU 通信的驱动 |
| CUDA Toolkit | `nvcc --version` | 编译 CUDA 程序和部分扩展使用的工具链 |
| Python 包自带 CUDA runtime | `torch.version.cuda` | 当前 PyTorch 构建所用 CUDA 版本 |

`nvidia-smi` 界面中的 CUDA 版本信息不应当作 `nvcc` 或 PyTorch runtime 的安装版本。当前 `nvcc` 不在 PATH，但 PyTorch 的 CUDA runtime 为 12.8。预编译包运行与从源码编译所需条件不同。

锁文件还包含 FAISS 的 CUDA 12.9 相关依赖，因此不能简单把整个项目描述成只有一个“系统 CUDA 12.8”。以各包锁定版本及实际兼容验证为准。

CUDA 12.x 存在同大版本的驱动兼容机制，但有新特性和 PTX/JIT 限制；不能仅凭驱动达到某个最低版本就认定所有 vLLM 算子一定可用。[NVIDIA CUDA 兼容说明](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html)

### 5.2 检查驱动和实际计算

先做系统和包版本检查：

```bash
nvidia-smi
cat /proc/driver/nvidia/version
command -v nvcc
nvcc --version

.pixi/envs/default/bin/python -B - <<'PY'
import torch
print("PyTorch:", torch.__version__)
print("Compiled CUDA:", torch.version.cuda)
PY
```

未安装 Toolkit 时，`command -v nvcc` / `nvcc --version` 无结果或失败并不等同于 PyTorch 不能运行。若需要编译扩展，应按相应包的官方要求准备 Toolkit，而不是盲目追加另一套 CUDA。

管理员恢复驱动后，在确认允许使用的 GPU 上做小规模实际运算验证；将下面的 GPU 编号换成已分配设备：

```bash
CUDA_VISIBLE_DEVICES=<已分配GPU编号> \
  .pixi/envs/default/bin/python -B - <<'PY'
import torch
print("CUDA available:", torch.cuda.is_available())
if not torch.cuda.is_available():
    raise SystemExit("CUDA 不可用")
x = torch.ones(2, device="cuda")
print("Device:", torch.cuda.get_device_name(0))
print("Result:", (x + x).cpu().tolist())
PY
```

上面的 `<已分配GPU编号>` 需要先替换，不能原样执行。看到 `CUDA available: True` 和结果 `[2.0, 2.0]`，才证明这套环境在所选设备上能完成小规模运算；它仍不代表大模型显存容量已经够用。

### 5.3 显存与设备分配

Qwen3.5-27B 的现有本地权重约 55.56 GB。BF16 权重本身就需要较大显存，还需预留 KV cache、激活及并发开销；不能把两张 24 GB 卡当成当前脚本已验证可用的配置。

现有模型脚本使用两张 GPU、`tensor-parallel-size=2`、最长上下文 50000、最大序列数 24、显存利用率 0.9。部署前需要核对两张卡的实际空闲显存和使用权。显存不足时应由维护者综合调整模型精度/量化、上下文长度和并发，而不是只扩大利用率。

`backend/script/setting.sh` 的 `CUDA_VISIBLE_DEVICES=0` 是**应用进程**可见设备，主要可能影响 OCR。vLLM 脚本的 GPU 选择独立配置。RAG embedding 当前为 CPU，不会因为设置了应用 GPU 就自动转成 GPU。

当前常规 `nvidia-smi` 报驱动库不匹配，需先解决这个系统环境问题再安排新 GPU 服务。管理员对共享 GPU 的维护需统一协调，指南不提供自动卸载驱动或重启机器的命令。

## 6 大模型服务和模型文件

### 6.1 模型资源

| 用途 | 当前模型或位置 | 运行方式 |
| --- | --- | --- |
| 对话、SQL、图片理解、图谱抽取 | Qwen3.5-27B | vLLM OpenAI 兼容接口 |
| 主模型本地权重 | `/data/public/model/qwen_xty/Qwen3.5-27B/` | 已存在，含 11 个 safetensors 分片 |
| 知识库 embedding | `/data/public/model/bge-small-zh-v1.5` | 应用进程本地 CPU，512 维 |
| 历史问题 embedding | `BAAI/bge-base-zh-v1.5` | 应用进程本地 CPU，需要模型缓存或联网下载 |
| OCR | RapidOCR / Docling | 本地执行，部分路径可尝试 GPU 后回退 CPU |

迁移时替换机器相关的绝对模型路径，保留模型配置、分片索引、tokenizer 和多模态所需文件；不能只拷贝某一个 safetensors 分片。模型 API 的 `model` 名称必须与 `/v1/models` 中的服务名称一致。

### 6.2 独立 vLLM 环境

```bash
pixi install --locked --manifest-path /data2/dlx/projects/vllm/pixi.toml

/data2/dlx/projects/vllm/.pixi/envs/default/bin/python -B - <<'PY'
import sys
import torch
import importlib.metadata as m
print(sys.version)
print("vLLM:", m.version("vllm"))
print("Torch:", torch.__version__)
print("CUDA:", torch.version.cuda)
PY
```

本机该环境为 Python 3.12.13、vLLM 0.17.1、Torch 2.10.0+cu128、Transformers 4.57.6。xty 应用环境则使用 Python 3.11.15 和 Transformers 4.51.3。两者分开维护，避免依赖互相覆盖。vLLM 含编译扩展，安装时应遵守对应 wheel 与 PyTorch/CUDA 的兼容要求。[vLLM 官方 GPU 安装说明](https://docs.vllm.ai/en/v0.17.1/getting_started/installation/gpu/)

### 6.3 核对已有服务后再启动

先检查端口和模型接口：

```bash
ss -ltnp 'sport = :62272'
curl --noproxy '*' --fail --silent --show-error \
  --connect-timeout 3 --max-time 10 \
  http://127.0.0.1:62272/v1/models
```

需要 API Key 的服务应按其认证方式访问。HTTP 200 还需核对返回的模型 ID，不能只看端口有人监听。

`scripts/start_vllm.sh` 当前实际参数为：

| 参数 | 当前脚本值 |
| --- | --- |
| 推理项目 | `/data2/dlx/projects/vllm` |
| 模型路径 | `/data/public/model/qwen_xty/Qwen3.5-27B/` |
| GPU | `2,3`，脚本注释中的 `4,5` 已不准确 |
| 端口 | `62272` |
| 监听地址 | `0.0.0.0` |
| 对外模型名 | `Qwen3.5-27B` |
| dtype | `bfloat16` |
| tensor parallel | `2` |
| GPU memory utilization | `0.9` |
| max model len | `50000` |
| max num seqs | `24` |
| tool call parser | `hermes`，启用 auto tool choice |

确认当前 GPU、模型目录、端口、驱动都适用，且没有应复用的服务后，才执行该启动脚本：

```bash
bash scripts/start_vllm.sh
```

`scripts/start.sh` 只检查 62272，不会替你启动 vLLM。旧模型脚本绑定全网卡；本机部署可在维护启动配置时改成环回地址，跨机部署则应配置实际地址与访问控制。

### 6.4 共享服务目录的差异

上级 `AGENTS.md` 登记的 `/data2/dlx/projects/vllm/qwen3-services` 当前不存在。实际 sibling 项目有 `scripts/`，其中默认值为：

| 实际脚本 | 默认端口 | 默认模型 |
| --- | --- | --- |
| `serve-embedding.sh` | 8100 | Qwen3-Embedding-4B |
| `serve.sh` | 8200 | Qwen3-Reranker-4B |
| `serve-llm.sh` | 8300 | Qwen2.5-7B-Instruct |

这些脚本的默认模型路径核查时不存在。它们不等同于 xty 当前的 62272/Qwen3.5-27B 服务，也没有成为当前 RAG 的远程 embedding/reranker 依赖。不要照旧登记直接执行不存在的 `qwen3-services/start.sh`，或在未配置模型目录前执行 `start-all`。

## 7 配置如何生效

### 7.1 主要配置入口

```text
启动 shell 环境
  → source backend/script/setting.sh
  → 启动 Python
  → data/databases.json 当前 active 数据库覆盖 DB_MYSQL_* 和 SQL 连接常量
  → 各模块读取各自环境变量/代码默认值
```

`setting.sh` 当前会根据自身文件路径计算 `SETTING_DIR`、`BACKEND_ROOT`、`PROJECT_ROOT`，因此不依赖启动前手工填写项目根路径。它也会清除小写代理变量，并设置本地服务的 `NO_PROXY/no_proxy`。

要区分以下几种情况：

- 大多数 `export VAR=固定值` 会覆盖启动前导出的同名变量。
- `${VAR:-默认值}` 的写法会保留已有非空变量，例如 `RAG_EMBED_MODEL`、`KL_MILVUS_URI`。
- 正常脚本没有自动加载 `backend/.env`；单独创建该文件不会生效。
- `后端参数配置文档.yaml` 是参考清单，不是程序加载的配置文件。
- `data/databases.json` 的 active 连接会覆盖聊天侧 MySQL 环境变量。只修改 `setting.sh` 的 IP 可能被注册表重新覆盖。
- 数据库图谱使用 `DB_*`，聊天和用户资料查询使用 `DB_MYSQL_*`，两套变量独立。
- 配置通常在模块导入时读取。修改配置文件后，已运行的进程不会自动全部重新加载；要核对真正监听端口的进程并由其管理者重启。

### 7.2 配置参考模板

下面只展示连接结构，**不是程序会自动读取的新配置文件**。实际按原配置入口修改，或在手动启动时先加载 `setting.sh`，再导出要覆盖的值。密码若包含 `$`、`#`、`!` 等字符，Shell 字面量应使用单引号。

```bash
# 聊天、SQL 和用户资料辅助查询
export DB_MYSQL_HOST='183.69.145.186'
export DB_MYSQL_PORT=33666
export DB_MYSQL_USER='hagongda'
export DB_MYSQL_PASSWORD='<MYSQL_PASSWORD>'
export DB_MYSQL_NAME='r_d_test'

# 数据库图谱；若需同一库，要与实际 active 配置保持一致
export DB_HOST="$DB_MYSQL_HOST"
export DB_PORT="$DB_MYSQL_PORT"
export DB_USER="$DB_MYSQL_USER"
export DB_PASSWORD="$DB_MYSQL_PASSWORD"
export DB_NAME="$DB_MYSQL_NAME"
export DB_CHARSET='utf8mb4'

# 企业用户 Token 存储
export PARTNER_REDIS_HOST='183.69.145.186'
export PARTNER_REDIS_PORT=6800
export PARTNER_REDIS_PASSWORD='<REDIS_PASSWORD>'
export PARTNER_REDIS_DB=1

# 模型接口；服务端若无 Key 验证，客户端仍可按服务约定设置占位值
export OPENAI_API_BASE='http://127.0.0.1:62272/v1'
export OPENAI_API_KEY='<MODEL_API_KEY>'
export CHAT_MODEL_NAME='Qwen3.5-27B'
export DB_LLM_BASE_URL="$OPENAI_API_BASE"
export DB_LLM_MODEL_NAME="$CHAT_MODEL_NAME"
export DB_LLM_API_KEY="$OPENAI_API_KEY"

# 对象存储；endpoint 不带 http:// 前缀
export MINIO_ENDPOINT='127.0.0.1:9000'
export MINIO_ACCESS_KEY='<MINIO_ACCESS_KEY>'
export MINIO_SECRET_KEY='<MINIO_SECRET_KEY>'
export MINIO_SECURE=false
export MINIO_BUCKET_NAME='xintuoyin-data'

# 知识库本地 Milvus Lite
export KL_MILVUS_URI="$PROJECT_ROOT/data/milvus/klclab_milvus.db"
export KL_MILVUS_DB_NAME='default'
export KL_MILVUS_TOKEN=''
export RAG_EMBED_MODEL='/data/public/model/bge-small-zh-v1.5'
export RAG_EMBED_DEVICE='cpu'

# 文件图谱抽取
export EXTERNAL_GRAPH_API_BASE="$OPENAI_API_BASE"
export EXTERNAL_GRAPH_MODEL_PATH="$CHAT_MODEL_NAME"
export EXTERNAL_GRAPH_EXTRACT_TIMEOUT_SECONDS=180
export FLASK_DEBUG=false
```

不要把真实凭据放入可分享的文档或命令参数。含凭据的配置和数据库注册表应按私密文件管理，并避免提交到公共仓库。

## 8 MySQL 配置和验证

### 8.1 两套连接配置

| 使用方 | 变量/配置 | 来源 |
| --- | --- | --- |
| SQL 问答 | `DB_MYSQL_*`，以及 active 注册表 | `setting.sh`、`data/databases.json`、`db_registry.py` |
| 公司名、部门、员工查询 | `DB_MYSQL_*` | `backend/services/user_auth.py` |
| 数据库图谱 | `DB_HOST/PORT/USER/PASSWORD/NAME/CHARSET` | `graph/modules/Graph/backend/config.py` |

当前连接目标为 `183.69.145.186:33666/r_d_test`，MySQL 账号是 `hagongda`。密码在现有私密配置中，不是网页用户密码。图谱模块还有代码默认凭据；部署时应使用明确配置覆盖并保持一致，避免只改一侧。

`data/databases.json` 结构示意：

```json
{
  "active_id": "db_default",
  "databases": [
    {
      "id": "db_default",
      "name": "r_d_test",
      "host": "183.69.145.186",
      "port": 33666,
      "user": "hagongda",
      "password": "<MYSQL_PASSWORD>"
    }
  ]
}
```

### 8.2 用 active 配置只读试连

在项目根目录执行。程序从配置文件读取密码，不输出密码：

```bash
.pixi/envs/default/bin/python -B - <<'PY'
from pathlib import Path
import json
import pymysql

cfg = json.loads(Path("data/databases.json").read_text())
item = next(x for x in cfg["databases"] if x["id"] == cfg["active_id"])
conn = pymysql.connect(
    host=item["host"], port=int(item["port"]), user=item["user"],
    password=item["password"], database=item["name"],
    connect_timeout=5, read_timeout=5, write_timeout=5,
    charset="utf8mb4",
)
try:
    with conn.cursor() as cur:
        cur.execute("SELECT 1, DATABASE(), VERSION()")
        print(cur.fetchone())
finally:
    conn.close()
PY
```

TCP 连接成功、账号认证成功、能执行查询，是不同层次的验证。MySQL 成功不代表同 IP 的 Redis 端口也能访问。

## 9 Redis 和用户权限

### 9.1 Redis 连接参数

| 项目 | 当前配置 |
| --- | --- |
| Host | `183.69.145.186` |
| Port | `6800` |
| Password | `PARTNER_REDIS_PASSWORD`，值省略 |
| Database | 逻辑数据库编号 `1`，不是 MySQL 风格的库名 |
| Username | 当前客户端未传用户名，按默认用户 `default` 进行密码认证 |
| 超时 | 连接 5 秒，读取 5 秒 |

Redis 支持仅密码的 `AUTH` 形式；若服务端要求自定义 ACL 用户，当前代码需要增加用户名配置支持，单独导出一个未被代码读取的变量不会生效。[Redis AUTH 文档](https://redis.io/docs/latest/commands/auth/)。逻辑库使用编号选择。[Redis SELECT 文档](https://redis.io/docs/latest/commands/select/)

### 9.2 accessToken 的实际流程

```text
浏览器 localStorage.token
  → 如果没有，使用 VITE_DEV_TOKEN
  → 请求头 accessToken
  → 后端 get_user_by_token()
  → Redis 查询 key 前缀 + Token
  → JSON 用户对象中的用户、员工、租户、角色
  → 具体 API 的权限判断
```

Redis key 前缀为：

```text
system:LOGIN_ENTERPRISE_USER_TOKEN:LOGIN_ENTERPRISE_USER_TOKEN_
```

当前项目没有独立的账号密码登录、Token 签发、刷新或写入 Redis 的实现。开发 Token 的最初签发来源尚未确认。仅浏览器保存了字符串，并不代表后端核验已经通过。

Redis 查询异常、记录不存在或 JSON 无法解析时，后端不能从 Redis 取得身份；请求会按游客处理。成功结果有 300 秒进程内缓存。角色名称为“超级管理员”时映射为 `enterprise_admin`，其他解析成功的身份映射为 `user`。

2026-10-23 权限更新：AI SQL 工具使用服务端可信身份，业务查询强制限制当前租户；普通员工按有效员工项目关联过滤，企业管理员可访问本租户全部有效项目。两类角色仍使用相同的业务表白名单，非项目表尚无工资、字段或部门等更细权限。详见同目录《权限合并审查_20261023.md》。知识库和图谱未在本次完善；`/api/admin/*` 当前仍缺少统一管理员权限检查，应部署在有访问控制的管理入口内，更换身份数据源或增加 SQL 隔离不会自动补齐这些授权规则。

### 9.3 分层测试 Redis

先不发送密码，仅检查 TCP：

```bash
.pixi/envs/default/bin/python -B - <<'PY'
import socket
with socket.create_connection(("183.69.145.186", 6800), timeout=5):
    print("TCP connected")
PY
```

端口可达后，在已授权的 Redis 目标上验证密码和逻辑库。下例需要有控制终端，交互输入密码，不将密码放进进程参数；不要直接作为无终端的定时任务运行：

```bash
.pixi/envs/default/bin/python -B - <<'PY'
from getpass import getpass
import redis
client = redis.Redis(
    host="183.69.145.186", port=6800, db=1,
    username=None, password=getpass("Redis 密码: "),
    socket_connect_timeout=5, socket_timeout=5,
    decode_responses=True,
)
try:
    print("PING:", client.ping())
finally:
    client.close()
PY
```

`PING: True` 证明这次客户端认证、选择逻辑库和命令执行成功，仍需使用实际有效 Token 验证业务身份。TCP 超时发生在密码验证之前；`NOAUTH` 表示已经到达 Redis、需要认证；`WRONGPASS` 则需要核对用户名、密码或 ACL 状态。

### 9.4 是否能改成 MySQL 验证 Token

当前可见的 MySQL 表结构有用户和角色表，但未发现可直接核验现有登录 Token 的会话表。不能直接把 Redis 查询替换成用户表查询就继续接受旧 Token。

若要迁移认证，需要可信的 Token→用户会话记录，包括租户、有效期和注销状态，并由登录签发方同步到 MySQL；也可对接该登录方的验证接口。若另建 xty 登录，则需要新增密码验证、Token 签发、过期和注销流程。当前代码尚未做这项迁移。

## 10 MinIO 对象存储

| 项目 | 当前代码配置 |
| --- | --- |
| API endpoint | `127.0.0.1:9000`，值不带 URL scheme |
| 控制台端口 | `9001` |
| 桶 | `xintuoyin-data` |
| API TLS | `MINIO_SECURE=false` |
| 应用凭据 | `MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY` |
| 服务端凭据 | `MINIO_ROOT_USER`、`MINIO_ROOT_PASSWORD` |
| 二进制 | `data/minio/bin/minio` |
| 服务数据 | `data/minio/storage` |
| 日志 | `data/logs/minio.log` |

Python 的 `minio` 包是 SDK，不是 MinIO Server。`pixi install` 不会代替安装服务端二进制。当前 `start_minio.sh` 在二进制不存在时从官方地址下载未锁定版本；可复现部署应预先准备并记录版本与校验值。

现脚本将服务端 root 用户和密码写为固定值，并监听所有网卡；导出自定义 `MINIO_ROOT_*` 再运行该脚本会被覆盖。需要自定义凭据时，先准备服务端二进制，再使用受控启动命令或由维护者调整脚本，同时让应用访问凭据与服务端一致。

单机手动启动示例，适用于新部署且端口未被占用的情况：

```bash
export MINIO_ROOT_USER='<MINIO_ROOT_USER>'
read -r -s -p 'MinIO 服务端密码: ' MINIO_ROOT_PASSWORD
echo
export MINIO_ROOT_PASSWORD
export MINIO_ACCESS_KEY="$MINIO_ROOT_USER"
export MINIO_SECRET_KEY="$MINIO_ROOT_PASSWORD"

mkdir -p "$PROJECT_ROOT/data/minio/storage"
"$PROJECT_ROOT/data/minio/bin/minio" server \
  "$PROJECT_ROOT/data/minio/storage" \
  --address 127.0.0.1:9000 --console-address 127.0.0.1:9001
```

需要把同一应用凭据配置到后端启动终端。服务端 root 身份可用作初始部署验证；长期运行也可配置具有本项目桶权限的专用访问身份。后端可能自动创建缺失的桶，访问身份要满足实际操作权限。

健康检查：

```bash
curl --noproxy '*' --fail --silent --show-error \
  --connect-timeout 3 --max-time 10 \
  http://127.0.0.1:9000/minio/health/live
```

健康接口成功不证明应用凭据或桶权限正确；需再用项目测试附件核查读写。若外部浏览器需要直接访问预签名对象 URL，`MINIO_ENDPOINT` 的主机名和 TLS 设置必须适合实际访问拓扑，不能把服务器的 `127.0.0.1` 当成外部客户端地址。

## 11 Milvus 与 embedding

### 11.1 知识库向量存储

当前默认使用 **Milvus Lite 本地文件**：

```bash
export KL_MILVUS_URI="$PROJECT_ROOT/data/milvus/klclab_milvus.db"
export KL_MILVUS_TOKEN=''
export KL_MILVUS_DB_NAME='default'
export MILVUS_COLLECTION='klclab_kb_chunks'
export RAG_EMBED_MODEL='/data/public/model/bge-small-zh-v1.5'
export RAG_EMBED_DEVICE='cpu'
```

本地模式不需要为知识库另起 19530 的 Milvus Server。目录需要可写，数据库文件要持久化。未加载 `setting.sh` 时，Python 裸默认 URI 是 `/tmp/klclab_milvus.db`，不适合作为持久部署的隐含数据位置。

若改成远程 Milvus，`KL_MILVUS_URI` 改为服务端 URI，并按服务配置填写 Token、数据库、集合。部署模式、索引支持与版本限制应按对应 Milvus 文档验证。[Milvus Lite 官方说明](https://milvus.io/docs/milvus_lite.md)

### 11.2 模型与向量维度

当前 bge-small-zh-v1.5 为 512 维，运行设备为 CPU。源码实际从 embedding 模型取得维度；`MILVUS_EMBED_DIM` 虽在脚本中声明，却没有被当前 Python 配置读取。

更换 embedding 模型时，需要新建适当集合或重建向量索引，确保模型与既有向量一致。不能只改模型路径继续混用原集合。应先保留现有数据与元数据，并明确重新索引范围。

### 11.3 历史问题推荐是另一套连接

`backend/agent/utils.py` 使用独立的：

```text
MILVUS_HISTORY_URI 默认 http://127.0.0.1:19530
QUERY_EMBEDDING_MODEL 默认 BAAI/bge-base-zh-v1.5
集合 user_query_history
设备 CPU
```

知识库 Lite 可用，不代表历史推荐的 19530 服务可用。如果不希望额外维护服务，可以在该部署中评估采用独立的 Lite 文件 URI：

```bash
export MILVUS_HISTORY_URI="$PROJECT_ROOT/data/milvus/history.db"
```

LangChain Milvus 支持文件 URI 的 Lite 用法，但这项配置仍需在本项目实际推荐流程中验收，避免和知识库集合混用。[LangChain Milvus 文档](https://docs.langchain.com/oss/python/integrations/vectorstores/milvus)

## 12 知识图谱和文件解析

### 12.1 正常启动与接口

主后端 8000 同时提供图谱页面和图谱 API，主要路径为：

```text
/
/upload
/get_graph
/graph/*
/external/*
/internal-binding/*
/api/health
```

这些路径与企业 `/api/*` 共用主后端，但并不是所有图谱路径都带 `/api` 前缀。图谱独立调试使用 `pixi run graph-standalone`；不得用旧 `modules/xintuoyin/app.py` 代替当前集成入口，它还保留旧机器路径。

### 12.2 图谱模型参数

| 环境变量 | 当前默认或用途 |
| --- | --- |
| `EXTERNAL_GRAPH_API_BASE` | `http://127.0.0.1:62272/v1` |
| `EXTERNAL_GRAPH_MODEL_PATH` | `Qwen3.5-27B`；实际是 API 的 model 名称 |
| `EXTERNAL_GRAPH_EXTRACT_TIMEOUT_SECONDS` | 180 秒，抽取子进程时限 |
| `GETGRAPH_API_BASE` | 若设置，会覆盖传给抽取器的 `--api_base` |
| `GETGRAPH_LLM_TIMEOUT` | 120 秒，单次模型调用 |
| `GETGRAPH_LLM_RETRIES` | 3 次 |
| `GETGRAPH_LLM_RETRY_SLEEP_SECONDS` | 2 秒递增等待基数 |
| `GETGRAPH_CATEGORY_MAX_TOKENS` | 64 |
| `GETGRAPH_EXTRACTION_MAX_TOKENS` | 4096 |
| `IMAGE_OCR_GPU_MIN_FREE_MB` | 4096，OCR GPU 空闲显存阈值 |
| `IMAGE_DIRECT_OCR_MIN_TEXT_LEN` | 20，判断直接 OCR 文本是否足够 |
| `GRAPH_CACHE_TTL_SECONDS` | 60 秒 |
| `FLASK_DEBUG` | Pixi 激活设为 false |

抽取器当前 API Key 是源码中的固定占位值，**没有读取 `OPENAI_API_KEY`**。若改为必须使用真实 API Key 的模型服务，仅改 URL 不够，需要维护者修正抽取器的密钥配置读取。

### 12.3 文件解析链和超时

上传文件后，图谱子进程继承后端的 Python 解释器，读取文本/表格，尝试 OCR，再调用模型分类、抽取实体关系，生成 JSON。另有 MinIO staging 存储步骤。

| 文件/功能 | 知识库/聊天解析 | 图谱抽取 |
| --- | --- | --- |
| TXT、Markdown、CSV | 本地读取/表格处理 | 文本/表格路径 |
| DOCX | Python 文档解析依赖 | Docling 等文档路径 |
| PPTX | python-pptx | Docling 等文档路径 |
| XLSX | openpyxl / pandas | 表格抽取路径 |
| DOC、PPT | 显式调用 LibreOffice 转换 | 没有同样的显式转换分支；需先转换或确认所用 Docling 的支持范围 |
| XLS | 显式调用 LibreOffice 转换 | 显式调用 `soffice` 转换 |
| PDF | pypdf，必要时 `pdftotext` 等回退 | pypdfium2、Docling、OCR 等路径 |
| 图片 | 通过支持多模态的主模型理解 | RapidOCR / Docling 本地 OCR |

模型 120 秒超时、重试时间、整个子进程 180 秒时限、对象存储等待和反向代理超时是不同限制。前端普通 Axios 请求的默认超时为 15 秒，图谱自身 fetch 路径需另看实现。解析超时不应仅靠增加其中一个参数就认定解决。

调试顺序：先用小 TXT/Markdown → 再用小 DOCX/XLSX → 再测扫描 PDF/图片 → 最后测大文件。一次成功的 `/api/health` 不代表文件解析、数据库和模型链路都通过。

## 13 前端环境与配置

### 13.1 Node.js 和 npm 依赖

当前锁定 Vite 7.0.4、Vue 3.5.17。Vite 和 plugin-vue 的 `engines.node` 为 `^20.19.0 || >=22.12.0`；本项目 Pixi 又限制 Node.js `>=20,<23`，所以可采用满足范围的 Node 20.19+ 或 Node 22.12+，当前项目 Node 22.22.2 满足要求。

在新部署或允许重建前端依赖时执行：

```bash
cd "$PROJECT_ROOT/frontend"
pixi run --locked npm ci
cd "$PROJECT_ROOT"
```

`npm ci` 使用 `package-lock.json`，并重建当前目录的 `node_modules`。正式部署优先采用锁文件；已有运行环境不要未经安排就重装依赖。现有 Pixi 的 `install-frontend` task 使用 `npm install`，可能改变锁文件。

### 13.2 前端变量

| 变量 | 用途 |
| --- | --- |
| `VITE_API_BASE` | API base，默认 `/api` |
| `VITE_DEV_TOKEN` | 浏览器没有 `localStorage.token` 时的开发 Token |
| `VITE_DEEPSEEK_BASE_URL` | 代码定义了备用地址，未找到当前实际消费者 |

当前 `frontend/.env.local` 有开发 Token。Vite 的 `VITE_*` 会进入客户端环境/构建结果，不可放数据库密码或模型服务端秘密。正式部署应使用实际企业用户的登录凭证，开发 Token 不能当作所有用户的公共身份。退出登录当前只清浏览器存储，后续请求还可能回退到开发 Token。

Vite 配置修改或环境变量修改后，要重启 dev server；静态部署的变量需要重新构建。

### 13.3 开发代理和图谱访问

`frontend/vite.config.js` 目前只代理：

```text
/api → http://127.0.0.1:8000
```

开发前端监听 5173，后端监听 8000。图谱 `/upload`、`/graph/*` 等路径不能假定已经被 Vite 代理。通过统一入口访问 Vue 和图谱时，应完整配置代理路由。

构建命令：

```bash
pixi run --locked build-frontend
```

输出在 `frontend/dist`。`npm run preview` 是构建预览命令，正式静态文件服务可交给 Nginx 等部署入口。

## 14 启动流程

### 14.1 先确认端口和资源归属

```bash
ss -ltnp 'sport = :8000'
ss -ltnp 'sport = :5173'
ss -ltnp 'sport = :9000'
ss -ltnp 'sport = :62272'
ps -eo user,pid,comm
```

确认已有服务能否复用，以及项目目录、日志、端口、GPU 的实际管理者。不要仅为了端口冲突就杀掉其他账号或其他项目的服务。

### 14.2 推荐的分组件启动

适用于首次部署、排错和共享机器。先安装环境，完成连接配置，确认模型与对象存储可用；若 MinIO 和模型服务已有实例，复用它们。

后端终端：

```bash
cd /data2/dlx/projects/xty
source backend/script/setting.sh

# 若需手动覆盖配置，应在 source 后配置，并先核对 active 数据库注册表。
# 图谱 DB_* 和 MinIO_* 也要在启动前配置好。
cd backend
pixi run --locked --manifest-path ../pixi.toml python app.py
```

另一个终端启动前端：

```bash
cd /data2/dlx/projects/xty
pixi run --locked dev-frontend
```

当前 `start-backend` task 的定义直接使用 `source`。本机 Pixi 任务 shell 对 `source` 的只读验证返回 `command not found`，因此不要把 `pixi run start-backend` 作为当前可用的推荐命令。使用前面的 Bash 显式加载流程；若希望一条命令完成配置加载和启动，应明确调用 Bash：

```bash
cd /data2/dlx/projects/xty
pixi run --locked bash -c \
  'cd backend && source script/setting.sh && exec python app.py'
```

该命令会加载 `setting.sh` 并覆盖其中的固定配置。需要手动覆盖时使用前面的分步流程。

### 14.3 一键启动与停止的影响

专用部署、且确认脚本范围适用时：

```bash
cd "$PROJECT_ROOT"
bash scripts/start.sh
```

它会启动/复用 MinIO，检查 vLLM，后台启动后端和前端，写入 `data/pids.server`。当前有几项限制：

- 会先停止 PID 文件里的旧进程，并用宽泛 `pkill -f` 匹配 uvicorn/Vite。
- `stop_all.sh` 还会按 `minio server` 进程名匹配，可能影响共享服务。
- 打印“启动完成”不是后端已经成功监听的证明，必须检查日志和实际端口。
- `BACKEND_PORT` 在脚本中只用于打印；`backend/app.py` 实际固定 8000。调整它不会改变后端端口。
- `FRONTEND_PORT` 会传给 Vite，实际可以改变前端端口，但代理/统一入口也要同步配置。

停止方式优先使用原进程管理工具和已确认归属的准确 PID。`bash scripts/stop_all.sh` 仅适合确认其广泛匹配范围不会影响其他服务的部署，不把它作为共享机器的默认停止命令。

## 15 生产入口和反向代理

### 15.1 路由要求

| 路径 | 应转发到 |
| --- | --- |
| `/api/*`、`/openapi.json` | 主后端 8000 |
| `/upload`、`/get_graph`、`/external-view` | 主后端 8000 |
| `/graph/*`、`/external/*`、`/internal-binding/*`、图谱 `/assets/*` | 主后端 8000 |
| Vue 页面及其静态资源 | `frontend/dist` 或开发前端 5173 |

后端 `/` 是图谱入口，Vue 页面在前端。如果将 cpolar 默认指向 8000，打开公网根地址展示的可能是图谱，而不是 Vue。

### 15.2 Nginx 参考配置

Vue 和图谱都使用根页面及 `/assets` 资源，完整保留现有页面时，优先使用两个域名：Vue 域名服务静态前端并转发业务 API，图谱域名转发整个后端。这样 `/external-view`、`/assets/js/*`、`/assets/css/*` 和图谱首页都保留原路径。以下域名为示例，需要替换并补齐实际 TLS 配置。

公网入口直接拒绝 `/api/admin/`。不要以 `allow 127.0.0.1` 判断管理用户身份：cpolar 等本地隧道可能以回环 IP 连接代理，使公网请求通过这种白名单。管理端需另设有身份认证的内部入口；也要限制直接访问后端 8000，否则可以绕过代理限制。

```nginx
server {
    listen 80;
    server_name app.example.com;
    root /data2/dlx/projects/xty/frontend/dist;
    index index.html;
    client_max_body_size 100m;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;

    location ^~ /api/admin/ {
        deny all;
    }
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
    location = /openapi.json {
        proxy_pass http://127.0.0.1:8000;
    }
    location / {
        try_files $uri $uri/ /index.html;
    }
}

server {
    listen 80;
    server_name graph.example.com;
    client_max_body_size 100m;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;

    location ^~ /api/admin/ {
        deny all;
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
```

后端按 `request.client.host` 生成游客身份，代理后的真实客户端 IP 也需正确传递。单机 Nginx 场景可在完成配置后，使用明确的 Uvicorn 启动参数替代 `python app.py`：

```bash
cd /data2/dlx/projects/xty
source backend/script/setting.sh
cd backend
pixi run --locked --manifest-path ../pixi.toml python -m uvicorn app:app \
  --host 127.0.0.1 --port 8000 \
  --proxy-headers --forwarded-allow-ips 127.0.0.1
```

只信任已确认的代理来源，不将 `forwarded-allow-ips` 设置成任意来源。如果 Nginx 前还有隧道/CDN，需要按该上游的可信 IP 和真实客户端信息配置 `real_ip` 链路；本示例中的 `$remote_addr` 可能只是上游代理地址，不能直接当作原访问者。游客 IP 身份不能代替正式用户登录。[Uvicorn 代理参数说明](https://www.uvicorn.org/settings/#http)

上传大小和 300 秒等待是示例运维值，需根据实际文件与 SLA 调整；它们不会改变代码内的 180 秒图谱抽取时限。SSE 对话需要关闭代理响应缓冲。两个域名的浏览器存储各自独立，Token 不会自动跨域同步，图谱企业身份链还需按实际客户端传递方式验收。

### 15.3 cpolar 可选隧道

项目脚本入口：

```bash
bash scripts/start_tun.sh 8000
tmux has-session -t cpolar
tail -n 50 cpolar.log
```

二进制在 `data/cpolar/cpolar`，会话名 `cpolar`，脚本固定请求 `xtyapp` 子域并使用 `-log=stdout`。账号认证、保留域名与实际可用公网域名需依据 cpolar 账号和日志确认。已有同名 tmux 会话时，脚本直接返回，不会应用新端口参数。

`http://xtyapp.vip.cpolar.cn/api` 与 `http://xtyapp.cpolar.top/...` 不是同一域名。不能把未分配域名当成已生效入口。`/api` 本身没有业务路由，可能正常返回 404；验证应访问 `/api/config/enums` 等具体接口。

隧道只能转发目标端口，不会替你安装 Vue、修复 Redis、增加管理员鉴权或自动补齐前端代理。需要展示 Vue 和图谱时，先按实际域名及路由准备代理入口，再按用途转发；公网代理必须继续拒绝管理 API 或实施真实身份认证。

## 16 分层验收

### 16.1 基础 HTTP 检查

```bash
curl --noproxy '*' --fail --silent --show-error --max-time 10 \
  http://127.0.0.1:9000/minio/health/live
curl --noproxy '*' --fail --silent --show-error --max-time 10 \
  http://127.0.0.1:62272/v1/models
curl --noproxy '*' --fail --silent --show-error --max-time 10 \
  http://127.0.0.1:8000/api/config/enums
curl --noproxy '*' --fail --silent --show-error --max-time 10 \
  http://127.0.0.1:8000/api/health
curl --noproxy '*' --fail --silent --show-error --max-time 10 \
  http://127.0.0.1:8000/openapi.json
curl --noproxy '*' --fail --silent --show-error --max-time 10 \
  http://127.0.0.1:5173/
```

`/api/health` 主要表示图谱应用路由可响应，并不检查数据库、模型和所有外部服务。当前 FastAPI 设置了 `openapi_url=None`，默认 `/docs` 和 `/redoc` 未启用；项目单独提供 `/openapi.json`。不要根据旧 README 的 `/docs` 地址判定服务失败。

### 16.2 企业身份验证

在可信的本机/HTTPS 入口，用实际有效 Token 请求知识库列表和部门接口。以下脚本需要有控制终端，交互输入且不输出 Token，避免把 Token 放进命令参数或 URL：

```bash
.pixi/envs/default/bin/python -B - <<'PY'
from getpass import getpass
import httpx
token = getpass("有效企业 accessToken: ")
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=20, trust_env=False) as client:
    for path in ["/api/kb/list?page=1&size=10&type=user", "/api/department_users"]:
        response = client.get(path, headers={"accessToken": token})
        print(path, "HTTP", response.status_code)
        try:
            body = response.json()
            print("message:", body.get("msg") if isinstance(body, dict) else "响应为 JSON")
        except ValueError:
            print("响应不是 JSON")
PY
```

不能用管理端无 Token 的接口返回 200 来证明企业用户认证成功。`PING` 成功也不能证明指定 Token 在 Redis 中存在。

### 16.3 业务验收

使用专门测试账号和可清理的测试资料，依次检查：

1. 普通对话、流式响应、中断和历史记录。
2. 简单只读数据库问题，以及普通用户/管理员的实际权限差异。
3. 创建测试知识库、上传小文本、索引、检索、公司与使用人隔离。
4. 图谱上传小文件，确认返回图谱、节点和边、附件及页面资源都可访问。
5. 再测试旧 Office 文件、图片和扫描 PDF。
6. 反馈、截图、历史导出和管理入口访问控制。

这些操作会写入业务数据，应放在明确的测试范围内。健康接口通过与全部业务通过需要分别记录。

## 17 日志与排错

| 服务/数据 | 位置 |
| --- | --- |
| 后端 | `data/logs/backend.log` |
| 前端 | `data/logs/frontend.log` |
| MinIO | `data/logs/minio.log` |
| 旧脚本启动的 vLLM | `/data2/dlx/projects/vllm/vllm.log` |
| cpolar | 项目根 `cpolar.log` |
| 后端/前端 PID 记录 | `data/pids.server` |
| 图谱输出/上传 | `graph/runtime/external_workspace/` |
| 图谱内部绑定 | `graph/runtime/internal_binding_workspace/` |

```bash
tail -n 100 data/logs/backend.log
tail -n 100 data/logs/frontend.log
tail -n 100 data/logs/minio.log
```

正确目录为 `data/logs/`，不是 `data/log/`。排查时保留日期和完整错误阶段，日志分享前检查是否包含用户资料或凭据。

| 现象 | 优先核查 |
| --- | --- |
| Redis TCP 超时 | 服务实际监听地址/端口、映射、防火墙、来源 IP 白名单；尚未涉及密码 |
| MySQL 成功但知识库 401 | Token 是否有效、Redis 是否可达、浏览器是否残留旧 Token |
| 超级管理员被要求登录 | Redis 身份解析结果是否变为游客；角色不是 Linux/MySQL 账号权限 |
| 不同角色查询相同数据库 | 当前 SQL 工具只做登录门槛，不能靠连接配置自动补齐隔离 |
| 文件解析超时 | 模型服务、OCR、存储、抽取子进程、前端和代理各自时限 |
| 缺少 `soffice` | 安装并确认 LibreOffice，重测旧 Office 文件 |
| 模型名不存在 | 比较 `/v1/models` 与各调用方 model 配置 |
| 图谱抽取新模型 401 | 抽取器固定占位 Key，没有读取主模型 Key |
| 图谱路径 404 | 是否挂载成功、Vite/代理是否覆盖根路径图谱接口 |
| `/api` 404 | 没有这个根路由，改测具体 API |
| `/docs` 404 | 当前没有默认文档 UI，使用 `/openapi.json` |
| 公网域名 404 | 检查域名实际分配和 cpolar 日志，区别隧道错误与后端路由错误 |
| `Address already in use` | 查实际监听 PID、所属账号和旧服务；不要直接按端口批量 kill |
| `nvidia-smi` mismatch | 系统 NVIDIA 内核模块和 NVML 用户态库版本 |
| `pip check` setuptools 冲突 | 现有环境漂移；核对锁文件、包元数据和安装历史 |
| 修改 IP 后仍旧连接 | active 注册表覆盖、独立图谱 DB_*、旧进程未重启 |
| 修改 backend/.env 无效 | 当前没有自动加载该文件 |

## 18 数据持久化与迁移

迁移已有系统时，要保留业务文件与关联数据，不能只复制数据库连接和知识库元数据就声称完整迁移。

| 资源 | 保留/迁移内容 |
| --- | --- |
| MySQL | 原数据库或正式备份；新地址、用户权限、两套连接配置 |
| Redis | 实际登录记录及其有效期，由登录系统管理 |
| MinIO | 桶内对象、历史、反馈、附件、知识库原文件及服务数据 |
| 知识库元数据 | `data/kb_metadata.json`，含租户、创建者、使用人 |
| 向量库 | `data/milvus/` 或对应远程集合；与模型和元数据保持一致 |
| 数据库注册表 | `data/databases.json`，含私密连接凭据 |
| 图谱 | `graph/runtime/` 中需要保留的图谱、上传文件及绑定数据 |
| 模型 | 原共享模型位置或完整可重建资源，更新机器相关路径 |
| 前端构建 | `frontend/dist`，以及构建时的正确变量 |
| 依赖 | 两个项目各自的 manifest/lock，前端 package-lock |

备份应使用存储系统支持的一致性方式，或在确认停止本项目写入后复制本地文件；不要在活跃写入时随意复制数据库文件当作已验证备份。日志和 PID 文件用于排错，不能当作可直接恢复的运行状态。不要复制整套 `.pixi` 到不同系统就假定环境可用；优先按锁文件重建。

## 19 当前参数调优与遗留项

常用的已读取参数：

| 参数 | 当前脚本值/默认 | 影响 |
| --- | --- | --- |
| `CHAT_MODEL_TEMPERATURE` | 0 | 主对话生成 |
| `CHAT_MODEL_MAX_TOKENS` | 4096 | 主对话输出上限 |
| `CHAT_MODEL_TIMEOUT` | 120 秒 | 主模型调用等待 |
| `CHAT_HISTORY_MAX_ROUNDS` | 6 | 携带历史轮数 |
| `CHAT_FILE_TEXT_MAX_CHARS` | 12000 | 对话文件文本上限 |
| `KB_FILE_TEXT_MAX_CHARS` | 40000 | 知识库文件提取上限 |
| `CHAT_STREAM_DELTA_CHARS` | 8 | 正文推流粒度 |
| `CHAT_STREAM_CHAR_DELAY_MS` | 15 | 推流延迟 |
| `CHAT_THINKING_CHUNK_SIZE` | 48 | 思考推流粒度 |
| `MILVUS_BATCH_SIZE` | 32 | embedding 批量处理 |
| `MILVUS_TOP_K` | 5 | 检索返回数 |
| `MILVUS_CHUNK_SIZE` | 800 | 分块字符数 |
| `MILVUS_CHUNK_OVERLAP` | 120 | 分块重叠 |
| `DB_MAX_REVISE_ROUND` | 4 | SQL 修复轮数 |
| `RESEARCH_MAX_RESULTS` | 3 | 联网搜索返回数 |
| `TAVILY_API_KEY` | 私密配置 | 联网搜索认证 |

旧文档中出现、但不能按描述认定生效的参数包括：

- `MILVUS_SCORE_THRESHOLD`：配置被读取，但未找到实际 search 阈值过滤使用。
- `MILVUS_EMBED_DIM`：实际维度由模型决定，没有被当前 Python 读取。
- `QUERY_DB_PATH`、`RAG_VECTOR_BACKEND`、`RAG_LLM_MODEL`、`RAG_LLM_TEMPERATURE`、`RESEARCH_SUMMARY_TEMPERATURE`、`CHAT_ENABLE_THINKING`、`SECURITY_ENABLE_*`：未找到当前 Python 消费点。
- YAML 的 worker 数量是参考项；当前 `python app.py` 启动不是已配置的多 worker 部署。使用本地 Milvus Lite、全局状态和文件元数据时，不能仅调大 worker 就认定并发安全。

修改参数后按实际调用路径验证效果；不把注释、参考 YAML 或变量存在本身当作功能已经生效的证明。

## 20 交接检查清单

- [ ] 项目路径、运行账号、服务管理者已确认。
- [ ] OS/架构和系统工具适用，`soffice` 可执行。
- [ ] xty Pixi 环境按锁安装，Python/Node 符合范围，`pip check` 无未解决冲突。
- [ ] vLLM 使用独立环境，模型路径和接口 model 名称匹配。
- [ ] NVIDIA 驱动及用户态库一致，常规 `nvidia-smi` 和实际 CUDA 运算正常。
- [ ] GPU 已分配，显存和磁盘余量满足模型、缓存、并发与文件规模。
- [ ] active MySQL 配置和图谱 DB_* 均正确，只读连接查询通过。
- [ ] Redis TCP、认证、逻辑库和有效 Token 查询分别通过。
- [ ] MinIO 健康、应用凭据、桶权限和附件访问通过。
- [ ] 知识库 Milvus 和历史推荐 Milvus 的配置分别确认。
- [ ] 前端锁定依赖已安装，构建和代理路由正确。
- [ ] 后端真正监听成功，图谱挂载和具体 API 路由正确。
- [ ] 企业与管理入口的权限边界已验证。
- [ ] 小文件、Office、PDF/图片、对话和知识库业务已验收。
- [ ] 日志、持久化数据和备份恢复方式已交接。
- [ ] 文档与模板不包含真实密码、API Key 或开发 Token。

## 21 配置源码索引

| 主题 | 优先核对的源码 |
| --- | --- |
| 完整环境和 task | `pixi.toml`、`pixi.lock` |
| 启动与停止 | `scripts/start.sh`、`scripts/stop_all.sh` |
| 默认环境参数 | `backend/script/setting.sh` |
| 主后端监听与图谱挂载 | `backend/app.py` |
| 用户身份和角色 | `backend/services/user_auth.py` |
| active 数据库优先级 | `backend/services/db_registry.py` |
| SQL 查询 | `backend/agent/tools/db_operator.py`、`backend/utils/DB_vllm_32B.py` |
| 对象存储 | `backend/services/storage_service.py`、`scripts/start_minio.sh` |
| 知识库向量 | `backend/services/milvus_service.py` |
| 历史推荐向量 | `backend/agent/utils.py` |
| 通用文件解析 | `backend/services/kb_file_parser.py` |
| 图谱上传/抽取 | `graph/app.py`、`graph/modules/xintuoyin/getgraph/main.py` |
| 图谱 MySQL | `graph/modules/Graph/backend/config.py` |
| 前端依赖/代理 | `frontend/package.json`、`package-lock.json`、`vite.config.js` |
| Token 读取/发送 | `frontend/src/utils/request.js`、`frontend/src/api/ai.js` |
| 独立模型启动 | `scripts/start_vllm.sh`、sibling `vllm/pixi.toml` |
| 隧道 | `scripts/start_tun.sh` |

旧 README、后端 YAML 和图谱参数文档可辅助理解业务，但遇到不一致时，以当前实际启动链和读取代码为准。

## 22 全部直接依赖声明

以下清单从当前 `pixi.toml` 和前端 `package.json` 自动整理。版本范围是声明，完整的精确版本及间接 CUDA/模型依赖见锁文件。

### Conda 直接依赖

| 包 | 声明范围 |
| --- | --- |
| `python` | `3.11.*` |
| `nodejs` | `>=20,<23` |
| `fastapi` | `*` |
| `uvicorn` | `*` |
| `python-multipart` | `*` |
| `openai` | `*` |
| `httpx` | `*` |
| `langgraph` | `>=1.0.5,<2` |
| `pymysql` | `>=1.1.2,<2` |
| `sqlparse` | `>=0.5.5,<0.6` |
| `llama-index` | `>=0.14.12,<0.15` |
| `llama-index-llms-openai` | `>=0.6.13,<0.7` |
| `llama-index-embeddings-openai` | `>=0.5.1,<0.6` |
| `docx2txt` | `>=0.9,<0.10` |
| `pypdf` | `>=6.6.0,<7` |
| `gunicorn` | `>=23.0.0,<24` |
| `regex` | `2024.11.6.*` |
| `pip` | `>=25.3,<26` |
| `faiss` | `>=1.9.0,<2` |
| `pandas` | `>=2.3.3,<3` |
| `redis-py` | `>=7.4.0,<8` |
| `pillow` | `>=10.0.0,<12.0.0` |
| `typer` | `>=0.12.5,<0.22.0` |

### PyPI 直接依赖

| 包 | 声明范围 |
| --- | --- |
| `socksio` | `*` |
| `langchain-openai` | `>=1.1.3, <2` |
| `langchain-community` | `>=0.4.1, <0.5` |
| `langchain-core` | `*` |
| `langchain` | `>=1.1.3, <2` |
| `langgraph` | `*` |
| `tavily-python` | `>=0.7.15, <0.8` |
| `llama-index` | `*` |
| `llama-index-llms-openai` | `*` |
| `llama-index-embeddings-openai` | `*` |
| `openpyxl` | `>=3.1.5, <4` |
| `langchain-huggingface` | `>=1.2.0, <2` |
| `sentence-transformers` | `>=5.2.3, <6` |
| `python-pptx` | `>=1.0.2, <2` |
| `minio` | `>=7.2.20, <8` |
| `pymilvus` | `>=2.6.11, <3` |
| `langchain-milvus` | `>=0.3.3, <0.4` |
| `llama-index-vector-stores-milvus` | `>=1.1.0, <2` |
| `setuptools` | `*` |
| `milvus` | `>=2.3.5, <3` |
| `flask` | `==3.0.3` |
| `flask-cors` | `>=4.0.0` |
| `docling` | `*` |
| `rapidocr-onnxruntime` | `*` |
| `pypdfium2` | `*` |
| `cryptography` | `>=47.0.0, <48` |
| `click` | `>=8.0.0` |
| `a2wsgi` | `>=1.10.0` |

### 前端运行依赖

| 包 | 声明范围 |
| --- | --- |
| `axios` | `^1.10.0` |
| `echarts` | `^6.0.0` |
| `element-plus` | `^2.10.4` |
| `github-markdown-css` | `^5.8.1` |
| `highlight.js` | `^11.11.1` |
| `jsencrypt` | `^3.3.2` |
| `lodash` | `^4.17.21` |
| `markdown-it` | `^14.1.0` |
| `normalize.css` | `^8.0.1` |
| `pinia` | `^3.0.3` |
| `vue` | `^3.5.17` |
| `vue-router` | `^4.5.1` |

### 前端开发依赖

| 包 | 声明范围 |
| --- | --- |
| `@vitejs/plugin-vue` | `^6.0.0` |
| `less` | `^4.3.0` |
| `vite` | `^7.0.0` |
| `vite-plugin-vue-devtools` | `^7.7.7` |

### 图谱子项目 requirements 原始范围

这些清单用于辨认旧子项目依赖范围，不替代根环境安装。

`graph/requirements.txt`：

```text
Flask==3.0.3
Flask-Cors>=4.0.0
PyMySQL>=1.1.0
openai>=1.0.0
pandas>=2.0.0
openpyxl>=3.1.0
click>=8.0.0
docling
minio>=7.2.20
```

`graph/modules/Graph/backend/requirements.txt`：

```text
Flask==3.0.3
```
