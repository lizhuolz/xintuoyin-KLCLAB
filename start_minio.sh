#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/runtime_paths.sh"

MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin}"
MINIO_API_PORT="${MINIO_API_PORT:-9000}"
MINIO_CONSOLE_PORT="${MINIO_CONSOLE_PORT:-9001}"
MINIO_BINARY_PATH="${MINIO_BINARY_PATH:-$XTY_MINIO_BIN_DIR/minio}"

mkdir -p "$XTY_MINIO_DATA_DIR" "$XTY_MINIO_BIN_DIR" "$XTY_MINIO_CONFIG_DIR"

if [ ! -x "$MINIO_BINARY_PATH" ]; then
    echo "未找到 MinIO 二进制: $MINIO_BINARY_PATH"
    echo "请先执行: ./setup_minio_env.sh"
    exit 1
fi

export MINIO_ROOT_USER
export MINIO_ROOT_PASSWORD
export MINIO_CONFIG_ENV_FILE="$XTY_MINIO_CONFIG_DIR/minio.env"

echo "启动 MinIO..."
echo "  binary : $MINIO_BINARY_PATH"
echo "  data   : $XTY_MINIO_DATA_DIR"
echo "  api    : http://127.0.0.1:$MINIO_API_PORT"
echo "  console: http://127.0.0.1:$MINIO_CONSOLE_PORT"

exec "$MINIO_BINARY_PATH" server "$XTY_MINIO_DATA_DIR" \
  --address ":$MINIO_API_PORT" \
  --console-address ":$MINIO_CONSOLE_PORT"
