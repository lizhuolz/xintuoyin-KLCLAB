# Backend API Test Checklist

适用范围:
- `backend/app.py`
- 面向接口测试与回归测试
- 默认服务以实际运行端口为准，当前重启脚本观测端口为 `8069`

使用说明:
- 每条用例执行后勾选结果。
- 除流式接口外，所有 JSON 接口都应检查 `X-Request-ID` 响应头存在。
- 除特别说明外，所有 JSON 接口都应检查响应字段包含 `success`、`code`、`message`、`request_id`。

通用检查项:
- [ ] 响应头包含 `X-Request-ID`
- [ ] 成功响应 `success=true`
- [ ] 失败响应 `success=false`
- [ ] JSON 接口 `Content-Type=application/json`
- [ ] 流式接口 `Content-Type` 包含 `text/plain`

## 1. DELETE /api/chat/{conversation_id}

前置条件:
- 准备一个已存在的历史文件，例如 `history_storage/conv001.json`

### 1.1 删除成功
- [ ] 请求: `DELETE /api/chat/conv001`
- [ ] 预期状态码: `200`
- [ ] 预期 `code=SUCCESS`
- [ ] 预期 `message=对话历史删除成功`
- [ ] 预期 `data.conversation_id=conv001`
- [ ] 预期历史文件被删除

### 1.2 会话不存在
- [ ] 请求: `DELETE /api/chat/not_exist_001`
- [ ] 预期状态码: `404`
- [ ] 预期 `code=CONVERSATION_NOT_FOUND`
- [ ] 预期 `message=对话历史不存在`

### 1.3 非法 conversation_id
- [ ] 请求: `DELETE /api/chat/bad.id`
- [ ] 预期状态码: `400`
- [ ] 预期 `code=INVALID_CONVERSATION_ID`
- [ ] 预期 `message=conversation_id格式非法`

### 1.4 删除文件异常
- [ ] 前置: 模拟 `os.remove()` 抛异常
- [ ] 请求: `DELETE /api/chat/conv_delete_fail`
- [ ] 预期状态码: `500`
- [ ] 预期 `code=DELETE_CONVERSATION_FAILED`
- [ ] 预期 `detail.error` 含异常信息

## 2. POST /api/chat

请求类型:
- `multipart/form-data`

必填字段:
- `message`
- `conversation_id`

### 2.1 基本对话成功
- [ ] 请求包含 `message=你好` `conversation_id=conv002`
- [ ] 预期状态码: `200`
- [ ] 预期 `Content-Type` 包含 `text/plain`
- [ ] 预期返回内容为模型输出文本
- [ ] 预期生成 `history_storage/conv002.json`
- [ ] 预期历史中包含 user 与 assistant 两条消息

### 2.2 默认参数回退
- [ ] 请求中 `system_prompt` 传空白
- [ ] 请求中 `user_identity` 传空白
- [ ] 预期系统内部回退到 `You are a helpful assistant`
- [ ] 预期系统内部回退到 `guest`

### 2.3 输入安全拦截
- [ ] 前置: 模拟安全模块返回不安全
- [ ] 请求: `message=危险内容`
- [ ] 预期状态码: `400`
- [ ] 预期 `code=INPUT_BLOCKED`
- [ ] 预期 `message` 为安全模块返回信息

### 2.4 message 为空白
- [ ] 请求: `message=   `
- [ ] 预期状态码: `400`
- [ ] 预期 `code=EMPTY_MESSAGE`
- [ ] 预期 `message=message不能为空`

### 2.5 conversation_id 非法
- [ ] 请求: `conversation_id=bad.id`
- [ ] 预期状态码: `400`
- [ ] 预期 `code=INVALID_CONVERSATION_ID`

### 2.6 缺失必填字段
- [ ] 请求中缺少 `message` 或 `conversation_id`
- [ ] 预期状态码: `422`
- [ ] 预期 `code=REQUEST_VALIDATION_ERROR`
- [ ] 预期 `detail` 为校验错误数组

### 2.7 指定 db_version
- [ ] 请求增加 `db_version=v2`
- [ ] 预期消息上下文前缀包含 `从数据库v2中`

### 2.8 指定 kb_category
- [ ] 请求增加 `kb_category=企业知识库`
- [ ] 预期系统提示词包含指定分类说明

### 2.9 web_search 开关
- [ ] 请求增加 `web_search=true`
- [ ] 预期下游接收到 `enable_web=true`

### 2.10 上传超长文本附件
- [ ] 上传一个超长 `txt` 文件
- [ ] 预期请求成功
- [ ] 预期附件内容被截断而不是整体塞入
- [ ] 预期上下文中包含 `文件内容过长，已截取前`
- [ ] 预期同时保留文件头部和尾部片段

### 2.11 上传损坏 PDF
- [ ] 上传无法解析的 `pdf`
- [ ] 预期请求仍返回 `200`
- [ ] 预期不会因为附件解析失败中断整个对话
- [ ] 预期模型仍可基于原始 message 正常返回

### 2.12 流式过程中下游异常
- [ ] 前置: 模拟 `agent_app.astream()` 抛异常
- [ ] 预期状态码仍为 `200`
- [ ] 预期响应文本中包含 `[系统错误][request_id=`
- [ ] 预期响应文本包含异常信息
- [ ] 预期不会写入成功历史

## 3. GET /api/kb/list

### 3.1 获取列表成功
- [ ] 请求: `GET /api/kb/list`
- [ ] 预期状态码: `200`
- [ ] 预期 `code=SUCCESS`
- [ ] 预期 `message=知识库列表获取成功`
- [ ] 预期 `data` 为数组
- [ ] 每个元素至少包含 `id` `name` `category` `enabled` `updatedAt`

### 3.2 底层服务异常
- [ ] 前置: 模拟 `kb_service.load_all()` 抛异常
- [ ] 预期状态码: `500`
- [ ] 预期 `code=INTERNAL_SERVER_ERROR`

## 4. GET /api/test/file_tree

### 4.1 documents 存在
- [ ] 请求: `GET /api/test/file_tree`
- [ ] 预期状态码: `200`
- [ ] 预期 `message=文件树获取成功`
- [ ] 预期 `data` 为树形数组
- [ ] 预期节点至少包含 `label`

### 4.2 documents 不存在
- [ ] 前置: 删除或隔离 `documents` 目录
- [ ] 请求: `GET /api/test/file_tree`
- [ ] 预期状态码: `200`
- [ ] 预期 `message=documents 目录不存在，返回空树`
- [ ] 预期 `data=[]`

### 4.3 过滤隐藏文件
- [ ] 前置: 在 `documents` 下创建隐藏文件或 `__pycache__`
- [ ] 预期返回结果中不包含这些节点

注意:
- 当前运行实例健康检查中该接口曾返回 `404`，测试前先确认访问的是正确端口和正确版本服务。

## 5. POST /api/kb/create

请求类型:
- `multipart/form-data`

### 5.1 创建成功
- [ ] 请求: `name=新增知识库` `model=openai` `category=部门知识库/技术部`
- [ ] 预期状态码: `201`
- [ ] 预期 `message=知识库创建成功`
- [ ] 预期返回对象包含 `id` `name` `category`

### 5.2 name 为空白
- [ ] 请求: `name=   `
- [ ] 预期状态码: `400`
- [ ] 预期 `code=EMPTY_KB_NAME`
- [ ] 预期 `message=name不能为空`

### 5.3 category 为空白
- [ ] 请求: `category=   `
- [ ] 预期状态码: `400`
- [ ] 预期 `code=EMPTY_KB_CATEGORY`
- [ ] 预期 `message=category不能为空`

### 5.4 缺失 name
- [ ] 请求中不传 `name`
- [ ] 预期状态码: `422`
- [ ] 预期 `code=REQUEST_VALIDATION_ERROR`

## 6. POST /api/kb/update

请求类型:
- `multipart/form-data`

### 6.1 更新成功
- [ ] 请求: `id=kb123456` 并传入 `name` `remark` `enabled` `users`
- [ ] 预期状态码: `200`
- [ ] 预期 `message=知识库更新成功`
- [ ] 预期 `users` 被解析为数组
- [ ] 预期 `enabled` 生效

### 6.2 非法 id
- [ ] 请求: `id=bad.id`
- [ ] 预期状态码: `400`
- [ ] 预期 `code=INVALID_KB_ID`

### 6.3 知识库不存在
- [ ] 请求: `id=missing001`
- [ ] 预期状态码: `404`
- [ ] 预期 `code=KB_NOT_FOUND`

### 6.4 name 传空白
- [ ] 请求: `name=   `
- [ ] 预期状态码: `400`
- [ ] 预期 `code=EMPTY_KB_NAME`

### 6.5 users 不是合法 JSON
- [ ] 请求: `users=not-json`
- [ ] 预期状态码: `400`
- [ ] 预期 `code=INVALID_USERS_FIELD`
- [ ] 预期 `detail.error` 含 JSON 解析错误

### 6.6 users 不是数组
- [ ] 请求: `users={"name":"alice"}`
- [ ] 预期状态码: `400`
- [ ] 预期 `code=INVALID_USERS_FIELD`
- [ ] 预期 `message=users 必须是 JSON 数组`

### 6.7 没有任何可更新字段
- [ ] 请求只传 `id`
- [ ] 预期状态码: `400`
- [ ] 预期 `code=EMPTY_UPDATE_PAYLOAD`
- [ ] 预期 `message=没有可更新的字段`

## 7. DELETE /api/kb/{id}

### 7.1 删除成功
- [ ] 请求: `DELETE /api/kb/kb123456`
- [ ] 预期状态码: `200`
- [ ] 预期 `message=知识库删除成功`
- [ ] 预期 `data.id=kb123456`
- [ ] 预期 `data.index_refresh.refreshed=true`

### 7.2 非法 id
- [ ] 请求: `DELETE /api/kb/bad.id`
- [ ] 预期状态码: `400`
- [ ] 预期 `code=INVALID_KB_ID`

### 7.3 KB 不存在
- [ ] 请求: `DELETE /api/kb/missing001`
- [ ] 预期状态码: `404`
- [ ] 预期 `code=KB_NOT_FOUND`

### 7.4 删除成功但索引刷新失败
- [ ] 前置: 模拟 `force_refresh_index()` 抛异常
- [ ] 预期状态码: `200`
- [ ] 预期 `message=知识库删除成功，但索引刷新失败`
- [ ] 预期 `data.index_refresh.refreshed=false`
- [ ] 预期 `data.index_refresh.error` 为异常信息

### 7.5 删除动作本身失败
- [ ] 前置: 模拟 `kb_service.delete_kb()` 返回 `False`
- [ ] 预期状态码: `500`
- [ ] 预期 `code=DELETE_KB_FAILED`

## 8. GET /api/kb/{id}/files

### 8.1 获取文件列表成功
- [ ] 请求: `GET /api/kb/kb123456/files`
- [ ] 预期状态码: `200`
- [ ] 预期 `message=知识库文件列表获取成功`
- [ ] 预期 `data` 为数组
- [ ] 预期文件项包含 `name` `size`

### 8.2 非法 id
- [ ] 请求: `GET /api/kb/bad.id/files`
- [ ] 预期状态码: `400`
- [ ] 预期 `code=INVALID_KB_ID`

### 8.3 KB 不存在
- [ ] 请求: `GET /api/kb/missing001/files`
- [ ] 预期状态码: `404`
- [ ] 预期 `code=KB_NOT_FOUND`

## 9. POST /api/kb/{id}/upload

请求类型:
- `multipart/form-data`

### 9.1 上传成功
- [ ] 请求: 上传 `manual.txt`
- [ ] 预期状态码: `201`
- [ ] 预期 `message=文件上传成功`
- [ ] 预期 `data.filename=manual.txt`
- [ ] 预期 `data.index_refresh.refreshed=true`

### 9.2 非法 id
- [ ] 请求: `POST /api/kb/bad.id/upload`
- [ ] 预期状态码: `400`
- [ ] 预期 `code=INVALID_KB_ID`

### 9.3 KB 不存在
- [ ] 请求: `POST /api/kb/missing001/upload`
- [ ] 预期状态码: `404`
- [ ] 预期 `code=KB_NOT_FOUND`

### 9.4 缺失 file 字段
- [ ] 请求中不传 `file`
- [ ] 预期状态码: `422`
- [ ] 预期 `code=REQUEST_VALIDATION_ERROR`

### 9.5 空文件名
- [ ] 请求上传空文件名
- [ ] 理论预期: `400` 或 `422`
- [ ] 当前实际: 触发服务 `500`
- [ ] 记录为已知缺陷，不作为通过标准
- [ ] 预期日志中可见 `Object of type ValueError is not JSON serializable`

### 9.6 save_file 抛 ValueError
- [ ] 前置: 模拟 `kb_service.save_file()` 抛 `ValueError`
- [ ] 预期状态码: `400`
- [ ] 预期 `code=INVALID_FILE_NAME`

### 9.7 save_file 抛普通异常
- [ ] 前置: 模拟 `kb_service.save_file()` 抛 `RuntimeError`
- [ ] 预期状态码: `500`
- [ ] 预期 `code=UPLOAD_FILE_FAILED`
- [ ] 预期 `detail.error` 含异常信息

### 9.8 上传成功但索引刷新失败
- [ ] 前置: 模拟 `force_refresh_index()` 抛异常
- [ ] 预期状态码: `201`
- [ ] 预期 `message=文件上传成功，但索引刷新失败`
- [ ] 预期 `data.index_refresh.refreshed=false`

## 10. POST /api/kb/{id}/delete_file

请求类型:
- `multipart/form-data`

### 10.1 删除成功
- [ ] 请求: `filename=readme.txt`
- [ ] 预期状态码: `200`
- [ ] 预期 `message=文件删除成功`
- [ ] 预期 `data.filename=readme.txt`

### 10.2 非法 id
- [ ] 请求: `POST /api/kb/bad.id/delete_file`
- [ ] 预期状态码: `400`
- [ ] 预期 `code=INVALID_KB_ID`

### 10.3 KB 不存在
- [ ] 请求: `POST /api/kb/missing001/delete_file`
- [ ] 预期状态码: `404`
- [ ] 预期 `code=KB_NOT_FOUND`

### 10.4 filename 为空白
- [ ] 请求: `filename=   `
- [ ] 预期状态码: `400`
- [ ] 预期 `code=EMPTY_FILE_NAME`
- [ ] 预期 `message=filename不能为空`

### 10.5 文件不存在
- [ ] 请求: `filename=missing.txt`
- [ ] 预期状态码: `404`
- [ ] 预期 `code=FILE_NOT_FOUND`
- [ ] 预期 `message=文件不存在`

### 10.6 delete_file 抛 ValueError
- [ ] 前置: 模拟 `kb_service.delete_file()` 抛 `ValueError`
- [ ] 预期状态码: `400`
- [ ] 预期 `code=INVALID_FILE_NAME`

### 10.7 delete_file 抛普通异常
- [ ] 前置: 模拟 `kb_service.delete_file()` 抛 `RuntimeError`
- [ ] 预期状态码: `500`
- [ ] 预期 `code=DELETE_FILE_FAILED`
- [ ] 预期 `detail.error` 含异常信息

### 10.8 删除成功但索引刷新失败
- [ ] 前置: 模拟 `force_refresh_index()` 抛异常
- [ ] 预期状态码: `200`
- [ ] 预期 `message=文件删除成功，但索引刷新失败`
- [ ] 预期 `data.index_refresh.refreshed=false`

## 11. 全局异常检查

### 11.1 路由未命中
- [ ] 请求不存在路径，例如 `GET /api/not-found`
- [ ] 预期状态码: `404`
- [ ] 预期 `code=HTTP_ERROR`
- [ ] 预期 `message=Not Found`

### 11.2 请求参数校验失败
- [ ] 构造缺失必填参数或参数类型错误请求
- [ ] 预期状态码: `422`
- [ ] 预期 `code=REQUEST_VALIDATION_ERROR`
- [ ] 预期 `detail` 为校验错误数组

### 11.3 未处理异常
- [ ] 前置: 模拟任意未捕获异常
- [ ] 预期状态码: `500`
- [ ] 预期 `code=INTERNAL_SERVER_ERROR`
- [ ] 预期 `message=系统内部错误`

## 12. 当前已知问题

- [ ] `POST /api/kb/{id}/upload` 空文件名上传时，当前不是返回标准 JSON 错误，而是触发 `500`。
- [ ] `bash conda_restart_services.sh` 启动端口与部分探针配置不一致，执行联调前需先确认测试地址。
