# Backend API Test Report

## Startup Check

- Command: `bash conda_restart_services.sh`
- Return code: `0`

### Startup Output

```text
🔄 正在重启业务服务 (Backend + Frontend)...
🛑 (隧道 Tunnel 将保持运行)
   停止旧后端 (PID: 3918896)...
   停止旧前端 (PID: 3919014)...
✅ 已激活 Conda 环境: xtyAgent
🚀 [1/2] 启动后端...
   ⚠️  gunicorn 未安装，回退为 uvicorn (端口: 8069)
✅ 后端 PID: 3920207
🚀 [2/2] 启动前端...
✅ 前端 PID: 3920287
⚠️  警告: 未检测到隧道进程记录。请运行 ./start_tunnel_only.sh 启动穿透。
🎉 服务重启完成！
📊 后端地址: http://127.0.0.1:8069
📊 查看后端日志: tail -f logs/backend.log
```

### Backend Log Tail

```text

```

### Health Probes

- `/api/kb/list`: HTTP 200 | `[{"id":"ca2a9642","name":"测试","model":"openai","category":"企业知识库","owner_info":"图湃（北京）医疗科技/技术部","physical_path":"企业知识库/图湃（北京）医疗科技/测试","remark":"","users":["王颖奇"],"enabled":false,"updatedAt":"2026/03/11 18:08:15","fileCount":0},{"id":"6e73d834","name":"aa","model":"openai","category":"企业知识库","owner_i`
- `/api/test/file_tree`: HTTP 404 | `{"detail":"Not Found"}`

## Unit Test Summary

- Tests run: `39`
- Passed: `38`
- Failed: `0`
- Errors: `1`
- Skipped: `0`
- Duration: `15.761s`

## Unit Test Cases

- `test_api.APITestCase.test_chat_file_parse_error_is_ignored`: passed
- `test_api.APITestCase.test_chat_includes_db_version_and_kb_category`: passed
- `test_api.APITestCase.test_chat_input_blocked`: passed
- `test_api.APITestCase.test_chat_invalid_conversation_id`: passed
- `test_api.APITestCase.test_chat_large_file_keeps_tail_context`: passed
- `test_api.APITestCase.test_chat_requires_non_empty_message`: passed
- `test_api.APITestCase.test_chat_stream_failure_returns_request_id`: passed
- `test_api.APITestCase.test_chat_success_stream`: passed
- `test_api.APITestCase.test_chat_uses_default_optional_values`: passed
- `test_api.APITestCase.test_create_kb_requires_name_and_category`: passed
- `test_api.APITestCase.test_create_kb_success`: passed
- `test_api.APITestCase.test_delete_conversation_invalid_identifier`: passed
- `test_api.APITestCase.test_delete_conversation_not_found`: passed
- `test_api.APITestCase.test_delete_conversation_remove_failure`: passed
- `test_api.APITestCase.test_delete_conversation_success`: passed
- `test_api.APITestCase.test_delete_kb_file_internal_failure`: passed
- `test_api.APITestCase.test_delete_kb_file_not_found`: passed
- `test_api.APITestCase.test_delete_kb_file_refresh_failure_is_reported`: passed
- `test_api.APITestCase.test_delete_kb_file_requires_filename`: passed
- `test_api.APITestCase.test_delete_kb_file_success`: passed
- `test_api.APITestCase.test_delete_kb_not_found`: passed
- `test_api.APITestCase.test_delete_kb_refresh_failure_is_reported`: passed
- `test_api.APITestCase.test_delete_kb_success`: passed
- `test_api.APITestCase.test_file_tree_missing_documents_dir`: passed
- `test_api.APITestCase.test_file_tree_success`: passed
- `test_api.APITestCase.test_get_kb_files_invalid_identifier`: passed
- `test_api.APITestCase.test_get_kb_files_success`: passed
- `test_api.APITestCase.test_kb_list_success`: passed
- `test_api.APITestCase.test_update_kb_invalid_identifier`: passed
- `test_api.APITestCase.test_update_kb_invalid_users`: passed
- `test_api.APITestCase.test_update_kb_not_found`: passed
- `test_api.APITestCase.test_update_kb_rejects_empty_payload`: passed
- `test_api.APITestCase.test_update_kb_success`: passed
- `test_api.APITestCase.test_update_kb_users_must_be_array`: passed
- `test_api.APITestCase.test_upload_kb_file_empty_filename`: error
- `test_api.APITestCase.test_upload_kb_file_internal_failure`: passed
- `test_api.APITestCase.test_upload_kb_file_missing_kb`: passed
- `test_api.APITestCase.test_upload_kb_file_refresh_failure_is_reported`: passed
- `test_api.APITestCase.test_upload_kb_file_success`: passed

## API Samples

### Success Sample

```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "知识库列表获取成功",
  "data": [
    {
      "id": "kb123456",
      "name": "默认知识库"
    }
  ],
  "request_id": "sample-request-id"
}
```

### Error Sample

```json
{
  "success": false,
  "code": "INVALID_KB_ID",
  "message": "id格式非法",
  "data": null,
  "detail": null,
  "request_id": "sample-request-id"
}
```

## Runner Output

```text
test_chat_file_parse_error_is_ignored (test_api.APITestCase) ... ok
test_chat_includes_db_version_and_kb_category (test_api.APITestCase) ... ok
test_chat_input_blocked (test_api.APITestCase) ... ok
test_chat_invalid_conversation_id (test_api.APITestCase) ... ok
test_chat_large_file_keeps_tail_context (test_api.APITestCase) ... ok
test_chat_requires_non_empty_message (test_api.APITestCase) ... ok
test_chat_stream_failure_returns_request_id (test_api.APITestCase) ... ok
test_chat_success_stream (test_api.APITestCase) ... ok
test_chat_uses_default_optional_values (test_api.APITestCase) ... ok
test_create_kb_requires_name_and_category (test_api.APITestCase) ... ok
test_create_kb_success (test_api.APITestCase) ... ok
test_delete_conversation_invalid_identifier (test_api.APITestCase) ... ok
test_delete_conversation_not_found (test_api.APITestCase) ... ok
test_delete_conversation_remove_failure (test_api.APITestCase) ... ok
test_delete_conversation_success (test_api.APITestCase) ... ok
test_delete_kb_file_internal_failure (test_api.APITestCase) ... ok
test_delete_kb_file_not_found (test_api.APITestCase) ... ok
test_delete_kb_file_refresh_failure_is_reported (test_api.APITestCase) ... ok
test_delete_kb_file_requires_filename (test_api.APITestCase) ... ok
test_delete_kb_file_success (test_api.APITestCase) ... ok
test_delete_kb_not_found (test_api.APITestCase) ... ok
test_delete_kb_refresh_failure_is_reported (test_api.APITestCase) ... ok
test_delete_kb_success (test_api.APITestCase) ... ok
test_file_tree_missing_documents_dir (test_api.APITestCase) ... ok
test_file_tree_success (test_api.APITestCase) ... ok
test_get_kb_files_invalid_identifier (test_api.APITestCase) ... ok
test_get_kb_files_success (test_api.APITestCase) ... ok
test_kb_list_success (test_api.APITestCase) ... ok
test_update_kb_invalid_identifier (test_api.APITestCase) ... ok
test_update_kb_invalid_users (test_api.APITestCase) ... ok
test_update_kb_not_found (test_api.APITestCase) ... ok
test_update_kb_rejects_empty_payload (test_api.APITestCase) ... ok
test_update_kb_success (test_api.APITestCase) ... ok
test_update_kb_users_must_be_array (test_api.APITestCase) ... ok
test_upload_kb_file_empty_filename (test_api.APITestCase) ... ERROR
test_upload_kb_file_internal_failure (test_api.APITestCase) ... ok
test_upload_kb_file_missing_kb (test_api.APITestCase) ... ok
test_upload_kb_file_refresh_failure_is_reported (test_api.APITestCase) ... ok
test_upload_kb_file_success (test_api.APITestCase) ... ok

======================================================================
ERROR: test_upload_kb_file_empty_filename (test_api.APITestCase)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/fastapi/routing.py", line 106, in app
    response = await f(request)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/fastapi/routing.py", line 472, in app
    raise validation_error
fastapi.exceptions.RequestValidationError: 1 validation error:
  {'type': 'value_error', 'loc': ('body', 'file'), 'msg': "Value error, Expected UploadFile, received: <class 'str'>", 'input': 'upload-body', 'ctx': {'error': ValueError("Expected UploadFile, received: <class 'str'>")}}

  File "/home/lyq/xintuoyin-KLCLAB/backend/app.py", line 646, in upload_kb_file
    POST /api/kb/{id}/upload

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/lyq/xintuoyin-KLCLAB/backend/tests/test_api.py", line 560, in test_upload_kb_file_empty_filename
    response = self.client.post(
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/testclient.py", line 546, in post
    return super().post(
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/httpx/_client.py", line 1144, in post
    return self.request(
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/testclient.py", line 445, in request
    return super().request(
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/httpx/_client.py", line 825, in request
    return self.send(request, auth=auth, follow_redirects=follow_redirects)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/httpx/_client.py", line 914, in send
    response = self._send_handling_auth(
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/httpx/_client.py", line 942, in _send_handling_auth
    response = self._send_handling_redirects(
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/httpx/_client.py", line 979, in _send_handling_redirects
    response = self._send_single_request(request)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/httpx/_client.py", line 1014, in _send_single_request
    response = transport.handle_request(request)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/testclient.py", line 348, in handle_request
    raise exc
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/testclient.py", line 345, in handle_request
    portal.call(self.app, scope, receive, send)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/anyio/from_thread.py", line 326, in call
    return cast(T_Retval, self.start_task_soon(func, *args).result())
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/concurrent/futures/_base.py", line 458, in result
    return self.__get_result()
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/concurrent/futures/_base.py", line 403, in __get_result
    raise self._exception
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/anyio/from_thread.py", line 257, in _call_func
    retval = await retval_or_awaitable
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/fastapi/applications.py", line 1139, in __call__
    await super().__call__(scope, receive, send)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/applications.py", line 107, in __call__
    await self.middleware_stack(scope, receive, send)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/middleware/errors.py", line 186, in __call__
    raise exc
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/middleware/errors.py", line 164, in __call__
    await self.app(scope, receive, _send)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/middleware/base.py", line 191, in __call__
    with recv_stream, send_stream, collapse_excgroups():
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/contextlib.py", line 153, in __exit__
    self.gen.throw(typ, value, traceback)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/_utils.py", line 85, in collapse_excgroups
    raise exc
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/middleware/base.py", line 193, in __call__
    response = await self.dispatch_func(request, call_next)
  File "/home/lyq/xintuoyin-KLCLAB/backend/app.py", line 203, in inject_request_id
    response = await call_next(request)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/middleware/base.py", line 168, in call_next
    raise app_exc from app_exc.__cause__ or app_exc.__context__
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/middleware/base.py", line 144, in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/middleware/cors.py", line 85, in __call__
    await self.app(scope, receive, send)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/middleware/exceptions.py", line 63, in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/fastapi/middleware/asyncexitstack.py", line 18, in __call__
    await self.app(scope, receive, send)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/routing.py", line 716, in __call__
    await self.middleware_stack(scope, receive, send)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/routing.py", line 736, in app
    await route.handle(scope, receive, send)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/routing.py", line 290, in handle
    await self.app(scope, receive, send)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/fastapi/routing.py", line 120, in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/_exception_handler.py", line 59, in wrapped_app
    response = await handler(conn, exc)
  File "/home/lyq/xintuoyin-KLCLAB/backend/app.py", line 221, in handle_validation_error
    return error_response(
  File "/home/lyq/xintuoyin-KLCLAB/backend/app.py", line 136, in error_response
    return JSONResponse(
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/responses.py", line 189, in __init__
    super().__init__(content, status_code, headers, media_type, background)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/responses.py", line 46, in __init__
    self.body = self.render(content)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/site-packages/starlette/responses.py", line 192, in render
    return json.dumps(
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/json/__init__.py", line 238, in dumps
    **kw).encode(obj)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/json/encoder.py", line 199, in encode
    chunks = self.iterencode(o, _one_shot=True)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/json/encoder.py", line 257, in iterencode
    return _iterencode(o, 0)
  File "/home/lyq/anaconda3/envs/xtyAgent/lib/python3.10/json/encoder.py", line 179, in default
    raise TypeError(f'Object of type {o.__class__.__name__} '
TypeError: Object of type ValueError is not JSON serializable

----------------------------------------------------------------------
Ran 39 tests in 15.761s

FAILED (errors=1)
```
