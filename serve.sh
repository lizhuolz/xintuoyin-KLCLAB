
#ollama serve
#CUDA_VISIBLE_DEVICES=4,5,6,7 vllm serve /data1/public/models/Qwen2.5-32B-Instruct --dtype auto --api-key token-abc123 --max-model-len 10000 --tensor-parallel-size 4


uvicorn server:app --host 0.0.0.0 --port 8000

curl -X POST http://0.0.0.0:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "0", "conver_id": "0", "message": "2025年二月总工时最长的人员id是？"}'