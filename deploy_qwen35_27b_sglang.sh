#!/usr/bin/env bash

set -euo pipefail

ENV_PREFIX="/data2/lyq/conda-envs/sglang_qwen35_27b"
MODEL_PATH="/data2/lyq/models/Qwen3.5-27B"
CUDA_ROOT="/usr/local/cuda-12.8"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1,2,3}"
export TMPDIR="${TMPDIR:-/data2/lyq/tmp}"
export SGLANG_DISABLE_CUDNN_CHECK="${SGLANG_DISABLE_CUDNN_CHECK:-1}"
export SGLANG_SKIP_DIST_MEM_CHECK="${SGLANG_SKIP_DIST_MEM_CHECK:-1}"
export SGLANG_DISABLE_PYNCCL="${SGLANG_DISABLE_PYNCCL:-1}"
export SGLANG_USE_MESSAGE_QUEUE_BROADCASTER="${SGLANG_USE_MESSAGE_QUEUE_BROADCASTER:-false}"
export CUDA_HOME="${CUDA_HOME:-$CUDA_ROOT}"
export PATH="${CUDA_HOME}/bin:${PATH}"
export LD_LIBRARY_PATH="${CUDA_HOME}/targets/x86_64-linux/lib:${CUDA_HOME}/lib64:${ENV_PREFIX}/lib/python3.10/site-packages/nvidia/cuda_runtime/lib:${LD_LIBRARY_PATH:-}"
export LIBRARY_PATH="${CUDA_HOME}/targets/x86_64-linux/lib:${CUDA_HOME}/lib64:${ENV_PREFIX}/lib/python3.10/site-packages/nvidia/cuda_runtime/lib:${LIBRARY_PATH:-}"
export PYTHONUNBUFFERED=1

exec "${ENV_PREFIX}/bin/python" -m sglang.launch_server \
  --model-path "${MODEL_PATH}" \
  --host 0.0.0.0 \
  --port 62273 \
  --served-model-name Qwen3.5-27B \
  --dtype bfloat16 \
  --enable-multimodal \
  --context-length 32768 \
  --tensor-parallel-size 4 \
  --mem-fraction-static 0.80 \
  --disable-cuda-graph \
  --disable-custom-all-reduce \
  --skip-server-warmup \
  --log-level info
