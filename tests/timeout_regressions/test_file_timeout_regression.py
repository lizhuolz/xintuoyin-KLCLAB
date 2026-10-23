"""Offline regressions. Pass XTY_SOURCE_ROOT to check a staged or real tree."""
import ast
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

ROOT = Path(os.environ.get("XTY_SOURCE_ROOT", "/data2/dlx/projects/xty"))


class FileTimeoutRegression(unittest.TestCase):
    def test_storage_returns_after_read_timeout(self):
        class SlowStorage(BaseHTTPRequestHandler):
            def do_GET(self):
                time.sleep(0.65)
                self.send_response(503)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), SlowStorage)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(os.environ, {
                "MINIO_ENDPOINT": f"127.0.0.1:{server.server_port}",
                "MINIO_SECURE": "false",
                "MINIO_ACCESS_KEY": "offline-test",
                "MINIO_SECRET_KEY": "offline-test",
                "MINIO_CONNECT_TIMEOUT_SECONDS": "0.1",
                "MINIO_READ_TIMEOUT_SECONDS": "0.1",
            }):
                spec = importlib.util.spec_from_file_location(
                    "timeout_storage", ROOT / "backend/services/storage_service.py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                start = time.monotonic()
                with self.assertLogs(module.logger, level="ERROR"):
                    result = module.storage_service.upload_file_obj(io.BytesIO(b"test"), "offline.txt")
                elapsed = time.monotonic() - start
                self.assertFalse(result)
                self.assertLess(elapsed, 0.5, f"MinIO staging blocked for {elapsed:.3f}s")
        finally:
            server.shutdown()
            server.server_close()

    def test_pdf_fallback_process_is_bounded_for_chat_and_kb(self):
        for relative, function_name, compact_name in [
            ("backend/app.py", "_extract_pdf_text", "_compact_text"),
            ("backend/services/kb_file_parser.py", "extract_pdf_text", "compact_text"),
        ]:
            with self.subTest(entry=relative), tempfile.TemporaryDirectory() as temp:
                tree = ast.parse((ROOT / relative).read_text())
                function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function_name)
                function.decorator_list = []
                child = Path(temp) / "slow_parser.py"
                child.write_text("import time\ntime.sleep(0.65)\nprint('late result')\n")
                passed_timeout = []

                def run_parser(command, **kwargs):
                    configured = kwargs.pop("timeout", None)
                    passed_timeout.append(configured)
                    # Scale the real child deadline for a fast deterministic test.
                    if configured is not None:
                        kwargs["timeout"] = min(configured, 0.1)
                    return subprocess.run([sys.executable, str(child)], **kwargs)

                namespace = {
                    "Path": Path, "PdfReader": None,
                    "subprocess": types.SimpleNamespace(run=run_parser),
                    compact_name: lambda text: text.strip(),
                }
                exec(compile(ast.Module(body=[function], type_ignores=[]), relative, "exec"), namespace)
                start = time.monotonic()
                result = namespace[function_name](Path(temp) / "sample.pdf")
                self.assertEqual(result, "", "timed-out child must not return a late result")
                self.assertTrue(passed_timeout and 0 < passed_timeout[0] <= 60)
                self.assertLess(time.monotonic() - start, 0.5)


if __name__ == "__main__":
    unittest.main()
