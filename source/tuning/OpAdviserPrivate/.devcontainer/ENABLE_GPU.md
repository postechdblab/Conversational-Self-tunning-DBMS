# Enabling GPU Support in Dev Container

## Current Status
The dev container does **NOT** have GPU support enabled. The DBMS tuning can run without GPUs, but some ML models may be slower on CPU.

## Requirements
- NVIDIA drivers installed on **host machine**
- NVIDIA Container Runtime installed on host
- Docker configured to use NVIDIA runtime

## Steps to Enable GPU Support

### 1. Update devcontainer.json

Add GPU runtime arguments to `.devcontainer/devcontainer.json`:

```json
"runArgs": [
    "--network=host",
    "--dns=141.223.1.2",
    "--dns=8.8.8.8",
    "--gpus=all"  // ADD THIS LINE
],
```

Or for specific GPUs:
```json
"runArgs": [
    "--network=host",
    "--dns=141.223.1.2",
    "--dns=8.8.8.8",
    "--gpus=\"device=0,1\""  // Use GPUs 0 and 1
],
```

### 2. Update Dockerfile (Optional)

If you need CUDA toolkit inside the container, use an NVIDIA base image:

```dockerfile
# Change first line from:
FROM mcr.microsoft.com/devcontainers/base:bionic

# To:
FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu18.04
```

### 3. Verify GPU Access

After rebuilding the container:

```bash
# Check GPU availability
nvidia-smi

# Check PyTorch GPU support
python3.8 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU count: {torch.cuda.device_count()}')"
```

## Check Host GPU Status

On your **host machine** (not in container), run:

```bash
# Check if GPUs are available
nvidia-smi

# Check if NVIDIA Container Runtime is installed
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu18.04 nvidia-smi
```

## Do You Need GPU Support?

**You DON'T need GPU if:**
- Running database benchmarks only (OLTPBench, TPC-H, Sysbench)
- MySQL tuning with small ML models
- Workload with primarily database operations

**You NEED GPU if:**
- Training large neural networks
- Using GPU-accelerated optimizers
- Running heavy ML workloads for knob tuning
- Performance is critical

## Current Workaround

The DBMS tuning system will work **without GPUs** - it will just use CPU for ML models. PyTorch will automatically fall back to CPU mode.

