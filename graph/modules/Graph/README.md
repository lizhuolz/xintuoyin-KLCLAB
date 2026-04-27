# 树状数据图谱系统（SQL 版可运行脚手架）

这是一个基于 **SQL 数据源** 的树状数据图谱系统脚手架，已经完成以下整理：

- 删除了全部 mock provider / mock 数据切换逻辑
- 前后端统一只使用 **SQL provider**
- 图谱仍保持“企业为根节点、固定一级节点 + 动态 SQL 子节点”的原有框架
- 节点详情改为 **按节点类型分发的详情解析器**，不再强制使用统一的 basic / dynamic / metrics 固定展示逻辑
- 后端代码已做拆分，方便你继续补 SQL 查询、补树节点、补详情模板

---

## 1. 当前项目结构

```text
Graph/
├── README.md
├── db_test.py
├── backend/
│   ├── app.py
│   ├── config.py
│   ├── requirements.txt
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── builders/
│   │   ├── __init__.py
│   │   └── graph_builder.py
│   ├── db/
│   │   ├── __init__.py
│   │   └── connection.py
│   ├── detail/
│   │   ├── __init__.py
│   │   └── resolvers.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── graph_models.py
│   ├── providers/
│   │   ├── __init__.py
│   │   └── sql_provider.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── graph_repository.py
│   └── services/
│       ├── __init__.py
│       ├── graph_service.py
│       └── user_service.py
└── frontend/
    ├── index.html
    └── assets/
        ├── css/
        │   └── styles.css
        └── js/
            ├── api.js
            ├── app.js
            ├── graph.js
            └── utils.js
```

---

## 2. 这次改了什么

### 2.1 删除 mock 相关逻辑

已删除：

- `backend/providers/mock_provider.py`
- `backend/providers/base.py`
- `backend/providers/factory.py`
- 前端 provider 下拉切换
- 所有 `?provider=mock` / `?provider=sql` 的前端调用方式

现在系统固定走：

- `backend/providers/sql_provider.py`

前端顶部仍保留 `Provider: sql` 标识，但它只是展示信息，不再允许切换。

### 2.2 节点详情从“统一接口”改为“可定制详情模板”

之前右侧详情面板默认写死为：

- 基础信息
- 动态信息
- 指标信息
- 说明

现在改为：

- 后端通过 `detail/resolvers.py` 按节点类型分发详情模板
- 当前已内置模板：
  - `enterprise`
  - `domain`
  - `DEPT`
  - `STAFF`
  - `default`
- 前端根据后端返回的 `view.sections` 动态渲染，不再绑定固定字段结构

也就是说，后续你想给某一类节点单独定制展示内容时，只需要：

1. 在 `detail/resolvers.py` 增加一个 resolver
2. 在 `DETAIL_RESOLVERS` 里注册节点类型
3. 返回自定义的 section 列表

不需要再改统一详情接口的整体逻辑。

### 2.3 后端代码拆分

为了方便你后续继续扩展，这次把原本堆在一个 provider 里的逻辑拆开了：

- `db/connection.py`
  - 数据库连接
- `repositories/graph_repository.py`
  - 纯 SQL 查询
- `builders/graph_builder.py`
  - 把 SQL 查询结果组装成图谱节点树
- `detail/resolvers.py`
  - 节点详情模板分发与组织
- `providers/sql_provider.py`
  - 负责串联 repository + builder + detail resolver

这样你以后补代码时职责会更清晰：

- 要补 SQL：改 `repositories`
- 要改树结构：改 `builders`
- 要改右侧详情展示：改 `detail`
- 要改接口行为：改 `services` 或 `api`

---

## 3. 当前接口

### 健康检查

```http
GET /api/health
```

### 当前用户

```http
GET /api/current-user
```

### 图谱数据

```http
GET /api/get_graph
```

与 `external_graph_api.md` 对齐的系统内展示别名：

```http
GET /api/internal/get_graph
GET /api/internal/workspace/status
```

### 节点详情

```http
GET /api/node/<node_id>
```

### 搜索节点

```http
GET /api/search?keyword=张三
```

---

## 4. 节点详情新返回结构

节点详情接口现在返回的是“节点元信息 + 详情视图定义”，示例：

```json
{
  "id": "4_STAFF_1001",
  "name": "张三",
  "type": "STAFF",
  "category": "dynamic",
  "level": 4,
  "summary": "工号：A001",
  "tags": [],
  "fixed": false,
  "leaf": true,
  "identity_key": "STAFF:1001",
  "parent_id": "3_DEPT_2001",
  "side": "right",
  "exists": true,
  "view": {
    "template": "staff",
    "sections": [
      {
        "type": "kv",
        "title": "员工档案",
        "items": [
          {"label": "员工ID", "value": "1001"},
          {"label": "姓名", "value": "张三"}
        ]
      },
      {
        "type": "text",
        "title": "节点说明",
        "content": "员工叶子节点，后续可继续补简历、证照、考勤统计等扩展内容。"
      }
    ]
  }
}
```

前端是根据 `view.sections` 渲染的，因此后续你可以为不同节点类型生成完全不同的内容块。

---

## 5. 你后续最常改的地方

### 补更多 SQL 查询

在：

- `backend/repositories/graph_repository.py`

例如继续增加：

- 财务节点查询
- 工资节点查询
- 考勤节点查询
- 项目库节点查询
- 风险点节点查询

### 改树结构

在：

- `backend/builders/graph_builder.py`

例如：

- 新增固定一级节点
- 给财务节点挂发票子树
- 给员工节点挂合同 / 证照 / 考勤统计子节点

### 改详情面板逻辑

在：

- `backend/detail/resolvers.py`

例如：

- 给 `salary_domain` 单独做工资统计视图
- 给 `project` 节点做“项目概览 + 成员列表 + 进度说明”
- 给 `finance_bill` 节点做“票据信息 + 金额信息 + 关联主体”

---

## 6. 运行方式

进入后端目录：

```bash
cd backend
```

安装依赖：

```bash
pip install -r requirements.txt
```

启动：

```bash
python app.py
```

浏览器打开：

```text
http://127.0.0.1:5000
```

---

## 7. 当前实现说明

当前图谱仍然保持“可运行优先”的实现方式：

- 企业根节点来自 `T_ENTERPRISE`
- 人事 > 成员 > 部门 > 员工 已接入 SQL 查询
- 工资 / 考勤 / 财务 等节点仍保留骨架，方便你继续补全
- 若数据库不可连接，系统会返回 SQL 占位树，保证前端不报错

如果你下一步要继续扩展，我建议优先顺序是：

1. 在 `repositories` 把剩余业务域 SQL 查出来
2. 在 `builders` 里把这些业务域挂到树上
3. 在 `detail/resolvers.py` 里为新节点类型补专属详情模板

这样后续系统会比较稳，也不会再出现“一个 provider 文件越写越大”的问题。
