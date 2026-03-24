#!/bin/bash

# ================= 配置区 =================
LOG_DIR="./logs"
PID_FILE="./pids.ngork"
NGROK_BIN="./ngrok"  
PORT=5173
# 这里填入你刚才截图里获取的固定域名
STATIC_DOMAIN="pulplike-partingly-emilee.ngrok-free.dev" 

# =========================================

mkdir -p $LOG_DIR

echo "🔍 检查隧道状态..."

# 检查是否已有隧道在运行
if [ -f $PID_FILE ]; then
    OLD_PID=$(grep "ngrok=" $PID_FILE | cut -d= -f2)
    
    # 检查进程是否存在
    if [ -n "$OLD_PID" ] && ps -p $OLD_PID > /dev/null; then
        echo "✅ Ngrok 正在运行 (PID: $OLD_PID)，无需重启。"
        echo "🌍 演示链接 (固定): https://$STATIC_DOMAIN"
        exit 0
    else
        echo "⚠️  PID文件中有记录但进程不存在，准备重新启动。"
        # 清理旧的 PID 记录
        sed -i '/ngrok=/d' $PID_FILE
    fi
fi

echo "🚀 启动 Ngrok 固定隧道..."

# 检查命令是否存在
if command -v $NGROK_BIN &> /dev/null; then
    # 启动 Ngrok，绑定本地端口和固定域名
    # 注意：如果不加 --log=stdout，ngrok 有时在后台不会输出标准日志
    nohup $NGROK_BIN http $PORT --domain=$STATIC_DOMAIN --log=stdout > $LOG_DIR/ngrok.log 2>&1 &
    
    NEW_PID=$!
    echo "✅ Ngrok PID: $NEW_PID"
    
    # 存入/追加 PID 文件
    if [ ! -f $PID_FILE ]; then
        echo "ngrok=$NEW_PID" > $PID_FILE
    else
        # 确保不重复写入，先清理
        sed -i '/ngrok=/d' $PID_FILE
        echo "ngrok=$NEW_PID" >> $PID_FILE
    fi

    echo "⏳ 正在建立连接 (3秒)..."
    sleep 3

    # 简单检查日志看有没有报错
    if grep -q "EROR" $LOG_DIR/ngrok.log; then
        echo "❌ 启动似乎遇到了问题，请检查 logs/ngrok.log"
        grep "EROR" $LOG_DIR/ngrok.log | tail -n 2
    else
        echo "=================================================="
        echo "🎉 隧道启动成功！"
        echo "🌍 你的甲方固定演示链接:"
        echo -e "\033[32mhttps://$STATIC_DOMAIN\033[0m"
        echo "=================================================="
    fi

else
    echo "❌ 错误: 找不到命令 '$NGROK_BIN'。请确保已安装并将其放入 /usr/local/bin"
fi