import io
import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

import httpx


class CollectingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.successes = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.successes.append(test)


def run_startup_check(repo_root: Path):
    command = ["bash", "conda_restart_services.sh"]
    proc = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    backend_log = repo_root / "logs" / "backend.log"
    log_tail = ""
    if backend_log.exists():
        log_tail = "\n".join(backend_log.read_text(encoding="utf-8", errors="ignore").splitlines()[-20:])

    probes = []
    for path in ["/api/kb/list", "/api/test/file_tree"]:
        try:
            response = httpx.get(f"http://127.0.0.1:8000{path}", timeout=5.0)
            probes.append(
                {
                    "path": path,
                    "status_code": response.status_code,
                    "body_preview": response.text[:300],
                }
            )
        except Exception as exc:
            probes.append({"path": path, "error": repr(exc)})

    return {
        "command": " ".join(command),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "backend_log_tail": log_tail,
        "probes": probes,
    }


def run_unit_tests(repo_root: Path):
    tests_dir = repo_root / "backend" / "tests"
    if str(tests_dir) not in sys.path:
        sys.path.insert(0, str(tests_dir))

    suite = unittest.defaultTestLoader.discover(str(tests_dir), pattern="test_*.py")
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=CollectingResult)
    started_at = time.time()
    result = runner.run(suite)
    duration = time.time() - started_at

    def serialize_case(test, outcome, detail=None):
        return {
            "name": test.id(),
            "outcome": outcome,
            "detail": detail or "",
        }

    cases = [serialize_case(test, "passed") for test in result.successes]
    cases.extend(serialize_case(test, "failed", detail) for test, detail in result.failures)
    cases.extend(serialize_case(test, "error", detail) for test, detail in result.errors)
    cases.extend(serialize_case(test, "skipped", reason) for test, reason in result.skipped)
    cases.sort(key=lambda item: item["name"])

    return {
        "duration_seconds": round(duration, 3),
        "tests_run": result.testsRun,
        "passed": len(result.successes),
        "failed": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "successful": result.wasSuccessful(),
        "runner_output": stream.getvalue(),
        "cases": cases,
    }


def build_sample_section():
    success_sample = {
        "success": True,
        "code": "SUCCESS",
        "message": "知识库列表获取成功",
        "data": [{"id": "kb123456", "name": "默认知识库"}],
        "request_id": "sample-request-id",
    }
    error_sample = {
        "success": False,
        "code": "INVALID_KB_ID",
        "message": "id格式非法",
        "data": None,
        "detail": None,
        "request_id": "sample-request-id",
    }
    return [
        "## API Samples",
        "",
        "### Success Sample",
        "",
        "```json",
        json.dumps(success_sample, ensure_ascii=False, indent=2),
        "```",
        "",
        "### Error Sample",
        "",
        "```json",
        json.dumps(error_sample, ensure_ascii=False, indent=2),
        "```",
        "",
    ]


def build_markdown_report(startup, tests):
    lines = []
    lines.append("# Backend API Test Report")
    lines.append("")
    lines.append("## Startup Check")
    lines.append("")
    lines.append(f"- Command: `{startup['command']}`")
    lines.append(f"- Return code: `{startup['returncode']}`")
    lines.append("")
    lines.append("### Startup Output")
    lines.append("")
    lines.append("```text")
    lines.append((startup["stdout"] or "").rstrip())
    if startup["stderr"]:
        lines.append(startup["stderr"].rstrip())
    lines.append("```")
    lines.append("")
    lines.append("### Backend Log Tail")
    lines.append("")
    lines.append("```text")
    lines.append((startup["backend_log_tail"] or "").rstrip())
    lines.append("```")
    lines.append("")
    lines.append("### Health Probes")
    lines.append("")
    for probe in startup["probes"]:
        if "error" in probe:
            lines.append(f"- `{probe['path']}`: ERROR {probe['error']}")
        else:
            lines.append(f"- `{probe['path']}`: HTTP {probe['status_code']} | `{probe['body_preview']}`")
    lines.append("")
    lines.append("## Unit Test Summary")
    lines.append("")
    lines.append(f"- Tests run: `{tests['tests_run']}`")
    lines.append(f"- Passed: `{tests['passed']}`")
    lines.append(f"- Failed: `{tests['failed']}`")
    lines.append(f"- Errors: `{tests['errors']}`")
    lines.append(f"- Skipped: `{tests['skipped']}`")
    lines.append(f"- Duration: `{tests['duration_seconds']}s`")
    lines.append("")
    lines.append("## Unit Test Cases")
    lines.append("")
    for case in tests["cases"]:
        lines.append(f"- `{case['name']}`: {case['outcome']}")
    lines.append("")
    lines.extend(build_sample_section())
    lines.append("## Runner Output")
    lines.append("")
    lines.append("```text")
    lines.append(tests["runner_output"].rstrip())
    lines.append("```")
    return "\n".join(lines) + "\n"


def main():
    repo_root = Path(__file__).resolve().parents[2]
    report_dir = repo_root / "backend" / "tests" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    startup = run_startup_check(repo_root)
    tests = run_unit_tests(repo_root)

    report = {
        "startup": startup,
        "tests": tests,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    json_path = report_dir / "api_test_report.json"
    md_path = report_dir / "api_test_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown_report(startup, tests), encoding="utf-8")

    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    print(json.dumps({
        "tests_run": tests["tests_run"],
        "passed": tests["passed"],
        "failed": tests["failed"],
        "errors": tests["errors"],
        "successful": tests["successful"],
    }, ensure_ascii=False))

    raise SystemExit(0 if tests["successful"] else 1)


if __name__ == "__main__":
    main()
