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
        # 使用 kill -9 确保彻底杀死可能卡住的 gunicorn 进程
        kill -9 $BACKEND_PID 2>/dev/null || true
        # 额外清理孤儿进程 (如果有)
        pkill -f "gunicorn.*app:app" 2>/dev/null || true
    fi
    
    if [ -n "$FRONTEND_PID" ]; then
        echo "   停止旧前端 (PID: $FRONTEND_PID)..."
        kill -9 $FRONTEND_PID 2>/dev/null || true
    fi
else
    echo "⚠️  PID 文件不存在，假定无服务运行。"
fi

# 2. 启动后端
echo "🚀 [1/2] 启动后端 (使用 Conda 环境: xtyAgent)..."
cd backend || exit

# 关键：加载配置
source script/setting.sh 2>/dev/null || echo "⚠️  Warning: script/setting.sh not found"
source script/env.sh 2>/dev/null || echo "⚠️  Warning: script/env.sh not found"


# 启动 gunicorn，移除原有的 pixi run，直接在 conda 环境中执行
nohup env CUDA_VISIBLE_DEVICE=5 gunicorn -w 2 -k uvicorn.workers.UvicornWorker \
    --log-level info \
    --access-logfile - --error-logfile - --capture-output \
    -b 0.0.0.0:8000 app:app \
    >> ../$LOG_DIR/backend.log 2>&1 &

NEW_BACKEND_PID=$!
echo "✅ 后端 PID: $NEW_BACKEND_PID"
cd ..

# 3. 启动前端
echo "🚀 [2/2] 启动前端..."
cd frontend || exit
# 注意：此时当前 shell 已经处于 xtyAgent 环境下。
# 如果 npm 也是通过该 conda 环境安装的，这里会直接使用环境内的 npm。
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