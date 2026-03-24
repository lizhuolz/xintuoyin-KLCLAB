#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$ROOT_DIR/pids.server"
PIXI_TOML="$ROOT_DIR/pixi.toml"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5174}"
CUDA_VISIBLE_DEVICES_VALUE="${CUDA_VISIBLE_DEVICES:-0,3}"

mkdir -p "$LOG_DIR"

if ! command -v pixi >/dev/null 2>&1; then
    echo "❌ 未找到 pixi，请先安装 pixi。" >&2
    exit 1
fi

if [ ! -f "$PIXI_TOML" ]; then
    echo "❌ 未找到 $PIXI_TOML，无法使用 pixi 环境启动后端。" >&2
    exit 1
fi

echo "🔄 正在重启业务服务 (Backend + Frontend)..."
echo "🛑 (隧道 Tunnel 将保持运行)"

# 1. 停止旧的业务进程 (保留 tunnel)
if [ -f "$PID_FILE" ]; then
    BACKEND_PID="$(grep '^backend=' "$PID_FILE" | cut -d= -f2 || true)"
    FRONTEND_PID="$(grep '^frontend=' "$PID_FILE" | cut -d= -f2 || true)"

    if [ -n "$BACKEND_PID" ]; then
        echo "   停止旧后端 (PID: $BACKEND_PID)..."
        kill -9 "$BACKEND_PID" 2>/dev/null || true
        pkill -f "gunicorn.*app:app" 2>/dev/null || true
        pkill -f "python -m uvicorn app:app" 2>/dev/null || true
        pkill -f "pixi run.*uvicorn app:app" 2>/dev/null || true
    fi

    if [ -n "$FRONTEND_PID" ]; then
        echo "   停止旧前端 (PID: $FRONTEND_PID)..."
        kill -9 "$FRONTEND_PID" 2>/dev/null || true
    fi
else
    echo "⚠️  PID 文件不存在，假定无服务运行。"
fi

# 2. 启动后端
# 关键点：pixi.toml 在仓库根目录，因此不能像旧脚本那样先 cd backend 再直接 pixi run。
# 这里通过 pixi run bash -lc 在 pixi 环境里执行，并在子 shell 中切到 backend 后加载配置。
echo "🚀 [1/2] 启动后端 (使用 Pixi 环境)..."
BACKEND_CMD="cd '$BACKEND_DIR' && source script/setting.sh && source script/env.sh && exec env PYTHONUNBUFFERED=1 CUDA_VISIBLE_DEVICES='$CUDA_VISIBLE_DEVICES_VALUE' python -m uvicorn app:app --host 0.0.0.0 --port '$BACKEND_PORT'"
setsid bash -lc "cd '$ROOT_DIR' && pixi run bash -lc \"$BACKEND_CMD\"" >> "$LOG_DIR/backend.log" 2>&1 < /dev/null &
NEW_BACKEND_PID=$!
echo "✅ 后端 PID: $NEW_BACKEND_PID"

# 3. 启动前端
# 前端当前仍按现有方式使用 npm；如果后续前端也迁移到 pixi，再单独调整。
echo "🚀 [2/2] 启动前端..."
setsid bash -lc "cd '$FRONTEND_DIR' && exec npm run dev -- --host '$FRONTEND_HOST' --port '$FRONTEND_PORT'" >> "$LOG_DIR/frontend.log" 2>&1 < /dev/null &
NEW_FRONTEND_PID=$!
echo "✅ 前端 PID: $NEW_FRONTEND_PID"

# 4. 更新 PID 文件 (保留 tunnel 行)
TUNNEL_LINE=""
if [ -f "$PID_FILE" ]; then
    TUNNEL_LINE="$(grep '^tunnel=' "$PID_FILE" || true)"
fi

{
    echo "backend=$NEW_BACKEND_PID"
    echo "frontend=$NEW_FRONTEND_PID"
    if [ -n "$TUNNEL_LINE" ]; then
        echo "$TUNNEL_LINE"
    fi
} > "$PID_FILE"

if [ -n "$TUNNEL_LINE" ]; then
    echo "🔗 隧道保持活跃。"
else
    echo "⚠️  警告: 未检测到隧道进程记录。请运行 ./start_tunnel_only.sh 启动穿透。"
fi

echo "🎉 服务重启完成！"
echo "📊 查看后端日志: tail -f $LOG_DIR/backend.log"
echo "📊 查看前端日志: tail -f $LOG_DIR/frontend.log"
