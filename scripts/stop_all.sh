#!/bin/bash
# 停止所有服务（后端 + 前端 + MinIO）
# 不影响 vLLM（独立项目管理）

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/data/pids.server"

echo "停止所有服务..."

# 从 PID 文件停止
if [ -f "$PID_FILE" ]; then
  while IFS='=' read -r name pid; do
    if [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
      kill "$pid" 2>/dev/null || true
      echo "已停止 $name (PID: $pid)"
    fi
  done < "$PID_FILE"
  rm -f "$PID_FILE"
fi

# 兜底清理
pkill -f "uvicorn app:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
pkill -f "minio server" 2>/dev/null || true

echo "所有服务已停止"
