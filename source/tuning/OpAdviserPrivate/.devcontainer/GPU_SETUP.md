# GPU Support - Complete Setup

## How GPU Access Works in Containers

```
┌──────────────────────────────────────────────────────────────┐
│ Host Machine                                                  │
│                                                               │
│  ✅ NVIDIA GPU Hardware (e.g., RTX 3090, A100)              │
│  ✅ NVIDIA Driver (e.g., 525.xx)                             │
│  ✅ NVIDIA Container Runtime                                 │
│  ✅ Docker with GPU support                                  │
└──────────────────────────────────────────────────────────────┘
                            ↓
                   --gpus=all flag
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ Container                                                     │
│                                                               │
│  ✅ GPU devices exposed (/dev/nvidia0, /dev/nvidiactl)       │
│  ✅ nvidia-smi binary (from nvidia-utils package)            │
│  ✅ PyTorch with CUDA support                                │
└──────────────────────────────────────────────────────────────┘
```

## What Each Component Does

### 1. `--gpus=all` (in devcontainer.json)
**Purpose:** Passes GPU devices from host to container

**What it does:**
- ✅ Makes `/dev/nvidia*` devices available
- ✅ Enables GPU memory access
- ✅ Allows CUDA applications to run

**What it does NOT do:**
- ❌ Does not install nvidia-smi
- ❌ Does not install CUDA toolkit
- ❌ Does not install drivers

### 2. `nvidia-utils` Package (in Dockerfile)
**Purpose:** Provides NVIDIA monitoring tools

**What it includes:**
- ✅ `nvidia-smi` - GPU monitoring command
- ✅ `nvidia-settings` - GPU configuration
- ✅ Other NVIDIA utilities

**Note:** The version should match (approximately) your host driver version.

### 3. PyTorch with CUDA (in Dockerfile)
**Purpose:** GPU-accelerated deep learning

**What it includes:**
- ✅ CUDA runtime libraries
- ✅ cuDNN for neural networks
- ✅ GPU-accelerated tensor operations

**Installed with:**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## Current Configuration

### ✅ In devcontainer.json
```json
"runArgs": [
    "--gpus=all"  // Passes all GPUs to container
]
```

### ✅ In Dockerfile
```dockerfile
# NVIDIA utilities (nvidia-smi)
RUN apt-get install -y nvidia-utils-525 || ...

# PyTorch with CUDA 11.8
RUN pip install torch ... --index-url .../cu118
```

## Verification After Rebuild

### Check 1: GPU Devices
```bash
ls -la /dev/nvidia*
# Should show: nvidia0, nvidia1, nvidiactl, nvidia-uvm, etc.
```

### Check 2: nvidia-smi
```bash
nvidia-smi
# Should show GPU information table
```

### Check 3: PyTorch CUDA
```bash
python3.8 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
# Should print: CUDA: True
```

### Check 4: Comprehensive Check
```bash
./check_gpu.sh
# Shows full GPU status report
```

## Troubleshooting

### Problem: `nvidia-smi: command not found` after rebuild

**Cause:** nvidia-utils package didn't install

**Solutions:**
1. Check if package is available for Ubuntu 18.04:
   ```bash
   apt-cache search nvidia-utils
   ```

2. Install manually in container:
   ```bash
   sudo apt-get update
   sudo apt-get install nvidia-utils-525
   ```

3. Alternative: Use NVIDIA base image (see Option 2 below)

### Problem: `nvidia-smi` works but shows "No devices found"

**Cause:** Container runtime not configured on host

**Fix on host machine:**
```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### Problem: PyTorch says `CUDA: False`

**Causes & Solutions:**

1. **Wrong PyTorch version:**
   ```bash
   # Reinstall with CUDA support
   pip uninstall torch
   pip install torch --index-url https://download.pytorch.org/whl/cu118
   ```

2. **CUDA version mismatch:**
   ```bash
   # Check host CUDA version
   nvidia-smi | grep "CUDA Version"
   # Install matching PyTorch version
   ```

## Alternative: Use NVIDIA Base Image

If `nvidia-utils` installation fails, you can switch to an NVIDIA base image:

### Change Dockerfile First Line:
```dockerfile
# FROM mcr.microsoft.com/devcontainers/base:bionic
FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu18.04
```

**Pros:**
- ✅ nvidia-smi pre-installed
- ✅ CUDA toolkit included
- ✅ Guaranteed compatibility

**Cons:**
- ❌ Larger image size (~4GB vs ~1GB)
- ❌ Different base system (may need adjustments)
- ❌ DevContainer features need manual setup

## Summary

| Component | Location | Purpose | Status |
|-----------|----------|---------|--------|
| `--gpus=all` | devcontainer.json | Pass GPU devices | ✅ Configured |
| nvidia-utils | Dockerfile | Provides nvidia-smi | ✅ Will install |
| PyTorch+CUDA | Dockerfile | GPU acceleration | ✅ Will install |
| Host drivers | Host machine | GPU drivers | ❓ Check host |
| Container runtime | Host machine | GPU passthrough | ❓ Check host |

## Quick Reference

```bash
# After rebuild, test GPU:
nvidia-smi                    # Shows GPU info
./check_gpu.sh               # Comprehensive check
python -c "import torch; print(torch.cuda.is_available())"

# Monitor GPU during training:
watch -n 1 nvidia-smi        # Update every second

# See GPU memory usage:
nvidia-smi --query-gpu=memory.used --format=csv
```

---

**Next Step:** Rebuild your container to apply these changes! 🚀

