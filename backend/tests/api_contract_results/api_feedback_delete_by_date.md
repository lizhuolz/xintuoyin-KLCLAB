# api_feedback_delete_by_date

## success

- status: PASS
- method: DELETE
- path: /api/feedback/{date}/{id}

### request
```json
{
  "date": "2026-04-01",
  "id": "fb_conv-feedback-delete_0"
}
```

### response
```json
{
  "code": 0,
  "msg": "删除反馈成功",
  "data": {
    "id": "fb_conv-feedback-delete_0"
  }
}
```

## not_found

- status: PASS
- method: DELETE
- path: /api/feedback/{date}/{id}

### request
```json
{
  "date": "2099-01-01",
  "id": "fb_missing_0"
}
```

### response
```json
{
  "code": 1,
  "msg": "删除反馈失败",
  "data": {
    "id": "fb_missing_0"
  }
}
```
