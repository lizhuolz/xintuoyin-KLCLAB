# 综合知识图谱系统（Graph + xintuoyin 融合版）

本版本按“最小改动、分层重构”的原则完成融合：

- **系统内知识图谱**：沿用 `Graph` 的前后端与数据库图谱接口，作为默认主界面。
- **系统外知识图谱**：沿用 `xintuoyin` 的文件上传、抽取、图谱编辑与完整原页面展示能力。
- **融合方式**：新增一个壳层 Flask 应用 `app.py`，统一对外提供入口；两个原项目代码继续分别保存在 `modules/Graph` 与 `modules/xintuoyin` 中，避免硬合并。

---

## 一、实现效果

启动后：

1. 首页默认显示 **系统内知识图谱**。
2. 顶部保留 **上传文件生成系统外图谱** 按钮。
3. 上传成功后，会新增一个 **系统外知识图谱** 子界面标签。
4. 点击该标签后，通过 iframe 完整显示原 `xintuoyin` 页面。
5. 子界面支持 **删除**，删除后会：
   - 清空系统外图谱数据；
   - 删除上传文件；
   - 隐藏系统外子界面标签。

---

## 二、目录结构

```text
merged_app/
├── app.py                         # 新增综合入口
├── requirements.txt
├── runtime/
│   └── external_workspace/        # 系统外图谱运行时数据
│       ├── uploads/
│       ├── output_graph.json
│       └── workspace_meta.json
└── modules/
    ├── Graph/                     # 原系统内图谱项目（基本保留）
    │   ├── backend/
    │   └── frontend/
    └── xintuoyin/                 # 原系统外图谱项目（基本保留）
        ├── getgraph/
        └── templates/
```

---

## 三、关键设计说明

### 1. 为什么没有把两个项目代码彻底揉在一起

因为你的要求是：

- 尽量不修改原代码；
- 后端将两个项目代码分开；
- 只做重构。

所以本方案采用的是：

- `Graph` 继续负责数据库图谱；
- `xintuoyin` 继续负责文件图谱；
- 壳层应用只负责：**统一入口、路由装配、子界面切换、系统外工作区生命周期管理**。

### 2. 主界面为什么选 `Graph`

这符合你的需求：**打开系统时主界面显示系统内知识图谱**。

### 3. 为什么系统外页面使用 iframe 承载

因为你要求：**完整展示原先的系统外图谱**。

如果强行把 `xintuoyin` 的大段前端逻辑改写进 `Graph` 前端，会改动很大、风险高。iframe 方式能够：

- 保持原页面几乎不动；
- 保留原上传、搜索、路径分析、图谱编辑等完整能力；
- 外层只新增切换与删除控制。

---

## 四、运行方式

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动综合系统

```bash
python app.py
```

默认读取 `Graph/backend/config.py` 中的启动配置。

---

## 五、环境变量（建议）

系统外图谱抽取仍会调用 `modules/xintuoyin/getgraph/main.py`，可以通过环境变量覆盖模型配置：

```bash
export EXTERNAL_GRAPH_API_BASE=http://localhost:8000/v1
export EXTERNAL_GRAPH_MODEL_PATH=/data1/public/models/Qwen2.5-32B-Instruct
```

说明：

- `EXTERNAL_GRAPH_API_BASE`：OpenAI 兼容接口地址
- `EXTERNAL_GRAPH_MODEL_PATH`：传给抽取脚本的模型名/路径

---

## 六、当前保留的接口

### 系统内图谱（Graph）

- `GET /api/health`
- `GET /api/current-user`
- `GET /api/graph`
- `GET /api/node/<node_id>`
- `GET /api/search?keyword=xxx`

### 系统外图谱（xintuoyin 能力）

- `POST /upload`
- `GET /get_graph`
- `POST /graph/node`
- `PUT /graph/node/<node_id>`
- `DELETE /graph/node/<node_id>`
- `POST /graph/link`
- `PUT /graph/link`
- `DELETE /graph/link`
- `POST /graph/merge`
- `POST /graph/clear`

### 壳层新增接口

- `GET /external/workspace/status`
- `POST /external/workspace/clear`
- `GET /external-view`

---

## 七、你后续如果还要继续完善，建议这样做

### 1. 如果要支持多个系统外子界面

当前实现是“一个系统外工作区”。如果你后续要支持：

- 每次上传生成一个独立子界面；
- 支持多个图谱批次切换；

可以把 `runtime/external_workspace` 改造成多工作区目录，例如：

```text
runtime/external_workspaces/<workspace_id>/
```

然后把当前的：

- `output_graph.json`
- `workspace_meta.json`
- `uploads/`

都下沉到每个 workspace 目录中。

### 2. 如果要进一步减少 iframe 感

可以再做一步：

- 把 `xintuoyin/templates/index.html` 里的接口地址全部参数化；
- 再把公共样式和头部工具条抽出去；
- 最后把页面嵌进统一布局。

但这一步属于“中等重构”，不再是最小改动。

---

## 八、当前交付结论

这份融合版已经满足你提出的核心目标：

- 两个项目代码仍然分开；
- 主界面默认是系统内知识图谱；
- 保留系统外上传文件能力；
- 上传后新增一个可切换、可删除的系统外图谱子界面；
- 子界面中完整展示原先系统外图谱页面。


## 本次修正

- 将 Graph 后端改为标准 Python 包导入，避免 `from api.routes`、`from config import settings` 这类依赖启动目录的脆弱写法。
- 新增 `modules/__init__.py`、`modules/Graph/__init__.py`、`modules/Graph/backend/__init__.py` 等包标记文件。
- 补齐 `runtime/external_workspace/` 初始化文件，避免压缩包中的空目录丢失。
- 启动时若运行期图谱文件不存在，会自动初始化空的 `output_graph.json` 与 `workspace_meta.json`。
