# 系统内数据库知识图谱 API 文档

本文档描述系统内数据库知识图谱（基于SQL数据库的只读图谱展示、检索、节点详情）相关接口。

所有接口统一返回格式：

```json
{
  "code": 0,
  "msg": "成功",
  "data": { ... }
}
```

系统内接口为**只读接口**，不包含上传、编辑、合并、清空等写操作。

---

## 1. 基础接口

### 1.1 健康检查
- **方法**：GET
- **路径**：`/api/health`
- **功能说明**：检查服务健康状态与当前 provider。
- **返回示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "status": "ok",
    "app": "graph_service",
    "provider": "sql"
  }
  ```

### 1.2 可用 Provider 查询
- **方法**：GET
- **路径**：`/api/providers`
- **功能说明**：返回当前可用的图谱数据提供者列表。
- **返回示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "default_provider": "sql",
    "available_providers": ["sql"]
  }
  ```

### 1.3 当前用户
- **方法**：GET
- **路径**：`/api/current-user`
- **功能说明**：返回当前登录企业/用户信息。
- **返回示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "enterprise_id": "xxx",
      "enterprise_name": "示例企业"
    }
  }
  ```

### 1.4 系统内图谱状态
- **方法**：GET
- **路径**：`/api/internal/workspace/status`
- **功能说明**：返回系统内图谱是否可用、节点数、关系数和图谱标识。
- **返回示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "exists": true,
      "node_count": 128,
      "link_count": 220,
      "graphId": "internal_sql_graph",
      "graphName": "internal_sql_graph.json",
      "available_graphs": ["internal_sql_graph.json"]
    }
  }
  ```

---

## 2. 图谱数据获取

### 2.1 获取系统内图谱（完整结构）
- **方法**：GET
- **路径**：`/api/graph`
- **功能说明**：获取当前系统内图谱全部节点与关系（包含 graphId、graphName 元信息）。
- **返回示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "graphId": "internal_sql_graph",
      "graphName": "internal_sql_graph.json",
      "nodes": [...],
      "links": [...]
    }
  }
  ```

### 2.2 获取系统内图谱（精简结构）
- **方法**：GET
- **路径**：`/api/get_graph`
- **功能说明**：获取当前系统内图谱全部节点与关系（与系统外 `test2.json` 同款交互结构，顶层直接是 `nodes` / `links`）。
- **返回示例**：
  ```json
  {
    "nodes": [
      {
        "id": "U_INTANGIBLE_ASSET_7e4f1d21b7aa9b8c",
        "name": "软著A",
        "group": 1,
        "attrs": {
          "资产名称": "软著A",
          "资产编码": "WX001"
        }
      }
    ],
    "links": [
      {
        "source": "enterprise_id",
        "target": "U_INTANGIBLE_ASSET_7e4f1d21b7aa9b8c",
        "relation": "包含"
      }
    ]
  }
  ```

### 2.3 获取系统内图谱（别名）
- **方法**：GET
- **路径**：`/api/internal/get_graph`
- **功能说明**：与 `/api/graph` 接口相同，返回完整结构的图谱数据。
- **返回示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "graphId": "internal_sql_graph",
      "graphName": "internal_sql_graph.json",
      "nodes": [...],
      "links": [...]
    }
  }
  ```

### 2.4 节点搜索
- **方法**：GET
- **路径**：`/api/search?keyword=关键词`
- **功能说明**：按节点名称/ID模糊匹配返回候选节点。
- **请求参数**：
  - `keyword` (string, 必填): 搜索关键词
- **返回示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "keyword": "软著",
    "data": [
      {
        "id": "U_INTANGIBLE_ASSET_7e4f1d21b7aa9b8c",
        "name": "软著A",
        "level": 2,
        "parent_id": "enterprise_id",
        "type": "无形资产",
        "identity_key": "软著A"
      }
    ]
  }
  ```
- **返回字段说明**：
  - `id`: 节点唯一标识
  - `name`: 节点名称
  - `level`: 节点层级深度
  - `parent_id`: 父节点 ID
- `type`: 节点类型
- `identity_key`: 实体身份标识键

### 2.5 获取系统内+绑定图谱合并视图
- **方法**：GET
- **路径**：`/api/combined_graph`
- **功能说明**：获取系统内 SQL 图谱与固定系统内绑定图谱文件的合并结果。
- **返回示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "graphId": "combined_graph",
      "graphName": "combined",
      "nodes": [...],
      "links": [...]
    }
  }
  ```

### 2.6 导出全部图谱
- **方法**：GET
- **路径**：`/api/get_all_graph`
- **功能说明**：一次返回当前可导出的全部图谱，包含：
  - 系统内 SQL 图谱
  - 系统内绑定图谱文件
  - 所有系统外图谱数据库文件
- **说明**：
  - 该接口用于跨平台导入/备份。
  - 系统外目录中的 `workspace_meta.json`、`temp_extracted_*.json` 不会计入导出结果。
- **返回示例**：
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
          "graphId": "internal_binding_graph",
          "graphName": "internal_binding_graph.json",
          "scope": "internal",
          "source": "internal_binding_workspace",
          "storageType": "json_file",
          "persisted": true,
          "isActive": true,
          "file_path": "runtime/internal_binding_workspace/internal_binding_graph.json",
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
- **返回字段说明**：
  - `exported_at`: 导出时间
  - `graph_count`: 导出的图谱总数
  - `internal_graph_count`: 系统内图谱数量
  - `external_graph_count`: 系统外图谱数量
  - `graphs`: 图谱数组
  - `scope`: `internal` 或 `external`
  - `source`: 图谱来源
  - `storageType`: 存储类型，当前为 `sql` 或 `json_file`
  - `persisted`: 是否为持久化存储
  - `isActive`: 是否为当前激活图谱
  - `file_path`: 图谱文件相对路径；SQL 图谱为 `null`

### 2.7 节点详情
- **方法**：GET
- **路径**：`/api/node/<node_id>`
- **功能说明**：返回指定节点详情视图（后端 resolver 结果，包含多来源属性块）。
- **路径参数**：
  - `node_id` (string, 必填): 节点 ID
- **返回示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "id": "U_INTANGIBLE_ASSET_7e4f1d21b7aa9b8c",
      "name": "软著A",
      "type": "无形资产",
      "attrs_blocks": [
        {
          "title": "项目库-项目-无形资产",
          "attrs": {
            "资产名称": "软著A",
            "获得方式": "自主研发"
          }
        },
        {
          "title": "财务-无形资产",
          "attrs": {
            "资产名称": "软著A",
            "原值": "50000.00"
          }
        }
      ]
    }
  }
  ```
- **返回字段说明**：
  - `id`: 节点唯一标识
  - `name`: 节点名称
  - `type`: 节点类型
  - `attrs_blocks`: 属性块数组，按来源分块展示属性

---

## 3. 实体种类说明

系统内图谱的节点 `group` 字段用于标识实体类型（与系统外图谱一致）：

| group 值 | 实体类型 | 说明 |
|----------|----------|------|
| 1 | 人员名称 | 项目人员、员工姓名等 |
| 2 | 企业名称 | 协作单位、企业主体等 |
| 3 | 资产名称 | 固定资产、无形资产、项目等 |
| 4 | 其它 | 其他未分类实体 |

---

## 4. 统一实体规则

系统内图谱已对以下实体执行统一（统一后仅保留一个节点）：

### 4.1 人员名称统一
来源包括：
- 项目库-项目-项目人员-员工姓名
- 人事-成员-部门-员工姓名
- 人事-工资-员工姓名
- 人事-考勤-员工姓名

### 4.2 固定资产统一
来源包括：
- 项目库-项目-固定资产-资产名称
- 财务-固定资产-资产名称
- 人事-考勤组-资产名称（固定资产类型）

### 4.3 无形资产统一
来源包括：
- 项目库-项目-无形资产-资产名称
- 财务-无形资产-资产名称
- 人事-考勤组-资产名称（无形资产类型）

**资产编码规则**：
- 固定资产编码以 `GD` 开头
- 无形资产编码以 `WX` 开头
- 当出现考勤组资产类型不明确时，后端会优先按编码前缀判定资产类型

---

## 5. 说明

- 本文档对应系统内数据库图谱接口，为**只读接口**。
- 系统外接口（包含写操作）请参考根目录文档：`external_graph_api.md`。
