# 知识图谱系统（文件上传版已完成 / 数据库版开发中）

本项目用于构建并展示企业研发场景知识图谱，当前包含两条技术路线：

- 系统外知识图谱（已完成）：上传文档/表格后，自动抽取实体关系并写入图谱 JSON，再通过 Web 页面可视化展示。
- 系统内知识图谱（开发中）：从数据库读取业务数据并转换为图谱，当前已提供数据库连接与查询原型，尚未接入主流程。

---

## 1. 当前能力与状态

### 1.1 已完成能力（可直接使用）

- 多文件上传并触发抽取流程（后端 `/upload`）。
- 自动识别文件类别并按对应规则抽取结构化信息（`getgraph/main.py` + `getgraph/prompt/`）。
- 图谱持久化为统一格式 `nodes + links`（`getgraph/graph_data/output_graph.json`）。
- 图谱可视化与交互：
  - 节点检索
  - 路径分析（层数 + 中间实体 + 关系 + 属性筛选）
  - 图谱编辑（增删改节点/关系）
  - 图谱合并、清空
  - Excel 节点弹窗预览

### 1.2 开发中能力（需继续实现）

- 数据库数据转图谱主流程集成（`database_convert_kg/db_extractor.py` 目前未被 `app.py` 调用）。
- “系统内图谱”与现有前端页面统一入口与切换机制。
- 数据库字段映射规则、实体去重与关系构建策略落地。

---

## 2. 目录结构与职责

```text
/data1/liwu/xintuoyin
├── app.py                          # Flask 主服务（上传、读取图谱、图谱编辑 API）
├── templates/index.html            # 前端可视化页面（D3）
├── getgraph/
│   ├── main.py                     # 文件解析 + LLM 抽取 + 图谱写入
│   ├── prompt/                     # 各文件类别的抽取规则模板
│   ├── graph_data/output_graph.json# 当前图谱数据文件（主读写文件）
│   ├── example.sh                  # 单文件抽取调用示例
│   └── vllm.sh                     # 本地 vLLM 启动示例
├── database_convert_kg/
│   └── db_extractor.py             # 数据库连接与按主键查询原型（开发中）
├── data/user_name/                 # 上传文件存储目录
└── requirement.txt                 # 当前基础依赖（不完整）
```

---

## 3. 运行流程（文件上传路线）

1. 启动模型服务（vLLM/OpenAI 兼容接口）。
2. 启动 Flask 服务（`app.py`）。
3. 浏览器访问页面并上传文件。
4. 后端调用 `getgraph/main.py`：
   - 解析文档内容
   - 识别文件类别
   - 按 `prompt` 规则抽取实体/属性
   - 写入 `getgraph/graph_data/output_graph.json`
5. 前端调用 `/get_graph` 拉取图谱并渲染。

---

## 4. 快速启动

### 4.1 环境要求

- Python 3.10+（建议）
- 可访问的 OpenAI 兼容接口（默认按 vLLM 接口调用）

### 4.2 安装依赖

当前 `requirement.txt` 仅包含最小依赖，建议按代码实际依赖安装：

```bash
pip install -r requirement.txt
pip install openai docling pandas openpyxl click
```

### 4.3 启动 vLLM（可选，按本地模型）

```bash
cd /data1/liwu/xintuoyin/getgraph
bash vllm.sh
```

### 4.4 启动 Web 服务

```bash
cd /data1/liwu/xintuoyin
python3 app.py
```

默认监听：

- `http://0.0.0.0:5002`
- 本机访问：`http://127.0.0.1:5002`

上传文件将保存到：

- `/data1/liwu/xintuoyin/data/user_name`

---

## 5. 关键接口说明（app.py）

### 5.1 页面与图谱读取

- `GET /`：前端页面
- `GET /get_graph`：读取当前图谱（统一返回 `nodes + links`）

### 5.2 文件抽取

- `POST /upload`：上传一个或多个文件并触发抽取
  - 表单字段：`file`（可多文件）
  - 每个文件会调用一次 `getgraph/main.py` 并写入同一图谱文件

### 5.3 图谱编辑

- `POST /graph/node`：新增节点
- `PUT /graph/node/<node_id>`：修改节点（支持改 ID、增量合并 attrs）
- `DELETE /graph/node/<node_id>`：删除节点（并删除相关边）
- `POST /graph/link`：新增关系
- `PUT /graph/link`：修改关系
- `DELETE /graph/link`：删除关系
- `POST /graph/merge`：合并外部图谱（支持传 JSON 或文件路径）
- `POST /graph/clear`：清空图谱

---

## 6. 图谱数据格式

统一格式（`get_graph` 返回 & 持久化格式）：

```json
{
  "nodes": [
    {
      "id": "节点ID",
      "group": 1,
      "attrs": {},
      "file_path": "来源文件名",
      "file_category": "文件类别",
      "type": "excel",
      "table_html": "<table>...</table>"
    }
  ],
  "links": [
    {
      "source": "源节点ID",
      "target": "目标节点ID",
      "relation": "关系名",
      "file_path": "来源文件名",
      "file_category": "文件类别"
    }
  ]
}
```

说明：

- `type=excel` 的节点会在前端以弹窗展示 `table_html`。
- 后端会对节点和关系做去重合并（同 ID 节点、同三元组边）。

---

## 7. 数据库路线（开发中）接手建议

当前 `database_convert_kg/db_extractor.py` 已具备：

- MySQL 连接
- `get_row_by_key(table_name, key, value)` 按主键抓取记录

建议按以下步骤推进：

1. 抽离数据库配置到环境变量（禁止明文写在代码中）。
2. 新增“数据库记录 -> 图谱结构”的转换层，输出与 `nodes + links` 一致。
3. 在 `app.py` 增加数据库图谱接口（例如 `/get_graph_db`）。
4. 前端增加“数据来源切换”（上传图谱 / 数据库图谱）。
5. 复用现有 `deduplicate_graph`、`merge_graph` 逻辑进行统一去重与合并。

---

## 8. 已知问题与注意事项

- 当前存在大量绝对路径，迁移到新机器前需统一替换。
- `requirement.txt` 依赖不完整，首次部署需手动补装。
- 上传接口串行调用抽取脚本，大文件/多文件时耗时较高。
- 数据库配置目前有明文敏感信息，必须在下一阶段治理。
- `getgraph/entity_attribute.py` 为历史草稿，主流程以 `getgraph/main.py` 为准。

---

## 9. 常用命令

### 9.1 单文件离线抽取（调试）

```bash
cd /data1/liwu/xintuoyin/getgraph
bash example.sh
```

### 9.2 内网穿透（可选）

```bash
cd /data1/liwu/xintuoyin
./cpolar http 5002
```

---

## 10. 交接结论

- 现阶段可直接用于“文件上传 -> 图谱抽取 -> 图谱可视化与编辑”的完整闭环。
- 数据库图谱已具备基础访问代码，但尚未纳入线上主链路。
- 后续开发重点应聚焦“数据库映射层 + 接口接入 + 配置安全治理”。
