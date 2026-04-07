# Project Memory

## 项目概览

- 项目名: `xintuoyin-KLCLAB`
- 主要形态: `FastAPI` 后端 + `Vite` 前端 + `MinIO` + `milvus-lite`
- 当前默认后端环境: `xtyAgent`
- 仓库根目录: `/home/lyq/xintuoyin-KLCLAB`
- 当前 README 重点是本地业务系统启动，不是模型部署文档

## 核心启动方式

- 项目主启动脚本: `/home/lyq/xintuoyin-KLCLAB/restart_services.sh`
- 典型启动前:
  - `cd /home/lyq/xintuoyin-KLCLAB`
  - `conda activate xtyAgent`
- 当前本地业务服务默认端口:
  - 后端: `0.0.0.0:8000`
  - 前端: `0.0.0.0:5173`
- 当前会话内确认到:
  - `8000` 正在监听
  - 未确认 `5173`

## 关键配置文件

- 后端主配置: `/home/lyq/xintuoyin-KLCLAB/backend/script/setting.sh`
- 这个文件很重要，多个 agent 任务都要先看它
- 当前 `setting.sh` 的模型相关关键项:
  - `RESEARCH_SUMMARY_MODEL="Qwen3.5-27B"`
  - `CHAT_MODEL_NAME="Qwen3.5-27B"`
  - `RAG_LLM_MODEL="Qwen3.5-27B"`
  - `OPENAI_API_BASE="http://10.249.40.204:62272/v1"`
  - `DB_LLM_BASE_URL="http://10.249.40.204:62272/v1"`
  - `DB_LLM_MODEL_NAME="Qwen3.5-27B"`
- 当前 RAG 向量存储:
  - `RAG_VECTOR_BACKEND="milvus"`
  - 但实际是 `milvus-lite` 本地 DB 文件，不是独立 Milvus 服务
- 当前 MySQL 配置写死在 `setting.sh`，敏感信息已在仓库内存在，后续 agent 不需要再到处找

## 运行时依赖与服务

- MinIO 启动相关:
  - `/home/lyq/xintuoyin-KLCLAB/setup_minio_env.sh`
  - `/home/lyq/xintuoyin-KLCLAB/start_minio.sh`
- 运行时路径辅助:
  - `/home/lyq/xintuoyin-KLCLAB/runtime_paths.sh`
- 当前日志文件:
  - `/home/lyq/xintuoyin-KLCLAB/logs/backend.log`
  - `/home/lyq/xintuoyin-KLCLAB/logs/frontend.log`
- 进程 PID 文件:
  - `/home/lyq/xintuoyin-KLCLAB/pids.server`

## 模型部署相关文件

- SGLang 启动脚本:
  - `/home/lyq/xintuoyin-KLCLAB/deploy_qwen35_27b_sglang.sh`
  - `/home/lyq/xintuoyin-KLCLAB/deploy_qwen3_32b_sglang.sh`
- vLLM 4 卡启动脚本:
  - `/home/lyq/xintuoyin-KLCLAB/deploy_qwen3_32b_vllm_4gpu.sh`
- `deploy_qwen3_32b_vllm_4gpu.sh` 已被改造成可覆写:
  - `CUDA_VISIBLE_DEVICES`
  - `PORT`
  - `TOOL_CALL_PARSER`
- 这个脚本当前默认包含:
  - `NCCL_P2P_DISABLE=1`
  - `NCCL_CUMEM_ENABLE=0`
  - `--enable-auto-tool-choice`
  - `--tool-call-parser qwen3_xml`
- 这些参数是之前排障后保留下来的有效配置，不要轻易删

## 近期模型部署排障结论

### Qwen3-32B / 4 GPU / vLLM

- 之前做过一轮 4 卡 `Qwen3-32B` 部署和压测
- 关键经验:
  - 4 卡直接起 `vllm` 时，若不设 `NCCL_P2P_DISABLE=1` 和 `NCCL_CUMEM_ENABLE=0`，容易卡在初始化阶段
  - 前台直接启动不稳定，最好用 `tmux` 或其他托管方式
  - 如果只看到 GPU 上残留 `VLLM::Worker`，但 API 端口不监听，通常是 APIServer 已退出，只剩孤儿 worker
- 之前还处理过 `tool_choice="auto"` 返回 `400` 的问题
  - 根因: 启动参数里缺少 `--enable-auto-tool-choice` 和 `--tool-call-parser`
  - 修复后已在日志中确认 `"auto" tool choice has been enabled.`

### Qwen3.5-27B / A800 2 GPU / 远端 vLLM

- 当前业务配置实际使用的服务是远端:
  - `http://10.249.40.204:62272/v1`
- 已验证:
  - `GET /v1/models` 返回模型 `Qwen3.5-27B`
  - `POST /v1/completions` 可正常响应
- 用户口径说明:
  - 这是 `A800` 双卡服务

## 压测工具与脚本

- 主压测脚本:
  - `/home/lyq/xintuoyin-KLCLAB/vllm_test/benchmark_vllm.py`
- 该脚本当前已做过增强:
  - 支持 `--env-label`
  - 在 `AutoTokenizer.from_pretrained()` 失败时，自动 fallback 到本地 `tokenizer.json`
- 这个 fallback 是为 `Qwen3.5-27B` 加的
  - 因为当前环境里的 `transformers 4.57.6` 仍不识别 `model_type=qwen3_5`
  - 但 `/data2/lyq/models/Qwen3.5-27B/tokenizer.json` 可以直接工作
- 额外报告生成脚本:
  - `/home/lyq/xintuoyin-KLCLAB/vllm_test/generate_comparison_report.py`
    - 用于历史 `2 GPU` vs 当前 `4 GPU`
  - `/home/lyq/xintuoyin-KLCLAB/vllm_test/generate_context_comparison_report.py`
    - 用于同一服务 `2024` vs `10000` 上下文对比

## 近期压测产物

### Qwen3-32B / 4 GPU

- 单组结果目录:
  - `/home/lyq/xintuoyin-KLCLAB/vllm_test/results_4gpu_ctx2024`
  - `/home/lyq/xintuoyin-KLCLAB/vllm_test/results_4gpu_ctx10k`
- 总报告目录:
  - `/home/lyq/xintuoyin-KLCLAB/vllm_test/report_4gpu`
- 总报告:
  - `/home/lyq/xintuoyin-KLCLAB/vllm_test/report_4gpu/report.md`
- 这组报告已经包含:
  - 部署方法
  - 2 卡历史 vs 4 卡当前
  - `2024` vs `10000`
  - 表格与 SVG 图

### Qwen3.5-27B / A800 双卡

- 单组结果目录:
  - `/home/lyq/xintuoyin-KLCLAB/vllm_test/results_a800_2gpu_ctx2024`
  - `/home/lyq/xintuoyin-KLCLAB/vllm_test/results_a800_2gpu_ctx10k`
- 对比报告目录:
  - `/home/lyq/xintuoyin-KLCLAB/vllm_test/report_a800_2gpu_qwen35_27b`
- 总报告:
  - `/home/lyq/xintuoyin-KLCLAB/vllm_test/report_a800_2gpu_qwen35_27b/report.md`

## 近期压测结论摘要

### Qwen3.5-27B / A800 双卡

- 压测地址: `http://10.249.40.204:62272/v1/completions`
- 模型: `Qwen3.5-27B`
- 压测口径:
  - 输入 `2024 -> 1024`
  - 输入 `10000 -> 1024`
  - 并发 `5 10 20 40 80 160`
  - timeout `180s`
- 结果摘要:
  - `2024`:
    - 最佳吞吐出现在并发 `160`
    - 约 `0.66 req/s`
    - 约 `2007.69 tok/s`
    - 并发 `160` 开始有 timeout，比例 `25%`
  - `10000`:
    - 最佳吞吐出现在并发 `40`
    - 约 `0.35 req/s`
    - 约 `3905.71 tok/s`
    - 并发 `80` 开始 timeout，比例 `40%`
- 关键判断:
  - 长上下文显著压缩稳定并发窗口
  - `2024` 在并发 `80` 仍稳定
  - `10000` 到并发 `80` 已明显超时

### Qwen3-32B / 4 GPU

- 总报告里记录的关键信息:
  - `2024` 最高吞吐约 `0.31 req/s`
  - `10000` 最高吞吐约 `0.23 req/s`
  - 两组在并发 `80` 都进入 `100% timeout`
- 当时结论是:
  - 当前 4 卡方案并没有优于仓库里的历史 2 卡基线

## 其他关键目录

- 后端源码: `/home/lyq/xintuoyin-KLCLAB/backend`
- 前端源码: `/home/lyq/xintuoyin-KLCLAB/frontend`
- Agent 相关代码: `/home/lyq/xintuoyin-KLCLAB/agent`
- 文档目录: `/home/lyq/xintuoyin-KLCLAB/documents`
- 反馈数据: `/home/lyq/xintuoyin-KLCLAB/feedbacks`
- 历史存储: `/home/lyq/xintuoyin-KLCLAB/history_storage`
- OpenAPI 文件: `/home/lyq/xintuoyin-KLCLAB/openapi.json`

## 接手时建议优先查看

- 先看:
  - `/home/lyq/xintuoyin-KLCLAB/README.md`
  - `/home/lyq/xintuoyin-KLCLAB/backend/script/setting.sh`
- 如果是业务系统问题，再看:
  - `/home/lyq/xintuoyin-KLCLAB/logs/backend.log`
  - `/home/lyq/xintuoyin-KLCLAB/logs/frontend.log`
- 如果是模型压测/部署问题，再看:
  - `/home/lyq/xintuoyin-KLCLAB/vllm_test/benchmark_vllm.py`
  - `/home/lyq/xintuoyin-KLCLAB/vllm_test/report_a800_2gpu_qwen35_27b/report.md`
  - `/home/lyq/xintuoyin-KLCLAB/vllm_test/report_4gpu/report.md`
  - `/home/lyq/xintuoyin-KLCLAB/deploy_qwen3_32b_vllm_4gpu.sh`

## 已知坑

- `transformers 4.57.6` 对 `Qwen3.5-27B` 的 `model_type=qwen3_5` 识别不稳定
  - 不要默认相信 `AutoTokenizer.from_pretrained()` 一定能过
  - 已在 benchmark 脚本中加了 `tokenizer.json` fallback
- 远端 `vLLM` 压测在沙箱环境下可能连不上，需要注意当前执行环境是否限制网络
- 只看 `nvidia-smi` 不足以判断服务活着
  - 还要看端口是否监听、APIServer 是否存在、日志是否继续刷新
- 孤儿 `VLLM::Worker` 可能长时间占卡
  - 看到只有 worker、没有 APIServer 时，要怀疑是残留进程

## 当前状态快照

- 仓库内存在完整的压测和报告产物，已经足够让其他 agent 直接复用
- 当前确认到 `8000` 正在监听
- 当前未确认本地 `62274` 或远端 `62272` 是否仍保持上次状态
- 若后续任务涉及模型调用，优先从 `backend/script/setting.sh` 读取真实服务地址，而不是假设本地端口
