docker run \
    --gpus all \
    -e CUDA_VISIBLE_DEVICES=0,1 \
    -p 30001:30001 \
    --ipc=host \
    --mount type=bind,source=/mnt,target=/mnt \
    lmsysorg/sglang:latest \
    python3 -m sglang.launch_server --model-path /mnt/sdd/hkkang/laser/huggingface/hub/models--openai--gpt-oss-20b/snapshots/6cee5e81ee83917806bbde320786a8fb61efebee --host 0.0.0.0 --port 30001 --tp 2