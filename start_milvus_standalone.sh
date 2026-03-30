#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/runtime_paths.sh"

MILVUS_PORT="${MILVUS_PORT:-19530}"

mkdir -p "$XTY_MILVUS_DATA_DIR" "$(dirname "$XTY_MILVUS_LOG_FILE")"

echo "正在启动 Milvus Standalone 服务..."
echo "  data: $XTY_MILVUS_DATA_DIR"
echo "  log : $XTY_MILVUS_LOG_FILE"
echo "  port: $MILVUS_PORT"

nohup pixi run milvus-server --data "$XTY_MILVUS_DATA_DIR" > "$XTY_MILVUS_LOG_FILE" 2>&1 &

echo "Milvus 正在后台启动，日志请查看: $XTY_MILVUS_LOG_FILE"
echo "API 地址: http://127.0.0.1:$MILVUS_PORT"
