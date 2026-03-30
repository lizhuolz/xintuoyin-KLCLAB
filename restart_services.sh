#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT_DIR/runtime_paths.sh"

LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$ROOT_DIR/pids.server"
BACKEND_ROOT="$ROOT_DIR/backend"
FRONTEND_ROOT="$ROOT_DIR/frontend"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

mkdir -p "$LOG_DIR"

find_conda_sh() {
    if command -v conda >/dev/null 2>&1; then
        local conda_base
        conda_base="$(conda info --base 2>/dev/null || true)"
        if [ -n "$conda_base" ] && [ -f "$conda_base/etc/profile.d/conda.sh" ]; then
            echo "$conda_base/etc/profile.d/conda.sh"
            return
        fi
    fi
    if [ -n "${CONDA_EXE:-}" ] && [ -f "$(dirname "$(dirname "$CONDA_EXE")")/etc/profile.d/conda.sh" ]; then
        echo "$(dirname "$(dirname "$CONDA_EXE")")/etc/profile.d/conda.sh"
        return
    fi
    if command -v conda >/dev/null 2>&1; then
        local conda_bin
        conda_bin="$(command -v conda)"
        if [ -f "$(dirname "$(dirname "$conda_bin")")/etc/profile.d/conda.sh" ]; then
            echo "$(dirname "$(dirname "$conda_bin")")/etc/profile.d/conda.sh"
            return
        fi
    fi
    local candidates=(
        "$HOME/anaconda3/etc/profile.d/conda.sh"
        "$HOME/miniconda3/etc/profile.d/conda.sh"
        "/opt/conda/etc/profile.d/conda.sh"
    )
    local item
    for item in "${candidates[@]}"; do
        if [ -f "$item" ]; then
            echo "$item"
            return
        fi
    done
    return 1
}

CONDA_SH="$(find_conda_sh || true)"
if [ -z "$CONDA_SH" ]; then
    echo "未找到 conda.sh，请先安装 Conda 或设置 CONDA_EXE。"
    exit 1
fi

echo "🔄 正在重启业务服务 (Backend + Frontend)..."
echo "🛑 (隧道 Tunnel 将保持运行)"

if [ -f "$PID_FILE" ]; then
    BACKEND_PID="$(grep "backend=" "$PID_FILE" | cut -d= -f2 || true)"
    FRONTEND_PID="$(grep "frontend=" "$PID_FILE" | cut -d= -f2 || true)"

    if [ -n "${BACKEND_PID:-}" ]; then
        echo "   停止旧后端 (PID: $BACKEND_PID)..."
        kill -9 "$BACKEND_PID" 2>/dev/null || true
        pkill -f "gunicorn.*app:app" 2>/dev/null || true
        pkill -f "python -m uvicorn app:app" 2>/dev/null || true
    fi

    if [ -n "${FRONTEND_PID:-}" ]; then
        echo "   停止旧前端 (PID: $FRONTEND_PID)..."
        kill -9 "$FRONTEND_PID" 2>/dev/null || true
    fi
    pkill -f "vite --host" 2>/dev/null || true
    pkill -f "npm run dev -- --host" 2>/dev/null || true
else
    echo "⚠️  PID 文件不存在，假定无服务运行。"
fi

echo "🚀 [1/2] 启动后端 (使用 Conda $XTY_CONDA_ENV_NAME 环境)..."
cd "$BACKEND_ROOT"
BACKEND_CMD="cd '$BACKEND_ROOT' && source '$CONDA_SH' && conda activate '$XTY_CONDA_ENV_NAME' && source script/setting.sh && source script/env.sh && exec env PYTHONUNBUFFERED=1 python -m uvicorn app:app --host 0.0.0.0 --port '$BACKEND_PORT'"
setsid bash -lc "$BACKEND_CMD" >> "$LOG_DIR/backend.log" 2>&1 < /dev/null &
NEW_BACKEND_PID=$!
echo "✅ 后端 PID: $NEW_BACKEND_PID"
cd "$ROOT_DIR"

echo "🚀 [2/2] 启动前端..."
cd "$FRONTEND_ROOT"
nohup npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" > "$LOG_DIR/frontend.log" 2>&1 &
NEW_FRONTEND_PID=$!
echo "✅ 前端 PID: $NEW_FRONTEND_PID"
cd "$ROOT_DIR"

TUNNEL_LINE=""
if [ -f "$PID_FILE" ]; then
    TUNNEL_LINE="$(grep "tunnel=" "$PID_FILE" || true)"
fi

echo "backend=$NEW_BACKEND_PID" > "$PID_FILE"
echo "frontend=$NEW_FRONTEND_PID" >> "$PID_FILE"
if [ -n "$TUNNEL_LINE" ]; then
    echo "$TUNNEL_LINE" >> "$PID_FILE"
    echo "🔗 隧道保持活跃。"
else
    echo "⚠️  警告: 未检测到隧道进程记录。请运行 ./start_tunnel_only.sh 启动穿透。"
fi

echo "🎉 服务重启完成！"
echo "📊 查看后端日志: tail -f logs/backend.log"
