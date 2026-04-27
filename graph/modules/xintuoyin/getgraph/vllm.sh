export CUDA_VISIBLE_DEVICES=0,1,2,3

#/data1/public/models/Qwen2.5-32B-Instruct

# vllm serve /data1/public/models/Qwen2.5-32B-Instruct \
#     --port 8000 \
#     --tensor_parallel_size 2 \

    
vllm serve /data1/public/models/Qwen2.5-32B-Instruct \
    --port 8000 \
    --tensor_parallel_size 2 \