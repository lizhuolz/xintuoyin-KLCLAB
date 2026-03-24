# api_history_list

## success

- status: PASS
- method: GET
- path: /api/history/list

### request
```json
{
  "search": "历史测试"
}
```

### response
```json
{
  "code": 0,
  "msg": "获取历史记录成功",
  "data": {
    "list": [
      {
        "conversation_id": "conv-history",
        "title": "历史测试",
        "updated_at": "1774367355203",
        "updatedAt": "2026/03/24 23:49:15",
        "message_count": 1,
        "user": {
          "name": "王颖奇",
          "phone": "15323720032",
          "categoryName": "图湃（北京）医疗科技"
        }
      }
    ],
    "total": 1
  }
}
```

## case_insensitive_search

- status: PASS
- method: GET
- path: /api/history/list

### request
```json
{
  "search": "alpha"
}
```

### response
```json
{
  "code": 0,
  "msg": "获取历史记录成功",
  "data": {
    "list": [
      {
        "conversation_id": "conv-case",
        "title": "Alpha Beta",
        "updated_at": "1774367355214",
        "updatedAt": "2026/03/24 23:49:15",
        "message_count": 1,
        "user": {
          "name": "王颖奇",
          "phone": "15323720032",
          "categoryName": "图湃（北京）医疗科技"
        }
      }
    ],
    "total": 1
  }
}
```

## invalid_time

- status: PASS
- method: GET
- path: /api/history/list

### request
```json
{
  "start_time": "bad-ts"
}
```

### response
```json
{
  "code": 1,
  "msg": "获取历史记录失败",
  "data": {
    "reason": "start_time 必须是毫秒时间戳字符串或整数"
  }
}
```
