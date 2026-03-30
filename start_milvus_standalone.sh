#!/bin/bash
# Milvus Standalone 启动脚本 (基于 milvus pypi 包)

MILVUS_DIR="/data1/dlx/projects/xintuoyin/milvus"
DATA_DIR="$MILVUS_DIR/data"
LOG_FILE="$MILVUS_DIR/milvus_server.log"

mkdir -p "$DATA_DIR"

echo "正在启动 Milvus Standalone 服务..."
# 使用 pixi 环境中的 milvus-server 命令启动
# 指定监听端口为 19530
nohup pixi run milvus-server --data "$DATA_DIR" > "$LOG_FILE" 2>&1 &

echo "Milvus 正在后台启动，日志请查看: $LOG_FILE"
echo "API 地址: http://127.0.0.1:19530"
