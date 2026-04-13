# api_feedback_file_download

## success

- status: PASS
- method: GET
- path: /api/feedback/{feedback_id}/files/{file_id}/download

### request
```json
{
  "feedback_id": "fb_conv-feedback-file-1775711887900_0",
  "file_id": "file-1"
}
```

### response
```json
{
  "status_code": 200,
  "content_length": 16
}
```
