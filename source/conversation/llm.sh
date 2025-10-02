docker run \
    --gpus all \
    -e CUDA_VISIBLE_DEVICES=2 \
    -p 30000:30000 \
    --ipc=host \
    --mount type=bind,source=/mnt,target=/mnt \
    lmsysorg/sglang:latest \
    python3 -m sglang.launch_server --model-path /mnt/sdb1/shpark/meta-llama-3.1-8B-instruct --host 0.0.0.0 --port 30000 --tp 1