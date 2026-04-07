# api_kb_update

## success

- status: PASS
- method: POST
- path: /api/kb/update

### request
```json
{
  "id": "kb_1",
  "remark": "新的备注",
  "enabled": "false"
}
```

### response
```json
{
  "code": 0,
  "msg": "更新知识库成功",
  "data": {
    "id": "kb_1",
    "name": "更新库",
    "category": "知识库",
    "model": "openai",
    "remark": "新的备注",
    "enabled": false,
    "users": [
      {
        "name": "张三",
        "phone": "1",
        "categoryName": "企业"
      }
    ],
    "fileCount": 0,
    "url": "知识库/更新库",
    "physical_path": "知识库/更新库",
    "owner_info": "",
    "created_at": "1",
    "updated_at": "2",
    "createdAt": "2026/03/24 00:00:00",
    "updatedAt": "2026/03/24 00:00:01",
    "files": [],
    "preview": false,
    "pending": {
      "delete_files": [],
      "upload_files": [],
      "metadata": {
        "remark": "新的备注",
        "enabled": false,
        "users": [
          {
            "name": "张三",
            "phone": "1",
            "categoryName": "企业"
          }
        ]
      },
      "confirm_required": false
    }
  }
}
```

## confirm_delete_and_upload

- status: PASS
- method: POST
- path: /api/kb/update
- notes: 知识库更新在 confirm=true 时应一次性提交元数据、删文件和传文件。

### request
```json
{
  "id": "kb_1",
  "remark": "确认备注",
  "delete_files": [
    "old.txt"
  ],
  "confirm": true,
  "files": [
    "new.txt"
  ]
}
```

### response
```json
{
  "code": 0,
  "msg": "更新知识库成功",
  "data": {
    "id": "kb_1",
    "name": "确认更新库",
    "category": "知识库",
    "model": "openai",
    "remark": "确认备注",
    "enabled": true,
    "users": [],
    "fileCount": 1,
    "url": "知识库/确认更新库",
    "physical_path": "知识库/确认更新库",
    "owner_info": "",
    "created_at": "1",
    "updated_at": "2",
    "createdAt": "2026/03/24 00:00:00",
    "updatedAt": "2026/03/24 00:00:01",
    "files": [
      {
        "file_id": "kb_1:new.txt",
        "name": "new.txt",
        "url": "知识库/确认更新库/new.txt",
        "size": 3,
        "uploaded_at": "3",
        "uploadedAt": "2026/03/24 00:00:02"
      }
    ],
    "preview": false,
    "pending": {
      "delete_files": [
        "old.txt"
      ],
      "upload_files": [
        "new.txt"
      ],
      "metadata": {
        "remark": "确认备注"
      },
      "confirm_required": false
    }
  }
}
```

## invalid_delete_files_json

- status: PASS
- method: POST
- path: /api/kb/update

### request
```json
{
  "id": "kb_1",
  "delete_files": "{\"bad\": true}"
}
```

### response
```json
{
  "code": 1,
  "msg": "更新知识库失败",
  "data": {
    "reason": "delete_files 必须是数组"
  }
}
```

## invalid_users_json

- status: PASS
- method: POST
- path: /api/kb/update

### request
```json
{
  "id": "kb_1",
  "users": "{bad json"
}
```

### response
```json
{
  "code": 1,
  "msg": "更新知识库失败",
  "data": {
    "reason": "users 字段不是合法 JSON"
  }
}
```

## not_found

- status: PASS
- method: POST
- path: /api/kb/update

### request
```json
{
  "id": "kb_missing",
  "remark": "新的备注"
}
```

### response
```json
{
  "code": 1,
  "msg": "更新知识库失败",
  "data": {
    "id": "kb_missing"
  }
}
```

## preview_delete_and_upload

- status: PASS
- method: POST
- path: /api/kb/update
- notes: 知识库更新支持预览模式，在 confirm=false 时只返回待删除/待上传结果，不真正落库。

### request
```json
{
  "id": "kb_1",
  "remark": "预览备注",
  "delete_files": [
    "old.txt"
  ],
  "confirm": false,
  "files": [
    "new.txt"
  ]
}
```

### response
```json
{
  "code": 0,
  "msg": "预览知识库更新成功",
  "data": {
    "id": "kb_1",
    "name": "预览更新库",
    "category": "知识库",
    "model": "openai",
    "remark": "预览备注",
    "enabled": true,
    "users": [],
    "fileCount": 1,
    "url": "知识库/预览更新库",
    "physical_path": "知识库/预览更新库",
    "owner_info": "",
    "created_at": "1",
    "updated_at": "2",
    "createdAt": "2026/03/24 00:00:00",
    "updatedAt": "2026/03/24 00:00:01",
    "files": [
      {
        "file_id": "pending:new.txt",
        "name": "new.txt",
        "url": "知识库/预览更新库/new.txt",
        "size": 0,
        "uploaded_at": "",
        "uploadedAt": "待提交"
      }
    ],
    "preview": true,
    "pending": {
      "delete_files": [
        "old.txt"
      ],
      "upload_files": [
        "new.txt"
      ],
      "metadata": {
        "remark": "预览备注"
      },
      "confirm_required": true
    }
  }
}
```
