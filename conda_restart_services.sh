#!/bin/bash

LOG_DIR="./logs"
PID_FILE="./pids.server"
CONDA_ENV_NAME="xtyAgent"
CONDA_BASE_DEFAULT="/home/lyq/anaconda3"
PREFERRED_BACKEND_PORT="${BACKEND_PORT:-8069}"
PROJECT_ROOT="$(pwd)"

find_available_port() {
    python3 - "$1" <<'PY'
import socket
import sys
start = int(sys.argv[1])
for port in range(start, start + 20):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        sock.close()
        continue
    sock.close()
    print(port)
    raise SystemExit(0)
raise SystemExit(1)
PY
}

mkdir -p "$LOG_DIR"
: > "$LOG_DIR/backend.log"

echo "🔄 正在重启业务服务 (Backend + Frontend)..."
echo "🛑 (隧道 Tunnel 将保持运行)"

if [ -f "$PID_FILE" ]; then
    BACKEND_PID=$(grep "backend=" "$PID_FILE" | cut -d= -f2)
    FRONTEND_PID=$(grep "frontend=" "$PID_FILE" | cut -d= -f2)

    if [ -n "$BACKEND_PID" ]; then
        echo "   停止旧后端 (PID: $BACKEND_PID)..."
        kill -9 "$BACKEND_PID" 2>/dev/null || true
        pkill -f "gunicorn.*app:app" 2>/dev/null || true
        pkill -f "uvicorn.*app:app" 2>/dev/null || true
    fi

    if [ -n "$FRONTEND_PID" ]; then
        echo "   停止旧前端 (PID: $FRONTEND_PID)..."
        kill -9 "$FRONTEND_PID" 2>/dev/null || true
    fi
else
    echo "⚠️  PID 文件不存在，假定无服务运行。"
fi

if command -v conda >/dev/null 2>&1; then
    CONDA_BASE=$(conda info --base 2>/dev/null)
fi
CONDA_BASE=${CONDA_BASE:-$CONDA_BASE_DEFAULT}
CONDA_SH="$CONDA_BASE/etc/profile.d/conda.sh"

if [ ! -f "$CONDA_SH" ]; then
    echo "❌ 未找到 conda.sh: $CONDA_SH"
    exit 1
fi

# shellcheck disable=SC1090
source "$CONDA_SH"
if ! conda activate "$CONDA_ENV_NAME"; then
    echo "❌ 无法激活 Conda 环境: $CONDA_ENV_NAME"
    exit 1
fi

echo "✅ 已激活 Conda 环境: $CONDA_ENV_NAME"

BACKEND_PORT=$(find_available_port "$PREFERRED_BACKEND_PORT")
if [ -z "$BACKEND_PORT" ]; then
    echo "❌ 未找到可用后端端口"
    exit 1
fi
if [ "$BACKEND_PORT" != "$PREFERRED_BACKEND_PORT" ]; then
    echo "⚠️  端口 $PREFERRED_BACKEND_PORT 已被占用，回退使用端口 $BACKEND_PORT"
fi
export VITE_BACKEND_PORT="$BACKEND_PORT"

echo "🚀 [1/2] 启动后端..."
BACKEND_BOOTSTRAP="source '$CONDA_SH' && conda activate '$CONDA_ENV_NAME' && cd '$PROJECT_ROOT/backend' && source script/setting.sh && source script/env.sh"
if command -v gunicorn >/dev/null 2>&1; then
    echo "   使用 gunicorn 启动后端 (端口: $BACKEND_PORT)"
    BACKEND_RUN="$BACKEND_BOOTSTRAP && exec env PYTHONUNBUFFERED=1 CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-4,5} gunicorn -w 2 -k uvicorn.workers.UvicornWorker --log-level info --access-logfile - --error-logfile - --capture-output -b 0.0.0.0:$BACKEND_PORT app:app"
else
    echo "   ⚠️  gunicorn 未安装，回退为 uvicorn (端口: $BACKEND_PORT)"
    BACKEND_RUN="$BACKEND_BOOTSTRAP && exec env PYTHONUNBUFFERED=1 CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-4,5} python -m uvicorn app:app --host 0.0.0.0 --port $BACKEND_PORT"
fi
nohup setsid bash -lc "$BACKEND_RUN" >> "$LOG_DIR/backend.log" 2>&1 < /dev/null &
NEW_BACKEND_PID=$!
sleep 2
if ! kill -0 "$NEW_BACKEND_PID" 2>/dev/null; then
    echo "❌ 后端进程启动后立即退出，请检查日志: $LOG_DIR/backend.log"
    tail -n 80 "$LOG_DIR/backend.log" 2>/dev/null || true
    exit 1
fi
echo "✅ 后端 PID: $NEW_BACKEND_PID"

echo "🚀 [2/2] 启动前端..."
cd frontend || exit 1
nohup npm run dev > ../$LOG_DIR/frontend.log 2>&1 &
NEW_FRONTEND_PID=$!
echo "✅ 前端 PID: $NEW_FRONTEND_PID"
cd ..

TUNNEL_LINE=""
if [ -f "$PID_FILE" ]; then
    TUNNEL_LINE=$(grep "tunnel=" "$PID_FILE")
fi

echo "backend=$NEW_BACKEND_PID" > "$PID_FILE"
echo "frontend=$NEW_FRONTEND_PID" >> "$PID_FILE"
echo "backend_port=$BACKEND_PORT" >> "$PID_FILE"
if [ -n "$TUNNEL_LINE" ]; then
    echo "$TUNNEL_LINE" >> "$PID_FILE"
    echo "🔗 隧道保持活跃。"
else
    echo "⚠️  警告: 未检测到隧道进程记录。请运行 ./start_tunnel_only.sh 启动穿透。"
fi

echo "🎉 服务重启完成！"
echo "📊 后端地址: http://127.0.0.1:$BACKEND_PORT"
echo "📊 查看后端日志: tail -f logs/backend.log"
