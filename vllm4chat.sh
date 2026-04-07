#!/usr/bin/env bash
set -euo pipefail

source /home/lyq/anaconda3/bin/activate vllm

: "${CUDA_VISIBLE_DEVICES:=4,5}"
: "${MODEL_PATH:=/data1/dlx/projects/vllm_xty/model}"
: "${PORT:=62274}"
: "${SERVED_MODEL_NAME:=Qwen3-32B}"
: "${TOOL_CALL_PARSER:=hermes}"

export CUDA_VISIBLE_DEVICES
export NCCL_P2P_DISABLE="${NCCL_P2P_DISABLE:-1}"
export NCCL_CUMEM_ENABLE="${NCCL_CUMEM_ENABLE:-0}"

exec vllm serve "${MODEL_PATH}" \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --dtype bfloat16 \
  --served-model-name "${SERVED_MODEL_NAME}" \
  --tensor-parallel-size 2 \
  --generation-config vllm \
  --gpu-memory-utilization 0.9 \
  --max-model-len 12000 \
  --max-num-seqs 128 \
  --enable-auto-tool-choice \
  --tool-call-parser "${TOOL_CALL_PARSER}" \
  --disable-custom-all-reduce \
  --enforce-eager
