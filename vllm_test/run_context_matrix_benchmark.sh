#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

CONDA_SH="${CONDA_SH:-/home/lyq/anaconda3/etc/profile.d/conda.sh}"
CONDA_ENV="${CONDA_ENV:-xtyAgent}"
BASE_URL="${BASE_URL:-http://10.249.40.204:62272}"
ENDPOINT="${ENDPOINT:-/v1/completions}"
MODEL_NAME="${MODEL_NAME:-Qwen3.5-27B}"
MODEL_PATH="${MODEL_PATH:-/data2/lyq/models/Qwen3.5-27B}"
TOKENIZER_PATH="${TOKENIZER_PATH:-${MODEL_PATH}}"
OUTPUT_DIR="${OUTPUT_DIR:-vllm_test/results_ctx_matrix_20260410}"
OUTPUT_LEN="${OUTPUT_LEN:-1024}"
TIMEOUT="${TIMEOUT:-180}"
MIN_REQUESTS="${MIN_REQUESTS:-10}"
CONTEXTS="${CONTEXTS:-4096 8192 16384 32768 50000}"
CONCURRENCIES="${CONCURRENCIES:-10 40 80 120 160 200 300 400}"

mkdir -p "${OUTPUT_DIR}/contexts" "${OUTPUT_DIR}/logs"

source "${CONDA_SH}"
conda activate "${CONDA_ENV}"

echo "Checking ${BASE_URL}/v1/models ..."
curl -fsS --max-time 15 "${BASE_URL}/v1/models" | tee "${OUTPUT_DIR}/models.json" >/dev/null

for context in ${CONTEXTS}; do
  context_dir="${OUTPUT_DIR}/contexts/ctx_${context}"
  echo "Running context=${context}, concurrencies=${CONCURRENCIES}"
  python vllm_test/benchmark_vllm.py \
    --base-url "${BASE_URL}" \
    --endpoint "${ENDPOINT}" \
    --model-name "${MODEL_NAME}" \
    --model-path "${MODEL_PATH}" \
    --tokenizer-path "${TOKENIZER_PATH}" \
    --input-len "${context}" \
    --output-len "${OUTPUT_LEN}" \
    --timeout "${TIMEOUT}" \
    --min-requests "${MIN_REQUESTS}" \
    --concurrencies ${CONCURRENCIES} \
    --output-dir "${context_dir}" \
    --env-label "context-matrix-${MODEL_NAME}" \
    2>&1 | tee "${OUTPUT_DIR}/logs/ctx_${context}.log"
done

python - <<'PY'
import csv
import json
import math
from datetime import datetime
from pathlib import Path

out = Path("vllm_test/results_ctx_matrix_20260410")
contexts_dir = out / "contexts"
rows = []
for ctx_dir in sorted(contexts_dir.glob("ctx_*"), key=lambda p: int(p.name.split("_", 1)[1])):
    ctx = int(ctx_dir.name.split("_", 1)[1])
    summary_path = ctx_dir / "summary.csv"
    if not summary_path.exists():
        continue
    with summary_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            merged = {"context_tokens": ctx, **row}
            rows.append(merged)

if not rows:
    raise SystemExit("No context benchmark summaries found.")

fieldnames = ["context_tokens"] + [name for name in rows[0] if name != "context_tokens"]
with (out / "matrix_summary.csv").open("w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

def fnum(value):
    if value in (None, "", "nan"):
        return None
    return float(value)

def fmt(value, digits=2, pct=False):
    number = fnum(value) if isinstance(value, str) else value
    if number is None or (isinstance(number, float) and math.isnan(number)):
        return "N/A"
    if pct:
        return f"{number * 100:.{digits}f}%"
    return f"{number:.{digits}f}"

def best_for_context(ctx):
    subset = [r for r in rows if int(r["context_tokens"]) == ctx]
    return max(subset, key=lambda r: fnum(r["successful_request_throughput_rps"]) or 0.0)

contexts = sorted({int(r["context_tokens"]) for r in rows})
concurrencies = sorted({int(r["concurrency"]) for r in rows})
by_key = {(int(r["context_tokens"]), int(r["concurrency"])): r for r in rows}
colors = ["#0f766e", "#ca8a04", "#c2410c", "#be123c", "#6d28d9", "#0369a1"]

def render_panel(x, y, w, h, title, y_label, metric, scale=1.0):
    inner_x, inner_y = x + 58, y + 38
    inner_w, inner_h = w - 92, h - 92
    values = []
    for ctx in contexts:
        for cc in concurrencies:
            row = by_key.get((ctx, cc))
            value = fnum(row.get(metric)) if row else None
            if value is not None:
                values.append(value * scale)
    y_max = max(values) if values else 1.0
    if y_max <= 0:
        y_max = 1.0
    y_max *= 1.12

    def xp(cc):
        if len(concurrencies) == 1:
            return inner_x + inner_w / 2
        return inner_x + (cc - min(concurrencies)) / (max(concurrencies) - min(concurrencies)) * inner_w

    def yp(value):
        return inner_y + inner_h - (value / y_max) * inner_h

    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="#fffaf0" stroke="#d6d3d1"/>',
        f'<text x="{x+20}" y="{y+28}" font-size="19" font-weight="700" fill="#1c1917">{title}</text>',
        f'<text x="{x+20}" y="{y+50}" font-size="12" fill="#78716c">{y_label}</text>',
    ]
    for idx in range(5):
        gy = inner_y + inner_h * idx / 4
        label = y_max - y_max * idx / 4
        parts.append(f'<line x1="{inner_x}" y1="{gy:.1f}" x2="{inner_x+inner_w}" y2="{gy:.1f}" stroke="#e7e5e4"/>')
        parts.append(f'<text x="{inner_x-8}" y="{gy+4:.1f}" text-anchor="end" font-size="10" fill="#78716c">{label:.1f}</text>')
    for cc in concurrencies:
        xx = xp(cc)
        parts.append(f'<line x1="{xx:.1f}" y1="{inner_y}" x2="{xx:.1f}" y2="{inner_y+inner_h}" stroke="#f5f5f4"/>')
        parts.append(f'<text x="{xx:.1f}" y="{inner_y+inner_h+20}" text-anchor="middle" font-size="10" fill="#78716c">{cc}</text>')

    for idx, ctx in enumerate(contexts):
        color = colors[idx % len(colors)]
        points = []
        for cc in concurrencies:
            row = by_key.get((ctx, cc))
            value = fnum(row.get(metric)) if row else None
            if value is not None:
                points.append((xp(cc), yp(value * scale)))
        ly = y + 26 + idx * 18
        lx = x + w - 150
        parts.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+18}" y2="{ly}" stroke="{color}" stroke-width="3"/>')
        parts.append(f'<text x="{lx+24}" y="{ly+4}" font-size="11" fill="#44403c">{ctx}</text>')
        if points:
            path = " ".join([f"M {points[0][0]:.1f} {points[0][1]:.1f}"] + [f"L {px:.1f} {py:.1f}" for px, py in points[1:]])
            parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="3"/>')
            for px, py in points:
                parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" fill="{color}"/>')
    parts.append(f'<text x="{inner_x+inner_w/2:.1f}" y="{inner_y+inner_h+42}" text-anchor="middle" font-size="12" fill="#57534e">Concurrency</text>')
    return "\n".join(parts)

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1560" height="1160" viewBox="0 0 1560 1160">
<rect width="100%" height="100%" fill="#f6f1e8"/>
<text x="70" y="48" font-size="34" font-family="Georgia, serif" font-weight="700" fill="#1c1917">VLLM Context Matrix Benchmark</text>
<text x="70" y="78" font-size="14" fill="#57534e">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | contexts: {" ".join(map(str, contexts))} | concurrencies: {" ".join(map(str, concurrencies))}</text>
{render_panel(70, 120, 680, 300, "Mean Latency", "Successful requests only, ms", "mean_latency_ms")}
{render_panel(810, 120, 680, 300, "P99 Latency", "Successful requests only, ms", "p99_latency_ms")}
{render_panel(70, 470, 680, 300, "Timeout Ratio", "Percent", "timeout_rate", 100.0)}
{render_panel(810, 470, 680, 300, "Successful req/s", "Completed requests per second", "successful_request_throughput_rps")}
{render_panel(70, 820, 680, 300, "Total token throughput", "Successful total tokens per second", "total_token_throughput_tps")}
<rect x="810" y="820" width="680" height="300" rx="18" fill="#fffaf0" stroke="#d6d3d1"/>
<text x="834" y="850" font-size="19" font-weight="700" fill="#1c1917">Best Stable Points</text>
'''
line_y = 884
for ctx in contexts:
    best = best_for_context(ctx)
    svg += f'<text x="834" y="{line_y}" font-size="13" fill="#44403c">ctx {ctx}: best concurrency {best["concurrency"]}, req/s {fmt(best["successful_request_throughput_rps"])}, timeout {fmt(best["timeout_rate"], pct=True)}</text>\n'
    line_y += 28
svg += "</svg>\n"
(out / "benchmark_matrix.svg").write_text(svg, encoding="utf-8")

lines = [
    "# VLLM 上下文/并发矩阵吞吐测试报告",
    "",
    f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    "- 模型: `Qwen3.5-27B`",
    "- 结果汇总: `matrix_summary.csv`",
    "- 图表: `benchmark_matrix.svg`",
    "",
    "## 图表",
    "",
    "![](benchmark_matrix.svg)",
    "",
    "## 各上下文最佳点",
    "",
]
for ctx in contexts:
    best = best_for_context(ctx)
    lines.append(f"- `{ctx}`: 并发 `{best['concurrency']}`, req/s `{fmt(best['successful_request_throughput_rps'])}`, timeout `{fmt(best['timeout_rate'], pct=True)}`, mean `{fmt(best['mean_latency_ms'])}` ms, P99 `{fmt(best['p99_latency_ms'])}` ms。")
lines.extend(["", "## 汇总表", "", "| Context | Concurrency | Success | Timeout% | Error% | Mean(ms) | P99(ms) | req/s | tok/s |", "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
for ctx in contexts:
    for cc in concurrencies:
        row = by_key.get((ctx, cc))
        if not row:
            continue
        lines.append(f"| {ctx} | {cc} | {row['success_count']}/{row['request_count']} | {fmt(row['timeout_rate'], pct=True)} | {fmt(row['error_rate'], pct=True)} | {fmt(row['mean_latency_ms'])} | {fmt(row['p99_latency_ms'])} | {fmt(row['successful_request_throughput_rps'])} | {fmt(row['total_token_throughput_tps'])} |")
(out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(out / "report.md")
print(out / "benchmark_matrix.svg")
print(out / "matrix_summary.csv")
PY
