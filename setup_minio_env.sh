#!/bin/bash
# MinIO 设置脚本

MINIO_DIR="/data1/dlx/projects/xintuoyin/minio"
DATA_DIR="$MINIO_DIR/data"
BIN_DIR="$MINIO_DIR/bin"

mkdir -p "$DATA_DIR"
mkdir -p "$BIN_DIR"

echo "正在下载 MinIO 二进制文件..."
if [ ! -f "$BIN_DIR/minio" ]; then
    curl -L https://dl.min.io/server/minio/release/linux-amd64/minio -o "$BIN_DIR/minio"
    chmod +x "$BIN_DIR/minio"
fi

# 创建启动脚本
cat << 'EOF' > "$MINIO_DIR/start_minio.sh"
#!/bin/bash
export MINIO_ROOT_USER=minioadmin
export MINIO_ROOT_PASSWORD=minioadmin
# 注意：生产环境建议修改上述密码

/data1/dlx/projects/xintuoyin/minio/bin/minio server /data1/dlx/projects/xintuoyin/minio/data --address ":9000" --console-address ":9001"
EOF

chmod +x "$MINIO_DIR/start_minio.sh"

echo "MinIO 环境准备就绪。"
echo "启动脚本: $MINIO_DIR/start_minio.sh"
echo "数据目录: $DATA_DIR"
echo "API 地址: http://127.0.0.1:9000"
echo "控制台地址: http://127.0.0.1:9001"
