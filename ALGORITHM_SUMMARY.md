# 项目算法与技术架构总结 (xintuoyin-vue)

## 1. 概览
本项目采用 **Agentic RAG (Agent-based Retrieval-Augmented Generation)** 架构，结合 **LangGraph** 状态机编排与 **LlamaIndex** 高性能检索技术，构建了一个支持分层权限控制、多模态交互和复杂任务规划的智能问答系统。

核心算法涵盖图论编排、向量检索、意图识别分类以及动态 Prompt 工程。

---

## 2. 核心算法与技术细节

### 2.1 Agent 编排与状态机算法 (LangGraph)
后端采用 **有向有环图 (Cyclic Graph)** 来管理对话流程，而非传统的线性链式调用。

*   **状态图构建 (StateGraph)**:
    *   定义全局状态 `GraphState`，包含 `messages` (对话历史序列)、`enable_web` (联网开关)、`sql_needed` (SQL意图标志) 等上下文变量。
    *   **节点 (Nodes)**: 将业务逻辑解耦为独立的功能单元，如 `chatbot_local` (主对话模型)、`tools_execution` (工具执行)、`sql_planner` (SQL生成器)、`should_sql` (意图判官)。
*   **条件路由算法 (Conditional Routing)**:
    *   **动态边 (Conditional Edges)**: 在节点执行完毕后，基于当前状态动态决定下一跳。
    *   **路由逻辑**:
        *   `route_start`: 根据 `enable_web` 开关决定进入本地模式还是联网模式。
        *   `route_after_chatbot`: 检查 LLM 输出是否包含 `tool_calls`。若有，跳转至工具执行节点；若无，跳转至 `should_sql` 进行二次意图判断。
        *   `route_after_should_sql`: 基于 `sql_needed` 标志位，决定是否分流至 SQL 生成子图。

### 2.2 RAG 检索与分层权限算法 (LlamaIndex)
知识库模块不仅仅是简单的向量相似度匹配，还引入了 **元数据过滤 (Metadata Filtering)** 来实现复杂的企业级权限控制。

*   **向量索引构建 (Vector Indexing)**:
    *   使用 `VectorStoreIndex` 对文档进行切片和 Embedding 向量化（模型：`text-embedding-3-small`）。
    *   **元数据注入**: 在索引构建阶段，自动解析文件物理路径，注入 `category_path` 元数据 (例如 `depts/dept_a`, `users/user_a1`)，作为权限标识。
*   **动态权限过滤算法 (RBAC Filtering)**:
    *   **权限映射**: 后端维护 `USER_ACCESS_MAP`，定义不同角色 (Admin, Manager, Employee) 可访问的路径集合。
    *   **布尔逻辑检索**: 在执行 `rag_tool` 时，根据当前用户身份 (`user_identity`) 动态构建 `MetadataFilters`。采用 **OR** 逻辑 (`condition="or"`)，即只要文档的 `category_path` 命中用户权限列表中的任意一项，即视为有权访问。
    *   **索引热更新**: 实现了索引的增量刷新机制 (`force_refresh_index`)，文件变动后自动清除内存单例并重建索引，保证检索实时性。

### 2.3 意图识别与分类算法 (Intent Classification)
为了精准处理复杂的用户请求，系统引入了专门的分类节点。

*   **SQL 意图判官 (`should_sql` node)**:
    *   使用轻量级模型 (`gpt-4o-mini`) 配合专门设计的 Prompt (`SystemMessage`)。
    *   **任务**: 分析用户最新的自然语言输入，判断是否涉及数据库查询（如聚合、统计、筛选）。
    *   **结构化输出**: 强制 LLM 输出严格的 JSON 格式 (`{"sql_needed": true/false, "reason": "..."}`)，确保下游逻辑的确定性。

### 2.4 Prompt 工程与上下文管理
*   **动态指令注入 (System Prompt Injection)**:
    *   在 `app.py` 层面，根据前端传入的 `kb_category` 或 `user_identity`，实时向 System Prompt 中追加强指令（例如：“用户选择了知识库：合同管理，请优先检索该类文档”）。
    *   这种机制显著提高了 LLM 对当前上下文的遵循度 (Adherence)。
*   **工具绑定 (Tool Binding)**:
    *   使用 LangChain 的 `bind_tools` 机制，将 Python 函数 (`rag_tool`, `sql_tool`, `calculator`) 的签名（Docstring + Type Hints）转化为 OpenAI Function Calling 格式，使模型能准确感知工具能力。

### 2.5 异步流式处理 (Async Streaming)
*   后端全链路采用 `asyncio` + `FastAPI StreamingResponse`。
*   **Token 级流式输出**: 利用 `agent_app.astream(..., stream_mode="messages")`，实时捕获 LLM 生成的每一个 Token (Chunk)，并通过 HTTP SSE (Server-Sent Events) 协议推送到前端。
*   **节点过滤**: 在流式传输过程中，算法会自动过滤掉非对话节点（如 `should_sql` 的内部思考过程），只向用户展示 `chatbot` 节点的最终回复，优化用户体验。

---

## 3. 技术栈总结
*   **LLM 框架**: LangGraph, LangChain
*   **RAG 引擎**: LlamaIndex (Core, VectorStore)
*   **Web 框架**: FastAPI (Async)
*   **向量模型**: OpenAI Text Embedding 3
*   **LLM 模型**: GPT-4o / GPT-4o-mini
*   **数据存储**: 本地文件系统 (JSON Metadata + Physical Files)
