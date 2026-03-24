import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import app as app_module


class FakeKBService:
    def __init__(self):
        self.items = {}

    def load_all(self):
        return list(self.items.values())

    def create_kb(self, name, model="openai", category="个人知识库"):
        kb_id = f"kb_{len(self.items) + 1}"
        item = {
            "id": kb_id,
            "name": name,
            "category": category,
            "model": model,
            "remark": "",
            "enabled": True,
            "users": [],
            "fileCount": 0,
            "url": f"{category}/{name}",
            "physical_path": f"{category}/{name}",
            "owner_info": "",
            "created_at": "1",
            "updated_at": "1",
            "createdAt": "2026/03/24 00:00:00",
            "updatedAt": "2026/03/24 00:00:00",
            "files": [],
        }
        self.items[kb_id] = item
        return {k: v for k, v in item.items() if k != "files"}

    def get_kb_detail(self, kb_id):
        item = self.items.get(kb_id)
        if not item:
            return None
        result = dict(item)
        result["fileCount"] = len(result.get("files", []))
        return result

    def update_kb(self, kb_id, update_data):
        item = self.items.get(kb_id)
        if not item:
            return None
        item.update(update_data)
        item["updatedAt"] = "2026/03/24 00:00:01"
        item["updated_at"] = "2"
        return {k: v for k, v in item.items() if k != "files"}

    def delete_kb(self, kb_id):
        item = self.items.pop(kb_id, None)
        if not item:
            return None
        return {k: v for k, v in item.items() if k != "files"}

    def save_files(self, kb_id, file_objs):
        item = self.items.get(kb_id)
        if not item:
            return None
        files = item.setdefault("files", [])
        for file_obj in file_objs:
            content = file_obj.file.read()
            files.append({
                "file_id": f"{kb_id}:{file_obj.filename}",
                "name": file_obj.filename,
                "url": f"{item['url']}/{file_obj.filename}",
                "size": len(content),
                "uploaded_at": "3",
                "uploadedAt": "2026/03/24 00:00:02",
            })
            file_obj.file.seek(0)
        item["fileCount"] = len(files)
        return list(files)

    def delete_files(self, kb_id, filenames):
        item = self.items.get(kb_id)
        if not item:
            return None
        before = item.get("files", [])
        remain = [f for f in before if f["name"] not in set(filenames)]
        deleted = [f["name"] for f in before if f["name"] in set(filenames)]
        item["files"] = remain
        item["fileCount"] = len(remain)
        return deleted


class APITestCase(unittest.TestCase):
    report_data = {}
    report_root = Path(__file__).with_name("api_contract_results")

    @classmethod
    def setUpClass(cls):
        if cls.report_root.exists():
            shutil.rmtree(cls.report_root)
        cls.report_root.mkdir(parents=True, exist_ok=True)

        async def fake_run_chat(message, conversation_id, system_prompt, web_search, user_identity):
            answer = f"模拟回答: {message}"
            sources = []
            if web_search:
                sources = [{"link": "https://example.com", "title": "示例来源", "content": "示例摘要"}]
            steps = [{"kind": "call", "node_name": "chatbot_local", "tool_name": "mock_tool", "preview": "{}", "tool_call_id": "tool-1"}]
            return answer, sources, steps

        async def fake_recommendations(user_msg, ai_msg):
            return ["追问1", "追问2", "追问3"]

        cls.original_run_chat = app_module.run_chat
        cls.original_generate_recommendations = app_module.generate_recommendations
        cls.original_check_input_safety = app_module.check_input_safety
        cls.original_check_output_safety = app_module.check_output_safety
        cls.original_kb_service = app_module.kb_service

        app_module.run_chat = fake_run_chat
        app_module.generate_recommendations = fake_recommendations
        app_module.check_input_safety = lambda message: (message, True, "")
        app_module.check_output_safety = lambda prompt, response: (True, "")

    @classmethod
    def tearDownClass(cls):
        app_module.run_chat = cls.original_run_chat
        app_module.generate_recommendations = cls.original_generate_recommendations
        app_module.check_input_safety = cls.original_check_input_safety
        app_module.check_output_safety = cls.original_check_output_safety
        app_module.kb_service = cls.original_kb_service

        summary = []
        total_cases = 0
        passed_cases = 0
        for endpoint, cases in sorted(cls.report_data.items()):
            endpoint_file = cls.report_root / f"{endpoint}.md"
            lines = [f"# {endpoint}", ""]
            for case in cases:
                total_cases += 1
                passed_cases += int(case["passed"])
                lines.extend([
                    f"## {case['case']}",
                    "",
                    f"- status: {'PASS' if case['passed'] else 'FAIL'}",
                    f"- method: {case['method']}",
                    f"- path: {case['path']}",
                ])
                if case.get("notes"):
                    lines.append(f"- notes: {case['notes']}")
                lines.extend([
                    "",
                    "### request",
                    "```json",
                    json.dumps(case.get("request", {}), ensure_ascii=False, indent=2),
                    "```",
                    "",
                    "### response",
                    "```json",
                    json.dumps(case.get("response", {}), ensure_ascii=False, indent=2),
                    "```",
                    "",
                ])
            endpoint_file.write_text("\n".join(lines), encoding="utf-8")
            summary.append({
                "endpoint": endpoint,
                "case_count": len(cases),
                "passed": sum(1 for c in cases if c["passed"]),
                "failed": sum(1 for c in cases if not c["passed"]),
                "file": endpoint_file.name,
            })

        (cls.report_root / "SUMMARY.json").write_text(
            json.dumps({
                "total_endpoints": len(summary),
                "total_cases": total_cases,
                "passed_cases": passed_cases,
                "failed_cases": total_cases - passed_cases,
                "endpoints": summary,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        summary_md = [
            "# API Test Summary",
            "",
            f"- total_endpoints: {len(summary)}",
            f"- total_cases: {total_cases}",
            f"- passed_cases: {passed_cases}",
            f"- failed_cases: {total_cases - passed_cases}",
            "",
        ]
        for item in summary:
            summary_md.append(f"- {item['endpoint']}: {item['passed']}/{item['case_count']} passed ({item['file']})")
        (cls.report_root / "SUMMARY.md").write_text("\n".join(summary_md), encoding="utf-8")

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        app_module.HISTORY_ROOT = base / "history_storage"
        app_module.FEEDBACK_ROOT = base / "feedbacks"
        app_module.CHAT_UPLOAD_ROOT = base / "uploads" / "chat"
        app_module.EXCELLENT_DIR = app_module.FEEDBACK_ROOT / "excellent_answers"
        app_module.NEGATIVE_QA_DIR = app_module.FEEDBACK_ROOT / "negative_answers"
        for path in [app_module.HISTORY_ROOT, app_module.FEEDBACK_ROOT, app_module.CHAT_UPLOAD_ROOT, app_module.EXCELLENT_DIR, app_module.NEGATIVE_QA_DIR]:
            path.mkdir(parents=True, exist_ok=True)
        app_module.kb_service = FakeKBService()
        self.client = TestClient(app_module.app)

    def tearDown(self):
        self.temp_dir.cleanup()

    @classmethod
    def record_case(cls, endpoint, case, method, path, request, response, passed, notes=""):
        cls.report_data.setdefault(endpoint, []).append({
            "case": case,
            "method": method,
            "path": path,
            "request": request,
            "response": response,
            "passed": bool(passed),
            "notes": notes,
        })

    def create_chat_round(self, conversation_id="conv1", message="你好", web_search=False):
        response = self.client.post("/api/chat", data={
            "conversation_id": conversation_id,
            "message": message,
            "web_search": str(web_search).lower(),
            "user_identity": "tester",
            "stream": "false",
        })
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def create_feedback(self, conversation_id="conv1"):
        chat_data = self.create_chat_round(conversation_id=conversation_id, message="反馈测试")
        response = self.client.post("/api/chat/feedback", data={
            "conversation_id": conversation_id,
            "message_index": chat_data["message_index"],
            "type": "like",
        })
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def create_kb(self, name="测试库"):
        response = self.client.post("/api/kb/create", data={"name": name, "category": "企业知识库", "model": "openai"})
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def test_api_chat_new_session(self):
        res = self.client.get("/api/chat/new_session")
        data = res.json()
        passed = res.status_code == 200 and data["code"] == 0 and "conversation_id" in data["data"]
        self.record_case("api_chat_new_session", "success", "GET", "/api/chat/new_session", {}, data, passed)
        self.assertTrue(passed)

    def test_api_chat(self):
        res = self.client.post("/api/chat", data={"conversation_id": "conv1", "message": "你好", "web_search": "true", "user_identity": "tester", "stream": "false"})
        data = res.json()
        passed = res.status_code == 200 and data["data"]["answer"].startswith("模拟回答") and len(data["data"]["resource"]) == 1
        self.record_case("api_chat", "success", "POST", "/api/chat", {"message": "你好", "conversation_id": "conv1", "web_search": True}, data, passed)
        self.assertTrue(passed)

    def test_api_chat_default_stream(self):
        res = self.client.post("/api/chat", data={"conversation_id": "conv-stream", "message": "默认流式", "user_identity": "tester"})
        body = res.text
        passed = res.status_code == 200 and "text/event-stream" in res.headers.get("content-type", "") and "\"type\": \"done\"" in body and "\"type\": \"answer_delta\"" in body
        self.record_case("api_chat", "default_stream_success", "POST", "/api/chat", {"conversation_id": "conv-stream", "message": "默认流式"}, {"content_type": res.headers.get("content-type"), "body": body}, passed, notes="不传 stream 时默认返回 SSE 事件流。")
        self.assertTrue(passed)

    def test_api_chat_title(self):
        self.create_chat_round(conversation_id="conv-title", message="标题测试")
        res = self.client.get("/api/chat/conv-title/title")
        data = res.json()
        passed = res.status_code == 200 and data["data"]["title"] == "标题测试"
        self.record_case("api_chat_title", "success", "GET", "/api/chat/{conversation_id}/title", {"conversation_id": "conv-title"}, data, passed)
        self.assertTrue(passed)

    def test_api_upload(self):
        res = self.client.post("/api/upload", data={"conversation_id": "conv-upload", "message_index": 0}, files={"files": ("note.txt", b"hello", "text/plain")})
        data = res.json()
        passed = res.status_code == 200 and data["data"]["files"][0]["filename"] == "note.txt"
        self.record_case("api_upload", "success", "POST", "/api/upload", {"conversation_id": "conv-upload", "message_index": 0, "files": ["note.txt"]}, data, passed)
        self.assertTrue(passed)

    def test_api_upload_negative_message_index(self):
        res = self.client.post("/api/upload", data={"conversation_id": "conv-upload", "message_index": -1}, files={"files": ("note.txt", b"hello", "text/plain")})
        data = res.json()
        passed = res.status_code == 400 and data["code"] == 1
        self.record_case("api_upload", "negative_message_index", "POST", "/api/upload", {"conversation_id": "conv-upload", "message_index": -1}, data, passed)
        self.assertTrue(passed)

    def test_api_history_list(self):
        self.create_chat_round(conversation_id="conv-history", message="历史测试")
        res = self.client.get("/api/history/list", params={"search": "历史测试"})
        data = res.json()
        passed = res.status_code == 200 and data["data"]["total"] >= 1
        self.record_case("api_history_list", "success", "GET", "/api/history/list", {"search": "历史测试"}, data, passed)
        self.assertTrue(passed)

    def test_api_history_list_invalid_time(self):
        res = self.client.get("/api/history/list", params={"start_time": "bad-ts"})
        data = res.json()
        passed = res.status_code == 400 and data["code"] == 1
        self.record_case("api_history_list", "invalid_time", "GET", "/api/history/list", {"start_time": "bad-ts"}, data, passed)
        self.assertTrue(passed)

    def test_api_history_detail(self):
        self.create_chat_round(conversation_id="conv-detail", message="详情测试")
        res = self.client.get("/api/history/conv-detail")
        data = res.json()
        passed = res.status_code == 200 and data["data"]["messages"][0]["question"] == "详情测试"
        self.record_case("api_history_detail", "success", "GET", "/api/history/{conversation_id}", {"conversation_id": "conv-detail"}, data, passed)
        self.assertTrue(passed)

    def test_api_chat_delete(self):
        self.create_chat_round(conversation_id="conv-delete", message="删除测试")
        res = self.client.delete("/api/chat/conv-delete")
        data = res.json()
        passed = res.status_code == 200 and data["code"] == 0
        self.record_case("api_chat_delete", "success", "DELETE", "/api/chat/{conversation_id}", {"conversation_id": "conv-delete"}, data, passed)
        self.assertTrue(passed)

    def test_api_history_batch_delete(self):
        self.create_chat_round(conversation_id="conv-b1", message="批量1")
        self.create_chat_round(conversation_id="conv-b2", message="批量2")
        res = self.client.post("/api/history/batch_delete", json={"ids": ["conv-b1", "conv-b2"]})
        data = res.json()
        passed = res.status_code == 200 and len(data["data"]["deleted_ids"]) == 2
        self.record_case("api_history_batch_delete", "success", "POST", "/api/history/batch_delete", {"ids": ["conv-b1", "conv-b2"]}, data, passed)
        self.assertTrue(passed)

    def test_api_chat_thinking(self):
        chat_data = self.create_chat_round(conversation_id="conv-think", message="思考测试")
        res = self.client.get("/api/chat/conv-think/thinking", params={"message_index": chat_data["message_index"], "stream": "false"})
        passed = res.status_code == 200 and "正式回答前" in res.text
        self.record_case("api_chat_thinking", "success", "GET", "/api/chat/{conversation_id}/thinking", {"conversation_id": "conv-think", "message_index": chat_data["message_index"]}, {"text": res.text}, passed)
        self.assertTrue(passed)

    def test_api_chat_thinking_default_stream(self):
        chat_data = self.create_chat_round(conversation_id="conv-think-stream", message="思考流式测试")
        res = self.client.get("/api/chat/conv-think-stream/thinking", params={"message_index": chat_data["message_index"]})
        body = res.text
        passed = res.status_code == 200 and res.headers.get("content-type", "").startswith("text/plain") and len(body) > 0
        self.record_case("api_chat_thinking", "default_stream_success", "GET", "/api/chat/{conversation_id}/thinking", {"conversation_id": "conv-think-stream", "message_index": chat_data["message_index"]}, {"content_type": res.headers.get("content-type"), "text": body}, passed, notes="不传 stream 时默认返回思考过程文本流。")
        self.assertTrue(passed)

    def test_api_chat_feedback_like(self):
        chat_data = self.create_chat_round(conversation_id="conv-feedback", message="点赞测试")
        res = self.client.post("/api/chat/feedback", data={"conversation_id": "conv-feedback", "message_index": chat_data["message_index"], "type": "like"})
        data = res.json()
        passed = res.status_code == 200 and data["data"]["state"] == "like"
        self.record_case("api_chat_feedback", "like_success", "POST", "/api/chat/feedback", {"conversation_id": "conv-feedback", "message_index": chat_data["message_index"], "type": "like"}, data, passed)
        self.assertTrue(passed)

    def test_api_chat_feedback_invalid_type(self):
        self.create_chat_round(conversation_id="conv-feedback-invalid", message="错误反馈")
        res = self.client.post("/api/chat/feedback", data={"conversation_id": "conv-feedback-invalid", "message_index": 0, "type": "bad"})
        data = res.json()
        passed = res.status_code == 400 and data["code"] == 1
        self.record_case("api_chat_feedback", "invalid_type", "POST", "/api/chat/feedback", {"conversation_id": "conv-feedback-invalid", "message_index": 0, "type": "bad"}, data, passed)
        self.assertTrue(passed)

    def test_api_chat_feedback_dislike_validation(self):
        self.create_chat_round(conversation_id="conv-feedback-dislike", message="点踩测试")
        res = self.client.post("/api/chat/feedback", data={"conversation_id": "conv-feedback-dislike", "message_index": 0, "type": "dislike"})
        data = res.json()
        passed = res.status_code == 400 and data["code"] == 1
        self.record_case("api_chat_feedback", "dislike_validation", "POST", "/api/chat/feedback", {"conversation_id": "conv-feedback-dislike", "message_index": 0, "type": "dislike"}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_upload_pictures(self):
        res = self.client.post("/api/feedback/upload_pictures", data={"conversation_id": "conv-pic", "message_index": 0}, files={"pictures": ("a.png", b"png", "image/png")})
        data = res.json()
        passed = res.status_code == 200 and data["data"]["pictures"][0]["filename"] == "a.png"
        self.record_case("api_feedback_upload_pictures", "success", "POST", "/api/feedback/upload_pictures", {"conversation_id": "conv-pic", "message_index": 0, "pictures": ["a.png"]}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_list(self):
        self.create_feedback("conv-feedback-list")
        res = self.client.get("/api/feedback/list", params={"type": "like"})
        data = res.json()
        passed = res.status_code == 200 and data["data"]["total"] >= 1
        self.record_case("api_feedback_list", "success", "GET", "/api/feedback/list", {"type": "like"}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_list_invalid_time(self):
        res = self.client.get("/api/feedback/list", params={"start_time": "bad-ts"})
        data = res.json()
        passed = res.status_code == 400 and data["code"] == 1
        self.record_case("api_feedback_list", "invalid_time", "GET", "/api/feedback/list", {"start_time": "bad-ts"}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_detail_by_id(self):
        feedback_data = self.create_feedback("conv-feedback-detail")
        res = self.client.get(f"/api/feedback/{feedback_data['id']}")
        data = res.json()
        passed = res.status_code == 200 and data["data"]["id"] == feedback_data["id"]
        self.record_case("api_feedback_detail_by_id", "success", "GET", "/api/feedback/{feedback_id}", {"feedback_id": feedback_data["id"]}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_detail_by_date(self):
        feedback_data = self.create_feedback("conv-feedback-date")
        date_dir = next(app_module.FEEDBACK_ROOT.glob("*/" + feedback_data["id"])) .parent.name
        res = self.client.get(f"/api/feedback/detail/{date_dir}/{feedback_data['id']}")
        data = res.json()
        passed = res.status_code == 200 and data["data"]["id"] == feedback_data["id"]
        self.record_case("api_feedback_detail_by_date", "success", "GET", "/api/feedback/detail/{date}/{id}", {"date": date_dir, "id": feedback_data["id"]}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_process(self):
        feedback_data = self.create_feedback("conv-feedback-process")
        res = self.client.post("/api/feedback/process", json={"id": feedback_data["id"], "processor": "tester", "is_collect": True})
        data = res.json()
        passed = res.status_code == 200 and data["data"]["process_status"] == "已处理"
        self.record_case("api_feedback_process", "success", "POST", "/api/feedback/process", {"id": feedback_data["id"], "processor": "tester", "is_collect": True}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_process_missing_id(self):
        res = self.client.post("/api/feedback/process", json={"processor": "tester"})
        data = res.json()
        passed = res.status_code == 400 and data["code"] == 1
        self.record_case("api_feedback_process", "missing_id", "POST", "/api/feedback/process", {"processor": "tester"}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_batch_delete(self):
        feedback_data = self.create_feedback("conv-feedback-batch")
        res = self.client.post("/api/feedback/batch_delete", json={"ids": [feedback_data["id"]]})
        data = res.json()
        passed = res.status_code == 200 and feedback_data["id"] in data["data"]["deleted_ids"]
        self.record_case("api_feedback_batch_delete", "success", "POST", "/api/feedback/batch_delete", {"ids": [feedback_data["id"]]}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_delete_by_date(self):
        feedback_data = self.create_feedback("conv-feedback-delete")
        target_dir = next(app_module.FEEDBACK_ROOT.glob("*/" + feedback_data["id"]))
        date_dir = target_dir.parent.name
        res = self.client.delete(f"/api/feedback/{date_dir}/{feedback_data['id']}")
        data = res.json()
        passed = res.status_code == 200 and data["code"] == 0
        self.record_case("api_feedback_delete_by_date", "success", "DELETE", "/api/feedback/{date}/{id}", {"date": date_dir, "id": feedback_data["id"]}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_list(self):
        self.create_kb()
        res = self.client.get("/api/kb/list")
        data = res.json()
        passed = res.status_code == 200 and data["data"]["total"] == 1
        self.record_case("api_kb_list", "success", "GET", "/api/kb/list", {}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_detail(self):
        kb = self.create_kb("详情库")
        res = self.client.get(f"/api/kb/{kb['id']}")
        data = res.json()
        passed = res.status_code == 200 and data["data"]["id"] == kb["id"]
        self.record_case("api_kb_detail", "success", "GET", "/api/kb/{id}", {"id": kb["id"]}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_create(self):
        res = self.client.post("/api/kb/create", data={"name": "新知识库", "category": "企业知识库", "model": "openai"})
        data = res.json()
        passed = res.status_code == 200 and data["data"]["name"] == "新知识库"
        self.record_case("api_kb_create", "success", "POST", "/api/kb/create", {"name": "新知识库", "category": "企业知识库", "model": "openai"}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_update(self):
        kb = self.create_kb("更新库")
        res = self.client.post("/api/kb/update", data={"id": kb["id"], "remark": "新的备注", "enabled": "false", "users": json.dumps([{"name": "张三", "phone": "1", "categoryName": "企业"}])})
        data = res.json()
        passed = res.status_code == 200 and data["data"]["remark"] == "新的备注" and data["data"]["enabled"] is False
        self.record_case("api_kb_update", "success", "POST", "/api/kb/update", {"id": kb["id"], "remark": "新的备注", "enabled": "false"}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_delete(self):
        kb = self.create_kb("删除库")
        res = self.client.delete(f"/api/kb/{kb['id']}")
        data = res.json()
        passed = res.status_code == 200 and data["data"]["id"] == kb["id"]
        self.record_case("api_kb_delete", "success", "DELETE", "/api/kb/{id}", {"id": kb["id"]}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_files(self):
        kb = self.create_kb("文件库")
        self.client.post(f"/api/kb/{kb['id']}/upload", files={"files": ("doc.txt", b"content", "text/plain")})
        res = self.client.get(f"/api/kb/{kb['id']}/files")
        data = res.json()
        passed = res.status_code == 200 and data["data"]["files"][0]["name"] == "doc.txt"
        self.record_case("api_kb_files", "success", "GET", "/api/kb/{id}/files", {"id": kb["id"]}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_upload(self):
        kb = self.create_kb("上传库")
        res = self.client.post(f"/api/kb/{kb['id']}/upload", files={"files": ("doc.txt", b"content", "text/plain")})
        data = res.json()
        passed = res.status_code == 200 and data["data"]["files"][0]["name"] == "doc.txt"
        self.record_case("api_kb_upload", "success", "POST", "/api/kb/{id}/upload", {"id": kb["id"], "files": ["doc.txt"]}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_delete_files(self):
        kb = self.create_kb("批量删文件库")
        self.client.post(f"/api/kb/{kb['id']}/upload", files=[("files", ("a.txt", b"a", "text/plain")), ("files", ("b.txt", b"b", "text/plain"))])
        res = self.client.post(f"/api/kb/{kb['id']}/delete_files", json={"filenames": ["a.txt", "b.txt"]})
        data = res.json()
        passed = res.status_code == 200 and len(data["data"]["deleted_files"]) == 2
        self.record_case("api_kb_delete_files", "success", "POST", "/api/kb/{id}/delete_files", {"id": kb["id"], "filenames": ["a.txt", "b.txt"]}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_delete_file(self):
        kb = self.create_kb("单删文件库")
        self.client.post(f"/api/kb/{kb['id']}/upload", files={"files": ("a.txt", b"a", "text/plain")})
        res = self.client.post(f"/api/kb/{kb['id']}/delete_file", data={"filename": "a.txt"})
        data = res.json()
        passed = res.status_code == 200 and data["data"]["deleted_files"] == ["a.txt"]
        self.record_case("api_kb_delete_file", "success", "POST", "/api/kb/{id}/delete_file", {"id": kb["id"], "filename": "a.txt"}, data, passed)
        self.assertTrue(passed)


    def test_api_chat_with_duplicate_filenames(self):
        res = self.client.post(
            "/api/chat",
            data={"conversation_id": "conv-files", "message": "带附件", "user_identity": "tester", "stream": "false"},
            files=[("files", ("same.txt", b"a", "text/plain")), ("files", ("same.txt", b"b", "text/plain"))],
        )
        data = res.json()
        filenames = [item["filename"] for item in data["data"]["uploaded_files"]]
        passed = res.status_code == 200 and filenames == ["same.txt", "same_1.txt"]
        self.record_case(
            "api_chat",
            "duplicate_upload_names",
            "POST",
            "/api/chat",
            {"conversation_id": "conv-files", "message": "带附件", "files": ["same.txt", "same.txt"]},
            data,
            passed,
            notes="同名上传文件应自动重命名，避免覆盖历史附件。",
        )
        self.assertTrue(passed)


    def test_api_chat_file_content_in_context(self):
        res = self.client.post(
            "/api/chat",
            data={"conversation_id": "conv-file-context", "message": "请根据附件内容回答", "user_identity": "tester", "stream": "false"},
            files={"files": ("context.txt", "附件里写着项目代号是北极星。".encode("utf-8"), "text/plain")},
        )
        data = res.json()
        answer = data["data"]["answer"]
        file_contexts = data["data"].get("file_contexts") or []
        passed = (
            res.status_code == 200
            and "项目代号是北极星" in answer
            and "请根据附件内容回答" in answer
            and file_contexts
            and "项目代号是北极星" in file_contexts[0].get("text", "")
        )
        self.record_case(
            "api_chat",
            "file_content_context",
            "POST",
            "/api/chat",
            {"conversation_id": "conv-file-context", "message": "请根据附件内容回答", "files": ["context.txt"]},
            data,
            passed,
            notes="上传附件后，模型上下文应同时包含附件正文和本轮文字问题。",
        )
        self.assertTrue(passed)

    def test_api_chat_history_context(self):
        self.create_chat_round(conversation_id="conv-history-context", message="第一轮问题")
        res = self.client.post(
            "/api/chat",
            data={"conversation_id": "conv-history-context", "message": "第二轮继续追问", "user_identity": "tester", "stream": "false"},
        )
        data = res.json()
        answer = data["data"]["answer"]
        passed = res.status_code == 200 and "第一轮问题" in answer and "第二轮继续追问" in answer
        self.record_case(
            "api_chat",
            "history_context",
            "POST",
            "/api/chat",
            {"conversation_id": "conv-history-context", "message": "第二轮继续追问"},
            data,
            passed,
            notes="同一会话的后续轮次应带上前序问答上下文。",
        )
        self.assertTrue(passed)

    def test_api_chat_run_chat_failure(self):
        async def boom(*args, **kwargs):
            raise RuntimeError("mock run_chat failed")

        original = app_module.run_chat
        app_module.run_chat = boom
        try:
            res = self.client.post("/api/chat", data={"conversation_id": "conv-error", "message": "失败分支", "user_identity": "tester", "stream": "false"})
            data = res.json()
            passed = res.status_code == 500 and data["code"] == 1 and data["data"]["reason"] == "mock run_chat failed"
            self.record_case(
                "api_chat",
                "run_chat_exception",
                "POST",
                "/api/chat",
                {"conversation_id": "conv-error", "message": "失败分支"},
                data,
                passed,
                notes="模拟模型执行异常，确认接口返回统一 500 错误结构。",
            )
            self.assertTrue(passed)
        finally:
            app_module.run_chat = original

    def test_api_chat_title_not_found(self):
        res = self.client.get("/api/chat/missing-title/title")
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_chat_title", "not_found", "GET", "/api/chat/{conversation_id}/title", {"conversation_id": "missing-title"}, data, passed)
        self.assertTrue(passed)

    def test_api_upload_out_of_range_message_index(self):
        res = self.client.post("/api/upload", data={"conversation_id": "conv-upload-gap", "message_index": 99}, files={"files": ("note.txt", b"hello", "text/plain")})
        data = res.json()
        passed = res.status_code == 200 and data["data"]["message_index"] == 99 and len(data["data"]["files"]) == 1
        self.record_case(
            "api_upload",
            "out_of_range_message_index",
            "POST",
            "/api/upload",
            {"conversation_id": "conv-upload-gap", "message_index": 99, "files": ["note.txt"]},
            data,
            passed,
            notes="当前实现允许上传到尚未存在的消息索引，仅返回文件信息，不回填历史消息。",
        )
        self.assertTrue(passed)

    def test_api_history_list_case_insensitive_search(self):
        self.create_chat_round(conversation_id="conv-case", message="Alpha Beta")
        res = self.client.get("/api/history/list", params={"search": "alpha"})
        data = res.json()
        titles = [item["title"] for item in data["data"]["list"]]
        passed = res.status_code == 200 and "Alpha Beta" in titles
        self.record_case("api_history_list", "case_insensitive_search", "GET", "/api/history/list", {"search": "alpha"}, data, passed)
        self.assertTrue(passed)

    def test_api_history_detail_not_found(self):
        res = self.client.get("/api/history/not-found")
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_history_detail", "not_found", "GET", "/api/history/{conversation_id}", {"conversation_id": "not-found"}, data, passed)
        self.assertTrue(passed)

    def test_api_chat_delete_not_found(self):
        res = self.client.delete("/api/chat/missing-delete")
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_chat_delete", "not_found", "DELETE", "/api/chat/{conversation_id}", {"conversation_id": "missing-delete"}, data, passed)
        self.assertTrue(passed)

    def test_api_history_batch_delete_invalid_ids(self):
        res = self.client.post("/api/history/batch_delete", json={"ids": "conv-bad"})
        data = res.json()
        passed = res.status_code == 400 and data["code"] == 1
        self.record_case("api_history_batch_delete", "invalid_ids_type", "POST", "/api/history/batch_delete", {"ids": "conv-bad"}, data, passed)
        self.assertTrue(passed)

    def test_api_chat_thinking_not_found(self):
        res = self.client.get("/api/chat/missing-thinking/thinking", params={"message_index": 0})
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_chat_thinking", "not_found", "GET", "/api/chat/{conversation_id}/thinking", {"conversation_id": "missing-thinking", "message_index": 0}, data, passed)
        self.assertTrue(passed)

    def test_api_chat_feedback_toggle_like(self):
        chat_data = self.create_chat_round(conversation_id="conv-feedback-toggle", message="重复点赞")
        self.client.post("/api/chat/feedback", data={"conversation_id": "conv-feedback-toggle", "message_index": chat_data["message_index"], "type": "like"})
        res = self.client.post("/api/chat/feedback", data={"conversation_id": "conv-feedback-toggle", "message_index": chat_data["message_index"], "type": "like"})
        data = res.json()
        passed = res.status_code == 200 and data["data"]["state"] is None
        self.record_case(
            "api_chat_feedback",
            "toggle_like_to_none",
            "POST",
            "/api/chat/feedback",
            {"conversation_id": "conv-feedback-toggle", "message_index": chat_data["message_index"], "type": "like"},
            data,
            passed,
            notes="重复提交同一点赞类型时，反馈状态应切换为 None。",
        )
        self.assertTrue(passed)

    def test_api_chat_feedback_dislike_with_reason(self):
        chat_data = self.create_chat_round(conversation_id="conv-feedback-ok", message="有效点踩")
        res = self.client.post(
            "/api/chat/feedback",
            data={
                "conversation_id": "conv-feedback-ok",
                "message_index": chat_data["message_index"],
                "type": "dislike",
                "reasons": json.dumps(["答案不完整"], ensure_ascii=False),
                "comment": "需要更具体",
            },
        )
        data = res.json()
        passed = res.status_code == 200 and data["data"]["state"] == "dislike" and data["data"]["reasons"] == ["答案不完整"]
        self.record_case(
            "api_chat_feedback",
            "dislike_with_reason",
            "POST",
            "/api/chat/feedback",
            {"conversation_id": "conv-feedback-ok", "message_index": chat_data["message_index"], "type": "dislike", "reasons": ["答案不完整"], "comment": "需要更具体"},
            data,
            passed,
        )
        self.assertTrue(passed)

    def test_api_chat_feedback_negative_message_index(self):
        self.create_chat_round(conversation_id="conv-feedback-neg", message="负索引")
        res = self.client.post("/api/chat/feedback", data={"conversation_id": "conv-feedback-neg", "message_index": -1, "type": "like"})
        data = res.json()
        passed = res.status_code == 400 and data["code"] == 1
        self.record_case("api_chat_feedback", "negative_message_index", "POST", "/api/chat/feedback", {"conversation_id": "conv-feedback-neg", "message_index": -1, "type": "like"}, data, passed)
        self.assertTrue(passed)

    def test_api_chat_feedback_not_found(self):
        res = self.client.post("/api/chat/feedback", data={"conversation_id": "missing-feedback", "message_index": 0, "type": "like"})
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_chat_feedback", "conversation_not_found", "POST", "/api/chat/feedback", {"conversation_id": "missing-feedback", "message_index": 0, "type": "like"}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_upload_pictures_duplicate_names(self):
        res = self.client.post(
            "/api/feedback/upload_pictures",
            data={"conversation_id": "conv-pic-dup", "message_index": 0},
            files=[("pictures", ("a.png", b"1", "image/png")), ("pictures", ("a.png", b"2", "image/png"))],
        )
        data = res.json()
        filenames = [item["filename"] for item in data["data"]["pictures"]]
        passed = res.status_code == 200 and filenames == ["a.png", "a_1.png"]
        self.record_case("api_feedback_upload_pictures", "duplicate_picture_names", "POST", "/api/feedback/upload_pictures", {"conversation_id": "conv-pic-dup", "message_index": 0, "pictures": ["a.png", "a.png"]}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_upload_pictures_negative_message_index(self):
        res = self.client.post("/api/feedback/upload_pictures", data={"conversation_id": "conv-pic-neg", "message_index": -1}, files={"pictures": ("a.png", b"png", "image/png")})
        data = res.json()
        passed = res.status_code == 400 and data["code"] == 1
        self.record_case("api_feedback_upload_pictures", "negative_message_index", "POST", "/api/feedback/upload_pictures", {"conversation_id": "conv-pic-neg", "message_index": -1}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_list_filter_no_match(self):
        self.create_feedback("conv-feedback-filter")
        res = self.client.get("/api/feedback/list", params={"enterprise": "不存在企业"})
        data = res.json()
        passed = res.status_code == 200 and data["data"]["total"] == 0
        self.record_case("api_feedback_list", "filter_no_match", "GET", "/api/feedback/list", {"enterprise": "不存在企业"}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_detail_by_id_not_found(self):
        res = self.client.get("/api/feedback/fb_missing_0")
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_feedback_detail_by_id", "not_found", "GET", "/api/feedback/{feedback_id}", {"feedback_id": "fb_missing_0"}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_detail_by_date_not_found(self):
        res = self.client.get("/api/feedback/detail/2099-01-01/fb_missing_0")
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_feedback_detail_by_date", "not_found", "GET", "/api/feedback/detail/{date}/{id}", {"date": "2099-01-01", "id": "fb_missing_0"}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_process_not_found(self):
        res = self.client.post("/api/feedback/process", json={"id": "fb_missing_0", "processor": "tester"})
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_feedback_process", "not_found", "POST", "/api/feedback/process", {"id": "fb_missing_0", "processor": "tester"}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_batch_delete_invalid_ids(self):
        res = self.client.post("/api/feedback/batch_delete", json={"ids": "fb_missing_0"})
        data = res.json()
        passed = res.status_code == 400 and data["code"] == 1
        self.record_case("api_feedback_batch_delete", "invalid_ids_type", "POST", "/api/feedback/batch_delete", {"ids": "fb_missing_0"}, data, passed)
        self.assertTrue(passed)

    def test_api_feedback_delete_by_date_not_found(self):
        res = self.client.delete("/api/feedback/2099-01-01/fb_missing_0")
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_feedback_delete_by_date", "not_found", "DELETE", "/api/feedback/{date}/{id}", {"date": "2099-01-01", "id": "fb_missing_0"}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_detail_not_found(self):
        res = self.client.get("/api/kb/kb_missing")
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_kb_detail", "not_found", "GET", "/api/kb/{id}", {"id": "kb_missing"}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_update_invalid_users(self):
        kb = self.create_kb("坏用户库")
        res = self.client.post("/api/kb/update", data={"id": kb["id"], "users": "{bad json"})
        data = res.json()
        passed = res.status_code == 400 and data["code"] == 1
        self.record_case("api_kb_update", "invalid_users_json", "POST", "/api/kb/update", {"id": kb["id"], "users": "{bad json"}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_update_not_found(self):
        res = self.client.post("/api/kb/update", data={"id": "kb_missing", "remark": "新的备注"})
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_kb_update", "not_found", "POST", "/api/kb/update", {"id": "kb_missing", "remark": "新的备注"}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_delete_not_found(self):
        res = self.client.delete("/api/kb/kb_missing")
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_kb_delete", "not_found", "DELETE", "/api/kb/{id}", {"id": "kb_missing"}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_files_not_found(self):
        res = self.client.get("/api/kb/kb_missing/files")
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_kb_files", "not_found", "GET", "/api/kb/{id}/files", {"id": "kb_missing"}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_upload_not_found(self):
        res = self.client.post("/api/kb/kb_missing/upload", files={"files": ("doc.txt", b"content", "text/plain")})
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_kb_upload", "not_found", "POST", "/api/kb/{id}/upload", {"id": "kb_missing", "files": ["doc.txt"]}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_delete_files_invalid_filenames(self):
        kb = self.create_kb("非法删文件库")
        res = self.client.post(f"/api/kb/{kb['id']}/delete_files", json={"filenames": "a.txt"})
        data = res.json()
        passed = res.status_code == 400 and data["code"] == 1
        self.record_case("api_kb_delete_files", "invalid_filenames_type", "POST", "/api/kb/{id}/delete_files", {"id": kb["id"], "filenames": "a.txt"}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_delete_files_not_found(self):
        res = self.client.post("/api/kb/kb_missing/delete_files", json={"filenames": ["a.txt"]})
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_kb_delete_files", "kb_not_found", "POST", "/api/kb/{id}/delete_files", {"id": "kb_missing", "filenames": ["a.txt"]}, data, passed)
        self.assertTrue(passed)

    def test_api_kb_delete_file_not_found(self):
        res = self.client.post("/api/kb/kb_missing/delete_file", data={"filename": "a.txt"})
        data = res.json()
        passed = res.status_code == 404 and data["code"] == 1
        self.record_case("api_kb_delete_file", "kb_not_found", "POST", "/api/kb/{id}/delete_file", {"id": "kb_missing", "filename": "a.txt"}, data, passed)
        self.assertTrue(passed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
