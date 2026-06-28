#!/bin/bash
# 启动 vLLM 推理服务（Qwen3.5-27B, GPU 4,5）
# 此脚本在 /data2/dlx/projects/vllm 目录下的独立 pixi 环境中运行

set -euo pipefail

VLLM_PROJECT="/data2/dlx/projects/vllm"
MODEL_PATH="/data2/dlx/models/base4/Qwen3.5-27B"
PORT=62272
GPUS="0,1"

if ! [ -d "$VLLM_PROJECT" ]; then
  echo "错误: vLLM 项目目录不存在: $VLLM_PROJECT"
  exit 1
fi

# 检查是否已在运行
if curl -s --noproxy '*' --connect-timeout 3 "http://127.0.0.1:${PORT}/v1/models" > /dev/null 2>&1; then
  echo "vLLM 已在端口 ${PORT} 运行"
  curl -s --noproxy '*' --connect-timeout 3 "http://127.0.0.1:${PORT}/v1/models" | python3 -m json.tool 2>/dev/null || true
  exit 0
fi

echo "启动 vLLM (Qwen3.5-27B, GPU ${GPUS}, 端口 ${PORT})..."

cd "$VLLM_PROJECT"
nohup env LD_LIBRARY_PATH=.pixi/envs/default/lib:${LD_LIBRARY_PATH:-} CUDA_VISIBLE_DEVICES=${GPUS} \
  pixi run vllm serve "$MODEL_PATH" \
  --host 0.0.0.0 \
  --port "$PORT" \
  --dtype bfloat16 \
  --served-model-name Qwen3.5-27B \
  --tensor-parallel-size 2 \
  --generation-config vllm \
  --gpu-memory-utilization 0.9 \
  --max-model-len 50000 \
  --max-num-seqs 24 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  > vllm.log 2>&1 &

echo "vLLM PID: $!"
echo "等待服务就绪..."

for i in $(seq 1 60); do
  if curl -s --noproxy '*' --connect-timeout 3 "http://127.0.0.1:${PORT}/v1/models" > /dev/null 2>&1; then
    echo "vLLM 服务就绪 (端口 ${PORT})"
    exit 0
  fi
  sleep 5
done

echo "警告: vLLM 启动超时，请检查日志: ${VLLM_PROJECT}/vllm.log"
