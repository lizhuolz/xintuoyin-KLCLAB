# setting.sh 参数说明

本文档对应 [setting.sh](/home/lyq/xintuoyin-KLCLAB/backend/script/setting.sh) 的当前实现，说明各环境变量的用途、默认值和调优方向。

## 使用方式

后端启动前通常会先加载：

```bash
cd backend
source script/setting.sh
source script/env.sh
```

如果直接使用项目启动脚本，则在仓库根目录执行：

```bash
./restart_services.sh
```

说明：

- `setting.sh` 负责业务运行参数、RAG 参数、Milvus 参数、SQL 工具参数等。
- `env.sh` 主要留给敏感信息或环境差异配置，例如 API Key。
- `setting.sh` 内部会动态计算 `BACKEND_ROOT`，因此路径类配置不再依赖当前工作目录。

## 路径与目录基准

### `SETTING_DIR`

`setting.sh` 所在目录的绝对路径，由脚本运行时自动计算。

- 主要用于让其它路径类变量基于脚本位置解析。
- 一般不需要手动改。

### `BACKEND_ROOT`

`backend` 根目录绝对路径，由 `SETTING_DIR` 自动推导。

- 当前很多路径类配置都以它为基准。
- 这样项目换目录、换用户、换机器后仍能保持稳定。

## Search / Web Retrieval

### `RESEARCH_MAX_RESULTS=3`

联网检索时最多保留多少条候选结果。

- 越大：覆盖更广，但速度更慢。
- 越小：响应更快，但可能漏信息。

### `RESEARCH_SUMMARY_MODEL="Qwen3.5-27B"`

用于整理搜索结果摘要的模型名。

- 这一步不是最终聊天回答，而是对搜索结果做压缩和归纳。
- 如果后续更换总结模型，可以只改这里，不影响主聊天模型配置。

### `RESEARCH_SUMMARY_TEMPERATURE=0`

搜索摘要阶段的温度。

- `0` 更稳定，适合事实整理。
- 一般不建议在摘要链路设太高。

## Query Embedding / Local Retrieval

### `QUERY_EMBEDDING_MODEL="BAAI/bge-base-zh-v1.5"`

本地查询检索使用的 embedding 模型名。

- 主要对应项目里非 Milvus 的查询向量化逻辑。
- 如果替换模型，要确认下游索引是否需要重建。

### `QUERY_DB_PATH="${QUERY_DB_PATH:-$BACKEND_ROOT/data/local_db_query}"`

本地查询检索数据目录。

- 默认基于 `BACKEND_ROOT` 动态计算。
- 也可以在启动前外部覆盖，例如：

```bash
export QUERY_DB_PATH=/data/query_index
source backend/script/setting.sh
```

## Main Chat Model

### `CHAT_MODEL_NAME="Qwen3.5-27B"`

主聊天链路使用的模型名。

- 日常对话、综合生成、部分工具路由会依赖它。
- 是影响整体回答质量的核心配置之一。

### `CHAT_MODEL_TEMPERATURE=0`

主聊天模型温度。

- `0` 更稳定，适合问答和工具调用。
- 如果未来要做更开放的创作场景，可以适度调高。

### `CHAT_MODEL_MAX_TOKENS=4096`

主聊天模型单次最大输出长度。

- 太小会截断回答。
- 太大则会增加响应时间和显存/推理开销。

### `CHAT_MODEL_TIMEOUT=120`

主聊天模型请求超时时间，单位秒。

- 联网、工具链或长回答场景下，这个值过小容易超时。

## SQL Routing / Planner

### `SQL_ROUTE_TEMPERATURE=0`

SQL 路由判断阶段温度。

- 用于判断是否走数据库工具链。
- 设为 `0` 可以减少同一问题路由不一致。

## Recommendation Generation

### `CHAT_RECOMMENDATION_INPUT_LIMIT=500`

推荐追问生成时，输入给推荐模块的最大文本长度。

- 太大影响速度。
- 太小则推荐内容不够贴近上下文。

### `CHAT_RECOMMENDATION_COUNT=3`

一次返回多少条推荐追问。

- 当前值适合常见前端卡片展示。

## Chat Context Assembly / Streaming

### `CHAT_HISTORY_MAX_ROUNDS=6`

单次请求最多带入多少轮历史对话。

- 值越大，多轮上下文越完整。
- 值越大，token 消耗也越高。

### `CHAT_FILE_TEXT_MAX_CHARS=12000`

聊天上传文件时，单个文件最多注入多少字符给模型。

- 太小读不全文件。
- 太大容易挤占上下文窗口。

### `KB_FILE_TEXT_MAX_CHARS=40000`

知识库文件解析入库时，单文件最多保留多少字符用于切块和向量化。

- 这是知识库入库上限，不是聊天附件上限。
- 太小会丢内容，太大则会增加切块和 embedding 开销。

### `CHAT_FILE_HISTORY_SNIPPET_CHARS=3000`

后续多轮追问中，从历史附件回填给模型的片段长度上限。

- 用来平衡上下文连续性和 token 成本。

### `CHAT_THINKING_CHUNK_SIZE=48`

思考过程流式输出分块大小。

- 越小，前端刷新更频繁。
- 越大，推送次数更少但实时感更弱。

## RAG / Milvus

### `RAG_VECTOR_BACKEND="milvus"`

知识库检索后端类型。

- 当前项目已切到 Milvus 路径。
- 这里的 Milvus 实际使用的是 `milvus-lite` 本地文件模式。

### `KL_MILVUS_URI="${KL_MILVUS_URI:-$BACKEND_ROOT/data/milvus/klclab_milvus.db}"`

Milvus Lite 本地数据库文件路径。

- 默认基于 `BACKEND_ROOT` 动态计算，不再写死绝对路径。
- 可以在外部覆盖，例如：

```bash
export KL_MILVUS_URI=/data/milvus/prod.db
source backend/script/setting.sh
```

- 当前项目里不需要单独启动 Milvus 进程，后端在知识库上传、删除、检索时会自动打开这个本地 DB 文件。

### `KL_MILVUS_TOKEN=""`

Milvus 连接 token。

- 对本地 `milvus-lite` 场景通常为空。
- 如果以后切到远端 Milvus Server，可以在这里配置认证信息。

### `KL_MILVUS_DB_NAME="default"`

Milvus 数据库名。

- 对当前本地模式影响较小。
- 切远端 Milvus 时可用于区分逻辑库。

### `MILVUS_COLLECTION="klclab_kb_chunks"`

知识库切块写入的 collection 名称。

- 更换后，相当于切到新的集合。
- 如果线上已有数据，改名要同步考虑重建和迁移。

### `MILVUS_CONSISTENCY_LEVEL="Bounded"`

Milvus 查询一致性级别。

- 当前值兼顾性能与可用性。

### `MILVUS_INDEX_TYPE="AUTOINDEX"`

Milvus 向量索引类型。

- 当前使用自动索引，部署简单。
- 如果后续数据量更大，可根据实际 Milvus 部署形态改用更细粒度索引方案。

### `MILVUS_METRIC_TYPE="COSINE"`

向量相似度度量方式。

- 当前 embedding 已做归一化，使用 `COSINE` 比较合适。

### `MILVUS_EMBED_DIM=512`

知识库 embedding 向量维度。

- 必须和 `RAG_EMBED_MODEL` 实际输出维度一致。
- 当前 `AI-ModelScope/bge-small-zh-v1.5` 输出就是 `512`。

### `MILVUS_BATCH_SIZE=32`

批量向量化时每批处理多少个文本块。

- 越大通常吞吐更高，但 CPU/内存压力更大。

### `MILVUS_TOP_K=5`

检索时最多返回多少个候选切块。

- 太小可能漏上下文。
- 太大则可能引入噪音。

### `MILVUS_SCORE_THRESHOLD=0.35`

检索命中阈值。

- 当前逻辑里用于进一步筛选 Milvus 返回结果。
- 需要结合实际分数分布调，过高会漏召回，过低会带入无关块。

### `MILVUS_CHUNK_SIZE=800`

知识库文本切块长度。

- 值越大，块内语义更完整。
- 值越大，也更容易把不相关内容混在同一块。

### `MILVUS_CHUNK_OVERLAP=120`

相邻切块重叠长度。

- 用于减少跨段落切分造成的信息断裂。
- 重叠过大则会增加冗余和向量数量。

## RAG Model Settings

### `RAG_LLM_MODEL="Qwen3.5-27B"`

RAG 结果整合时使用的模型名。

- 当前知识库检索已接到 Milvus，但最终自然语言生成仍依赖问答模型服务是否部署。

### `RAG_LLM_TEMPERATURE=0.1`

RAG 回答温度。

- 适合检索增强场景，既保持稳定又保留少量语言自然度。

### `RAG_EMBED_MODEL="AI-ModelScope/bge-small-zh-v1.5"`

知识库向量化使用的本地 embedding 模型。

- 当前通过 `modelscope` 下载和解析。
- 如果本地不存在，运行时会尝试用 `modelscope` 获取。
- 更换模型后，需要重新对已有知识库切块做 embedding。

### `RAG_EMBED_DEVICE="cpu"`

知识库 embedding 运行设备。

- 当前使用 CPU，便于部署且依赖更少。
- 如果后续文档量很大，可以考虑切到 GPU。

## SQL Tool LLM Settings

### `DB_LLM_BASE_URL="http://0.0.0.0:62272/v1"`

数据库工具链使用的大模型服务地址。

- 这组配置主要用于自然语言转 SQL、SQL 修订和选表等阶段。
- 如果数据库工具要与主聊天模型分开部署，这里就是独立入口。

### `DB_LLM_MODEL_NAME="Qwen3.5-27B"`

数据库工具链使用的模型名。

### `DB_LLM_SELECTOR_TEMPERATURE=0.1`

选表/选字段阶段温度。

### `DB_LLM_SELECTOR_MAX_TOKENS=1024`

选表/规划阶段最大输出长度。

### `DB_LLM_GENERATE_TEMPERATURE=0.0`

SQL 生成阶段温度。

- 建议保持低温，减少 SQL 漂移。

### `DB_LLM_GENERATE_MAX_TOKENS=1024`

SQL 生成阶段最大输出长度。

### `DB_LLM_REVISE_TEMPERATURE=0.0`

SQL 修订阶段温度。

- 建议保持低温，聚焦修错。

### `DB_MAX_REVISE_ROUND=4`

SQL 自动修订最多尝试多少轮。

- 太大可能明显拉长响应时间。

补充：

- `DB_LLM_API_KEY` 是可选项。
- 如果未设置，代码会回退到 `OPENAI_API_KEY`。

## MySQL Connection

### `DB_MYSQL_HOST="183.69.138.62"`

MySQL 主机地址。

### `DB_MYSQL_PORT=33666`

MySQL 端口。

### `DB_MYSQL_USER="hagongda"`

数据库用户名。

### `DB_MYSQL_PASSWORD='ha.G/o[tEst]n%gD*a'`

数据库密码。

- 当前能工作，但不建议长期明文保留在仓库脚本里。
- 更建议迁到部署环境变量或 Secret 管理。

### `DB_MYSQL_NAME="r_d_test"`

默认数据库名。

## 其它运行配置

### `OPENAI_API_KEY="EMPTY"`

当前 OpenAI 兼容接口 key 占位值。

- 对本地或自建兼容网关场景常见。

### `OPENAI_API_BASE="http://0.0.0.0:62272/v1"`

OpenAI 兼容模型服务地址。

- 主聊天、RAG 生成等链路是否能真正回答，取决于该地址上的模型服务是否已经部署并可用。

### `TAVILY_API_KEY`

联网搜索工具使用的 API Key。

### `SECURITY_ENABLE_GIBBERISH=0`
### `SECURITY_ENABLE_NO_REFUSAL=0`
### `SECURITY_ENABLE_BAN_TOPICS=0`
### `SECURITY_ENABLE_TOXICITY=0`

安全扫描和内容控制相关开关。

- `0` 表示关闭。
- 如果后续要增强输入输出安全策略，可以按需开启。

## 启动说明

当前后端完整启动顺序通常是：

```bash
cd /home/lyq/xintuoyin-KLCLAB
./restart_services.sh
```

该脚本会：

1. 停掉旧前后端进程。
2. 进入 `backend`。
3. 加载 `conda activate xtyAgent`。
4. `source script/setting.sh`。
5. `source script/env.sh`。
6. 启动 `uvicorn app:app --host 0.0.0.0 --port 8000`。
7. 再启动前端 `npm run dev`。

说明：

- 当前 Milvus 使用的是 `milvus-lite` 本地文件模式，不需要额外单独启动 Milvus 服务。
- 第一次调用知识库上传、删除、检索相关 API 时，后端会自动打开 `KL_MILVUS_URI` 指向的本地 `.db` 文件。

## 调优建议

如果你希望更稳定：

- 保持大部分 `TEMPERATURE` 在 `0` 到 `0.1`
- 控制 `CHAT_HISTORY_MAX_ROUNDS`
- 控制 `MILVUS_TOP_K` 和 `MILVUS_SCORE_THRESHOLD`

如果你希望更快：

- 降低 `RESEARCH_MAX_RESULTS`
- 降低 `CHAT_RECOMMENDATION_INPUT_LIMIT`
- 降低 `CHAT_HISTORY_MAX_ROUNDS`
- 减小 `MILVUS_BATCH_SIZE`

如果你希望知识库召回更完整：

- 适当提高 `MILVUS_TOP_K`
- 适当降低 `MILVUS_SCORE_THRESHOLD`
- 调整 `MILVUS_CHUNK_SIZE` 和 `MILVUS_CHUNK_OVERLAP`

## 安全建议

- `setting.sh` 和 `env.sh` 当前包含真实数据库地址、密码、API Key 等敏感信息。
- 如果仓库要共享、演示或上远端，建议尽快迁到 `.env`、部署平台变量或 Secret 管理服务。
- 文档可以提交，但敏感配置本身不建议长期明文保留。
