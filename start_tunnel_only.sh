#!/bin/bash

# ================= 配置区 =================
LOG_DIR="./logs"
PID_FILE="./pids.ngrok"
NGROK_BIN="./ngrok"
PORT=8000
# 这里填入你刚才截图里获取的固定域名
STATIC_DOMAIN="pulplike-partingly-emilee.ngrok-free.dev"
NGROK_CONFIG="${NGROK_CONFIG:-$HOME/.config/ngrok/ngrok.yml}"
NGROK_AUTHTOKEN="${NGROK_AUTHTOKEN:-}"

# =========================================

mkdir -p "$LOG_DIR"

has_ngrok_auth() {
    [ -n "$NGROK_AUTHTOKEN" ] && return 0
    [ -f "$NGROK_CONFIG" ] && grep -Eq '^[[:space:]]*authtoken:[[:space:]]*[^[:space:]#]+' "$NGROK_CONFIG"
}

echo "🔍 检查隧道状态..."

# 检查是否已有隧道在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(grep "ngrok=" "$PID_FILE" | cut -d= -f2)

    # 检查进程是否存在
    if [ -n "$OLD_PID" ] && ps -p "$OLD_PID" > /dev/null; then
        echo "✅ Ngrok 正在运行 (PID: $OLD_PID)，无需重启。"
        echo "🌍 演示链接 (固定): https://$STATIC_DOMAIN"
        exit 0
    else
        echo "⚠️  PID 文件中有记录但进程不存在，准备重新启动。"
        # 清理旧的 PID 记录
        sed -i '/ngrok=/d' "$PID_FILE"
    fi
fi

echo "🚀 启动 Ngrok 固定隧道..."

# 检查命令是否存在
if command -v "$NGROK_BIN" > /dev/null 2>&1; then
    if ! has_ngrok_auth; then
        echo "❌ 未检测到 ngrok authtoken，进程会立即退出。"
        echo "请先执行以下任一方式后再重试："
        echo "1. ./ngrok config add-authtoken <你的token>"
        echo "2. export NGROK_AUTHTOKEN=<你的token>"
        echo "默认配置文件路径: $NGROK_CONFIG"
        exit 1
    fi

    # 启动 Ngrok，绑定本地端口和固定域名
    : > "$LOG_DIR/ngrok.log"

    if [ -n "$NGROK_AUTHTOKEN" ]; then
        nohup "$NGROK_BIN" http "$PORT" --domain="$STATIC_DOMAIN" --log=stdout --authtoken="$NGROK_AUTHTOKEN" > "$LOG_DIR/ngrok.log" 2>&1 &
    else
        nohup "$NGROK_BIN" http "$PORT" --domain="$STATIC_DOMAIN" --log=stdout > "$LOG_DIR/ngrok.log" 2>&1 &
    fi

    NEW_PID=$!
    echo "✅ Ngrok PID: $NEW_PID"

    # 存入/追加 PID 文件
    if [ ! -f "$PID_FILE" ]; then
        echo "ngrok=$NEW_PID" > "$PID_FILE"
    else
        # 确保不重复写入，先清理
        sed -i '/ngrok=/d' "$PID_FILE"
        echo "ngrok=$NEW_PID" >> "$PID_FILE"
    fi

    echo "⏳ 正在建立连接 (3秒)..."
    sleep 3

    # 检查进程是否仍然存活，避免误报“启动成功”
    if ! ps -p "$NEW_PID" > /dev/null; then
        echo "❌ Ngrok 启动失败，进程已退出。"
        echo "最近日志："
        tail -n 20 "$LOG_DIR/ngrok.log"
        sed -i '/ngrok=/d' "$PID_FILE"
        exit 1
    fi

    # 简单检查日志看有没有报错
    if grep -Eqi 'lvl=eror|^ERROR:' "$LOG_DIR/ngrok.log"; then
        echo "❌ 启动似乎遇到了问题，请检查 logs/ngrok.log"
        grep -Ei 'lvl=eror|^ERROR:' "$LOG_DIR/ngrok.log" | tail -n 5
        exit 1
    fi

    echo "=================================================="
    echo "🎉 隧道启动成功！"
    echo "🌍 你的甲方固定演示链接:"
    echo -e "\033[32mhttps://$STATIC_DOMAIN\033[0m"
    echo "=================================================="
else
    echo "❌ 错误: 找不到命令 '$NGROK_BIN'。请确保已安装并将其放入 /usr/local/bin"
    exit 1
fi
