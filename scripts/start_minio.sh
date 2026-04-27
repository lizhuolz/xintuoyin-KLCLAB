#!/bin/bash
# 启动 MinIO 对象存储服务

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MINIO_BIN="$ROOT_DIR/data/minio/bin/minio"
MINIO_DATA="$ROOT_DIR/data/minio/storage"
MINIO_LOG="$ROOT_DIR/data/logs/minio.log"
API_PORT=9000
CONSOLE_PORT=9001

mkdir -p "$MINIO_DATA" "$(dirname "$MINIO_LOG")"

# 下载 MinIO（如果不存在）
if [ ! -f "$MINIO_BIN" ]; then
  echo "下载 MinIO..."
  mkdir -p "$(dirname "$MINIO_BIN")"
  curl -fsSL https://dl.min.io/server/minio/release/linux-amd64/minio -o "$MINIO_BIN"
  chmod +x "$MINIO_BIN"
  echo "MinIO 下载完成"
fi

# 检查是否已在运行
if curl -s --noproxy '*' --connect-timeout 2 "http://127.0.0.1:${API_PORT}/minio/health/live" > /dev/null 2>&1; then
  echo "MinIO 已在运行 (API: ${API_PORT}, Console: ${CONSOLE_PORT})"
  exit 0
fi

echo "启动 MinIO (API: ${API_PORT}, Console: ${CONSOLE_PORT})..."
export MINIO_ROOT_USER=minioadmin
export MINIO_ROOT_PASSWORD=minioadmin

nohup "$MINIO_BIN" server "$MINIO_DATA" \
  --address ":${API_PORT}" \
  --console-address ":${CONSOLE_PORT}" \
  > "$MINIO_LOG" 2>&1 &

sleep 2
if curl -s --noproxy '*' --connect-timeout 3 "http://127.0.0.1:${API_PORT}/minio/health/live" > /dev/null 2>&1; then
  echo "MinIO 启动成功"
else
  echo "警告: MinIO 可能未启动成功，请检查日志: $MINIO_LOG"
fi
