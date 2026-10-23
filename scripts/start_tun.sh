#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CPOLAR_BIN="$ROOT_DIR/data/cpolar/cpolar"
LOCAL_PORT="${1:-8000}"
SESSION="cpolar"
LOG_FILE="$ROOT_DIR/cpolar.log"

if [[ ! -x "$CPOLAR_BIN" ]]; then
    echo "错误：cpolar 不存在或不可执行：$CPOLAR_BIN" >&2
    exit 1
fi

if ! command -v tmux >/dev/null 2>&1; then
    echo "错误：未安装 tmux" >&2
    exit 1
fi

# 已经运行则不重复启动
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "cpolar 会话已存在，本次未重新启动，也未应用新的启动参数"
    echo "日志: $LOG_FILE"
    exit 0
fi

tmux new-session -d -s "$SESSION" \
    "exec \"$CPOLAR_BIN\" http -subdomain=xtyapp -log=stdout \"$LOCAL_PORT\" >> \"$LOG_FILE\" 2>&1"

sleep 1

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "cpolar 会话已启动，请查看日志确认隧道连接状态"
    echo "本地端口: $LOCAL_PORT"
    echo "日志: $LOG_FILE"
    echo "查看会话: tmux attach -t $SESSION"
else
    echo "cpolar 启动失败，请检查日志：$LOG_FILE" >&2
    exit 1
fi