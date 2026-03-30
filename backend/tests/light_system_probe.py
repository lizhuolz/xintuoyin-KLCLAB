import json
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path("/home/lyq/xintuoyin-KLCLAB")
ARTIFACT_DIR = ROOT / "backend" / "tests" / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

BACKEND_BASE = os.environ.get("LIGHT_PROBE_BACKEND", "http://127.0.0.1:8000")
FRONTEND_BASES = [
    os.environ.get("LIGHT_PROBE_FRONTEND_1", "http://127.0.0.1:5173"),
    os.environ.get("LIGHT_PROBE_FRONTEND_2", "http://127.0.0.1:5174"),
]
MINIO_API = os.environ.get("LIGHT_PROBE_MINIO_API", "http://127.0.0.1:9000")
MINIO_CONSOLE = os.environ.get("LIGHT_PROBE_MINIO_CONSOLE", "http://127.0.0.1:9001")

TIMEOUT = 20
CHAT_TIMEOUT = 120
REPORT_JSON = ARTIFACT_DIR / "light_system_probe_report.json"
REPORT_MD = ARTIFACT_DIR / "light_system_probe_report.md"


def now_iso():
    return datetime.now().isoformat()


def request(method, url, *, expect_json=True, timeout=TIMEOUT, **kwargs):
    started = time.time()
    try:
        response = requests.request(method, url, timeout=timeout, **kwargs)
        elapsed_ms = round((time.time() - started) * 1000, 2)
        payload = None
        if expect_json:
            try:
                payload = response.json()
            except Exception:
                payload = None
        return {
            "ok": 200 <= response.status_code < 300,
            "status": response.status_code,
            "elapsed_ms": elapsed_ms,
            "headers": dict(response.headers),
            "json": payload if isinstance(payload, dict) else None,
            "text_preview": response.text[:500],
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "elapsed_ms": round((time.time() - started) * 1000, 2),
            "headers": {},
            "json": None,
            "text_preview": "",
            "error": str(exc),
        }


def stress(label, fn, total=6, workers=3):
    latencies = []
    ok = 0
    failed = 0
    samples = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fn) for _ in range(total)]
        for future in as_completed(futures):
            result = future.result()
            latencies.append(result.get("elapsed_ms", 0))
            if result.get("ok"):
                ok += 1
            else:
                failed += 1
            if len(samples) < 3:
                samples.append({
                    "status": result.get("status"),
                    "elapsed_ms": result.get("elapsed_ms"),
                    "error": result.get("error"),
                })
    latencies.sort()
    return {
        "label": label,
        "total": total,
        "workers": workers,
        "ok": ok,
        "failed": failed,
        "latency_ms": {
            "min": latencies[0] if latencies else None,
            "p50": latencies[len(latencies) // 2] if latencies else None,
            "max": latencies[-1] if latencies else None,
        },
        "samples": samples,
    }


def summarize_case(result):
    if result.get("json") and isinstance(result["json"], dict):
        body = result["json"]
    else:
        body = result.get("text_preview")
    return {
        "ok": result.get("ok"),
        "status": result.get("status"),
        "elapsed_ms": result.get("elapsed_ms"),
        "body": body,
        "error": result.get("error"),
    }


def run_probe():
    report = {
        "generated_at": now_iso(),
        "targets": {
            "backend": BACKEND_BASE,
            "frontend": FRONTEND_BASES,
            "minio_api": MINIO_API,
            "minio_console": MINIO_CONSOLE,
        },
        "ports": {},
        "frontend_proxy": {},
        "backend_api": {},
        "kb_lifecycle": {},
        "stress": {},
        "summary": {},
    }

    report["ports"]["backend_new_session"] = summarize_case(
        request("GET", f"{BACKEND_BASE}/api/chat/new_session")
    )
    report["ports"]["minio_api_health"] = summarize_case(
        request("GET", f"{MINIO_API}/minio/health/live", expect_json=False)
    )
    report["ports"]["minio_console_root"] = summarize_case(
        request("GET", MINIO_CONSOLE, expect_json=False)
    )

    frontend_results = {}
    for base in FRONTEND_BASES:
        frontend_results[base] = {
            "root": summarize_case(request("GET", base, expect_json=False)),
            "proxy_new_session": summarize_case(request("GET", f"{base}/api/chat/new_session")),
            "proxy_kb_list": summarize_case(request("GET", f"{base}/api/kb/list")),
        }
    report["frontend_proxy"] = frontend_results

    backend_session = request("GET", f"{BACKEND_BASE}/api/chat/new_session")
    conversation_id = ((backend_session.get("json") or {}).get("data") or {}).get("conversation_id")
    report["backend_api"]["new_session"] = summarize_case(backend_session)

    if conversation_id:
        chat_resp = request(
            "POST",
            f"{BACKEND_BASE}/api/chat",
            timeout=CHAT_TIMEOUT,
            data={
                "conversation_id": conversation_id,
                "message": "请回复：light-probe-ok",
                "user_identity": "light_probe",
                "stream": "false",
            },
        )
        title_resp = request("GET", f"{BACKEND_BASE}/api/chat/{conversation_id}/title")
        history_resp = request("GET", f"{BACKEND_BASE}/api/history/{conversation_id}")
        thinking_resp = request(
            "GET",
            f"{BACKEND_BASE}/api/chat/{conversation_id}/thinking",
            params={"message_index": 0, "stream": "false"},
            expect_json=False,
            timeout=TIMEOUT,
        )
        report["backend_api"]["chat_non_stream"] = summarize_case(chat_resp)
        report["backend_api"]["chat_title"] = summarize_case(title_resp)
        report["backend_api"]["history_detail"] = summarize_case(history_resp)
        report["backend_api"]["thinking_text"] = summarize_case(thinking_resp)

    kb_state = {"cleanup": []}
    kb_id = None
    file_name = None
    temp_path = None
    try:
        unique = f"light_probe_{int(time.time())}"
        create_kb = request(
            "POST",
            f"{BACKEND_BASE}/api/kb/create",
            data={"name": unique, "category": "个人知识库", "model": "openai"},
        )
        report["kb_lifecycle"]["create"] = summarize_case(create_kb)
        kb_id = ((create_kb.get("json") or {}).get("data") or {}).get("id")

        if kb_id:
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
                handle.write(f"知识库轻量验收令牌：{unique}\n")
                temp_path = handle.name

            with open(temp_path, "rb") as fh:
                upload = request(
                    "POST",
                    f"{BACKEND_BASE}/api/kb/{kb_id}/upload",
                    files={"files": ("verify.txt", fh, "text/plain")},
                    timeout=CHAT_TIMEOUT,
                )
            files_resp = request("GET", f"{BACKEND_BASE}/api/kb/{kb_id}/files")
            detail_resp = request("GET", f"{BACKEND_BASE}/api/kb/{kb_id}")
            report["kb_lifecycle"]["upload"] = summarize_case(upload)
            report["kb_lifecycle"]["files"] = summarize_case(files_resp)
            report["kb_lifecycle"]["detail"] = summarize_case(detail_resp)

            file_list = (((files_resp.get("json") or {}).get("data") or {}).get("files") or [])
            if file_list:
                file_name = file_list[0].get("name")
                delete_file = request(
                    "POST",
                    f"{BACKEND_BASE}/api/kb/{kb_id}/delete_file",
                    data={"filename": file_name},
                )
                report["kb_lifecycle"]["delete_file"] = summarize_case(delete_file)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
        if kb_id:
            delete_kb = request("DELETE", f"{BACKEND_BASE}/api/kb/{kb_id}")
            report["kb_lifecycle"]["delete_kb"] = summarize_case(delete_kb)

    report["stress"]["backend_new_session"] = stress(
        "backend_new_session",
        lambda: request("GET", f"{BACKEND_BASE}/api/chat/new_session"),
        total=12,
        workers=4,
    )
    report["stress"]["backend_kb_list"] = stress(
        "backend_kb_list",
        lambda: request("GET", f"{BACKEND_BASE}/api/kb/list"),
        total=8,
        workers=4,
    )
    report["stress"]["frontend_proxy_new_session"] = stress(
        "frontend_proxy_new_session",
        lambda: request("GET", f"{FRONTEND_BASES[0]}/api/chat/new_session"),
        total=8,
        workers=4,
    )

    checks = []
    checks.append(report["ports"]["backend_new_session"].get("ok"))
    checks.append(report["ports"]["minio_api_health"].get("ok"))
    checks.append(report["ports"]["minio_console_root"].get("status") == 200)
    checks.extend(item["proxy_new_session"].get("ok") for item in frontend_results.values())
    checks.append(report["backend_api"].get("chat_non_stream", {}).get("ok"))
    checks.append(report["kb_lifecycle"].get("create", {}).get("ok"))
    checks.append(report["kb_lifecycle"].get("upload", {}).get("ok"))
    checks.append(report["kb_lifecycle"].get("files", {}).get("ok"))
    checks.append(report["kb_lifecycle"].get("delete_kb", {}).get("ok"))

    report["summary"] = {
        "all_critical_checks_passed": all(bool(item) for item in checks),
        "critical_check_count": len(checks),
        "passed_checks": sum(1 for item in checks if item),
        "notes": [
            "前端代理通过 5173/5174 的 /api 路径直连后端验证。",
            "轻量压测只覆盖无模型或低成本接口，避免重型模型调用导致报告不可复现。",
            "聊天主链路保留 1 次真实非流式调用，验证前后端集成未断。"
        ],
    }
    return report


def write_reports(report):
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Light System Probe Report",
        "",
        f"- generated_at: {report['generated_at']}",
        f"- backend: {report['targets']['backend']}",
        f"- frontends: {', '.join(report['targets']['frontend'])}",
        f"- minio_api: {report['targets']['minio_api']}",
        f"- minio_console: {report['targets']['minio_console']}",
        f"- all_critical_checks_passed: {report['summary']['all_critical_checks_passed']}",
        f"- passed_checks: {report['summary']['passed_checks']}/{report['summary']['critical_check_count']}",
        "",
        "## Ports",
        "",
    ]

    for name, result in report["ports"].items():
        lines.append(f"- {name}: status={result.get('status')} ok={result.get('ok')} elapsed_ms={result.get('elapsed_ms')}")

    lines.extend(["", "## Frontend Proxy", ""])
    for base, result in report["frontend_proxy"].items():
        lines.append(f"- {base} root: status={result['root'].get('status')} ok={result['root'].get('ok')}")
        lines.append(f"- {base} proxy_new_session: status={result['proxy_new_session'].get('status')} ok={result['proxy_new_session'].get('ok')}")
        lines.append(f"- {base} proxy_kb_list: status={result['proxy_kb_list'].get('status')} ok={result['proxy_kb_list'].get('ok')}")

    lines.extend(["", "## Backend API", ""])
    for name, result in report["backend_api"].items():
        lines.append(f"- {name}: status={result.get('status')} ok={result.get('ok')} elapsed_ms={result.get('elapsed_ms')}")

    lines.extend(["", "## KB Lifecycle", ""])
    for name, result in report["kb_lifecycle"].items():
        lines.append(f"- {name}: status={result.get('status')} ok={result.get('ok')} elapsed_ms={result.get('elapsed_ms')}")

    lines.extend(["", "## Stress", ""])
    for name, result in report["stress"].items():
        lat = result["latency_ms"]
        lines.append(
            f"- {name}: ok={result['ok']}/{result['total']} failed={result['failed']} latency_ms(min/p50/max)={lat['min']}/{lat['p50']}/{lat['max']}"
        )

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    probe_report = run_probe()
    write_reports(probe_report)
    print(json.dumps({
        "json_report": str(REPORT_JSON),
        "markdown_report": str(REPORT_MD),
        "all_critical_checks_passed": probe_report["summary"]["all_critical_checks_passed"],
        "passed_checks": probe_report["summary"]["passed_checks"],
        "critical_check_count": probe_report["summary"]["critical_check_count"],
    }, ensure_ascii=False, indent=2))
