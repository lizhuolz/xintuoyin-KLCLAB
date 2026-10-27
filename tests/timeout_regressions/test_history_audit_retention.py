"""Offline HTTP regressions for personal history hiding and platform retention.

Run with the project Python, without importing the application or its services:
    XTY_SOURCE_ROOT=. python -B tests/timeout_regressions/test_history_audit_retention.py

The harness recursively extracts actual route/helper AST nodes, keeps the actual
FastAPI decorators, and uses httpx.ASGITransport. Only synthetic in-memory
storage, request identity, and the clock replace service boundaries. All socket
connections and subprocess launches are forbidden. Authentication middleware,
real MinIO, and deployment configuration are intentionally outside this test.
"""

import ast
import asyncio
import contextlib
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import types
from typing import Any, Dict, List, Optional
import unittest
from unittest.mock import patch
import warnings

from fastapi import APIRouter, Body, FastAPI, Query
from fastapi.exceptions import FastAPIDeprecationWarning
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font


ROOT = Path(os.environ.get("XTY_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
SOURCE = ROOT / "backend/app.py"
ROUTES = {
    "list_histories": ("GET", "/api/history/list"),
    "get_history_detail": ("GET", "/api/history/{conversation_id}"),
    "delete_history": ("DELETE", "/api/chat/{conversation_id}"),
    "batch_delete_history": ("POST", "/api/history/batch_delete"),
    "export_history_detail": ("POST", "/api/history/export"),
    "admin_list_histories": ("GET", "/api/admin/history/list"),
    "admin_get_history_detail": ("GET", "/api/admin/history/{conversation_id}"),
    "admin_delete_history": ("DELETE", "/api/admin/history/{conversation_id}"),
    "admin_batch_delete_history": ("POST", "/api/admin/history/batch_delete"),
    "admin_export_history": ("POST", "/api/admin/history/export"),
    "download_history_uploaded_file": (
        "GET", "/api/history/{conversation_id}/messages/{message_index}/files/{file_id}/download",
    ),
    "admin_download_history_file": (
        "GET", "/api/admin/history/{conversation_id}/messages/{message_index}/files/{file_id}/download",
    ),
}
LIST_SIGNATURE = [
    ("search", "str", "Query", ""),
    ("start_time", "Optional[str]", "Query", None),
    ("end_time", "Optional[str]", "Query", None),
    ("page", "int", "Query", 1),
    ("size", "int", "Query", 10),
]
USER = {
    "name": "Synthetic Same Name", "user_id": "fixture-user-a",
    "staff_id": "fixture-user-a", "tenant_id": "fixture-tenant-a",
    "phone": "fixture-phone", "company": "Fixture Company",
    "ip_address": "192.0.2.10", "access_token": "fixture-token-a",
}


class MemoryStorage:
    """StorageService-compatible memory boundary, including its swallowed list error."""

    def __init__(self):
        self.objects = {}
        self.uploads = []
        self.deletes = []
        self.fail_upload_numbers = set()
        self.fail_all_uploads = False
        self.fail_marker_listing = False
        self.bucket_name = "offline-fixture"
        self.client = types.SimpleNamespace(list_objects=self.list_objects)

    def ensure_ready(self):
        return None

    def list_objects(self, bucket_name, prefix="", recursive=True):
        assert bucket_name == self.bucket_name
        if self.fail_marker_listing and not prefix.startswith("history/"):
            raise RuntimeError("synthetic marker listing outage")
        for name, payload in sorted(self.objects.items()):
            if name.startswith(prefix):
                yield types.SimpleNamespace(
                    object_name=name, size=len(payload),
                    last_modified=datetime(2026, 10, 27, tzinfo=timezone.utc),
                )

    def list_files(self, prefix):
        try:
            return [vars(obj) for obj in self.list_objects(self.bucket_name, prefix, True)]
        except Exception:
            # The real service swallows list exceptions. Marker reads must use
            # its client directly so an outage cannot silently reveal history.
            return []

    def read_file_bytes(self, object_name):
        return self.objects.get(object_name, b"")

    def upload_file_obj(self, file_obj, object_name, content_type=None):
        self.uploads.append(object_name)
        if self.fail_all_uploads or len(self.uploads) in self.fail_upload_numbers:
            return False
        file_obj.seek(0)
        self.objects[object_name] = file_obj.read()
        return True

    def delete_file(self, object_name):
        self.deletes.append(object_name)
        self.objects.pop(object_name, None)
        return True


def extract_namespace(storage, current_user):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    definitions = {
        node.name: node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    application = FastAPI()
    admin_router = APIRouter(prefix="/api/admin")
    namespace = {
        "__name__": "offline_history_retention_routes", "__file__": str(SOURCE),
        "app": application, "admin_router": admin_router,
        "Body": Body, "Query": Query, "JSONResponse": JSONResponse,
        "StreamingResponse": StreamingResponse, "Optional": Optional,
        "Any": Any, "Dict": Dict, "List": List, "Path": Path,
        "datetime": datetime, "timedelta": timedelta, "timezone": timezone,
        "hashlib": hashlib, "io": io, "json": json, "os": os, "re": re,
        "Workbook": Workbook, "Alignment": Alignment, "Font": Font,
        "storage_service": storage, "get_logged_in_user": current_user,
        "now_ms": lambda: 1793059200000,
        "now_display": lambda: "2026-10-27 08:00:00",
    }
    # Literal configuration is safe to load; never execute startup, imports,
    # service constructors, environment probes, or unrelated route bodies.
    for node in tree.body:
        if isinstance(node, ast.Assign):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    namespace[target.id] = value
    selected = set(ROUTES) | {"load_history_record", "save_history_record"}
    pending = list(selected)
    while pending:
        node = definitions[pending.pop()]
        for dependency in ast.walk(node):
            if not isinstance(dependency, ast.Name):
                continue
            name = dependency.id
            if name in definitions and name not in namespace and name not in selected:
                selected.add(name)
                pending.append(name)
    body = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in selected:
            node = copy.deepcopy(node)
            if node.name not in ROUTES:
                node.decorator_list = []
            body.append(node)
    with warnings.catch_warnings():
        # Preserve the production Body(example=...) declaration verbatim.
        warnings.filterwarnings("ignore", category=FastAPIDeprecationWarning)
        exec(compile(ast.Module(body=body, type_ignores=[]), str(SOURCE), "exec"), namespace)
    application.include_router(admin_router)
    return namespace, application, definitions


class HistoryAuditRetention(unittest.TestCase):
    def setUp(self):
        self.storage = MemoryStorage()
        self.user = copy.deepcopy(USER)
        self.forbidden_attempts = []

        def forbidden(*args, **kwargs):
            self.forbidden_attempts.append("external operation")
            raise AssertionError("external sockets and subprocesses are forbidden")

        isolation = contextlib.ExitStack()
        self.addCleanup(isolation.close)
        for target, attribute in (
            (socket, "create_connection"), (socket.socket, "connect"),
            (socket.socket, "connect_ex"), (socket.socket, "bind"),
            (subprocess, "Popen"), (os, "system"),
        ):
            isolation.enter_context(patch.object(target, attribute, forbidden))
        self.ns, self.app, self.definitions = extract_namespace(self.storage, lambda: dict(self.user))
        self.runner = asyncio.Runner()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app, raise_app_exceptions=False),
            base_url="http://offline-fixture",
        )
        self.addCleanup(self.runner.close)
        self.addCleanup(lambda: self.runner.run(self.client.aclose()))

    def tearDown(self):
        self.assertEqual(self.forbidden_attempts, [])

    def request(self, method, path, **kwargs):
        async def bounded_request():
            async def tick():
                # Keep the loop advancing while Starlette streams BytesIO via
                # AnyIO workers, even in sandboxes restricting socket wakeups.
                while True:
                    await asyncio.sleep(0.005)

            ticker = asyncio.create_task(tick())
            try:
                return await asyncio.wait_for(self.client.request(method, path, **kwargs), timeout=5)
            finally:
                ticker.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await ticker

        return self.runner.run(bounded_request())

    def expect_success(self, response, data=None):
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(set(payload), {"code", "msg", "data"})
        self.assertEqual(payload["code"], 0)
        if data is not None:
            self.assertEqual(payload["data"], data)
        return payload["data"]

    def seed(self, conversation_id, timestamp=1700000000000, question=None, user=None):
        user = copy.deepcopy(user or self.user)
        attachment = f"chat_files/{conversation_id}/fixture.txt"
        record = {
            "conversation_id": conversation_id,
            "title": question or f"Synthetic question {conversation_id}",
            "created_at": timestamp - 12345, "updated_at": timestamp,
            "createdAt": "2023-11-14 22:13:07", "updatedAt": "2023-11-14 22:13:20",
            "message_count": 1,
            "user": {
                **user, "categoryName": user["company"], "record_id": conversation_id,
            },
            "messages": [{
                "message_index": 0,
                "question": question or f"Synthetic question {conversation_id}",
                "answer": f"Synthetic original answer {conversation_id}",
                "created_at": timestamp - 1000, "updated_at": timestamp,
                "uploaded_files": [{
                    "file_id": "fixture-file", "filename": "fixture.txt", "object_name": attachment,
                }],
            }],
        }
        path = f"history/2023-11-14/{conversation_id}.json"
        # Deliberately retain unusual whitespace: rewriting an equivalent record
        # is a retention failure, including hidden metadata or new timestamps.
        raw = (" \n" + json.dumps(record, ensure_ascii=False, indent=3) + "\n ").encode()
        self.storage.objects[path] = raw
        self.storage.objects[attachment] = b"Synthetic original attachment bytes\x00\xff"
        return path, raw, record, attachment

    def personal_list(self, **params):
        return self.expect_success(self.request("GET", "/api/history/list", params=params))

    def hide(self, conversation_id):
        return self.request("DELETE", f"/api/chat/{conversation_id}")

    def workbook_rows(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("spreadsheetml.sheet", response.headers["content-type"])
        workbook = load_workbook(io.BytesIO(response.content), read_only=True)
        try:
            return list(workbook.active.iter_rows(values_only=True))
        finally:
            workbook.close()

    def test_existing_route_paths_methods_parameter_types_and_defaults(self):
        registered = {
            route.endpoint.__name__: (next(iter(route.methods)), route.path)
            for route in self.app.routes if route.endpoint.__name__ in ROUTES
        }
        self.assertEqual(registered, ROUTES)
        for name, node in self.definitions.items():
            if name not in ROUTES:
                continue
            args = node.args
            self.assertFalse(args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg)
            defaults = [None] * (len(args.args) - len(args.defaults)) + list(args.defaults)
            signature = []
            for argument, default in zip(args.args, defaults):
                if default is None:
                    wrapper, value = None, "REQUIRED"
                else:
                    self.assertIsInstance(default, ast.Call)
                    wrapper = ast.unparse(default.func)
                    value = ast.literal_eval(default.args[0])
                signature.append((argument.arg, ast.unparse(argument.annotation), wrapper, value))
            if name in {"list_histories", "admin_list_histories"}:
                expected = LIST_SIGNATURE
            elif name in {"batch_delete_history", "admin_batch_delete_history"}:
                expected = [("data", "dict", "Body", Ellipsis)]
            elif name in {"export_history_detail", "admin_export_history"}:
                expected = [("data", "Optional[dict]", "Body", None)]
            elif name in {"download_history_uploaded_file", "admin_download_history_file"}:
                expected = [("conversation_id", "str", None, "REQUIRED"),
                            ("message_index", "int", None, "REQUIRED"),
                            ("file_id", "str", None, "REQUIRED")]
            else:
                expected = [("conversation_id", "str", None, "REQUIRED")]
            self.assertEqual(signature, expected, name)

    def test_single_delete_preserves_original_bytes_messages_timestamps_and_attachment(self):
        path, raw, record, attachment = self.seed("single")
        attachment_bytes = self.storage.objects[attachment]
        self.expect_success(self.hide("single"), {"conversation_id": "single"})
        self.assertEqual(self.storage.objects.get(path), raw)
        self.assertEqual(self.storage.objects[attachment], attachment_bytes)
        self.assertEqual(self.storage.deletes, [])
        self.assertEqual(self.personal_list()["total"], 0)
        self.assertEqual(self.request("GET", "/api/history/single").status_code, 404)
        admin = self.expect_success(self.request("GET", "/api/admin/history/single"))
        for key in ("messages", "created_at", "updated_at", "createdAt", "updatedAt"):
            self.assertEqual(admin[key], record[key])
        listing = self.expect_success(self.request("GET", "/api/admin/history/list"))
        self.assertEqual(listing["total"], 1)
        rows = self.workbook_rows(self.request("POST", "/api/admin/history/export", json={"ids": ["single"]}))
        self.assertIn(record["messages"][0]["answer"], rows[1][-1])
        download = self.request("GET", "/api/admin/history/single/messages/0/files/fixture-file/download")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content, attachment_bytes)
        self.assertEqual(self.storage.objects[path], raw)

    def test_batch_delete_preserves_all_originals_and_only_hides_requested_records(self):
        fixtures = {cid: self.seed(cid) for cid in ("batch-one", "batch-two", "keep")}
        originals = dict(self.storage.objects)
        self.expect_success(self.request("POST", "/api/history/batch_delete", json={
            "ids": ["batch-one", "batch-two", "missing"],
        }), {"deleted_ids": ["batch-one", "batch-two"]})
        for name, payload in originals.items():
            self.assertEqual(self.storage.objects.get(name), payload, name)
        self.assertEqual(self.storage.deletes, [])
        self.assertEqual([row["conversation_id"] for row in self.personal_list()["list"]], ["keep"])
        for cid in fixtures:
            response = self.request("GET", f"/api/admin/history/{cid}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"]["messages"], fixtures[cid][2]["messages"])

    def test_hidden_history_is_filtered_before_total_pagination_and_search(self):
        self.seed("hidden-newest", 1700000004000, "needle hidden")
        self.seed("keep-first", 1700000003000, "needle keep first")
        self.seed("keep-second", 1700000002000, "needle keep second")
        self.seed("keep-unmatched", 1700000001000, "different topic")
        self.expect_success(self.hide("hidden-newest"))
        listing = self.personal_list(search="needle", page=2, size=1)
        self.assertEqual({key: listing[key] for key in ("total", "page", "size", "total_pages")},
                         {"total": 2, "page": 2, "size": 1, "total_pages": 2})
        self.assertEqual([row["conversation_id"] for row in listing["list"]], ["keep-second"])
        self.assertEqual(self.personal_list(search="needle hidden")["total"], 0)
        self.assertEqual(self.personal_list()["total"], 3)
        admin = self.expect_success(self.request("GET", "/api/admin/history/list", params={"search": "needle"}))
        self.assertEqual(admin["total"], 3)

    def test_same_name_users_have_independent_hidden_state(self):
        path, raw, _, _ = self.seed("shared-name")
        self.expect_success(self.hide("shared-name"))
        self.user.update(user_id="fixture-user-b", staff_id="fixture-user-b", access_token="fixture-token-b")
        self.assertEqual(self.personal_list()["total"], 1)
        self.assertEqual(self.request("GET", "/api/history/shared-name").status_code, 200)
        self.expect_success(self.hide("shared-name"))
        self.assertEqual(self.personal_list()["total"], 0)
        self.user = copy.deepcopy(USER)
        self.assertEqual(self.personal_list()["total"], 0)
        self.assertEqual(self.storage.objects[path], raw)

    def test_same_user_id_in_other_tenant_has_independent_hidden_state(self):
        self.seed("shared-tenant")
        self.expect_success(self.hide("shared-tenant"))
        self.user["tenant_id"] = "fixture-tenant-b"
        self.assertEqual(self.personal_list()["total"], 1)
        self.assertEqual(self.request("GET", "/api/history/shared-tenant").status_code, 200)
        self.expect_success(self.hide("shared-tenant"))
        self.assertEqual(self.personal_list()["total"], 0)
        self.user["tenant_id"] = USER["tenant_id"]
        self.assertEqual(self.personal_list()["total"], 0)

    def test_token_and_display_name_change_do_not_reset_hidden_state(self):
        self.seed("stable-identity")
        self.expect_success(self.hide("stable-identity"))
        self.user.update(access_token="fixture-rotated-token", name="Changed fixture name")
        self.assertEqual(self.request("GET", "/api/history/stable-identity").status_code, 404)
        self.assertEqual(self.personal_list()["total"], 0)
        self.expect_success(self.hide("stable-identity"), {"conversation_id": "stable-identity"})

    def test_guests_without_user_id_have_independent_hidden_state_by_ip(self):
        self.user = {
            "role": "guest", "name": "Synthetic Guest", "company": "",
            "ip_address": "192.0.2.30", "access_token": "",
        }
        path, raw, _, _ = self.seed("guest-ip")
        self.expect_success(self.hide("guest-ip"))
        self.assertEqual(self.personal_list()["total"], 0)
        self.assertEqual(self.request("GET", "/api/history/guest-ip").status_code, 404)

        self.user["ip_address"] = "192.0.2.31"
        self.assertEqual(self.personal_list()["total"], 1)
        self.assertEqual(self.request("GET", "/api/history/guest-ip").status_code, 200)
        self.user["ip_address"] = "192.0.2.30"
        self.assertEqual(self.personal_list()["total"], 0)
        self.assertEqual(self.request("GET", "/api/history/guest-ip").status_code, 404)
        self.assertEqual(self.storage.objects.get(path), raw)

    def test_guest_same_ip_shares_hidden_state_despite_different_untrusted_tokens(self):
        self.user = {
            "role": "guest", "name": "Synthetic Guest", "company": "",
            "ip_address": "192.0.2.40", "access_token": "fixture-invalid-token-a",
        }
        path, raw, _, _ = self.seed("guest-token")
        self.expect_success(self.hide("guest-token"))
        for token in ("", "fixture-invalid-token-b", "fixture-invalid-token-c"):
            # Each request represents another guest at the same IP. Invalid
            # credentials do not create a separate authenticated identity.
            self.user = {
                "role": "guest", "name": "Synthetic Guest", "company": "",
                "ip_address": "192.0.2.40", "access_token": token,
            }
            self.assertEqual(self.personal_list()["total"], 0)
            self.assertEqual(self.request("GET", "/api/history/guest-token").status_code, 404)
            self.expect_success(self.hide("guest-token"), {"conversation_id": "guest-token"})
        self.assertEqual(self.storage.objects.get(path), raw)

    def test_repeated_single_and_batch_delete_are_idempotent(self):
        path, raw, _, _ = self.seed("repeat")
        for _ in range(2):
            self.expect_success(self.hide("repeat"), {"conversation_id": "repeat"})
        self.expect_success(self.request("POST", "/api/history/batch_delete", json={"ids": ["repeat"]}),
                            {"deleted_ids": ["repeat"]})
        self.assertEqual(self.storage.objects.get(path), raw)
        self.assertEqual(self.personal_list()["total"], 0)

    def test_missing_history_returns_404_without_writing_marker(self):
        response = self.hide("does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], 1)
        self.assertEqual(response.json()["data"], {"conversation_id": "does-not-exist"})
        self.assertEqual(self.storage.objects, {})
        self.assertEqual(self.storage.uploads, [])

    def test_batch_partial_marker_write_failure_reports_only_successes(self):
        first = self.seed("partial-success")
        second = self.seed("partial-failure")
        self.storage.fail_upload_numbers = {2}
        result = self.request("POST", "/api/history/batch_delete", json={
            "ids": ["partial-success", "partial-failure", "missing"],
        })
        self.expect_success(result, {"deleted_ids": ["partial-success"]})
        self.assertEqual(self.storage.objects.get(first[0]), first[1])
        self.assertEqual(self.storage.objects.get(second[0]), second[1])
        self.assertEqual(self.request("GET", "/api/history/partial-success").status_code, 404)
        self.assertEqual(self.request("GET", "/api/history/partial-failure").status_code, 200)
        self.assertEqual([row["conversation_id"] for row in self.personal_list()["list"]], ["partial-failure"])

    def test_single_marker_write_failure_returns_500_and_keeps_visibility(self):
        path, raw, _, _ = self.seed("failed-marker")
        self.storage.fail_all_uploads = True
        response = self.hide("failed-marker")
        self.assertEqual(response.status_code, 500, response.text)
        self.assertEqual(response.json()["code"], 1)
        self.assertEqual(self.storage.objects.get(path), raw)
        self.assertEqual(self.storage.deletes, [])
        self.assertEqual(self.personal_list()["total"], 1)
        self.assertEqual(self.request("GET", "/api/history/failed-marker").status_code, 200)

    def test_stale_chat_save_cannot_resurrect_personal_history(self):
        self.seed("in-flight")
        stale_record, stale_path = self.ns["load_history_record"]("in-flight", self.user)
        self.expect_success(self.hide("in-flight"))
        stale_record["messages"].append({
            "message_index": 1, "question": "Synthetic in-flight question",
            "answer": "Synthetic in-flight answer",
        })
        self.ns["save_history_record"](stale_record, stale_path)
        self.assertEqual(self.personal_list()["total"], 0)
        self.assertEqual(self.request("GET", "/api/history/in-flight").status_code, 404)
        admin = self.expect_success(self.request("GET", "/api/admin/history/in-flight"))
        self.assertEqual(len(admin["messages"]), 2)
        self.assertEqual(admin["messages"][-1]["answer"], "Synthetic in-flight answer")

    def test_marker_listing_failure_returns_500_without_exposing_hidden_record(self):
        self.seed("marker-outage")
        self.expect_success(self.hide("marker-outage"))
        self.storage.fail_marker_listing = True
        for path in ("/api/history/list", "/api/history/marker-outage"):
            response = self.request("GET", path)
            self.assertEqual(response.status_code, 500, (path, response.text))
            self.assertNotIn("Synthetic original answer", response.text)
        platform = self.expect_success(self.request("GET", "/api/admin/history/marker-outage"))
        self.assertTrue(platform["messages"])

    def test_personal_export_keeps_existing_401_guard_platform_export_keeps_original(self):
        _, _, record, _ = self.seed("export-hidden")
        self.expect_success(self.hide("export-hidden"))
        for payload in ({"ids": ["export-hidden"]}, {}, {"search": "Synthetic"}):
            response = self.request("POST", "/api/history/export", json=payload)
            self.assertEqual(response.status_code, 401, response.text)
            self.assertEqual(response.json()["code"], 1)
        rows = self.workbook_rows(self.request("POST", "/api/admin/history/export", json={"ids": ["export-hidden"]}))
        self.assertIn(record["messages"][0]["question"], rows[1][-1])
        self.assertIn(record["messages"][0]["answer"], rows[1][-1])

    def test_sanitized_conversation_alias_cannot_bypass_hidden_state(self):
        path, raw, _, _ = self.seed("canonical")
        self.expect_success(self.hide("canonical!"), {"conversation_id": "canonical!"})
        self.assertEqual(self.storage.objects.get(path), raw)
        self.assertEqual(self.request("GET", "/api/history/canonical").status_code, 404)
        self.assertEqual(self.request("GET", "/api/history/canonical!").status_code, 404)
        self.assertEqual(self.personal_list()["total"], 0)

    def test_platform_single_delete_still_physically_deletes_original(self):
        path, _, _, _ = self.seed("platform-single")
        self.expect_success(self.request("DELETE", "/api/admin/history/platform-single"),
                            {"conversation_id": "platform-single"})
        self.assertNotIn(path, self.storage.objects)
        self.assertIn(path, self.storage.deletes)

    def test_platform_single_delete_physically_deletes_personally_hidden_original(self):
        path, raw, _, _ = self.seed("platform-hidden")
        self.expect_success(self.hide("platform-hidden"))
        self.assertEqual(self.storage.objects.get(path), raw)
        self.expect_success(self.request("DELETE", "/api/admin/history/platform-hidden"),
                            {"conversation_id": "platform-hidden"})
        self.assertNotIn(path, self.storage.objects)
        self.assertIn(path, self.storage.deletes)

    def test_platform_batch_delete_still_physically_deletes_originals(self):
        first = self.seed("platform-batch-one")
        second = self.seed("platform-batch-two")
        self.expect_success(self.request("POST", "/api/admin/history/batch_delete", json={
            "ids": ["platform-batch-one", "missing", "platform-batch-two"],
        }), {"deleted_ids": ["platform-batch-one", "platform-batch-two"]})
        self.assertNotIn(first[0], self.storage.objects)
        self.assertNotIn(second[0], self.storage.objects)


if __name__ == "__main__":
    unittest.main(verbosity=2)
