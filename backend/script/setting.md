# setting.sh 参数说明

本文档用于说明 `backend/script/setting.sh` 中各个环境变量的用途、默认值以及常见调优方向。

## 使用方式

启动后端前，通常需要先加载配置：

```bash
source backend/script/setting.sh
source backend/script/env.sh
```

说明：

- `setting.sh` 负责业务参数、模型参数、检索参数、数据库工具参数等运行配置。
- `env.sh` 主要放 API Key、Base URL、前端接口地址、CUDA 设备等敏感或环境相关配置。
- 两者都是通过 `export` 注入当前 shell 环境，后续启动脚本会直接读取这些变量。

## 1. Search / Web Retrieval

### `RESEARCH_MAX_RESULTS=5`

用于控制联网检索时最多返回多少条候选结果。

- 值越大：召回面更广，但处理时间更长，摘要成本也更高。
- 值越小：响应更快，但可能漏掉有价值的信息源。
- 适合场景：如果外部搜索结果质量不稳定，可以适当提高到 `8` 或 `10`；如果追求速度，可降到 `3`。

### `RESEARCH_SUMMARY_MODEL="gpt-4o"`

用于对检索结果做总结、压缩和归纳的模型。

- 该模型不直接负责最终聊天回复，而是负责“搜索结果摘要”这一步。
- 如果希望摘要更强，可以使用更强模型；如果更关注成本，也可以替换为更轻量模型。

### `RESEARCH_SUMMARY_TEMPERATURE=0`

控制搜索摘要模型的随机性。

- `0` 表示尽量稳定、可复现，适合信息整理和事实总结。
- 如果提高到 `0.3` 以上，摘要表达可能更灵活，但稳定性会下降。

## 2. Query Embedding / Local Retrieval

### `QUERY_EMBEDDING_MODEL="BAAI/bge-base-zh-v1.5"`

用于将查询文本向量化，以支持本地知识检索或相似度搜索。

- 这是一个偏中文语义检索的 embedding 模型。
- 如果知识库内容以中文为主，这类模型通常更合适。
- 更换模型后，通常需要重新构建或同步已有向量库，否则查询向量与历史向量维度或语义空间可能不一致。

### `QUERY_DB_PATH="./data/local_db_query"`

本地查询向量库或检索数据库的存储路径。

- 用于保存与查询检索相关的数据索引。
- 修改路径时，需要确认目录存在且运行账号有读写权限。
- 如果切换到新路径，而旧数据未迁移，可能会导致检索结果为空或表现异常。

## 3. Main Chat Model

### `CHAT_MODEL_NAME="gpt-4o"`

主聊天链路使用的核心大模型。

- 用户日常对话、问答、综合生成通常会依赖这个模型。
- 这是最影响整体回复质量的关键配置之一。

### `CHAT_MODEL_TEMPERATURE=0`

主聊天模型的生成随机性。

- `0` 更偏向稳定、保守、可重复。
- 如果产品更强调创意、润色、开放式生成，可适当提高到 `0.2` 到 `0.7`。
- 如果场景偏问答、知识助手、SQL 助手，一般建议保持较低值。

### `CHAT_MODEL_MAX_TOKENS=4096`

限制单次聊天生成的最大 token 数。

- 值越大：允许更长回复，但成本和响应时间会增加。
- 值过小：可能出现回答被截断、总结不完整的问题。
- 如果前端常出现长回答中断，可以优先检查该值是否过低。

### `CHAT_MODEL_TIMEOUT=120`

主聊天模型请求超时时间，单位通常为秒。

- `120` 表示最多等待 120 秒。
- 如果外部模型服务偶发较慢，可以适当调高。
- 如果系统更关注快速失败和重试，可以适当调低。

## 4. SQL Routing / Planner

### `SQL_ROUTE_TEMPERATURE=0`

用于 SQL 路由、意图判断或规划阶段的随机性控制。

- 该阶段通常负责判断“是否需要走数据库查询”“走哪条工具链”。
- 设为 `0` 可以减少路由抖动，避免同一问题在不同请求中进入不同分支。

## 5. Recommendation Generation

### `CHAT_RECOMMENDATION_INPUT_LIMIT=500`

用于推荐问题、猜你想问或联想建议生成时的输入长度限制。

- 主要作用是避免推荐模块读取过长上下文，影响速度和成本。
- 如果推荐内容不够贴近上下文，可以适当调大。
- 如果推荐链路较慢，可适当调小。

### `CHAT_RECOMMENDATION_COUNT=3`

控制一次返回多少条推荐内容。

- 当前值 `3` 比较适合前端展示。
- 若前端卡片较多，可增大；若页面较紧凑，可减小到 `2`。

## 6. Chat Context Assembly / Streaming

### `CHAT_HISTORY_MAX_ROUNDS=6`

组装上下文时，最多带入多少轮历史对话。

- 值越大：上下文更完整，更能理解多轮会话。
- 值越大也意味着 token 消耗更高，并可能引入陈旧上下文噪音。
- 如果模型常“忘记前文”，可以适度增大；如果常被旧问题干扰，可以适度减小。

### `CHAT_FILE_TEXT_MAX_CHARS=12000`

单个上传文件可提取进入上下文的最大字符数。

- 用于控制文件内容注入模型时的上限。
- 值过大可能导致上下文膨胀，影响对话成本和速度。
- 值过小则可能让模型读不到关键段落。

### `CHAT_FILE_HISTORY_SNIPPET_CHARS=3000`

文件历史片段保留的最大字符数。

- 适用于会话中已经处理过的文件内容，在后续轮次里保留部分摘要或片段。
- 这是在“上下文连续性”和“token 成本”之间做平衡的参数。

### `CHAT_THINKING_CHUNK_SIZE=48`

流式输出或 thinking 内容分块大小。

- 数值越小：前端感受到的流式刷新更频繁。
- 数值越大：分块次数更少，但单次更新更长。
- 如果前端展示希望更顺滑，可以略微减小；如果服务端推送过于频繁，可以略微增大。

## 7. RAG Model Settings

### `RAG_LLM_MODEL="gpt-4o"`

RAG 问答链路中用于生成最终回答或整合检索结果的模型。

- 与主聊天模型可以相同，也可以单独指定。
- 如果 RAG 场景对准确性要求更高，通常会给它配一个能力更稳的模型。

### `RAG_LLM_TEMPERATURE=0.1`

RAG 回答生成温度。

- 相比纯聊天，RAG 更依赖事实和检索结果，因此通常建议较低温度。
- `0.1` 能在稳定性和语言自然度之间做一个折中。

### `RAG_EMBED_MODEL="text-embedding-3-small"`

RAG 使用的向量化模型。

- 用于文档切片向量化和检索匹配。
- 如果更换该模型，往往需要对已有知识库重新做 embedding。
- 不同 embedding 模型的维度、语言适配能力、成本都会不同。

## 8. SQL Tool LLM Settings

这一组参数用于数据库查询工具链，比如自然语言转 SQL、SQL 选择、SQL 修订等。

### `DB_LLM_BASE_URL="https://api.claudeshop.top/v1"`

数据库工具链所使用的大模型服务地址。

- 与主聊天模型可以共用，也可以独立配置。
- 单独拆开配置的好处是：SQL 工具可以接不同网关、不同模型，便于隔离调优。

### `DB_LLM_MODEL_NAME="gpt-4o"`

数据库工具链默认使用的模型名称。

- 主要影响 SQL 生成、修订、选择等阶段的理解和推理能力。

### `DB_LLM_SELECTOR_TEMPERATURE=0.1`

用于 SQL selector 阶段的温度。

- selector 阶段通常负责挑选表、字段、候选 SQL 或执行策略。
- 适度保留一点灵活性有助于探索，但不宜过高。

### `DB_LLM_SELECTOR_MAX_TOKENS=1024`

selector 阶段可生成的最大 token 数。

- 如果 selector 输出内容较复杂，例如需要返回多候选计划，可适当增加。
- 如果只是简单决策，当前值通常够用。

### `DB_LLM_GENERATE_TEMPERATURE=0.0`

用于 SQL 生成阶段的温度。

- 设为 `0.0` 是比较典型的数据库场景配置。
- 目的是尽量减少 SQL 结构漂移，提高同类问题下生成 SQL 的稳定性。

### `DB_LLM_GENERATE_MAX_TOKENS=1024`

SQL 生成阶段的最大输出 token。

- 如果 SQL 逻辑复杂、包含多层子查询，可能需要更大上限。
- 但对大多数普通查询来说，`1024` 已经比较宽松。

### `DB_LLM_REVISE_TEMPERATURE=0.0`

用于 SQL 修订阶段的温度。

- 当 SQL 执行报错、字段不匹配、语法需要修正时，会进入 revise 逻辑。
- 低温度有助于让修订过程更聚焦问题本身，而不是生成过多不必要变化。

### `DB_MAX_REVISE_ROUND=4`

SQL 最多允许自动修订多少轮。

- 值越大：系统更愿意“自动纠错”。
- 值越大也可能导致请求耗时明显上升。
- 如果数据库结构比较稳定但模型偶发小错误，保留 `3` 到 `4` 轮通常比较合适。

补充：

- 注释里提到 `DB_LLM_API_KEY` 是可选项。
- 如果未设置 `DB_LLM_API_KEY`，代码会回退使用 `OPENAI_API_KEY`。
- 这意味着数据库工具链可以单独配 key，也可以复用全局 key。

## 9. MySQL Connection

这一组变量用于 `sql_tool` 连接 MySQL 数据库。

### `DB_MYSQL_HOST="183.69.138.62"`

MySQL 服务主机地址。

- 可以是 IP，也可以是域名。
- 如果数据库部署在内网，需要确认运行环境具备访问权限。

### `DB_MYSQL_PORT=33666`

MySQL 服务端口。

- 默认 MySQL 端口通常是 `3306`，这里使用了自定义端口 `33666`。
- 迁移数据库环境时，这个值很容易被遗漏。

### `DB_MYSQL_USER="hagongda"`

数据库用户名。

- 建议使用权限最小化的专用账号，而不是高权限 root 账号。

### `DB_MYSQL_PASSWORD='ha.G/o[tEst]n%gD*a'`

数据库密码。

- 当前直接写在 `setting.sh` 中，能够工作，但不利于安全管理。
- 更推荐迁移到独立的私密环境文件、CI Secret、容器 Secret 或部署平台变量中。

### `DB_MYSQL_NAME="r_d_test"`

默认连接的数据库名。

- 如果系统存在多库环境，需要确认该值与目标业务库一致。
- 当模型生成 SQL 时，默认会基于这个数据库上下文进行操作。

## 调优建议

如果你希望更稳定：

- 保持大部分 `TEMPERATURE=0` 或接近 `0`
- 控制 `CHAT_HISTORY_MAX_ROUNDS` 不要过大
- 控制检索和推荐的输入规模

如果你希望更快：

- 降低 `RESEARCH_MAX_RESULTS`
- 降低 `CHAT_RECOMMENDATION_INPUT_LIMIT`
- 缩小 `CHAT_HISTORY_MAX_ROUNDS`
- 适度缩短 `CHAT_MODEL_TIMEOUT`

如果你希望回答更完整：

- 提高 `CHAT_MODEL_MAX_TOKENS`
- 适当增加 `CHAT_FILE_TEXT_MAX_CHARS`
- 根据实际场景增加 `CHAT_HISTORY_MAX_ROUNDS`

如果你希望 SQL 更稳：

- 保持 `SQL_ROUTE_TEMPERATURE=0`
- 保持 `DB_LLM_GENERATE_TEMPERATURE=0.0`
- 不要把 `DB_MAX_REVISE_ROUND` 设得过高

## 安全建议

- `env.sh` 和 `setting.sh` 中目前包含真实的 API Key、数据库地址和数据库密码。
- 如果仓库会被多人访问、推送到远端或用于演示，建议尽快改为 `.env`、部署平台变量或密钥管理服务。
- 文档可以提交到仓库，但敏感配置本身不建议长期明文保留。
