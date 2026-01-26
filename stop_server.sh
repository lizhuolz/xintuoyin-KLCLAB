#!/bin/bash

PID_FILE="./pids.server"

if [ ! -f $PID_FILE ]; then
    echo "❌ 服务未运行 (找不到 PID 文件)。"
    exit 0
fi

echo "🛑 正在停止所有服务..."

# 循环读取 PID 文件并杀进程
while IFS='=' read -r name pid; do
    if [ -n "$pid" ]; then
        if ps -p $pid > /dev/null; then
            kill $pid
            echo "✅ 已停止 $name (PID: $pid)"
        else
            echo "⚠️  进程 $name (PID: $pid) 已不存在，跳过。"
        fi
    fi
done < "$PID_FILE"

rm $PID_FILE
echo "🧹 清理完成，端口已释放。"