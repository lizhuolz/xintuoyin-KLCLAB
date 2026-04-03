#!/usr/bin/env bash
set -euo pipefail

source /home/lyq/anaconda3/bin/activate vllm

: "${CUDA_VISIBLE_DEVICES:=0,1,2,3}"
: "${PORT:=62274}"
: "${TOOL_CALL_PARSER:=qwen3_xml}"

export CUDA_VISIBLE_DEVICES
export NCCL_P2P_DISABLE="${NCCL_P2P_DISABLE:-1}"
export NCCL_CUMEM_ENABLE="${NCCL_CUMEM_ENABLE:-0}"
export TOOL_CALL_PARSER

exec vllm serve /data1/dlx/projects/vllm_xty/model \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --served-model-name Qwen3-32B \
  --dtype bfloat16 \
  --tensor-parallel-size 4 \
  --generation-config vllm \
  --gpu-memory-utilization 0.9 \
  --max-model-len 12000 \
  --max-num-seqs 128 \
  --enable-auto-tool-choice \
  --tool-call-parser "${TOOL_CALL_PARSER}" \
  --disable-custom-all-reduce \
  --enforce-eager
