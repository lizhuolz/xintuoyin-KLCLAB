#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/runtime_paths.sh"

MINIO_BINARY_PATH="${MINIO_BINARY_PATH:-$XTY_MINIO_BIN_DIR/minio}"
MINIO_RELEASE_URL="${MINIO_RELEASE_URL:-https://dl.min.io/server/minio/release/linux-amd64/minio}"

mkdir -p "$XTY_MINIO_DATA_DIR" "$XTY_MINIO_BIN_DIR" "$XTY_MINIO_CONFIG_DIR"

echo "准备 MinIO 运行目录..."
echo "  root: $XTY_MINIO_ROOT"
echo "  data: $XTY_MINIO_DATA_DIR"
echo "  bin : $XTY_MINIO_BIN_DIR"

if [ ! -x "$MINIO_BINARY_PATH" ]; then
    echo "正在下载 MinIO 二进制文件..."
    curl -L "$MINIO_RELEASE_URL" -o "$MINIO_BINARY_PATH"
    chmod +x "$MINIO_BINARY_PATH"
else
    echo "MinIO 二进制已存在: $MINIO_BINARY_PATH"
fi

echo "MinIO 环境准备就绪。"
echo "启动命令: ./start_minio.sh"
echo "也可自定义目录:"
echo "  export XTY_MINIO_ROOT=/your/runtime/minio"
echo "  ./setup_minio_env.sh"
