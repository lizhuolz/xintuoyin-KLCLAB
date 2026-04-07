#!/usr/bin/env python3
import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate context comparison report for one deployment.")
    parser.add_argument("--ctx2024", required=True)
    parser.add_argument("--ctx10k", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--deployment-note", action="append", default=[])
    return parser.parse_args()


def read_metadata(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def to_float(value: str | None) -> float | None:
    if value in (None, "", "nan"):
        return None
    return float(value)


def to_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    return int(float(value))


def normalize_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            "concurrency": to_int(row["concurrency"]),
            "request_count": to_int(row["request_count"]),
            "success_count": to_int(row["success_count"]),
            "timeout_count": to_int(row["timeout_count"]),
            "timeout_rate": to_float(row["timeout_rate"]),
            "mean_latency_ms": to_float(row["mean_latency_ms"]),
            "p99_latency_ms": to_float(row["p99_latency_ms"]),
            "successful_request_throughput_rps": to_float(row["successful_request_throughput_rps"]),
            "total_token_throughput_tps": to_float(row["total_token_throughput_tps"]),
        }
        for row in rows
    ]


def fmt_float(value: float | None, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return f"{value:.{digits}f}"


def fmt_pct(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.{digits}f}%"


def index_by_concurrency(rows: list[dict]) -> dict[int, dict]:
    return {row["concurrency"]: row for row in rows}


def best_row(rows: list[dict]) -> dict:
    return max(rows, key=lambda row: row["successful_request_throughput_rps"] or 0.0)


def first_timeout_row(rows: list[dict]) -> dict | None:
    timed = [row for row in rows if (row["timeout_rate"] or 0.0) > 0]
    return min(timed, key=lambda row: row["concurrency"]) if timed else None


def render_line_panel(x: int, y: int, width: int, height: int, title: str, y_label: str, xs: list[int], series: list[tuple[str, list[float | None], str]]) -> str:
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
            path = " ".join([f"M {valid_points[0][0]:.1f} {valid_points[0][1]:.1f}"] + [f"L {px:.1f} {py:.1f}" for px, py in valid_points[1:]])
            parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="3"/>')
            for px, py in valid_points:
                parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{color}"/>')
    return "\n".join(parts)


def build_svg(path: Path, rows_2024: list[dict], rows_10k: list[dict], subtitle: str) -> None:
    xs = sorted({row["concurrency"] for row in rows_2024} | {row["concurrency"] for row in rows_10k})
    map_2024 = index_by_concurrency(rows_2024)
    map_10k = index_by_concurrency(rows_10k)
    width, height = 1360, 900
    panel_w, panel_h = 590, 320
    left_x, right_x, top_y, bottom_y = 70, 690, 90, 470

    def values(rows_map: dict[int, dict], key: str) -> list[float | None]:
        return [rows_map.get(x, {}).get(key) for x in xs]

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#f7fafc"/>
<text x="70" y="40" font-size="28" font-weight="700" fill="#102a43">Qwen3.5-27B A800x2 Context Comparison</text>
<text x="70" y="64" font-size="13" fill="#486581">{subtitle}</text>
{render_line_panel(left_x, top_y, panel_w, panel_h, "Successful req/s", "req/s", xs, [("2024", values(map_2024, "successful_request_throughput_rps"), "#0b6e4f"), ("10000", values(map_10k, "successful_request_throughput_rps"), "#c44900")])}
{render_line_panel(right_x, top_y, panel_w, panel_h, "Total tok/s", "tok/s", xs, [("2024", values(map_2024, "total_token_throughput_tps"), "#0b6e4f"), ("10000", values(map_10k, "total_token_throughput_tps"), "#c44900")])}
{render_line_panel(left_x, bottom_y, panel_w, panel_h, "Mean Latency", "ms", xs, [("2024", values(map_2024, "mean_latency_ms"), "#0b6e4f"), ("10000", values(map_10k, "mean_latency_ms"), "#c44900")])}
{render_line_panel(right_x, bottom_y, panel_w, panel_h, "Timeout Ratio", "%", xs, [("2024", [None if v is None else v * 100 for v in values(map_2024, "timeout_rate")], "#0b6e4f"), ("10000", [None if v is None else v * 100 for v in values(map_10k, "timeout_rate")], "#c44900")])}
</svg>
"""
    path.write_text(svg, encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dir_2024 = Path(args.ctx2024)
    dir_10k = Path(args.ctx10k)
    meta_2024 = read_metadata(dir_2024 / "metadata.json")
    meta_10k = read_metadata(dir_10k / "metadata.json")
    rows_2024 = normalize_rows(read_csv_rows(dir_2024 / "summary.csv"))
    rows_10k = normalize_rows(read_csv_rows(dir_10k / "summary.csv"))

    subtitle = f"Endpoint: {meta_2024['base_url']}{meta_2024['endpoint']} | Model: {meta_2024['model_name']}"
    build_svg(out_dir / "comparison_ctx2024_vs_ctx10k.svg", rows_2024, rows_10k, subtitle)

    best_2024 = best_row(rows_2024)
    best_10k = best_row(rows_10k)
    timeout_2024 = first_timeout_row(rows_2024)
    timeout_10k = first_timeout_row(rows_10k)
    map_2024 = index_by_concurrency(rows_2024)
    map_10k = index_by_concurrency(rows_10k)
    all_concurrency = sorted(set(map_2024) | set(map_10k))

    lines = [
        "# Qwen3.5-27B A800 双卡压测报告",
        "",
        f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 接口: `{meta_2024['base_url']}{meta_2024['endpoint']}`",
        f"- 模型: `{meta_2024['model_name']}`",
        f"- 环境标记: `{meta_2024.get('env_label', 'unknown')}`",
        f"- `2024` 输入实际约 `{meta_2024['prompt_tokens_actual']}` token，输出 `1024` token。",
        f"- `10000` 输入实际约 `{meta_10k['prompt_tokens_actual']}` token，输出 `1024` token。",
        f"- 并发档位: `{' '.join(map(str, meta_2024['concurrencies']))}`",
        f"- 客户端 timeout: `{meta_2024['timeout_seconds']}s`",
        "",
        "## 部署信息",
        "",
        "- 来源: `backend/script/setting.sh`",
        "- DB/Chat Base URL: `http://10.249.40.204:62272/v1`",
        "- 服务模型: `Qwen3.5-27B`",
        "- 硬件说明: 用户指定为 `A800 2卡`",
    ]
    for note in args.deployment_note:
        lines.append(f"- {note}")
    lines.extend(
        [
            "",
            "## 核心结论",
            "",
            f"- `2024` 最佳吞吐出现在并发 `{best_2024['concurrency']}`，约 `{fmt_float(best_2024['successful_request_throughput_rps'])}` req/s，`{fmt_float(best_2024['total_token_throughput_tps'])}` tok/s。",
            f"- `10000` 最佳吞吐出现在并发 `{best_10k['concurrency']}`，约 `{fmt_float(best_10k['successful_request_throughput_rps'])}` req/s，`{fmt_float(best_10k['total_token_throughput_tps'])}` tok/s。",
            (
                f"- `2024` 首个出现 timeout 的并发点是 `{timeout_2024['concurrency']}`，timeout 比例 `{fmt_pct(timeout_2024['timeout_rate'])}`。"
                if timeout_2024
                else "- `2024` 在本次并发范围内未出现 timeout。"
            ),
            (
                f"- `10000` 首个出现 timeout 的并发点是 `{timeout_10k['concurrency']}`，timeout 比例 `{fmt_pct(timeout_10k['timeout_rate'])}`。"
                if timeout_10k
                else "- `10000` 在本次并发范围内未出现 timeout。"
            ),
            "",
            "## 对比图",
            "",
            "![](comparison_ctx2024_vs_ctx10k.svg)",
            "",
            "## 对比表",
            "",
            "| 并发 | 2024 成功 | 2024 Timeout% | 2024 Mean(ms) | 2024 req/s | 2024 tok/s | 10000 成功 | 10000 Timeout% | 10000 Mean(ms) | 10000 req/s | 10000 tok/s |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    rows_csv = []
    for concurrency in all_concurrency:
        row_2024 = map_2024.get(concurrency)
        row_10k = map_10k.get(concurrency)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(concurrency),
                    str(row_2024["success_count"]) if row_2024 else "N/A",
                    fmt_pct(row_2024["timeout_rate"]) if row_2024 else "N/A",
                    fmt_float(row_2024["mean_latency_ms"]) if row_2024 else "N/A",
                    fmt_float(row_2024["successful_request_throughput_rps"]) if row_2024 else "N/A",
                    fmt_float(row_2024["total_token_throughput_tps"]) if row_2024 else "N/A",
                    str(row_10k["success_count"]) if row_10k else "N/A",
                    fmt_pct(row_10k["timeout_rate"]) if row_10k else "N/A",
                    fmt_float(row_10k["mean_latency_ms"]) if row_10k else "N/A",
                    fmt_float(row_10k["successful_request_throughput_rps"]) if row_10k else "N/A",
                    fmt_float(row_10k["total_token_throughput_tps"]) if row_10k else "N/A",
                ]
            )
            + " |"
        )
        rows_csv.append(
            {
                "concurrency": concurrency,
                "ctx2024_success_count": row_2024["success_count"] if row_2024 else "",
                "ctx2024_timeout_pct": fmt_pct(row_2024["timeout_rate"]) if row_2024 else "",
                "ctx2024_mean_latency_ms": fmt_float(row_2024["mean_latency_ms"]) if row_2024 else "",
                "ctx2024_req_s": fmt_float(row_2024["successful_request_throughput_rps"]) if row_2024 else "",
                "ctx2024_tok_s": fmt_float(row_2024["total_token_throughput_tps"]) if row_2024 else "",
                "ctx10k_success_count": row_10k["success_count"] if row_10k else "",
                "ctx10k_timeout_pct": fmt_pct(row_10k["timeout_rate"]) if row_10k else "",
                "ctx10k_mean_latency_ms": fmt_float(row_10k["mean_latency_ms"]) if row_10k else "",
                "ctx10k_req_s": fmt_float(row_10k["successful_request_throughput_rps"]) if row_10k else "",
                "ctx10k_tok_s": fmt_float(row_10k["total_token_throughput_tps"]) if row_10k else "",
            }
        )

    lines.extend(
        [
            "",
            "## 原始产物",
            "",
            f"- `2024` 汇总: `{dir_2024}/summary.csv`",
            f"- `2024` 单组报告: `{dir_2024}/report.md`",
            f"- `10000` 汇总: `{dir_10k}/summary.csv`",
            f"- `10000` 单组报告: `{dir_10k}/report.md`",
            f"- 对比表 CSV: `{out_dir / 'comparison.csv'}`",
            "",
        ]
    )

    with (out_dir / "comparison.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows_csv[0].keys()))
        writer.writeheader()
        writer.writerows(rows_csv)

    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
