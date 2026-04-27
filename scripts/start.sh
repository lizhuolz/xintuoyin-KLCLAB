#!/bin/bash
# 一键启动所有服务：MinIO -> 后端 -> 前端
# vLLM 需要单独启动：./scripts/start_vllm.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/data/logs"
PID_FILE="$ROOT_DIR/data/pids.server"
BACKEND_ROOT="$ROOT_DIR/backend"
FRONTEND_ROOT="$ROOT_DIR/frontend"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

mkdir -p "$LOG_DIR"

# 0. 停止旧进程
if [ -f "$PID_FILE" ]; then
  while IFS='=' read -r name pid; do
    if [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
      kill "$pid" 2>/dev/null || true
      echo "停止旧 $name (PID: $pid)"
    fi
  done < "$PID_FILE"
  rm -f "$PID_FILE"
fi
pkill -f "uvicorn app:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true

# 1. 启动 MinIO
echo "[1/3] 启动 MinIO..."
bash "$ROOT_DIR/scripts/start_minio.sh"

# 2. 检查 vLLM
echo "[2/3] 检查 vLLM..."
if curl -s --noproxy '*' --connect-timeout 3 "http://127.0.0.1:62272/v1/models" > /dev/null 2>&1; then
  echo "vLLM 已在运行"
else
  echo "警告: vLLM 未运行，请先执行 ./scripts/start_vllm.sh"
fi

# 3. 启动后端
echo "[3/3] 启动后端 + 前端..."

cd "$BACKEND_ROOT"
BACKEND_CMD="source script/setting.sh && export PYTHONUNBUFFERED=1 && exec pixi run --manifest-path '$ROOT_DIR/pixi.toml' python app.py"
setsid bash -c "$BACKEND_CMD" >> "$LOG_DIR/backend.log" 2>&1 < /dev/null &
BACKEND_PID=$!
echo "后端 PID: $BACKEND_PID (端口 $BACKEND_PORT)"
cd "$ROOT_DIR"

cd "$FRONTEND_ROOT"
nohup pixi run --manifest-path "$ROOT_DIR/pixi.toml" npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "前端 PID: $FRONTEND_PID (端口 $FRONTEND_PORT)"
cd "$ROOT_DIR"

# 写入 PID 文件
echo "backend=$BACKEND_PID" > "$PID_FILE"
echo "frontend=$FRONTEND_PID" >> "$PID_FILE"

echo ""
echo "============================="
echo "启动完成！"
echo "前端: http://localhost:$FRONTEND_PORT"
echo "后端: http://localhost:$BACKEND_PORT"
echo "日志: tail -f $LOG_DIR/backend.log"
echo "============================="
