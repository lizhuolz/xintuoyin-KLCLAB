# Backend API Detailed Documentation

基于 `backend/app.py` 当前实现与 `backend/tests/test_api.py`、`backend/tests/reports/api_test_report.md` 的实际测试结果整理。

## 1. 通用约定

### 1.1 服务信息
- 应用名: `KLCLAB Backend API`
- 默认本地启动入口: `python backend/app.py`
- 当前重启脚本观测到的后端端口: `8069`

### 1.2 通用响应头
除流式接口外，所有 JSON 接口都会返回:
- `Content-Type: application/json`
- `X-Request-ID: <服务端生成的请求 ID>`

### 1.3 通用 JSON 响应结构

成功响应:
```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "业务成功消息",
  "data": {},
  "request_id": "f6f1c7..."
}
```

失败响应:
```json
{
  "success": false,
  "code": "ERROR_CODE",
  "message": "错误说明",
  "data": null,
  "detail": {},
  "request_id": "f6f1c7..."
}
```

说明:
- `detail` 仅在部分失败场景存在。
- `request_id` 由中间件注入，便于日志追踪。
- 路由级 404 也会进入统一异常处理，返回 `code=HTTP_ERROR`。

### 1.4 标识符校验规则
以下字段使用相同的标识符约束:
- `conversation_id`
- `id` 知识库 ID

允许字符:
- 字母 `a-z A-Z`
- 数字 `0-9`
- `-`
- `_`

非法示例:
- `bad.id`
- `../kb1`
- `中文id`
- `kb 001`

业务层错误码:
- `INVALID_CONVERSATION_ID`
- `INVALID_KB_ID`

注意:
- 包含 `/` 的路径参数可能先被路由层拦截成 404，而不会进入业务校验。

## 2. 接口清单

- `DELETE /api/chat/{conversation_id}` 删除对话历史
- `POST /api/chat` 对话接口，返回流式纯文本
- `GET /api/kb/list` 获取知识库列表
- `GET /api/test/file_tree` 获取 documents 文件树
- `POST /api/kb/create` 创建知识库
- `POST /api/kb/update` 更新知识库
- `DELETE /api/kb/{id}` 删除知识库
- `GET /api/kb/{id}/files` 获取知识库文件列表
- `POST /api/kb/{id}/upload` 上传知识库文件
- `POST /api/kb/{id}/delete_file` 删除知识库文件

## 3. 详细接口说明

## 3.1 DELETE /api/chat/{conversation_id}

用途:
- 删除后端磁盘中保存的某轮对话 JSON 历史。

路径参数:
- `conversation_id: string` 必填，仅允许字母数字下划线连字符。

成功响应:
- HTTP `200`
```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "对话历史删除成功",
  "data": {
    "conversation_id": "conv001"
  },
  "request_id": "sample-request-id"
}
```

边界与失败返回:
- 非法 `conversation_id`
  - HTTP `400`
  - `code: INVALID_CONVERSATION_ID`
  - `message: conversation_id格式非法`
- 历史不存在
  - HTTP `404`
  - `code: CONVERSATION_NOT_FOUND`
  - `message: 对话历史不存在`
- 文件删除失败
  - HTTP `500`
  - `code: DELETE_CONVERSATION_FAILED`
```json
{
  "success": false,
  "code": "DELETE_CONVERSATION_FAILED",
  "message": "删除对话历史失败",
  "data": null,
  "detail": {
    "error": "permission denied"
  },
  "request_id": "sample-request-id"
}
```

已验证测试:
- 成功删除
- 不存在会话
- 非法 ID
- `os.remove` 异常

## 3.2 POST /api/chat

用途:
- 提交一轮对话，Agent 以流式纯文本返回回答。

请求类型:
- `multipart/form-data`

表单参数:
- `message: string` 必填，去掉空白后不能为空。
- `conversation_id: string` 必填。
- `files: UploadFile[]` 可选，支持多个附件。
- `system_prompt: string` 可选，空白时回退为 `You are a helpful assistant`。
- `web_search: bool` 可选，默认 `false`。
- `db_version: string` 可选，非空时会前置到用户消息中。
- `kb_category: string` 可选，非空时写入系统提示词。
- `user_identity: string` 可选，空白时回退为 `guest`。

成功响应:
- HTTP `200`
- `Content-Type: text/plain; charset=utf-8`
- 响应体为连续文本流，不是 JSON。

成功样例:
```text
你好，世界
```

内部行为:
- 会对 `message` 执行输入安全检查。
- 会提取附件内容并拼进上下文。
- 超长附件会截断，保留前后文。
- 对话成功输出后会落盘到 `history_storage/<conversation_id>.json`。
- 若流式过程中异常，不会切成 JSON 错误，而是继续输出一段错误文本。

边界与失败返回:
- `message` 为空白
  - HTTP `400`
  - `code: EMPTY_MESSAGE`
  - `message: message不能为空`
- `conversation_id` 非法
  - HTTP `400`
  - `code: INVALID_CONVERSATION_ID`
  - `message: conversation_id格式非法`
- 输入安全拦截
  - HTTP `400`
  - `code: INPUT_BLOCKED`
  - `message` 为安全模块返回内容，例如 `输入被拦截`
- 表单缺失必填字段
  - HTTP `422`
  - `code: REQUEST_VALIDATION_ERROR`
  - `message: 请求参数校验失败`
  - `detail` 为 FastAPI 校验错误数组

流式异常返回:
- HTTP 状态仍是 `200`
- 追加输出:
```text
[系统错误][request_id=<request_id>] stream boom
```

附件解析边界:
- 支持 `.pdf` `.docx` `.xlsx` `.xls` 和其他 UTF-8 文本文件。
- PDF/Office 解析失败时，不中断请求，只跳过该文件内容。
- 超长文件会插入类似提示:
```text
[文件内容过长，已截取前 1000 字符和后 3000 字符，中间省略 N 字符]
```

已验证测试:
- 正常流式输出
- 默认值回退
- `db_version` 与 `kb_category` 注入
- 输入安全拦截
- 非法会话 ID
- 空消息
- 超长文本附件截断
- 坏 PDF 容错
- 流式异常输出 request_id

## 3.3 GET /api/kb/list

用途:
- 获取知识库列表。

请求参数:
- 无

成功响应:
- HTTP `200`
```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "知识库列表获取成功",
  "data": [
    {
      "id": "kb123456",
      "name": "默认知识库",
      "model": "openai",
      "category": "企业知识库",
      "physical_path": "企业知识库/默认知识库",
      "remark": "",
      "users": ["tester"],
      "enabled": true,
      "updatedAt": "2026/03/24 12:00:00",
      "fileCount": 1
    }
  ],
  "request_id": "sample-request-id"
}
```

边界与失败返回:
- 代码层无显式业务校验。
- 若底层 `kb_service.load_all()` 抛异常，会进入统一异常处理:
  - HTTP `500`
  - `code: INTERNAL_SERVER_ERROR`
  - `message: 系统内部错误`

已验证测试:
- 成功获取列表

## 3.4 GET /api/test/file_tree

用途:
- 返回 `documents` 目录的物理树结构。

请求参数:
- 无

成功响应 1: documents 存在
- HTTP `200`
- `message: 文件树获取成功`
```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "文件树获取成功",
  "data": [
    {
      "label": "企业知识库",
      "children": [
        {
          "label": "默认知识库",
          "children": [
            {
              "label": "说明.txt"
            }
          ]
        }
      ]
    }
  ],
  "request_id": "sample-request-id"
}
```

成功响应 2: documents 不存在
- HTTP `200`
- `message: documents 目录不存在，返回空树`
```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "documents 目录不存在，返回空树",
  "data": [],
  "request_id": "sample-request-id"
}
```

边界说明:
- 忽略隐藏文件和 `__pycache__`。
- 目录和文件混排时，目录优先排序。

已验证测试:
- 目录存在
- 目录不存在

补充说明:
- 在当前重启后的运行实例健康检查里，此接口实际返回过 `404`。这说明运行中的服务版本可能与当前 `backend/app.py` 不一致，或健康探针访问了错误实例。

## 3.5 POST /api/kb/create

用途:
- 创建知识库。

请求类型:
- `multipart/form-data`

表单参数:
- `name: string` 必填，去空白后不能为空。
- `model: string` 可选，默认 `openai`。
- `category: string` 可选参数定义了默认值 `users/guest`，但如果显式传空白字符串仍会触发业务校验失败。

成功响应:
- HTTP `201`
- `message: 知识库创建成功`

边界与失败返回:
- `name` 空白
  - HTTP `400`
  - `code: EMPTY_KB_NAME`
  - `message: name不能为空`
- `category` 空白
  - HTTP `400`
  - `code: EMPTY_KB_CATEGORY`
  - `message: category不能为空`
- 缺失 `name`
  - HTTP `422`
  - `code: REQUEST_VALIDATION_ERROR`

已验证测试:
- 成功创建
- 空白名称

## 3.6 POST /api/kb/update

用途:
- 更新知识库元信息。

请求类型:
- `multipart/form-data`

表单参数:
- `id: string` 必填。
- `name: string` 可选，若传入则不能为空白。
- `remark: string` 可选。
- `enabled: bool` 可选。
- `users: string` 可选，必须是 JSON 数组字符串。

成功响应:
- HTTP `200`
- `message: 知识库更新成功`

成功样例:
```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "知识库更新成功",
  "data": {
    "id": "kb123456",
    "name": "更新后知识库",
    "remark": "备注",
    "users": ["alice", "bob"],
    "enabled": false
  },
  "request_id": "sample-request-id"
}
```

边界与失败返回:
- `id` 非法
  - HTTP `400`
  - `code: INVALID_KB_ID`
- 知识库不存在
  - HTTP `404`
  - `code: KB_NOT_FOUND`
  - `message: 知识库不存在`
- `name` 传入空白
  - HTTP `400`
  - `code: EMPTY_KB_NAME`
- `users` 不是合法 JSON
  - HTTP `400`
  - `code: INVALID_USERS_FIELD`
  - `message: users 必须是合法的 JSON 数组字符串`
  - `detail.error` 含 JSON 解析错误信息
- `users` 是 JSON 但不是数组
  - HTTP `400`
  - `code: INVALID_USERS_FIELD`
  - `message: users 必须是 JSON 数组`
- 除 `id` 外没有任何更新字段
  - HTTP `400`
  - `code: EMPTY_UPDATE_PAYLOAD`
  - `message: 没有可更新的字段`

已验证测试:
- 成功更新
- 非法 ID
- KB 不存在
- `users` 非 JSON
- `users` 非数组
- 空更新载荷

## 3.7 DELETE /api/kb/{id}

用途:
- 删除知识库并尝试刷新索引。

路径参数:
- `id: string` 必填。

成功响应 1: 删除成功且索引刷新成功
- HTTP `200`
- `message: 知识库删除成功`
```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "知识库删除成功",
  "data": {
    "id": "kb123456",
    "index_refresh": {
      "refreshed": true,
      "error": null
    }
  },
  "request_id": "sample-request-id"
}
```

成功响应 2: 删除成功但索引刷新失败
- HTTP `200`
- `message: 知识库删除成功，但索引刷新失败`
```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "知识库删除成功，但索引刷新失败",
  "data": {
    "id": "kb123456",
    "index_refresh": {
      "refreshed": false,
      "error": "refresh failed"
    }
  },
  "request_id": "sample-request-id"
}
```

边界与失败返回:
- 非法 `id`
  - HTTP `400`
  - `code: INVALID_KB_ID`
- 知识库不存在
  - HTTP `404`
  - `code: KB_NOT_FOUND`
- 删除失败
  - HTTP `500`
  - `code: DELETE_KB_FAILED`

已验证测试:
- 成功删除
- 不存在 KB
- 刷新索引失败但删除成功

## 3.8 GET /api/kb/{id}/files

用途:
- 获取知识库文件列表。

路径参数:
- `id: string` 必填。

成功响应:
- HTTP `200`
- `message: 知识库文件列表获取成功`
```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "知识库文件列表获取成功",
  "data": [
    {
      "name": "readme.txt",
      "size": "0.0 KB"
    }
  ],
  "request_id": "sample-request-id"
}
```

边界与失败返回:
- 非法 `id`
  - HTTP `400`
  - `code: INVALID_KB_ID`
- 知识库不存在
  - HTTP `404`
  - `code: KB_NOT_FOUND`

已验证测试:
- 成功获取文件列表
- 非法 ID

## 3.9 POST /api/kb/{id}/upload

用途:
- 上传文件到指定知识库，并尝试刷新索引。

请求类型:
- `multipart/form-data`

路径参数:
- `id: string` 必填。

表单参数:
- `file: UploadFile` 必填。

成功响应 1: 上传成功且索引刷新成功
- HTTP `201`
- `message: 文件上传成功`
```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "文件上传成功",
  "data": {
    "id": "kb123456",
    "filename": "manual.txt",
    "index_refresh": {
      "refreshed": true,
      "error": null
    }
  },
  "request_id": "sample-request-id"
}
```

成功响应 2: 上传成功但索引刷新失败
- HTTP `201`
- `message: 文件上传成功，但索引刷新失败`

边界与失败返回:
- 非法 `id`
  - HTTP `400`
  - `code: INVALID_KB_ID`
- 知识库不存在
  - HTTP `404`
  - `code: KB_NOT_FOUND`
- 业务层检测到空文件名
  - HTTP `400`
  - `code: EMPTY_FILE_NAME`
  - `message: 上传文件名不能为空`
- `kb_service.save_file()` 抛 `ValueError`
  - HTTP `400`
  - `code: INVALID_FILE_NAME`
- `kb_service.save_file()` 抛其他异常
  - HTTP `500`
  - `code: UPLOAD_FILE_FAILED`
```json
{
  "success": false,
  "code": "UPLOAD_FILE_FAILED",
  "message": "文件上传失败",
  "data": null,
  "detail": {
    "error": "disk full"
  },
  "request_id": "sample-request-id"
}
```
- 缺失 `file`
  - 理论上 HTTP `422`
  - `code: REQUEST_VALIDATION_ERROR`

当前已发现的真实异常行为:
- 当 multipart 中提交空文件名时，FastAPI 在进入业务逻辑前抛出 `RequestValidationError`。
- 该错误的 `detail.ctx.error` 含 `ValueError` 对象，而统一错误响应直接把 `exc.errors()` 放进 JSON，导致序列化失败。
- 实际结果不是预期的 `400/422 JSON`，而是服务内部 `500`。

实际观测错误摘要:
- 触发场景: 空文件名上传
- 实际表现: `TypeError: Object of type ValueError is not JSON serializable`
- 根因位置: `handle_validation_error()` -> `error_response()`

已验证测试:
- 成功上传
- KB 不存在
- 存储异常
- 索引刷新失败
- 空文件名触发真实缺陷

## 3.10 POST /api/kb/{id}/delete_file

用途:
- 删除知识库中的指定文件，并尝试刷新索引。

请求类型:
- `multipart/form-data`

路径参数:
- `id: string` 必填。

表单参数:
- `filename: string` 必填，去空白后不能为空。

成功响应 1: 删除成功且索引刷新成功
- HTTP `200`
- `message: 文件删除成功`

成功响应 2: 删除成功但索引刷新失败
- HTTP `200`
- `message: 文件删除成功，但索引刷新失败`
```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "文件删除成功，但索引刷新失败",
  "data": {
    "id": "kb123456",
    "filename": "manual.txt",
    "index_refresh": {
      "refreshed": false,
      "error": "refresh failed"
    }
  },
  "request_id": "sample-request-id"
}
```

边界与失败返回:
- 非法 `id`
  - HTTP `400`
  - `code: INVALID_KB_ID`
- 知识库不存在
  - HTTP `404`
  - `code: KB_NOT_FOUND`
- `filename` 为空白
  - HTTP `400`
  - `code: EMPTY_FILE_NAME`
  - `message: filename不能为空`
- 文件不存在
  - HTTP `404`
  - `code: FILE_NOT_FOUND`
  - `message: 文件不存在`
- 底层删除抛 `ValueError`
  - HTTP `400`
  - `code: INVALID_FILE_NAME`
- 底层删除抛其他异常
  - HTTP `500`
  - `code: DELETE_FILE_FAILED`
```json
{
  "success": false,
  "code": "DELETE_FILE_FAILED",
  "message": "文件删除失败",
  "data": null,
  "detail": {
    "error": "unlink failed"
  },
  "request_id": "sample-request-id"
}
```

已验证测试:
- 成功删除
- 空文件名
- 文件不存在
- 内部异常
- 索引刷新失败

## 4. 全局异常与边界行为

### 4.1 请求参数校验失败
统一处理器:
- `handle_validation_error()`

理论返回:
- HTTP `422`
- `code: REQUEST_VALIDATION_ERROR`
- `message: 请求参数校验失败`
- `detail: exc.errors()`

样例:
```json
{
  "success": false,
  "code": "REQUEST_VALIDATION_ERROR",
  "message": "请求参数校验失败",
  "data": null,
  "detail": [
    {
      "loc": ["body", "message"],
      "msg": "Field required",
      "type": "missing"
    }
  ],
  "request_id": "sample-request-id"
}
```

实际风险:
- 若 `exc.errors()` 中包含不可 JSON 序列化对象，会反向触发 500。
- 当前已在空文件名上传场景中复现。

### 4.2 路由未命中
统一处理器:
- `handle_http_error()`

返回:
- HTTP `404`
- `code: HTTP_ERROR`
- `message: Not Found`

### 4.3 未处理异常
统一处理器:
- `handle_unexpected_error()`

返回:
- HTTP `500`
- `code: INTERNAL_SERVER_ERROR`
- `message: 系统内部错误`
- `detail.error` 为异常字符串

样例:
```json
{
  "success": false,
  "code": "INTERNAL_SERVER_ERROR",
  "message": "系统内部错误",
  "data": null,
  "detail": {
    "error": "disk full"
  },
  "request_id": "sample-request-id"
}
```

## 5. 测试覆盖摘要

当前单元测试覆盖结论:
- 总数: `39`
- 通过: `38`
- 失败: `0`
- 错误: `1`

唯一错误用例:
- `test_upload_kb_file_empty_filename`

说明:
- 该错误不是测试代码问题，而是当前服务实现的真实异常路径缺陷。

## 6. 建议修复项

建议优先修复两点:
1. 在 `handle_validation_error()` 中将 `exc.errors()` 做 JSON 可序列化清洗，避免 `ValueError` 等对象直接进入响应体。
2. 将健康检查端口与 `conda_restart_services.sh` 实际启动端口统一，避免接口探针误测到旧实例或错误实例。
