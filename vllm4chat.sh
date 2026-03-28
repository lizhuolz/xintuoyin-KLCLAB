export CUDA_VISIBLE_DEVICES=1,4,5,6

vllm serve  /data2/lyq/models/Qwen3.5-27B \
  --host 0.0.0.0 \
  --port 62272 \
  --dtype bfloat16 \
  --served-model-name Qwen3.5-27B \
  --tensor-parallel-size 4 \
  --generation-config vllm\
  --gpu-memory-utilization 0.9 \
  --max-model-len 50000 \
  --max-num-seqs 256 \
  --enable-auto-tool-choice\
  --tool-call-parser hermes\