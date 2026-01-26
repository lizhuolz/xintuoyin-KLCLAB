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
        kill $BACKEND_PID 2>/dev/null || true
    fi
    
    if [ -n "$FRONTEND_PID" ]; then
        echo "   停止旧前端 (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID 2>/dev/null || true
    fi
else
    echo "⚠️  PID 文件不存在，假定无服务运行。"
fi

# 2. 启动后端
echo "🚀 [1/2] 启动后端..."
cd backend || exit
source env.sh

# [修改点 1] 添加环境变量 PYTHONUNBUFFERED=1 消除缓冲延迟
# [修改点 2] 添加 --log-level info 显式指定级别
# [修改点 3] 使用 >> 进行追加写入，而不是覆盖
nohup env PYTHONUNBUFFERED=1 gunicorn -w 4 -k uvicorn.workers.UvicornWorker \
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
nohup npm run dev > ../$LOG_DIR/frontend.log 2>&1 &
NEW_FRONTEND_PID=$!
echo "✅ 前端 PID: $NEW_FRONTEND_PID"
cd ..

# 4. 更新 PID 文件 (保留 tunnel 行)
# 思路：读取旧文件的 tunnel 行（如果有），然后重写文件
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
