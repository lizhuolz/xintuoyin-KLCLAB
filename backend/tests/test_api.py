import importlib.util
import json
import shutil
import sys
import tempfile
import types
import unittest
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk, ToolMessage


class DummyCompiledAgent:
    async def astream(self, inputs, stream_mode="messages"):
        if False:
            yield None


class DummyGraphBuilder:
    def compile(self):
        return DummyCompiledAgent()


class FakeStreamingAgent:
    def __init__(self, chunks=None, fail_with=None, chunk_node="chatbot_local", extra_events=None):
        self.chunks = chunks or []
        self.fail_with = fail_with
        self.chunk_node = chunk_node
        self.extra_events = extra_events or []

    async def astream(self, inputs, stream_mode="messages"):
        if self.fail_with is not None:
            raise self.fail_with

        for message, metadata in self.extra_events:
            yield message, metadata

        for chunk in self.chunks:
            yield AIMessageChunk(content=chunk), {"langgraph_node": self.chunk_node}

    async def ainvoke(self, inputs):
        return {"messages": []}


class CapturingStreamingAgent(FakeStreamingAgent):
    def __init__(self, chunks=None, fail_with=None, chunk_node="chatbot_local", extra_events=None):
        super().__init__(chunks=chunks, fail_with=fail_with, chunk_node=chunk_node, extra_events=extra_events)
        self.last_inputs = None

    async def astream(self, inputs, stream_mode="messages"):
        self.last_inputs = inputs
        async for item in super().astream(inputs, stream_mode=stream_mode):
            yield item


class FakeKBService:
    def __init__(self):
        self.kbs = [
            {
                "id": "kb123456",
                "name": "默认知识库",
                "model": "openai",
                "category": "企业知识库",
                "physical_path": "企业知识库/默认知识库",
                "remark": "",
                "users": ["tester"],
                "enabled": True,
                "updatedAt": "2026/03/24 12:00:00",
            }
        ]
        self.files = {"kb123456": {"readme.txt": b"hello"}}

    def _clone_kb(self, kb):
        result = deepcopy(kb)
        result["fileCount"] = len(self.files.get(kb["id"], {}))
        return result

    def load_all(self):
        return [self._clone_kb(kb) for kb in self.kbs]

    def get_kb(self, kb_id):
        for kb in self.kbs:
            if kb["id"] == kb_id:
                return self._clone_kb(kb)
        return None

    def create_kb(self, name, model="openai", category="users/guest"):
        kb = {
            "id": "newkb001",
            "name": name,
            "model": model,
            "category": category,
            "physical_path": f"{category}/{name}",
            "remark": "",
            "users": [],
            "enabled": True,
            "updatedAt": "2026/03/24 12:30:00",
        }
        self.kbs.append(kb)
        self.files[kb["id"]] = {}
        return self._clone_kb(kb)

    def update_kb(self, kb_id, update_data):
        for kb in self.kbs:
            if kb["id"] == kb_id:
                kb.update(update_data)
                kb["updatedAt"] = "2026/03/24 12:45:00"
                return self._clone_kb(kb)
        return None

    def delete_kb(self, kb_id):
        exists = any(kb["id"] == kb_id for kb in self.kbs)
        if not exists:
            return False
        self.kbs = [kb for kb in self.kbs if kb["id"] != kb_id]
        self.files.pop(kb_id, None)
        return True

    def list_files(self, kb_id):
        if not any(kb["id"] == kb_id for kb in self.kbs):
            return []
        return [
            {"name": name, "size": f"{len(content) / 1024:.1f} KB"}
            for name, content in self.files.get(kb_id, {}).items()
        ]

    def save_files(self, kb_id, file_objs):
        if not any(kb["id"] == kb_id for kb in self.kbs):
            return []
        saved = []
        for file_obj in file_objs:
            filename = Path((file_obj.filename or "").strip()).name
            if not filename:
                raise ValueError("文件名不能为空")
            self.files.setdefault(kb_id, {})[filename] = file_obj.file.read()
            saved.append(filename)
        return saved

    def save_file(self, kb_id, file_obj):
        saved = self.save_files(kb_id, [file_obj])
        return saved[0] if saved else False

    def delete_file(self, kb_id, filename):
        if not any(kb["id"] == kb_id for kb in self.kbs):
            return False
        safe_name = Path((filename or "").strip()).name
        if not safe_name:
            raise ValueError("文件名不能为空")
        return self.files.get(kb_id, {}).pop(safe_name, None) is not None


_LOADED_APP = None


def load_app_module():
    global _LOADED_APP
    if _LOADED_APP is not None:
        return _LOADED_APP

    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    agent_pkg = types.ModuleType("agent")
    agent_pkg.__path__ = []
    build_graph_mod = types.ModuleType("agent.build_graph")
    build_graph_mod.graph_builder = DummyGraphBuilder()
    tools_pkg = types.ModuleType("agent.tools")
    tools_pkg.__path__ = []
    rag_tool_mod = types.ModuleType("agent.tools.rag_tool")
    rag_tool_mod.force_refresh_index = lambda: None

    sys.modules["agent"] = agent_pkg
    sys.modules["agent.build_graph"] = build_graph_mod
    sys.modules["agent.tools"] = tools_pkg
    sys.modules["agent.tools.rag_tool"] = rag_tool_mod

    utils_pkg = types.ModuleType("utils")
    utils_pkg.__path__ = []
    security_mod = types.ModuleType("utils.security")
    security_mod.check_input_safety = lambda text: (text, True, "")
    security_mod.check_output_safety = lambda prompt, response: (True, "")
    sys.modules["utils"] = utils_pkg
    sys.modules["utils.security"] = security_mod

    spec = importlib.util.spec_from_file_location("app_under_test", backend_dir / "app.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _LOADED_APP = module
    return module


class APITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_module = load_app_module()

    def setUp(self):
        self.temp_root = Path(tempfile.mkdtemp(prefix="api-tests-"))
        backend_dir = self.temp_root / "backend"
        backend_dir.mkdir(parents=True, exist_ok=True)
        docs_dir = self.temp_root / "documents"
        (docs_dir / "企业知识库" / "默认知识库").mkdir(parents=True, exist_ok=True)
        (docs_dir / "企业知识库" / "默认知识库" / "说明.txt").write_text("demo", encoding="utf-8")

        self.app_module.current_dir = str(backend_dir)
        self.app_module.HISTORY_DIR = self.temp_root / "history_storage"
        self.app_module.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        self.app_module.kb_service = FakeKBService()
        self.app_module.agent_app = FakeStreamingAgent(chunks=["你好", "，世界"])
        self.app_module.force_refresh_index = lambda: None
        self.app_module.check_input_safety = lambda text: (text, True, "")
        self.app_module.check_output_safety = lambda prompt, response: (True, "")
        self.client = TestClient(self.app_module.app)

    def tearDown(self):
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def assert_success_response(self, response, message=None):
        self.assertTrue(response.headers.get("X-Request-ID"))
        self.assertEqual(response.headers.get("content-type"), "application/json")
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["code"], "SUCCESS")
        self.assertIn("request_id", payload)
        if message is not None:
            self.assertEqual(payload["message"], message)
        return payload

    def assert_error_response(self, response, status_code, code):
        self.assertEqual(response.status_code, status_code)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["code"], code)
        self.assertIn("request_id", payload)
        return payload

    def test_delete_conversation_success(self):
        history_file = self.app_module.HISTORY_DIR / "conv001.json"
        history_file.write_text("[]", encoding="utf-8")

        response = self.client.delete("/api/chat/conv001")

        self.assertEqual(response.status_code, 200)
        payload = self.assert_success_response(response, "对话历史删除成功")
        self.assertEqual(payload["data"]["conversation_id"], "conv001")
        self.assertFalse(history_file.exists())

    def test_delete_conversation_not_found(self):
        response = self.client.delete("/api/chat/missing001")
        self.assert_error_response(response, 404, "CONVERSATION_NOT_FOUND")

    def test_delete_conversation_invalid_identifier(self):
        response = self.client.delete("/api/chat/bad.id")
        self.assert_error_response(response, 400, "INVALID_CONVERSATION_ID")

    def test_delete_conversation_remove_failure(self):
        history_file = self.app_module.HISTORY_DIR / "conv_delete_fail.json"
        history_file.write_text("[]", encoding="utf-8")
        original_remove = self.app_module.os.remove

        def fail_remove(path):
            raise OSError("permission denied")

        self.app_module.os.remove = fail_remove
        try:
            response = self.client.delete("/api/chat/conv_delete_fail")
        finally:
            self.app_module.os.remove = original_remove

        payload = self.assert_error_response(response, 500, "DELETE_CONVERSATION_FAILED")
        self.assertEqual(payload["detail"]["error"], "permission denied")

    def test_chat_success_stream(self):
        response = self.client.post(
            "/api/chat",
            data={
                "message": "你好",
                "conversation_id": "conv002",
                "system_prompt": "系统提示",
                "web_search": "false",
                "user_identity": "guest",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers.get("content-type", ""))
        self.assertEqual(response.text, "你好，世界")
        history_file = self.app_module.HISTORY_DIR / "conv002.json"
        self.assertTrue(history_file.exists())
        history = json.loads(history_file.read_text(encoding="utf-8"))
        self.assertEqual(history[-1]["content"], "你好，世界")

    def test_chat_requires_non_empty_message(self):
        response = self.client.post(
            "/api/chat",
            data={"message": "   ", "conversation_id": "conv_empty_message"},
        )
        self.assert_error_response(response, 400, "EMPTY_MESSAGE")

    def test_chat_invalid_conversation_id(self):
        response = self.client.post(
            "/api/chat",
            data={"message": "你好", "conversation_id": "../conv"},
        )
        self.assert_error_response(response, 400, "INVALID_CONVERSATION_ID")

    def test_chat_input_blocked(self):
        self.app_module.check_input_safety = lambda text: (text, False, "输入被拦截")
        response = self.client.post(
            "/api/chat",
            data={"message": "危险内容", "conversation_id": "conv003"},
        )
        self.assert_error_response(response, 400, "INPUT_BLOCKED")

    def test_chat_uses_default_optional_values(self):
        agent = CapturingStreamingAgent(chunks=["ok"])
        self.app_module.agent_app = agent

        response = self.client.post(
            "/api/chat",
            data={
                "message": "你好",
                "conversation_id": "conv_defaults",
                "system_prompt": "   ",
                "user_identity": "   ",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "ok")
        self.assertFalse(agent.last_inputs["enable_web"])
        self.assertEqual(agent.last_inputs["user_identity"], "guest")
        system_message = agent.last_inputs["messages"][0].content
        self.assertIn("You are a helpful assistant", system_message)
        self.assertIn("当前用户身份: guest", system_message)

    def test_chat_includes_db_version_and_kb_category(self):
        agent = CapturingStreamingAgent(chunks=["ok"])
        self.app_module.agent_app = agent

        response = self.client.post(
            "/api/chat",
            data={
                "message": "给我结果",
                "conversation_id": "conv_db",
                "db_version": "v2",
                "kb_category": "企业知识库",
                "web_search": "true",
                "user_identity": "analyst",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "ok")
        self.assertTrue(agent.last_inputs["enable_web"])
        self.assertEqual(agent.last_inputs["user_identity"], "analyst")
        human_message = agent.last_inputs["messages"][1].content
        system_message = agent.last_inputs["messages"][0].content
        self.assertIn("从数据库v2中 给我结果", human_message)
        self.assertIn("已指定分类 '企业知识库'", system_message)

    def test_chat_stream_failure_returns_request_id(self):
        self.app_module.agent_app = FakeStreamingAgent(fail_with=RuntimeError("stream boom"))

        response = self.client.post(
            "/api/chat",
            data={"message": "你好", "conversation_id": "conv_stream_fail"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("[系统错误][request_id=", response.text)
        self.assertIn("stream boom", response.text)
        history_file = self.app_module.HISTORY_DIR / "conv_stream_fail.json"
        self.assertFalse(history_file.exists())

    def test_chat_large_file_keeps_tail_context(self):
        agent = CapturingStreamingAgent(chunks=["done"])
        self.app_module.agent_app = agent
        large_content = (("文件开头-" * 1200) + ("中间内容-" * 3000) + ("文件结尾-" * 1200)).encode("utf-8")

        response = self.client.post(
            "/api/chat",
            data={
                "message": "帮我解读这个文件",
                "conversation_id": "conv_large_file",
            },
            files={"files": ("large.txt", large_content, "text/plain")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "done")
        human_message = agent.last_inputs["messages"][1].content
        self.assertIn("帮我解读这个文件", human_message)
        self.assertIn("文件 large.txt 内容:", human_message)
        self.assertIn("文件内容过长，已截取前", human_message)
        self.assertIn("文件开头-", human_message)
        self.assertIn("文件结尾-", human_message)

    def test_chat_file_parse_error_is_ignored(self):
        agent = CapturingStreamingAgent(chunks=["done"])
        self.app_module.agent_app = agent
        broken_pdf = b"%PDF-1.4\nthis-is-not-a-real-pdf"

        response = self.client.post(
            "/api/chat",
            data={
                "message": "只看文本",
                "conversation_id": "conv_bad_pdf",
            },
            files={"files": ("broken.pdf", broken_pdf, "application/pdf")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "done")
        human_message = agent.last_inputs["messages"][1].content
        self.assertEqual(human_message, "只看文本")

    def test_chat_events_returns_structured_trace(self):
        search_payload = json.dumps(
            {
                "results": [
                    {
                        "url": "https://example.com/a",
                        "main_title": "主标题",
                        "sub_title": "副标题",
                        "summary": "摘要",
                        "raw_content": "原文",
                    }
                ]
            },
            ensure_ascii=False,
        )
        tool_message = ToolMessage(content=search_payload, name="tavily_search_with_summary", tool_call_id="call-1")
        agent = CapturingStreamingAgent(
            chunks=["final"],
            chunk_node="chatbot_web",
            extra_events=[
                (tool_message, {"langgraph_node": "tools_web"}),
            ],
        )
        self.app_module.agent_app = agent

        response = self.client.post(
            "/api/chat/events",
            data={"message": "联网搜一下", "conversation_id": "conv_events", "web_search": "true"},
        )

        self.assertEqual(response.status_code, 200)
        payload = self.assert_success_response(response, "会话事件获取成功")
        events = payload["data"]["events"]
        event_types = [item["type"] for item in events]
        self.assertIn("node.enter", event_types)
        self.assertIn("tool.result", event_types)
        self.assertIn("search.results", event_types)
        self.assertIn("answer.delta", event_types)
        self.assertEqual(payload["data"]["final_answer"], "final")
        self.assertEqual(payload["data"]["search_results"][0]["url"], "https://example.com/a")

    def test_chat_search_artifacts_returns_search_payload(self):
        search_payload = json.dumps(
            {
                "results": [
                    {
                        "url": "https://example.com/b",
                        "main_title": "标题B",
                        "sub_title": "副标题B",
                        "summary": "摘要B",
                        "raw_content": "原文B",
                    }
                ]
            },
            ensure_ascii=False,
        )
        tool_message = ToolMessage(content=search_payload, name="tavily_search_with_summary", tool_call_id="call-2")
        self.app_module.agent_app = FakeStreamingAgent(
            chunks=["answer"],
            chunk_node="chatbot_web",
            extra_events=[(tool_message, {"langgraph_node": "tools_web"})],
        )

        response = self.client.post(
            "/api/chat/search-artifacts",
            data={"message": "搜索结果", "conversation_id": "conv_search_artifacts", "web_search": "true"},
        )

        self.assertEqual(response.status_code, 200)
        payload = self.assert_success_response(response, "搜索抓取结果获取成功")
        self.assertEqual(payload["data"]["result_count"], 1)
        self.assertEqual(payload["data"]["search_results"][0]["main_title"], "标题B")
        self.assertEqual(payload["data"]["final_answer"], "answer")

    def test_kb_list_success(self):
        response = self.client.get("/api/kb/list")
        self.assertEqual(response.status_code, 200)
        payload = self.assert_success_response(response, "知识库列表获取成功")
        self.assertEqual(payload["data"][0]["id"], "kb123456")

    def test_file_tree_success(self):
        response = self.client.get("/api/test/file_tree")
        self.assertEqual(response.status_code, 200)
        payload = self.assert_success_response(response, "文件树获取成功")
        labels = [item["label"] for item in payload["data"]]
        self.assertIn("企业知识库", labels)

    def test_file_tree_missing_documents_dir(self):
        docs_dir = self.temp_root / "documents"
        shutil.rmtree(docs_dir, ignore_errors=True)

        response = self.client.get("/api/test/file_tree")
        self.assertEqual(response.status_code, 200)
        payload = self.assert_success_response(response, "documents 目录不存在，返回空树")
        self.assertEqual(payload["data"], [])

    def test_create_kb_success(self):
        response = self.client.post(
            "/api/kb/create",
            data={"name": "新增知识库", "model": "openai", "category": "部门知识库/技术部"},
        )
        self.assertEqual(response.status_code, 201)
        payload = self.assert_success_response(response, "知识库创建成功")
        self.assertEqual(payload["data"]["name"], "新增知识库")

    def test_create_kb_requires_name_and_category(self):
        response = self.client.post(
            "/api/kb/create",
            data={"name": "   ", "category": "   "},
        )
        self.assert_error_response(response, 400, "EMPTY_KB_NAME")

    def test_update_kb_success(self):
        response = self.client.post(
            "/api/kb/update",
            data={
                "id": "kb123456",
                "name": "更新后知识库",
                "remark": "备注",
                "enabled": "false",
                "users": json.dumps(["alice", "bob"]),
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = self.assert_success_response(response, "知识库更新成功")
        self.assertEqual(payload["data"]["name"], "更新后知识库")
        self.assertEqual(payload["data"]["users"], ["alice", "bob"])
        self.assertFalse(payload["data"]["enabled"])

    def test_update_kb_invalid_users(self):
        response = self.client.post(
            "/api/kb/update",
            data={"id": "kb123456", "users": "not-json"},
        )
        self.assert_error_response(response, 400, "INVALID_USERS_FIELD")

    def test_update_kb_users_must_be_array(self):
        response = self.client.post(
            "/api/kb/update",
            data={"id": "kb123456", "users": json.dumps({"name": "alice"})},
        )
        self.assert_error_response(response, 400, "INVALID_USERS_FIELD")

    def test_update_kb_rejects_empty_payload(self):
        response = self.client.post(
            "/api/kb/update",
            data={"id": "kb123456"},
        )
        self.assert_error_response(response, 400, "EMPTY_UPDATE_PAYLOAD")

    def test_update_kb_not_found(self):
        response = self.client.post(
            "/api/kb/update",
            data={"id": "missing001", "remark": "x"},
        )
        self.assert_error_response(response, 404, "KB_NOT_FOUND")

    def test_update_kb_invalid_identifier(self):
        response = self.client.post(
            "/api/kb/update",
            data={"id": "../bad", "remark": "x"},
        )
        self.assert_error_response(response, 400, "INVALID_KB_ID")

    def test_delete_kb_success(self):
        response = self.client.delete("/api/kb/kb123456")
        self.assertEqual(response.status_code, 200)
        payload = self.assert_success_response(response, "知识库删除成功")
        self.assertEqual(payload["data"]["id"], "kb123456")

    def test_delete_kb_refresh_failure_is_reported(self):
        self.app_module.force_refresh_index = lambda: (_ for _ in ()).throw(RuntimeError("refresh failed"))
        response = self.client.delete("/api/kb/kb123456")
        self.assertEqual(response.status_code, 200)
        payload = self.assert_success_response(response, "知识库删除成功，但索引刷新失败")
        self.assertFalse(payload["data"]["index_refresh"]["refreshed"])
        self.assertEqual(payload["data"]["index_refresh"]["error"], "refresh failed")

    def test_delete_kb_not_found(self):
        response = self.client.delete("/api/kb/missing001")
        self.assert_error_response(response, 404, "KB_NOT_FOUND")

    def test_get_kb_files_success(self):
        response = self.client.get("/api/kb/kb123456/files")
        self.assertEqual(response.status_code, 200)
        payload = self.assert_success_response(response, "知识库文件列表获取成功")
        self.assertEqual(payload["data"][0]["name"], "readme.txt")

    def test_get_kb_files_invalid_identifier(self):
        response = self.client.get("/api/kb/bad.id/files")
        self.assert_error_response(response, 400, "INVALID_KB_ID")

    def test_upload_kb_file_success(self):
        response = self.client.post(
            "/api/kb/kb123456/upload",
            files=[("files", ("manual.txt", b"upload-body", "text/plain"))],
        )
        self.assertEqual(response.status_code, 201)
        payload = self.assert_success_response(response, "文件上传成功")
        self.assertEqual(payload["data"]["filename"], "manual.txt")
        self.assertEqual(payload["data"]["uploaded_count"], 1)
        self.assertIn("manual.txt", self.app_module.kb_service.files["kb123456"])

    def test_upload_kb_multiple_files_success(self):
        response = self.client.post(
            "/api/kb/kb123456/upload",
            files=[
                ("files", ("manual.txt", b"upload-body", "text/plain")),
                ("files", ("report.csv", b"a,b\n1,2", "text/csv")),
            ],
        )
        self.assertEqual(response.status_code, 201)
        payload = self.assert_success_response(response, "文件上传成功")
        self.assertEqual(payload["data"]["uploaded_count"], 2)
        self.assertEqual(payload["data"]["filenames"], ["manual.txt", "report.csv"])

    def test_upload_kb_file_missing_kb(self):
        response = self.client.post(
            "/api/kb/missing001/upload",
            files=[("files", ("manual.txt", b"upload-body", "text/plain"))],
        )
        self.assert_error_response(response, 404, "KB_NOT_FOUND")

    def test_upload_kb_file_empty_filename(self):
        response = self.client.post(
            "/api/kb/kb123456/upload",
            files=[("files", ("", b"upload-body", "text/plain"))],
        )
        payload = self.assert_error_response(response, 400, "EMPTY_FILE_NAME")
        self.assertEqual(payload["message"], "上传文件名不能为空")

    def test_upload_kb_file_unsupported_type(self):
        response = self.client.post(
            "/api/kb/kb123456/upload",
            files=[("files", ("malware.exe", b"noop", "application/octet-stream"))],
        )
        payload = self.assert_error_response(response, 400, "UNSUPPORTED_FILE_TYPE")
        self.assertIn("malware.exe", payload["detail"]["invalid_filenames"])

    def test_upload_kb_file_internal_failure(self):
        self.app_module.kb_service.save_files = lambda kb_id, file_objs: (_ for _ in ()).throw(RuntimeError("disk full"))
        response = self.client.post(
            "/api/kb/kb123456/upload",
            files=[("files", ("manual.txt", b"upload-body", "text/plain"))],
        )
        payload = self.assert_error_response(response, 500, "UPLOAD_FILE_FAILED")
        self.assertEqual(payload["detail"]["error"], "disk full")

    def test_upload_kb_file_refresh_failure_is_reported(self):
        self.app_module.force_refresh_index = lambda: (_ for _ in ()).throw(RuntimeError("refresh failed"))
        response = self.client.post(
            "/api/kb/kb123456/upload",
            files=[("files", ("manual.txt", b"upload-body", "text/plain"))],
        )
        self.assertEqual(response.status_code, 201)
        payload = self.assert_success_response(response, "文件上传成功，但索引刷新失败")
        self.assertFalse(payload["data"]["index_refresh"]["refreshed"])
        self.assertEqual(payload["data"]["index_refresh"]["error"], "refresh failed")

    def test_delete_kb_file_success(self):
        response = self.client.post(
            "/api/kb/kb123456/delete_file",
            data={"filename": "readme.txt"},
        )
        self.assertEqual(response.status_code, 200)
        payload = self.assert_success_response(response, "文件删除成功")
        self.assertEqual(payload["data"]["filename"], "readme.txt")
        self.assertNotIn("readme.txt", self.app_module.kb_service.files["kb123456"])

    def test_delete_kb_file_requires_filename(self):
        response = self.client.post(
            "/api/kb/kb123456/delete_file",
            data={"filename": "   "},
        )
        self.assert_error_response(response, 400, "EMPTY_FILE_NAME")

    def test_delete_kb_file_not_found(self):
        response = self.client.post(
            "/api/kb/kb123456/delete_file",
            data={"filename": "missing.txt"},
        )
        self.assert_error_response(response, 404, "FILE_NOT_FOUND")

    def test_delete_kb_file_internal_failure(self):
        self.app_module.kb_service.delete_file = lambda kb_id, filename: (_ for _ in ()).throw(RuntimeError("unlink failed"))
        response = self.client.post(
            "/api/kb/kb123456/delete_file",
            data={"filename": "readme.txt"},
        )
        payload = self.assert_error_response(response, 500, "DELETE_FILE_FAILED")
        self.assertEqual(payload["detail"]["error"], "unlink failed")

    def test_delete_kb_file_refresh_failure_is_reported(self):
        self.app_module.kb_service.files["kb123456"]["manual.txt"] = b"demo"
        self.app_module.force_refresh_index = lambda: (_ for _ in ()).throw(RuntimeError("refresh failed"))
        response = self.client.post(
            "/api/kb/kb123456/delete_file",
            data={"filename": "manual.txt"},
        )
        self.assertEqual(response.status_code, 200)
        payload = self.assert_success_response(response, "文件删除成功，但索引刷新失败")
        self.assertFalse(payload["data"]["index_refresh"]["refreshed"])
        self.assertEqual(payload["data"]["index_refresh"]["error"], "refresh failed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
