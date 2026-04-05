#!/usr/bin/env python3
import argparse
import asyncio
import csv
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp
import numpy as np
from transformers import AutoTokenizer, PreTrainedTokenizerFast


DEFAULT_CONCURRENCIES = [10, 20, 50, 100, 200, 500]
DEFAULT_BASE_URL = "http://127.0.0.1:62272"
DEFAULT_ENDPOINT = "/v1/completions"
DEFAULT_MODEL_NAME = "Qwen3-32B"
DEFAULT_MODEL_PATH = "/data1/dlx/projects/vllm_xty/model"
DEFAULT_TOKENIZER_PATH = "/data1/dlx/projects/vllm_xty/model"
DEFAULT_INPUT_LEN = 2048
DEFAULT_OUTPUT_LEN = 1024
DEFAULT_TIMEOUT = 180
DEFAULT_MIN_REQUESTS = 30
DEFAULT_ENV_LABEL = "unknown"


@dataclass
class RequestResult:
    request_id: int
    concurrency: int
    ok: bool
    timed_out: bool
    status_code: int | None
    latency_s: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    error_type: str | None
    error_message: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark a VLLM OpenAI-compatible endpoint.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--tokenizer-path", default=DEFAULT_TOKENIZER_PATH)
    parser.add_argument("--input-len", type=int, default=DEFAULT_INPUT_LEN)
    parser.add_argument("--output-len", type=int, default=DEFAULT_OUTPUT_LEN)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--min-requests", type=int, default=DEFAULT_MIN_REQUESTS)
    parser.add_argument("--concurrencies", type=int, nargs="+", default=DEFAULT_CONCURRENCIES)
    parser.add_argument("--output-dir", default="vllm_test")
    parser.add_argument("--env-label", default=DEFAULT_ENV_LABEL)
    parser.add_argument("--trust-remote-code", action="store_true", default=True)
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=float), pct))


def safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.fmean(values))


def fmt_float(value: float | None, digits: int = 2) -> str:
    if value is None or math.isnan(value):
        return "N/A"
    return f"{value:.{digits}f}"


def build_prompt(tokenizer: Any, target_tokens: int) -> tuple[str, int]:
    seed = (
        "This benchmark prompt measures throughput latency timeout rate and error rate for a "
        "VLLM deployment. It contains repetitive neutral text so the request length is controlled. "
    )
    token_ids = tokenizer.encode(seed, add_special_tokens=False)
    if not token_ids:
        raise RuntimeError("Tokenizer returned no tokens for the benchmark seed text.")
    repeats = (target_tokens // len(token_ids)) + 4
    merged = token_ids * repeats
    prompt = tokenizer.decode(merged[:target_tokens], skip_special_tokens=True)
    actual = len(tokenizer.encode(prompt, add_special_tokens=False))
    if actual < target_tokens:
        deficit = target_tokens - actual
        prompt += " " + ("benchmark " * max(4, deficit))
        actual = len(tokenizer.encode(prompt, add_special_tokens=False))
    return prompt, actual


def load_tokenizer(tokenizer_path: str, trust_remote_code: bool) -> Any:
    try:
        return AutoTokenizer.from_pretrained(
            tokenizer_path,
            trust_remote_code=trust_remote_code,
        )
    except Exception as exc:  # noqa: BLE001
        tokenizer_json = Path(tokenizer_path) / "tokenizer.json"
        if tokenizer_json.exists():
            return PreTrainedTokenizerFast(tokenizer_file=str(tokenizer_json))
        raise RuntimeError(f"Failed to load tokenizer from {tokenizer_path}: {exc}") from exc


async def warmup_once(session: aiohttp.ClientSession, url: str, model_name: str, prompt: str, output_len: int) -> None:
    payload = {
        "model": model_name,
        "prompt": prompt,
        "max_tokens": min(64, output_len),
        "temperature": 0,
    }
    async with session.post(url, json=payload) as response:
        await response.text()


async def single_request(
    session: aiohttp.ClientSession,
    url: str,
    model_name: str,
    prompt: str,
    output_len: int,
    concurrency: int,
    request_id: int,
) -> RequestResult:
    payload = {
        "model": model_name,
        "prompt": prompt,
        "max_tokens": output_len,
        "temperature": 0,
    }
    started = time.perf_counter()
    try:
        async with session.post(url, json=payload) as response:
            text = await response.text()
            elapsed = time.perf_counter() - started
            if response.status != 200:
                return RequestResult(
                    request_id=request_id,
                    concurrency=concurrency,
                    ok=False,
                    timed_out=False,
                    status_code=response.status,
                    latency_s=elapsed,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    error_type="http_error",
                    error_message=text[:500],
                )
            data = json.loads(text)
            usage = data.get("usage") or {}
            return RequestResult(
                request_id=request_id,
                concurrency=concurrency,
                ok=True,
                timed_out=False,
                status_code=response.status,
                latency_s=elapsed,
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                total_tokens=int(usage.get("total_tokens") or 0),
                error_type=None,
                error_message=None,
            )
    except asyncio.TimeoutError as exc:
        return RequestResult(
            request_id=request_id,
            concurrency=concurrency,
            ok=False,
            timed_out=True,
            status_code=None,
            latency_s=time.perf_counter() - started,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            error_type="timeout",
            error_message=str(exc) or f"Request exceeded {session.timeout.total}s timeout",
        )
    except Exception as exc:  # noqa: BLE001
        return RequestResult(
            request_id=request_id,
            concurrency=concurrency,
            ok=False,
            timed_out=False,
            status_code=None,
            latency_s=time.perf_counter() - started,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            error_type=type(exc).__name__,
            error_message=str(exc)[:500],
        )


async def run_concurrency(
    concurrency: int,
    request_count: int,
    url: str,
    model_name: str,
    prompt: str,
    output_len: int,
    timeout_s: int,
) -> list[RequestResult]:
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    connector = aiohttp.TCPConnector(limit=0, ssl=False)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        await warmup_once(session, url, model_name, prompt, output_len)
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded(request_id: int) -> RequestResult:
            async with semaphore:
                return await single_request(session, url, model_name, prompt, output_len, concurrency, request_id)

        tasks = [asyncio.create_task(bounded(i)) for i in range(request_count)]
        return await asyncio.gather(*tasks)


def summarize_results(
    concurrency: int,
    request_count: int,
    results: list[RequestResult],
    wall_s: float,
) -> dict[str, Any]:
    successes = [r for r in results if r.ok]
    failures = [r for r in results if not r.ok]
    timeouts = [r for r in results if r.timed_out]
    non_timeout_errors = [r for r in failures if not r.timed_out]
    success_latencies_ms = [r.latency_s * 1000 for r in successes]
    prompt_tokens = sum(r.prompt_tokens for r in successes)
    completion_tokens = sum(r.completion_tokens for r in successes)
    total_tokens = sum(r.total_tokens for r in successes)
    return {
        "concurrency": concurrency,
        "request_count": request_count,
        "success_count": len(successes),
        "failure_count": len(failures),
        "timeout_count": len(timeouts),
        "error_count": len(non_timeout_errors),
        "success_rate": len(successes) / request_count if request_count else 0.0,
        "failure_rate": len(failures) / request_count if request_count else 0.0,
        "error_rate": len(non_timeout_errors) / request_count if request_count else 0.0,
        "timeout_rate": len(timeouts) / request_count if request_count else 0.0,
        "mean_latency_ms": safe_mean(success_latencies_ms),
        "p50_latency_ms": percentile(success_latencies_ms, 50),
        "p95_latency_ms": percentile(success_latencies_ms, 95),
        "p99_latency_ms": percentile(success_latencies_ms, 99),
        "wall_time_s": wall_s,
        "successful_request_throughput_rps": len(successes) / wall_s if wall_s > 0 else 0.0,
        "attempted_request_throughput_rps": request_count / wall_s if wall_s > 0 else 0.0,
        "output_token_throughput_tps": completion_tokens / wall_s if wall_s > 0 else 0.0,
        "total_token_throughput_tps": total_tokens / wall_s if wall_s > 0 else 0.0,
        "mean_prompt_tokens_success": (prompt_tokens / len(successes)) if successes else None,
        "mean_completion_tokens_success": (completion_tokens / len(successes)) if successes else None,
    }


def write_jsonl(path: Path, results: list[RequestResult]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for item in results:
            fh.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "concurrency",
        "request_count",
        "success_count",
        "failure_count",
        "timeout_count",
        "error_count",
        "success_rate",
        "failure_rate",
        "error_rate",
        "timeout_rate",
        "mean_latency_ms",
        "p50_latency_ms",
        "p95_latency_ms",
        "p99_latency_ms",
        "wall_time_s",
        "successful_request_throughput_rps",
        "attempted_request_throughput_rps",
        "output_token_throughput_tps",
        "total_token_throughput_tps",
        "mean_prompt_tokens_success",
        "mean_completion_tokens_success",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_svg(rows: list[dict[str, Any]], output_path: Path, base_url: str, endpoint: str, input_len: int, output_len: int) -> None:
    width = 1380
    height = 960
    margin_left = 70
    margin_right = 30
    panel_width = 590
    panel_height = 320
    x0_left = margin_left
    x0_right = margin_left + panel_width + 80
    top_y = 80
    bottom_y = top_y + panel_height + 120
    colors = {
        "mean": "#0b6e4f",
        "p99": "#c44900",
        "timeout": "#9a031e",
        "error": "#5f0f40",
        "req": "#005f73",
        "tok": "#33658a",
    }

    xs = [row["concurrency"] for row in rows]

    def panel_svg(x: int, y: int, title: str, y_label: str, series: list[tuple[str, list[float | None], str]]) -> str:
        flat_values = [value for _, values, _ in series for value in values if value is not None]
        y_min = 0.0
        y_max = max(flat_values) if flat_values else 1.0
        if y_max <= 0:
            y_max = 1.0
        y_max *= 1.1
        inner_x = x + 50
        inner_y = y + 20
        inner_w = panel_width - 90
        inner_h = panel_height - 70

        def x_pos(value: float) -> float:
            if len(xs) == 1:
                return inner_x + inner_w / 2
            return inner_x + (value - min(xs)) / (max(xs) - min(xs)) * inner_w

        def y_pos(value: float) -> float:
            return inner_y + inner_h - ((value - y_min) / (y_max - y_min) * inner_h)

        parts = [
            f'<rect x="{x}" y="{y}" width="{panel_width}" height="{panel_height}" rx="14" fill="#ffffff" stroke="#d8dee9"/>',
            f'<text x="{x + 20}" y="{y + 28}" font-size="18" font-weight="700" fill="#102a43">{title}</text>',
            f'<text x="{x + 20}" y="{y + 48}" font-size="12" fill="#486581">{y_label}</text>',
        ]

        for i in range(5):
            y_grid = inner_y + (inner_h / 4) * i
            label_value = y_max - ((y_max - y_min) / 4) * i
            parts.append(f'<line x1="{inner_x}" y1="{y_grid:.1f}" x2="{inner_x + inner_w}" y2="{y_grid:.1f}" stroke="#e6edf3"/>')
            parts.append(f'<text x="{inner_x - 8}" y="{y_grid + 4:.1f}" text-anchor="end" font-size="11" fill="#7b8794">{label_value:.1f}</text>')

        for value in xs:
            xpos = x_pos(value)
            parts.append(f'<line x1="{xpos:.1f}" y1="{inner_y}" x2="{xpos:.1f}" y2="{inner_y + inner_h}" stroke="#f0f4f8"/>')
            parts.append(f'<text x="{xpos:.1f}" y="{inner_y + inner_h + 22}" text-anchor="middle" font-size="11" fill="#7b8794">{value}</text>')

        parts.append(f'<text x="{inner_x + inner_w / 2:.1f}" y="{inner_y + inner_h + 42}" text-anchor="middle" font-size="12" fill="#486581">Concurrency</text>')

        legend_x = x + panel_width - 170
        legend_y = y + 26
        for idx, (name, values, color) in enumerate(series):
            ly = legend_y + idx * 18
            parts.append(f'<line x1="{legend_x}" y1="{ly}" x2="{legend_x + 18}" y2="{ly}" stroke="{color}" stroke-width="3"/>')
            parts.append(f'<text x="{legend_x + 24}" y="{ly + 4}" font-size="12" fill="#334e68">{name}</text>')
            valid_points = [(x_pos(cx), y_pos(val)) for cx, val in zip(xs, values) if val is not None]
            if valid_points:
                path = " ".join(
                    [f"M {valid_points[0][0]:.1f} {valid_points[0][1]:.1f}"]
                    + [f"L {px:.1f} {py:.1f}" for px, py in valid_points[1:]]
                )
                parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="3"/>')
                for px, py in valid_points:
                    parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{color}"/>')
        return "\n".join(parts)

    mean_values = [row["mean_latency_ms"] for row in rows]
    p99_values = [row["p99_latency_ms"] for row in rows]
    timeout_values = [row["timeout_rate"] * 100 for row in rows]
    error_values = [row["error_rate"] * 100 for row in rows]
    req_values = [row["successful_request_throughput_rps"] for row in rows]
    tok_values = [row["total_token_throughput_tps"] for row in rows]
    output_tok_values = [row["output_token_throughput_tps"] for row in rows]

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#f7fafc"/>
<text x="70" y="38" font-size="28" font-weight="700" fill="#102a43">VLLM Throughput Benchmark</text>
<text x="70" y="62" font-size="13" fill="#486581">Endpoint: {base_url}{endpoint} | Payload target: {input_len}/{output_len} tokens</text>
{panel_svg(x0_left, top_y, "Latency", "Latency (ms)", [("Mean", mean_values, colors["mean"]), ("P99", p99_values, colors["p99"])])}
{panel_svg(x0_right, top_y, "Failure Ratio", "Rate (%)", [("Timeout", timeout_values, colors["timeout"]), ("Error", error_values, colors["error"])])}
{panel_svg(x0_left, bottom_y, "Request Throughput", "req/s", [("Successful req/s", req_values, colors["req"])])}
{panel_svg(x0_right, bottom_y, "Token Throughput", "tok/s", [("Total tok/s", tok_values, colors["tok"]), ("Output tok/s", output_tok_values, colors["mean"])])}
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")


def build_markdown_report(
    args: argparse.Namespace,
    actual_prompt_tokens: int,
    rows: list[dict[str, Any]],
    md_path: Path,
    csv_name: str,
    svg_name: str,
) -> None:
    best_req = max(rows, key=lambda row: row["successful_request_throughput_rps"])
    lowest_timeout = min(rows, key=lambda row: row["timeout_rate"])
    lines = [
        "# VLLM 吞吐测试报告",
        "",
        f"- 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Conda 环境: `{args.env_label}`",
        f"- 基准接口: `{args.base_url}{args.endpoint}`",
        f"- 模型名: `{args.model_name}`",
        f"- 模型路径: `{args.model_path}`",
        f"- tokenizer 路径: `{args.tokenizer_path}`",
        f"- 目标负载: 输入 `{args.input_len}` token, 输出 `{args.output_len}` token",
        f"- 实际构造 prompt token 数: 约 `{actual_prompt_tokens}`",
        f"- 客户端超时阈值: `{args.timeout}` 秒",
        f"- 请求数策略: `max(并发数, {args.min_requests})`",
        "",
        "## 结果概览",
        "",
        f"- 最高成功吞吐出现在并发 `{best_req['concurrency']}`，约 `{best_req['successful_request_throughput_rps']:.2f}` req/s。",
        f"- 最低 timeout 比例出现在并发 `{lowest_timeout['concurrency']}`，约 `{lowest_timeout['timeout_rate'] * 100:.2f}%`。",
        f"- 详细汇总见 `{csv_name}`，图表见 `{svg_name}`。",
        "",
        "## 汇总表",
        "",
        "| 并发数 | 请求数 | 成功 | 失败 | Timeout | Error | Mean Latency(ms) | P99(ms) | Timeout% | Error% | Success req/s | Total tok/s |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["concurrency"]),
                    str(row["request_count"]),
                    str(row["success_count"]),
                    str(row["failure_count"]),
                    str(row["timeout_count"]),
                    str(row["error_count"]),
                    fmt_float(row["mean_latency_ms"]),
                    fmt_float(row["p99_latency_ms"]),
                    fmt_float(row["timeout_rate"] * 100),
                    fmt_float(row["error_rate"] * 100),
                    fmt_float(row["successful_request_throughput_rps"]),
                    fmt_float(row["total_token_throughput_tps"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- `Error%` 仅统计非 timeout 失败请求占比，例如 HTTP 5xx 或连接异常。",
            "- `Timeout%` 单独统计客户端在超时阈值内未收到完整响应的请求占比。",
            "- 延迟统计仅基于成功请求的端到端响应时间。",
            "",
            f"![benchmark chart]({svg_name})",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")


async def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    ensure_dir(out_dir)
    details_dir = out_dir / "details"
    ensure_dir(details_dir)

    url = args.base_url.rstrip("/") + args.endpoint
    tokenizer = load_tokenizer(args.tokenizer_path, args.trust_remote_code)
    prompt, actual_prompt_tokens = build_prompt(tokenizer, args.input_len)

    summary_rows: list[dict[str, Any]] = []
    metadata = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "env_label": args.env_label,
        "base_url": args.base_url,
        "endpoint": args.endpoint,
        "model_name": args.model_name,
        "model_path": args.model_path,
        "tokenizer_path": args.tokenizer_path,
        "input_len_target": args.input_len,
        "output_len_target": args.output_len,
        "prompt_tokens_actual": actual_prompt_tokens,
        "timeout_seconds": args.timeout,
        "concurrencies": args.concurrencies,
        "min_requests": args.min_requests,
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    for concurrency in args.concurrencies:
        request_count = max(concurrency, args.min_requests)
        started = time.perf_counter()
        results = await run_concurrency(
            concurrency=concurrency,
            request_count=request_count,
            url=url,
            model_name=args.model_name,
            prompt=prompt,
            output_len=args.output_len,
            timeout_s=args.timeout,
        )
        wall_s = time.perf_counter() - started
        summary = summarize_results(concurrency, request_count, results, wall_s)
        summary_rows.append(summary)
        write_jsonl(details_dir / f"concurrency_{concurrency}.jsonl", results)
        print(
            json.dumps(
                {
                    "concurrency": concurrency,
                    "request_count": request_count,
                    "success_count": summary["success_count"],
                    "timeout_count": summary["timeout_count"],
                    "error_count": summary["error_count"],
                    "mean_latency_ms": summary["mean_latency_ms"],
                    "p99_latency_ms": summary["p99_latency_ms"],
                    "successful_request_throughput_rps": summary["successful_request_throughput_rps"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    csv_path = out_dir / "summary.csv"
    svg_path = out_dir / "benchmark.svg"
    md_path = out_dir / "report.md"
    write_summary_csv(csv_path, summary_rows)
    build_svg(
        summary_rows,
        svg_path,
        base_url=args.base_url,
        endpoint=args.endpoint,
        input_len=args.input_len,
        output_len=args.output_len,
    )
    build_markdown_report(
        args=args,
        actual_prompt_tokens=actual_prompt_tokens,
        rows=summary_rows,
        md_path=md_path,
        csv_name=csv_path.name,
        svg_name=svg_path.name,
    )


if __name__ == "__main__":
    asyncio.run(main())
