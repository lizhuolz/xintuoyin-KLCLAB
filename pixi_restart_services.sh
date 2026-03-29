#!/bin/bash

# ================= 配置区 =================
LOG_DIR="./logs"
PID_FILE="./pids.server"
# =========================================

mkdir -p $LOG_DIR

echo "🔄 正在重启业务服务 (Backend + Frontend)..."
echo "🛑 (隧道 Tunnel 将保持运行)"

# 1. 停止旧的业务进程 (保留 tunnel)
if [ -f $PID_FILE ]; then
    BACKEND_PID=$(grep "backend=" $PID_FILE | cut -d= -f2)
    FRONTEND_PID=$(grep "frontend=" $PID_FILE | cut -d= -f2)
    
    if [ -n "$BACKEND_PID" ]; then
        echo "   停止旧后端 (PID: $BACKEND_PID)..."
        kill -9 $BACKEND_PID 2>/dev/null || true
        pkill -f "gunicorn.*app:app" 2>/dev/null || true
        pkill -f "python -m uvicorn app:app" 2>/dev/null || true
    fi
    
    if [ -n "$FRONTEND_PID" ]; then
        echo "   停止旧前端 (PID: $FRONTEND_PID)..."
        kill -9 $FRONTEND_PID 2>/dev/null || true
    fi
else
    echo "⚠️  PID 文件不存在，假定无服务运行。"
fi

# 2. 启动后端
echo "🚀 [1/2] 启动后端 (使用 Pixi 环境)..."
cd backend || exit

# 关键：通过独立 shell 加载后端配置并使用 pixi 运行
BACKEND_CMD="source script/setting.sh && source script/env.sh && export PYTHONUNBUFFERED=1 && exec pixi run python app.py"
setsid bash -c "$BACKEND_CMD" >> ../$LOG_DIR/backend.log 2>&1 < /dev/null &

NEW_BACKEND_PID=$!
echo "✅ 后端 PID: $NEW_BACKEND_PID"
cd ..

# 3. 启动前端
echo "🚀 [2/2] 启动前端..."
cd frontend || exit
# 同样建议使用 pixi run (如果前端也是 pixi 管理) 或直接 npm
nohup npm run dev > ../$LOG_DIR/frontend.log 2>&1 &
NEW_FRONTEND_PID=$!
echo "✅ 前端 PID: $NEW_FRONTEND_PID"
cd ..

# 4. 更新 PID 文件 (保留 tunnel 行)
TUNNEL_LINE=""
if [ -f $PID_FILE ]; then
    TUNNEL_LINE=$(grep "tunnel=" $PID_FILE)
fi

echo "backend=$NEW_BACKEND_PID" > $PID_FILE
echo "frontend=$NEW_FRONTEND_PID" >> $PID_FILE
if [ -n "$TUNNEL_LINE" ]; then
    echo "$TUNNEL_LINE" >> $PID_FILE
    echo "🔗 隧道保持活跃。"
else
    echo "⚠️  警告: 未检测到隧道进程记录。请运行 ./start_tunnel_only.sh 启动穿透。"
fi

echo "🎉 服务重启完成！"
echo "📊 查看后端日志: tail -f logs/backend.log"
