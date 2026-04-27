# 图谱系统二次开发接口文档

## 本次修改的两个接口总结

---

### 1. `/upload` 接口

**位置**: `app.py`

**功能**: 上传文件提取图谱，根据参数决定图谱存储位置。其中 `isDefault=true` 时不直接写系统内 SQL 图谱，而是写入一份固定的“系统内绑定图谱文件”，展示时始终与系统内图谱合并。

**调用逻辑**:

```
┌─────────────────────────────────────────────────────────────────┐
│                        /upload POST请求                          │
│                    (multipart/form-data)                         │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────────┐
              │   解析 isDefault 参数      │
              │   (默认 true)              │
              └───────────┬───────────────┘
                          │
            ┌─────────────┴─────────────┐
            │                           │
            ▼                           ▼
    ┌───────────────┐            ┌───────────────┐
    │ isDefault=true│            │isDefault=false│
    └───────┬───────┘            └───────┬───────┘
            │                            │
            ▼                            ▼
    ┌──────────────────────┐    ┌─────────────────────────────┐
    │ 保存上传文件到         │    │  graphId 是否为空?           │
    │ internal_binding      │    ├─────────────┬─────────────┤
    │ workspace/uploads     │    │   为空        │  非空        │
    └──────────┬───────────┘    │   ▼            ▼            │
               │                │ 创建新数据库   切换到指定数据库 │
               ▼                │ new_graph_xxx.json  graphId.json
    ┌──────────────────────┐    └─────────────┬─────────────┘
    │ 提取单文件图谱到临时文件 │                  │
    └──────────┬───────────┘                  ▼
               │                 ┌─────────────────────────────┐
               ▼                 │  执行 run_external_extractor │
    ┌──────────────────────┐     │  保存到当前激活的外部图谱数据库 │
    │ 合并到固定绑定文件     │     └─────────────────────────────┘
    │ internal_binding_     │
    │ graph.json           │
    └──────────┬───────────┘
               │
               ▼
    ┌──────────────────────┐
    │ /api/combined_graph  │
    │ 自动合并展示          │
    │ 系统内图谱 + 绑定图谱 │
    └──────────────────────┘
```

**参数说明**:

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `file` | file[] | 必填 | 上传的文件 |
| `isDefault` | boolean | `true` | `true`→系统内绑定图谱文件（始终与系统内图谱一起展示），`false`→外部图谱数据库 |
| `graphId` | string | 空 | 仅`isDefault=false`时有效。空=创建新数据库，非空=匹配现有数据库 |

**返回值**:

```json
{
  "code": 0,
  "msg": "成功",
  "data": {
    "status": "success",
    "message": "成功处理 N 个文件并挂载到系统内绑定图谱",
    "isDefault": true,
    "files": [...],
    "merged_to": "internal_binding_graph",
    "binding_graph": {
      "graphId": "internal_binding_graph",
      "graphName": "internal_binding_graph.json",
      "node_count": N,
      "link_count": M
    },
    "graph": { "node_count": X, "link_count": Y }
  }
}
```

**运行时文件说明**:

- 系统内绑定图谱文件：`runtime/internal_binding_workspace/internal_binding_graph.json`
- 系统内绑定上传目录：`runtime/internal_binding_workspace/uploads/`
- 每次 `isDefault=true` 上传后，抽取结果会持续合并到这份固定文件中。

---

### 2. `/api/combined_graph` 接口

**位置**: `modules/Graph/backend/api/routes.py`

**功能**: 获取系统内图谱和系统内绑定图谱文件的合并数据

**调用逻辑**:

```
┌─────────────────────────────────────────┐
│         /api/combined_graph GET         │
└─────────────────┬───────────────────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  1. 获取系统内图谱   │
        │  GraphService      │
        │  .get_graph()       │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  2. 读取绑定图谱文件   │
        │  runtime/internal_  │
        │  binding_workspace/ │
        │  internal_binding_  │
        │  graph.json         │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  3. 合并节点        │
        │  internal + binding │
        │  按 id 去重         │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  4. 合并关系         │
        │  source+target+relation│
        │  三元组去重          │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  5. 返回合并结果     │
        └─────────────────────┘
```

**返回值**:

```json
{
  "code": 0,
  "msg": "成功",
  "data": {
    "graphId": "combined_graph",
    "graphName": "combined",
    "nodes": [
      { "id": "节点1", "group": 1, "attrs": {...} },
      ...
    ],
    "links": [
      { "source": "节点1", "target": "节点2", "relation": "关系" },
      ...
    ]
  }
}
```

---

### 两接口关系图

```
前端/客户端
    │
    ├──────────────────┐
    │                  │
    ▼                  ▼
/upload            /api/combined_graph
(提交文件)          (获取图谱)
    │                  │
    ▼                  │
isDefault?             │
    │                  │
    ├─true────────────►│  合并展示
    │   系统内图谱 + 绑定图谱 │
    │                  │
    └─false           │
        外部图谱数据库   │
        (独立展示，不参与此接口)
```

---

## 使用示例

### 1. 上传文件到系统内绑定图谱

```bash
curl -X POST http://localhost:5000/upload \
  -F "file=@document.pdf" \
  -F "isDefault=true"
```

### 2. 上传文件到外部图谱（新数据库）

```bash
curl -X POST http://localhost:5000/upload \
  -F "file=@document.pdf" \
  -F "isDefault=false"
```

### 3. 上传文件到现有外部图谱

```bash
curl -X POST http://localhost:5000/upload \
  -F "file=@document.pdf" \
  -F "isDefault=false" \
  -F "graphId=output_graph"
```

### 4. 获取合并图谱

```bash
curl http://localhost:5000/api/combined_graph
```

---

### 3. `/api/get_all_graph` 接口

**位置**: `modules/Graph/backend/api/routes.py`

**功能**: 一次导出全部图谱，便于导入其他平台。返回内容包含：

- 系统内 SQL 图谱
- 系统内绑定图谱文件
- 所有系统外图谱数据库文件

**过滤规则**:

- 不包含 `workspace_meta.json`
- 不包含 `temp_extracted_*.json`

**返回值示例**:

```json
{
  "code": 0,
  "msg": "成功",
  "data": {
    "exported_at": "2026-04-22T12:34:56",
    "graph_count": 5,
    "internal_graph_count": 2,
    "external_graph_count": 3,
    "graphs": [
      {
        "graphId": "internal_sql_graph",
        "graphName": "internal_sql_graph.json",
        "scope": "internal",
        "source": "sql_provider",
        "storageType": "sql",
        "persisted": false,
        "isActive": true,
        "node_count": 128,
        "link_count": 220,
        "file_path": null,
        "nodes": [...],
        "links": [...]
      },
      {
        "graphId": "output_graph",
        "graphName": "output_graph.json",
        "scope": "external",
        "source": "external_workspace",
        "storageType": "json_file",
        "persisted": true,
        "isActive": true,
        "file_path": "runtime/external_workspace/output_graph.json",
        "nodes": [...],
        "links": [...]
      }
    ]
  }
}
```

**使用示例**:

```bash
curl http://localhost:5000/api/get_all_graph
```
