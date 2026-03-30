#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source /home/lyq/anaconda3/etc/profile.d/conda.sh
conda activate xtyAgent

cd "$ROOT_DIR"
python vllm_test/benchmark_vllm.py "$@"
