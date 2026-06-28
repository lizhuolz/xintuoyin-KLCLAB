# 图谱编辑 API

本文档面向直接调用后端接口的场景，不依赖旧前端页面。

## 目标

- 所有编辑接口都支持按 `graphId` 精确操作指定图谱
- 不传 `graphId` 时，保持兼容，默认操作当前图谱
- 支持外部图谱和内部绑定图谱

## graphId 规则

- 外部图谱：传图谱文件名去掉 `.json` 之后的值
  - 例如：`new_graph_1777295337138`
- 内部绑定图谱：固定传 `internal_binding_graph`
- 非法值会返回 `400`
  - 例如：包含路径、`..`、`workspace_meta`
- 指定图谱不存在会返回 `404`

## 节点类型 group

- `1`：人员
- `2`：企业
- `3`：资产/项目
- `4`：其它/文件

编辑节点时可以直接修改 `group`。

## 查询图谱

### `GET /get_graph`

按 `graphId` 查询图谱。

示例：

```bash
curl 'http://127.0.0.1:8000/get_graph?graphId=new_graph_1777295337138'
```

返回示例：

```json
{
  "code": 0,
  "msg": "成功",
  "data": {
    "graphId": "new_graph_1777295337138",
    "graphName": "new_graph_1777295337138.json",
    "nodes": [],
    "links": []
  }
}
```

## 节点接口

### `POST /graph/node`

新增节点。

请求体示例：

```json
{
  "graphId": "new_graph_1777295337138",
  "id": "person_zhangsan",
  "group": 1,
  "attrs": {
    "姓名": "张三",
    "部门": "研发部"
  }
}
```

### `PUT /graph/node/<node_id>`

修改节点。

- 支持修改 `id`
- 支持修改 `group`
- `attrs` 按增量合并，不会覆盖掉原有全部属性

请求体示例：

```json
{
  "graphId": "new_graph_1777295337138",
  "id": "person_zhangsan_v2",
  "group": 2,
  "attrs": {
    "企业名称": "张三工作室"
  }
}
```

### `DELETE /graph/node/<node_id>`

删除节点，同时删除与该节点关联的边。

请求体示例：

```json
{
  "graphId": "new_graph_1777295337138"
}
```

## 关系接口

### `POST /graph/link`

新增关系。

- 若 `source` 或 `target` 不存在，会自动补一个空节点
- 自动补节点时默认 `group=1`，如需精确类型，建议先建节点再建边

请求体示例：

```json
{
  "graphId": "new_graph_1777295337138",
  "source": "contract.docx",
  "target": "person_zhangsan",
  "relation": "项目联系人"
}
```

### `PUT /graph/link`

修改关系。

- 通过 `old_source + old_target + old_relation` 定位原关系
- 可更新 `source`、`target`、`relation`
- 也可附带额外字段

请求体示例：

```json
{
  "graphId": "new_graph_1777295337138",
  "old_source": "contract.docx",
  "old_target": "person_zhangsan",
  "old_relation": "项目联系人",
  "relation": "负责人",
  "note": "manually adjusted"
}
```

### `DELETE /graph/link`

删除关系。

请求体示例：

```json
{
  "graphId": "new_graph_1777295337138",
  "source": "contract.docx",
  "target": "person_zhangsan",
  "relation": "负责人"
}
```

## 图谱级接口

### `POST /graph/merge`

把外部图谱并入指定图谱。

支持两种输入：

- `graph`：直接传图谱 JSON
- `file_path`：传本地 JSON 文件路径

请求体示例：

```json
{
  "graphId": "new_graph_1777295337138",
  "graph": {
    "nodes": [
      {"id": "project_a", "group": 3, "attrs": {"项目名称": "项目A"}}
    ],
    "links": []
  }
}
```

### `POST /graph/clear`

清空指定图谱。

请求体示例：

```json
{
  "graphId": "new_graph_1777295337138"
}
```

## 返回约定

编辑成功时，返回体里的 `data.graphId` 一定是最终被操作的图谱：

```json
{
  "code": 0,
  "msg": "成功",
  "data": {
    "status": "success",
    "graphId": "new_graph_1777295337138",
    "graph": {}
  }
}
```
