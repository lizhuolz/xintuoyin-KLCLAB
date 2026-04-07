#!/usr/bin/env python3
import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate benchmark comparison report.")
    parser.add_argument("--old-ctx2024", required=True)
    parser.add_argument("--new-ctx2024", required=True)
    parser.add_argument("--old-ctx10k", required=True)
    parser.add_argument("--new-ctx10k", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--historical-deployment-note", action="append", default=[])
    parser.add_argument("--current-deployment-note", action="append", default=[])
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_metadata(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def to_float(value: str | None) -> float | None:
    if value in (None, "", "nan"):
        return None
    return float(value)


def to_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    return int(float(value))


def normalize_rows(rows: list[dict]) -> list[dict]:
    normalized = []
    for row in rows:
        normalized.append(
            {
                "concurrency": to_int(row["concurrency"]),
                "request_count": to_int(row["request_count"]),
                "success_count": to_int(row["success_count"]),
                "failure_count": to_int(row["failure_count"]),
                "timeout_count": to_int(row["timeout_count"]),
                "error_count": to_int(row["error_count"]),
                "success_rate": to_float(row["success_rate"]),
                "failure_rate": to_float(row["failure_rate"]),
                "error_rate": to_float(row["error_rate"]),
                "timeout_rate": to_float(row["timeout_rate"]),
                "mean_latency_ms": to_float(row["mean_latency_ms"]),
                "p99_latency_ms": to_float(row["p99_latency_ms"]),
                "wall_time_s": to_float(row["wall_time_s"]),
                "successful_request_throughput_rps": to_float(row["successful_request_throughput_rps"]),
                "total_token_throughput_tps": to_float(row["total_token_throughput_tps"]),
            }
        )
    return normalized


def fmt_float(value: float | None, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return f"{value:.{digits}f}"


def fmt_pct(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.{digits}f}%"


def pct_delta(new: float | None, old: float | None) -> float | None:
    if new is None or old is None or old == 0:
        return None
    return (new - old) / old


def index_by_concurrency(rows: list[dict]) -> dict[int, dict]:
    return {row["concurrency"]: row for row in rows}


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_line_panel(
    x: int,
    y: int,
    width: int,
    height: int,
    title: str,
    y_label: str,
    xs: list[int],
    series: list[tuple[str, list[float | None], str]],
) -> str:
    inner_x = x + 56
    inner_y = y + 28
    inner_w = width - 84
    inner_h = height - 86
    flat_values = [value for _, values, _ in series for value in values if value is not None]
    y_min = 0.0
    y_max = max(flat_values) if flat_values else 1.0
    if y_max <= 0:
        y_max = 1.0
    y_max *= 1.10

    def x_pos(value: float) -> float:
        if len(xs) == 1:
            return inner_x + inner_w / 2
        return inner_x + (value - min(xs)) / (max(xs) - min(xs)) * inner_w

    def y_pos(value: float) -> float:
        return inner_y + inner_h - ((value - y_min) / (y_max - y_min) * inner_h)

    parts = [
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="14" fill="#ffffff" stroke="#d8dee9"/>',
        f'<text x="{x + 18}" y="{y + 26}" font-size="18" font-weight="700" fill="#102a43">{title}</text>',
        f'<text x="{x + 18}" y="{y + 46}" font-size="12" fill="#486581">{y_label}</text>',
    ]

    for i in range(5):
        y_grid = inner_y + (inner_h / 4) * i
        label_value = y_max - ((y_max - y_min) / 4) * i
        parts.append(f'<line x1="{inner_x}" y1="{y_grid:.1f}" x2="{inner_x + inner_w}" y2="{y_grid:.1f}" stroke="#e6edf3"/>')
        parts.append(f'<text x="{inner_x - 8}" y="{y_grid + 4:.1f}" text-anchor="end" font-size="11" fill="#7b8794">{label_value:.1f}</text>')

    for value in xs:
        xpos = x_pos(value)
        parts.append(f'<line x1="{xpos:.1f}" y1="{inner_y}" x2="{xpos:.1f}" y2="{inner_y + inner_h}" stroke="#f0f4f8"/>')
        parts.append(f'<text x="{xpos:.1f}" y="{inner_y + inner_h + 20}" text-anchor="middle" font-size="11" fill="#7b8794">{value}</text>')

    parts.append(f'<text x="{inner_x + inner_w / 2:.1f}" y="{inner_y + inner_h + 40}" text-anchor="middle" font-size="12" fill="#486581">Concurrency</text>')

    legend_x = x + width - 180
    legend_y = y + 24
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


def build_dual_svg(
    path: Path,
    title: str,
    subtitle: str,
    rows_a: list[dict],
    label_a: str,
    rows_b: list[dict],
    label_b: str,
) -> None:
    xs = sorted({row["concurrency"] for row in rows_a} | {row["concurrency"] for row in rows_b})
    map_a = index_by_concurrency(rows_a)
    map_b = index_by_concurrency(rows_b)
    width = 1360
    height = 900
    panel_w = 590
    panel_h = 320
    left_x = 70
    right_x = 690
    top_y = 90
    bottom_y = 470
    colors = ("#0b6e4f", "#c44900")

    def values(rows_map: dict[int, dict], key: str) -> list[float | None]:
        return [rows_map.get(x, {}).get(key) for x in xs]

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#f7fafc"/>
<text x="70" y="40" font-size="28" font-weight="700" fill="#102a43">{title}</text>
<text x="70" y="64" font-size="13" fill="#486581">{subtitle}</text>
{render_line_panel(left_x, top_y, panel_w, panel_h, "Successful req/s", "req/s", xs, [(label_a, values(map_a, "successful_request_throughput_rps"), colors[0]), (label_b, values(map_b, "successful_request_throughput_rps"), colors[1])])}
{render_line_panel(right_x, top_y, panel_w, panel_h, "Total tok/s", "tok/s", xs, [(label_a, values(map_a, "total_token_throughput_tps"), colors[0]), (label_b, values(map_b, "total_token_throughput_tps"), colors[1])])}
{render_line_panel(left_x, bottom_y, panel_w, panel_h, "Mean Latency", "ms", xs, [(label_a, values(map_a, "mean_latency_ms"), colors[0]), (label_b, values(map_b, "mean_latency_ms"), colors[1])])}
{render_line_panel(right_x, bottom_y, panel_w, panel_h, "Timeout Ratio", "%", xs, [(label_a, [None if v is None else v * 100 for v in values(map_a, "timeout_rate")], colors[0]), (label_b, [None if v is None else v * 100 for v in values(map_b, "timeout_rate")], colors[1])])}
</svg>
"""
    path.write_text(svg, encoding="utf-8")


def build_historical_table(old_rows: list[dict], new_rows: list[dict], label: str) -> list[dict]:
    old_map = index_by_concurrency(old_rows)
    new_map = index_by_concurrency(new_rows)
    shared = sorted(set(old_map) & set(new_map))
    rows = []
    for concurrency in shared:
        old_row = old_map[concurrency]
        new_row = new_map[concurrency]
        rows.append(
            {
                "context": label,
                "concurrency": concurrency,
                "old_req_s": fmt_float(old_row["successful_request_throughput_rps"]),
                "new_req_s": fmt_float(new_row["successful_request_throughput_rps"]),
                "req_s_delta_pct": fmt_pct(pct_delta(new_row["successful_request_throughput_rps"], old_row["successful_request_throughput_rps"])),
                "old_tok_s": fmt_float(old_row["total_token_throughput_tps"]),
                "new_tok_s": fmt_float(new_row["total_token_throughput_tps"]),
                "tok_s_delta_pct": fmt_pct(pct_delta(new_row["total_token_throughput_tps"], old_row["total_token_throughput_tps"])),
                "old_timeout_pct": fmt_pct(old_row["timeout_rate"]),
                "new_timeout_pct": fmt_pct(new_row["timeout_rate"]),
            }
        )
    return rows


def best_row(rows: list[dict]) -> dict:
    return max(rows, key=lambda row: row["successful_request_throughput_rps"] or 0.0)


def first_timeout_row(rows: list[dict]) -> dict | None:
    timed = [row for row in rows if (row["timeout_rate"] or 0.0) > 0]
    return min(timed, key=lambda row: row["concurrency"]) if timed else None


def build_markdown(
    out_dir: Path,
    meta_old_2024: dict,
    old_2024: list[dict],
    meta_new_2024: dict,
    new_2024: list[dict],
    meta_old_10k: dict,
    old_10k: list[dict],
    meta_new_10k: dict,
    new_10k: list[dict],
    historical_deployment_notes: list[str],
    current_deployment_notes: list[str],
) -> None:
    current_compare_name = "comparison_4gpu_ctx2024_vs_ctx10k.svg"
    hist_2024_name = "comparison_ctx2024_2gpu_vs_4gpu.svg"
    hist_10k_name = "comparison_ctx10k_2gpu_vs_4gpu.svg"

    hist_rows = build_historical_table(old_2024, new_2024, "2024")
    hist_rows.extend(build_historical_table(old_10k, new_10k, "10000"))
    write_csv(
        out_dir / "historical_comparison.csv",
        [
            "context",
            "concurrency",
            "old_req_s",
            "new_req_s",
            "req_s_delta_pct",
            "old_tok_s",
            "new_tok_s",
            "tok_s_delta_pct",
            "old_timeout_pct",
            "new_timeout_pct",
        ],
        hist_rows,
    )

    lines = [
        "# Qwen3-32B 四卡吞吐对比报告",
        "",
        f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 当前服务: `http://127.0.0.1:62274/v1/completions`",
        f"- 当前部署环境: `{meta_new_2024.get('env_label', '/data2/lyq/conda-envs/sglang_qwen35_27b')}`",
        "- 当前部署卡数: `4 GPU`",
        "- 历史基线: 仓库内 `2 GPU` 测试结果",
        "",
        "## 当前四卡测试口径",
        "",
        f"- `2024` 上下文: 输入约 `{meta_new_2024['prompt_tokens_actual']}` token，输出 `1024` token，并发 `{' '.join(map(str, meta_new_2024['concurrencies']))}`。",
        f"- `10000` 上下文: 输入约 `{meta_new_10k['prompt_tokens_actual']}` token，输出 `1024` token，并发 `{' '.join(map(str, meta_new_10k['concurrencies']))}`。",
        f"- 客户端 timeout: `{meta_new_2024['timeout_seconds']}s`。",
        "",
        "## 部署方法",
        "",
        "### 历史 2 卡基线",
        "",
    ]
    for note in historical_deployment_notes:
        lines.append(f"- {note}")
    if not historical_deployment_notes:
        lines.append("- 仓库中已有 `results_fine` 和 `results_ctx10k` 作为历史 2 卡基线，本次未重新部署历史实例。")

    lines.extend(
        [
            "",
            "### 当前 4 卡部署",
            "",
        ]
    )
    for note in current_deployment_notes:
        lines.append(f"- {note}")
    if not current_deployment_notes:
        lines.append("- 当前报告未提供额外部署说明。")

    lines.extend(
        [
            "",
            "## 当前四卡结论",
            "",
        ]
    )

    current_best_2024 = best_row(new_2024)
    current_best_10k = best_row(new_10k)
    current_timeout_2024 = first_timeout_row(new_2024)
    current_timeout_10k = first_timeout_row(new_10k)
    lines.append(
        f"- `2024` 上下文最高成功吞吐出现在并发 `{current_best_2024['concurrency']}`，约 `{fmt_float(current_best_2024['successful_request_throughput_rps'])}` req/s，`{fmt_float(current_best_2024['total_token_throughput_tps'])}` tok/s。"
    )
    lines.append(
        f"- `10000` 上下文最高成功吞吐出现在并发 `{current_best_10k['concurrency']}`，约 `{fmt_float(current_best_10k['successful_request_throughput_rps'])}` req/s，`{fmt_float(current_best_10k['total_token_throughput_tps'])}` tok/s。"
    )
    lines.append(
        f"- `2024` 上下文首个出现 timeout 的并发点是 `{current_timeout_2024['concurrency']}`，timeout 比例 `{fmt_pct(current_timeout_2024['timeout_rate'])}`。"
        if current_timeout_2024
        else "- `2024` 上下文在本次并发范围内未出现 timeout。"
    )
    lines.append(
        f"- `10000` 上下文首个出现 timeout 的并发点是 `{current_timeout_10k['concurrency']}`，timeout 比例 `{fmt_pct(current_timeout_10k['timeout_rate'])}`。"
        if current_timeout_10k
        else "- `10000` 上下文在本次并发范围内未出现 timeout。"
    )
    lines.extend(
        [
            "",
            "## 当前四卡 2024 vs 10000",
            "",
            f"![]({current_compare_name})",
            "",
            "| 并发 | 2024 成功 | 2024 Timeout% | 2024 req/s | 2024 tok/s | 10000 成功 | 10000 Timeout% | 10000 req/s | 10000 tok/s |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    new_2024_map = index_by_concurrency(new_2024)
    new_10k_map = index_by_concurrency(new_10k)
    all_concurrency = sorted(set(new_2024_map) | set(new_10k_map))
    for concurrency in all_concurrency:
        row_2024 = new_2024_map.get(concurrency)
        row_10k = new_10k_map.get(concurrency)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(concurrency),
                    str(row_2024["success_count"]) if row_2024 else "N/A",
                    fmt_pct(row_2024["timeout_rate"]) if row_2024 else "N/A",
                    fmt_float(row_2024["successful_request_throughput_rps"]) if row_2024 else "N/A",
                    fmt_float(row_2024["total_token_throughput_tps"]) if row_2024 else "N/A",
                    str(row_10k["success_count"]) if row_10k else "N/A",
                    fmt_pct(row_10k["timeout_rate"]) if row_10k else "N/A",
                    fmt_float(row_10k["successful_request_throughput_rps"]) if row_10k else "N/A",
                    fmt_float(row_10k["total_token_throughput_tps"]) if row_10k else "N/A",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 历史 2 卡 vs 当前 4 卡: 2024 上下文",
            "",
            f"![]({hist_2024_name})",
            "",
            "| 并发 | 2卡 req/s | 4卡 req/s | req/s 变化 | 2卡 tok/s | 4卡 tok/s | tok/s 变化 | 2卡 Timeout% | 4卡 Timeout% |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in build_historical_table(old_2024, new_2024, "2024"):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["concurrency"]),
                    row["old_req_s"],
                    row["new_req_s"],
                    row["req_s_delta_pct"],
                    row["old_tok_s"],
                    row["new_tok_s"],
                    row["tok_s_delta_pct"],
                    row["old_timeout_pct"],
                    row["new_timeout_pct"],
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 历史 2 卡 vs 当前 4 卡: 10000 上下文",
            "",
            f"![]({hist_10k_name})",
            "",
            "| 并发 | 2卡 req/s | 4卡 req/s | req/s 变化 | 2卡 tok/s | 4卡 tok/s | tok/s 变化 | 2卡 Timeout% | 4卡 Timeout% |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in build_historical_table(old_10k, new_10k, "10000"):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["concurrency"]),
                    row["old_req_s"],
                    row["new_req_s"],
                    row["req_s_delta_pct"],
                    row["old_tok_s"],
                    row["new_tok_s"],
                    row["tok_s_delta_pct"],
                    row["old_timeout_pct"],
                    row["new_timeout_pct"],
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 原始产物",
            "",
            f"- 当前 2024 汇总: `results_4gpu_ctx2024/summary.csv`",
            f"- 当前 10000 汇总: `results_4gpu_ctx10k/summary.csv`",
            f"- 当前 2024 图表: `results_4gpu_ctx2024/benchmark.svg`",
            f"- 当前 10000 图表: `results_4gpu_ctx10k/benchmark.svg`",
            f"- 历史对比表: `historical_comparison.csv`",
            "",
        ]
    )

    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    old_2024_dir = Path(args.old_ctx2024)
    new_2024_dir = Path(args.new_ctx2024)
    old_10k_dir = Path(args.old_ctx10k)
    new_10k_dir = Path(args.new_ctx10k)

    old_2024 = normalize_rows(read_csv_rows(old_2024_dir / "summary.csv"))
    new_2024 = normalize_rows(read_csv_rows(new_2024_dir / "summary.csv"))
    old_10k = normalize_rows(read_csv_rows(old_10k_dir / "summary.csv"))
    new_10k = normalize_rows(read_csv_rows(new_10k_dir / "summary.csv"))

    meta_old_2024 = read_metadata(old_2024_dir / "metadata.json")
    meta_new_2024 = read_metadata(new_2024_dir / "metadata.json")
    meta_old_10k = read_metadata(old_10k_dir / "metadata.json")
    meta_new_10k = read_metadata(new_10k_dir / "metadata.json")
    meta_new_2024["env_label"] = meta_new_2024.get("env_label") or "/data2/lyq/conda-envs/sglang_qwen35_27b"

    build_dual_svg(
        out_dir / "comparison_4gpu_ctx2024_vs_ctx10k.svg",
        title="4 GPU Context Comparison",
        subtitle="Qwen3-32B on http://127.0.0.1:62274/v1/completions",
        rows_a=new_2024,
        label_a="4GPU 2024",
        rows_b=new_10k,
        label_b="4GPU 10000",
    )
    build_dual_svg(
        out_dir / "comparison_ctx2024_2gpu_vs_4gpu.svg",
        title="2024 Context: 2 GPU vs 4 GPU",
        subtitle="Historical baseline vs current deployment",
        rows_a=old_2024,
        label_a="2GPU history",
        rows_b=new_2024,
        label_b="4GPU current",
    )
    build_dual_svg(
        out_dir / "comparison_ctx10k_2gpu_vs_4gpu.svg",
        title="10000 Context: 2 GPU vs 4 GPU",
        subtitle="Historical baseline vs current deployment",
        rows_a=old_10k,
        label_a="2GPU history",
        rows_b=new_10k,
        label_b="4GPU current",
    )
    build_markdown(
        out_dir,
        meta_old_2024,
        old_2024,
        meta_new_2024,
        new_2024,
        meta_old_10k,
        old_10k,
        meta_new_10k,
        new_10k,
        args.historical_deployment_note,
        args.current_deployment_note,
    )


if __name__ == "__main__":
    main()
