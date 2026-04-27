# 系统外知识图谱 API 文档

本文档描述了系统外知识图谱（包含多图谱数据库切换、文件上传提取、节点和边编辑）所涉及的所有 API 接口。

---

## 1. 环境与文件管理

### 1.1 获取工作区状态
- **方法**：GET
- **路径**：`/external/workspace/status`
- **功能说明**：获取当前工作区的元数据信息，包括上传的文件列表、图谱节点数、关系数以及可用的图谱数据库列表。
- **请求参数**：无
- **返回结果示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "exists": true,
      "files": ["test.pdf"],
      "last_upload_at": "2023-10-01T12:00:00",
      "node_count": 10,
      "link_count": 5,
      "current_db": "output_graph.json",
      "available_dbs": ["output_graph.json", "test_db.json"]
    }
  }
  ```

### 1.2 切换图谱数据库
- **方法**：POST
- **路径**：`/external/workspace/switch_db`
- **功能说明**：切换当前系统外图谱指向的底层 JSON 数据库文件。
- **请求体** (application/json)：
  - `db_name` (string, 必填): 目标图谱数据库文件名（需以 .json 结尾）
- **返回结果示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "status": "success",
      "current_db": "test_db.json",
      "message": "已切换至图谱: test_db.json"
    }
  }
  ```

### 1.3 创建新图谱数据库
- **方法**：POST
- **路径**：`/external/workspace/create_db`
- **功能说明**：创建一个全新的图谱数据库文件并自动切换到该库。
- **请求体** (application/json)：
  - `db_name` (string, 必填): 新图谱数据库的名称
- **返回结果示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "status": "success",
      "current_db": "new_db.json",
      "message": "已创建并切换至新图谱: new_db.json"
    }
  }
  ```

### 1.4 清空工作区
- **方法**：POST
- **路径**：`/external/workspace/clear`
- **功能说明**：清空当前激活的图谱数据，并删除所有上传暂存的文件。
- **请求参数**：无
- **返回结果示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "status": "success",
      "message": "工作区已清空"
    }
  }
  ```

### 1.5 上传文件提取图谱
- **方法**：POST
- **路径**：`/upload`
- **功能说明**：上传多个文档或图片，通过后台大模型脚本提取图谱数据并合并到当前激活的图谱库中。
- **请求体** (multipart/form-data)：
  - `file` (file, 必填): 支持多文件上传
- **返回结果示例** (200 完全成功 / 207 部分失败)：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "status": "success",
      "message": "成功保存 2 个文件",
      "files": [
        {
          "id": "file_1699999999999_report.pdf",
          "name": "report.pdf",
          "url": "/external/file/report.pdf"
        },
        {
          "id": "file_1700000000001_doc.docx",
          "name": "doc.docx",
          "url": "/external/file/doc.docx"
        }
      ],
      "workspace": {
        "exists": true,
        "files": ["report.pdf", "doc.docx"],
        "node_count": 15,
        "link_count": 8
      },
      "graph": {
        "node_count": 15,
        "link_count": 8
      }
    }
  }
  ```
- **字段说明**：
  - `id`: 服务器为文件生成的唯一标识
  - `name`: 文件原始名称
  - `url`: 文件访问URL，可通过 `/external/file/{filename}` 下载

### 1.6 访问上传的文件
- **方法**：GET
- **路径**：`/external/file/<filename>`
- **功能说明**：根据文件名获取之前上传的文档内容。
- **路径参数**：
  - `filename` (string, 必填): 文件名
- **返回结果**：文件二进制流

---

## 2. 图谱数据获取与编辑

### 2.1 获取当前图谱数据
- **方法**：GET
- **路径**：`/get_graph`
- **功能说明**：获取当前激活图谱的所有节点和关系数据，同时返回当前图谱的标识信息。
- **请求参数**：无
- **返回结果示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "graphId": "output_graph",
      "graphName": "output_graph.json",
      "nodes": [
        {
          "id": "节点ID",
          "group": 1,
          "attrs": {"属性名": "属性值"}
        }
      ],
      "links": [
        {
          "source": "起点节点ID",
          "target": "终点节点ID",
          "relation": "关系名称"
        }
      ]
    }
  }
  ```
- **字段说明**：
  - `graphId`: 图谱ID（自动从文件名生成，去除.json后缀）
  - `graphName`: 图谱完整文件名
  - `nodes`: 节点数组，每个节点包含 `id`（节点唯一标识）、`group`（实体种类：1-人员名称, 2-企业名称, 3-资产名称, 4-其它）、`attrs`（属性字典）
  - `links`: 关系数组

### 2.2 新增节点
- **方法**：POST
- **路径**：`/graph/node`
- **功能说明**：向当前图谱中手动新增一个节点。
- **请求体** (application/json)：
  - `id` (string, 必填): 节点唯一标识/名称
  - `group` (int, 否): 实体种类，默认1。可选值：1-人员名称, 2-企业名称, 3-资产名称, 4-其它
  - `attrs` (object, 否): 节点的属性字典（键值对）
- **返回结果示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "status": "success",
      "node": {
        "id": "新节点ID",
        "group": 1,
        "attrs": {}
      }
    }
  }
  ```

### 2.3 修改节点
- **方法**：PUT
- **路径**：`/graph/node/<node_id>`
- **功能说明**：修改指定节点的信息（支持修改 ID 和增量更新属性）。
- **路径参数**：
  - `node_id` (string, 必填): 原节点的 ID
- **请求体** (application/json)：
  - `id` (string, 否): 新的节点 ID
  - `group` (int, 否): 新的实体种类
  - `attrs` (object, 否): 需要增量更新的属性字典
- **返回结果示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "status": "success",
      "node": {
        "id": "新节点ID",
        "group": 2,
        "attrs": {"更新后的属性": "值"}
      }
    }
  }
  ```

### 2.4 删除节点
- **方法**：DELETE
- **路径**：`/graph/node/<node_id>`
- **功能说明**：删除指定节点，并级联删除与该节点相关的所有边（关系）。
- **路径参数**：
  - `node_id` (string, 必填): 要删除的节点 ID
- **返回结果示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "status": "success",
      "deleted_node": "被删除的节点ID",
      "deleted_links_count": 3
    }
  }
  ```

### 2.5 新增关系
- **方法**：POST
- **路径**：`/graph/link`
- **功能说明**：在两个节点之间新增一条关系边。如果起点或终点节点不存在，会自动创建对应节点（group默认为1）。
- **请求体** (application/json)：
  - `source` (string, 必填): 起点节点 ID
  - `target` (string, 必填): 终点节点 ID
  - `relation` (string, 必填): 关系名称/边类型
- **返回结果示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "status": "success",
      "link": {
        "source": "起点节点ID",
        "target": "终点节点ID",
        "relation": "关系名称"
      }
    }
  }
  ```

### 2.6 修改关系
- **方法**：PUT
- **路径**：`/graph/link`
- **功能说明**：修改现有的某条关系边。
- **请求体** (application/json)：
  - `old_source` (string, 必填): 原起点 ID
  - `old_target` (string, 必填): 原终点 ID
  - `old_relation` (string, 必填): 原关系名称
  - `source` (string, 否): 新起点 ID
  - `target` (string, 否): 新终点 ID
  - `relation` (string, 否): 新关系名称
- **返回结果示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "status": "success",
      "link": {
        "source": "新起点节点ID",
        "target": "新终点节点ID",
        "relation": "新关系名称"
      }
    }
  }
  ```

### 2.7 删除关系
- **方法**：DELETE
- **路径**：`/graph/link`
- **功能说明**：删除指定的某条关系边。
- **请求体** (application/json)：
  - `source` (string, 必填): 起点节点 ID
  - `target` (string, 必填): 终点节点 ID
  - `relation` (string, 必填): 关系名称/边类型
- **返回结果示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "status": "success",
      "deleted_link": {
        "source": "起点节点ID",
        "target": "终点节点ID",
        "relation": "关系名称"
      }
    }
  }
  ```

### 2.8 图谱合并
- **方法**：POST
- **路径**：`/graph/merge`
- **功能说明**：将外部传入的图谱 JSON 数据合并到当前图谱中（执行去重策略）。
- **请求体** (application/json)：
  - `graph` (object, 否): 包含 nodes 和 links 的图谱对象
  - `file_path` (string, 否): 服务器本地的待合并 JSON 文件绝对路径
- **返回结果示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "status": "success",
      "base_node_count": 10,
      "base_link_count": 5,
      "incoming_node_count": 8,
      "incoming_link_count": 3,
      "merged_node_count": 15,
      "merged_link_count": 7
    }
  }
  ```

### 2.9 清空当前图谱数据
- **方法**：POST
- **路径**：`/graph/clear`
- **功能说明**：单纯清空当前激活数据库文件内的图谱节点和连线数据（不删除文件本身和工作区上传暂存记录）。
- **请求参数**：无
- **返回结果示例**：
  ```json
  {
    "code": 0,
    "msg": "成功",
    "data": {
      "status": "success",
      "message": "图谱已清空"
    }
  }
  ```

---

## 3. 实体种类说明

系统外图谱的节点 `group` 字段用于标识实体类型：

| group 值 | 实体类型 | 说明 |
|----------|----------|------|
| 1 | 人员名称 | 负责人、参与人员、专家等 |
| 2 | 企业名称 | 甲方乙方、协作单位、购买方销售方等 |
| 3 | 资产名称 | 项目名称、成果名称、发票类型等 |
| 4 | 其它 | 不可抗力、部门等未分类实体 |

---

## 4. 错误码说明

| HTTP 状态码 | code 值 | 说明 |
|-------------|---------|------|
| 200 | 0 | 成功 |
| 400 | 400 | 请求参数错误 |
| 404 | 404 | 资源不存在 |
| 409 | 409 | 资源冲突（如重复创建） |
| 500 | 500 | 服务器内部错误 |
