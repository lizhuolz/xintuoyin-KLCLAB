# api_feedback_list

## success

- status: PASS
- method: GET
- path: /api/feedback/list

### request
```json
{
  "type": "like"
}
```

### response
```json
{
  "code": 0,
  "msg": "获取反馈列表成功",
  "data": {
    "list": [
      {
        "id": "fb_conv-feedback-list_0",
        "conversation_id": "conv-feedback-list",
        "message_index": 0,
        "type": "like",
        "state": "like",
        "reasons": [],
        "comment": "",
        "pictures": [],
        "name": "王颖奇",
        "enterprise": "图湃（北京）医疗科技",
        "phone": "15323720032",
        "time": "1774367355101",
        "update_time": "1774367355101",
        "createdAt": "2026/03/24 23:49:15",
        "updatedAt": "2026/03/24 23:49:15",
        "process_status": "未处理"
      }
    ],
    "total": 1
  }
}
```

## filter_no_match

- status: PASS
- method: GET
- path: /api/feedback/list

### request
```json
{
  "enterprise": "不存在企业"
}
```

### response
```json
{
  "code": 0,
  "msg": "获取反馈列表成功",
  "data": {
    "list": [],
    "total": 0
  }
}
```

## invalid_time

- status: PASS
- method: GET
- path: /api/feedback/list

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
