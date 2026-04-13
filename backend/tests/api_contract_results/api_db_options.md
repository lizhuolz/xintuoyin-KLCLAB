# api_db_options

## success

- status: PASS
- method: GET
- path: /api/db/options
- notes: 数据库切换先读选项接口，再将返回的 value 作为 /api/chat 的 db_version 传入。

### request
```json
{}
```

### response
```json
{
  "code": 0,
  "msg": "获取数据库选项成功",
  "data": {
    "options": [
      {
        "label": "数据库1",
        "value": "1"
      },
      {
        "label": "数据库2",
        "value": "2"
      }
    ]
  }
}
```
