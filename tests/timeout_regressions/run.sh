#!/usr/bin/env bash
set -euo pipefail

SUITE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SUITE_DIR/../.." && pwd)"
PYTHON_BIN="$PROJECT_DIR/.pixi/envs/default/bin/python"
REPORT_DIR="$(mktemp -d /tmp/xty-timeout-regressions-XXXXXXXX)"
export XTY_SOURCE_ROOT="$PROJECT_DIR"
export XTY_ORIGINAL_ROOT="$PROJECT_DIR"
export XTY_CHAT_TEST_REPORT="$REPORT_DIR/chat_upload_results.json"

# Each harness substitutes external services in its own process.
"$PYTHON_BIN" -B "$SUITE_DIR/test_file_timeout_regression.py"
"$PYTHON_BIN" -B "$SUITE_DIR/test_graph_db_connection.py" \
    --source-root "$PROJECT_DIR" --reference-root "$PROJECT_DIR" \
    --report "$REPORT_DIR/graph_db_results.json"
"$PYTHON_BIN" -B "$SUITE_DIR/test_auth_mysql_connections.py" \
    --source-root "$PROJECT_DIR" --report "$REPORT_DIR/auth_mysql_results.json"
"$PYTHON_BIN" -B "$SUITE_DIR/test_graph_upload_regression.py"
"$PYTHON_BIN" -B "$SUITE_DIR/test_kb_update_isolated.py"
"$PYTHON_BIN" -B "$SUITE_DIR/test_chat_upload_regression.py"
printf 'Regression reports: %s\n' "$REPORT_DIR"
