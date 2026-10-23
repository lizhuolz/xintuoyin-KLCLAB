"""Offline characterization of real KB routes/services; never import app.py.

All metadata and downloaded fixture files live in TemporaryDirectory; storage,
identity and vectors are fixtures. No server, production data, token or Redis is
used. XTY_SOURCE_ROOT may point to a staged tree; unmodified files fall back to
XTY_ORIGINAL_ROOT. Parse failure and rollback contracts run by default.
"""
import ast
import asyncio
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
import types
import unittest
from datetime import datetime
from unittest.mock import patch

from starlette.responses import JSONResponse

sys.dont_write_bytecode = True
ORIGINAL = Path(os.environ.get("XTY_ORIGINAL_ROOT", "/data2/dlx/projects/xty"))
ROOT = Path(os.environ.get("XTY_SOURCE_ROOT", str(ORIGINAL)))


def source(relative):
    candidate = ROOT / relative
    return candidate if candidate.is_file() else ORIGINAL / relative


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, source(relative))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def extract_nodes(relative, names, namespace):
    tree = ast.parse(source(relative).read_text())
    selected = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in names:
            node.decorator_list = []
            selected.append(node)
    assert {n.name for n in selected} == set(names)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source(relative)), "exec"), namespace)


class MemoryStorage:
    def __init__(self):
        self.objects = {"kb/fixture/original.txt": b"original fixture text"}
        self.unavailable = False
        self.move_failure = False
        self.mutations = []

    def ensure_ready(self):
        if self.unavailable:
            raise RuntimeError("isolated storage unavailable")

    def list_files(self, prefix):
        return [{"object_name": k, "size": len(v), "last_modified": datetime(2026, 1, 1)}
                for k, v in self.objects.items() if k.startswith(prefix)]

    def get_presigned_url(self, name):
        return "memory://fixture/" + name

    def download_file(self, name, target):
        if name not in self.objects:
            return False
        Path(target).write_bytes(self.objects[name])
        return True

    def read_file_bytes(self, name):
        return self.objects[name]

    def move_object(self, old, new):
        if self.move_failure:
            return False
        self.objects[new] = self.objects.pop(old)
        self.mutations.append(("move", old, new))
        return True

    def delete_file(self, name):
        self.objects.pop(name, None)
        self.mutations.append(("delete", name))
        return True

    def upload_file_obj(self, file_obj, name, content_type):
        self.objects[name] = file_obj.read()
        self.mutations.append(("upload", name))
        return True


class FixtureVectors:
    def __init__(self, milvus):
        self.records = []
        self.build_calls = []
        self.deleted = []
        settings = types.SimpleNamespace(chunk_size=800, chunk_overlap=120)
        self.real = milvus.MilvusService(settings)
        self.real.embed_texts = lambda texts: [[0.0, 1.0] for _ in texts]

    def delete_by_kb(self, kb_id):
        self.deleted.append(kb_id)
        self.records = []

    def build_chunk_records(self, **kwargs):
        self.build_calls.append(kwargs)
        return self.real.build_chunk_records(**kwargs)

    def upsert_records(self, records):
        self.records = records


class KBUpdateIsolated(unittest.TestCase):
    route_names = ("update_kb", "admin_update_kb")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xty_kb_offline_")
        self.addCleanup(self.temp.cleanup)
        self.net_guard = patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden"))
        self.net_guard.start()
        self.addCleanup(self.net_guard.stop)
        self.parser = load_module("offline_kb_parser", "backend/services/kb_file_parser.py")
        self.milvus = load_module("offline_kb_vectors", "backend/services/milvus_service.py")
        self.storage = MemoryStorage()
        self.vector = FixtureVectors(self.milvus)
        self.metadata = Path(self.temp.name) / "kb_metadata.json"
        self.initial = [{"id": "fixture-kb", "name": "original", "physical_path": "fixture",
                         "category": "知识库", "users": [], "enabled": True}]
        self.metadata.write_text(json.dumps(self.initial))
        self.ns = {"io": io, "json": json, "logging": logging, "tempfile": tempfile,
                   "datetime": datetime, "Path": Path, "DEFAULT_KB_CATEGORY": "知识库",
                   "METADATA_FILE": self.metadata, "storage_service": self.storage,
                   "build_milvus_service_from_env": lambda: self.vector,
                   "extract_kb_file_text": self.parser.extract_kb_file_text,
                   "now_ms": lambda: "1000", "now_display": lambda: "fixture time",
                   "get_user_profile": lambda: {"staff_id": "fixture-user"}}
        extract_nodes("backend/services/kb_service.py", ["KBService"], self.ns)
        self.service = self.ns["KBService"]()
        self.identity = {"role": "user", "staff_id": "fixture-user"}
        self.staged = {}

        async def payload(request):
            return request

        self.routes = {"Request": dict, "JSONResponse": JSONResponse, "json": json,
                       "kb_service": self.service, "_get_request_payload": payload,
                       "get_logged_in_user": lambda: self.identity,
                       "require_role": lambda role: None if self.identity["role"] == "user" else JSONResponse({}, status_code=401),
                       "_require_kb_access": lambda kb_id: None if kb_id == "fixture-kb" else JSONResponse({}, status_code=403),
                       "resolve_staging_files": lambda ids: [self.staged[x] for x in ids]}
        extract_nodes("backend/app.py", ["success_response", "error_response", *self.route_names], self.routes)

    def invoke(self, route, **payload):
        response = asyncio.run(self.routes[route]({"id": "fixture-kb", "confirm": True, **payload}))
        if isinstance(response, JSONResponse):
            return response.status_code, json.loads(response.body)
        return 200, response

    def add_staged(self, filename, content=b"new fixture text"):
        self.storage.objects["staging/fixture"] = content
        self.staged["fixture-upload"] = {"filename": filename, "staging_object": "staging/fixture"}

    def test_normal_text_update_and_preview_use_actual_parser(self):
        for route in self.route_names:
            with self.subTest(route=route):
                self.add_staged("new.txt")
                before = self.metadata.read_bytes()
                code, body = self.invoke(route, name="changed", add_file_ids=["fixture-upload"], confirm=False)
                self.assertEqual(code, 200)
                self.assertTrue(body["data"]["preview"])
                self.assertEqual(self.metadata.read_bytes(), before)
                self.assertFalse(self.storage.mutations)
                code, body = self.invoke(route, name="changed", add_file_ids=["fixture-upload"])
                self.assertEqual(code, 200)
                self.assertEqual(body["code"], 0)
                self.assertFalse(body["data"]["preview"])
                self.assertTrue(any(r["content"] == "new fixture text" for r in self.vector.records))
                # Reset fixture after each independently exercised route.
                self.storage = MemoryStorage()
                self.ns["storage_service"] = self.storage
                self.metadata.write_text(json.dumps(self.initial))

    def test_minio_unavailable_returns_500_without_metadata_or_object_writes(self):
        before = self.metadata.read_bytes()
        self.storage.unavailable = True
        for route in self.route_names:
            with self.subTest(route=route):
                status, body = self.invoke(route, name="changed")
                self.assertEqual(status, 500)
                self.assertEqual(body["code"], 1)
                self.assertEqual(self.metadata.read_bytes(), before)
                self.assertEqual(self.storage.mutations, [])
                self.assertEqual(self.vector.deleted, [])

    def test_storage_move_failure_rolls_metadata_back(self):
        self.add_staged("new.txt")
        self.storage.move_failure = True
        for route in self.route_names:
            with self.subTest(route=route):
                status, _ = self.invoke(route, name="changed", add_file_ids=["fixture-upload"])
                self.assertEqual(status, 500)
                self.assertEqual(json.loads(self.metadata.read_text()), self.initial)
                self.assertNotIn("kb/fixture/new.txt", self.storage.objects)

    def test_escaping_parser_exception_returns_500_and_restores_deleted_object(self):
        def fail_parser(path):
            raise RuntimeError("isolated parser failure")
        self.ns["extract_kb_file_text"] = fail_parser
        for route in self.route_names:
            with self.subTest(route=route):
                self.add_staged("new.txt")
                status, _ = self.invoke(route, name="changed", add_file_ids=["fixture-upload"], delete_files=["original.txt"])
                self.assertEqual(status, 500)
                self.assertEqual(json.loads(self.metadata.read_text()), self.initial)
                self.assertIn("kb/fixture/original.txt", self.storage.objects)
                self.assertNotIn("kb/fixture/new.txt", self.storage.objects)

    def test_guest_is_rejected_before_storage(self):
        self.identity["role"] = "guest"
        self.storage.unavailable = True
        status, _ = self.invoke("update_kb", name="changed")
        self.assertEqual(status, 401)
        self.assertEqual(self.storage.mutations, [])

    def test_sync_parse_blocks_another_task_on_the_event_loop(self):
        def slow_parser(path):
            time.sleep(0.15)
            return "fixture"
        self.ns["extract_kb_file_text"] = slow_parser

        async def measure(route):
            start = time.monotonic()
            async def ticker():
                await asyncio.sleep(0.01)
                return time.monotonic() - start
            _, first_tick = await asyncio.gather(
                self.routes[route]({"id": "fixture-kb", "confirm": True}), ticker())
            return first_tick

        for route in self.route_names:
            with self.subTest(route=route):
                self.assertGreater(asyncio.run(measure(route)), 0.14)


class KBParseFailureRegression(KBUpdateIsolated):
    # Do not re-run inherited characterization cases in this regression class.
    test_normal_text_update_and_preview_use_actual_parser = None
    test_minio_unavailable_returns_500_without_metadata_or_object_writes = None
    test_storage_move_failure_rolls_metadata_back = None
    test_escaping_parser_exception_returns_500_and_restores_deleted_object = None
    test_guest_is_rejected_before_storage = None
    test_sync_parse_blocks_another_task_on_the_event_loop = None

    def assert_rollback(self, status, body):
        self.assertEqual(status, 500, f"actual HTTP {status}, code={body['code']}")
        self.assertEqual(body["code"], 1)
        self.assertEqual(json.loads(self.metadata.read_text()), self.initial)
        kb_objects = {key: value for key, value in self.storage.objects.items() if key.startswith("kb/")}
        self.assertEqual(kb_objects, {"kb/fixture/original.txt": b"original fixture text"})
        self.assertEqual([r["content"] for r in self.vector.records], ["original fixture text"])
        self.assertEqual([r["file_name"] for r in self.vector.records], ["original.txt"])

    def test_malformed_docx_reports_failure_and_restores_original_index(self):
        for route in self.route_names:
            with self.subTest(route=route):
                self.add_staged("broken.docx", b"not an OOXML zip")
                status, body = self.invoke(route, name="changed", add_file_ids=["fixture-upload"])
                self.assert_rollback(status, body)

    def test_parser_exception_reports_failure_and_restores_original_index(self):
        def fail_pdf(path):
            raise RuntimeError("isolated PDF parse failure")
        self.parser.extract_pdf_text = fail_pdf
        for route in self.route_names:
            with self.subTest(route=route):
                self.add_staged("broken.pdf", b"fixture")
                status, body = self.invoke(route, name="changed", add_file_ids=["fixture-upload"])
                self.assert_rollback(status, body)


if __name__ == "__main__":
    unittest.main()
