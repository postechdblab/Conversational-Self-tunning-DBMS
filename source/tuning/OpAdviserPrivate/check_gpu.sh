#!/bin/bash

echo "=========================================="
echo "GPU AVAILABILITY CHECK"
echo "=========================================="
echo ""

# Check nvidia-smi
echo "1. Checking nvidia-smi..."
if command -v nvidia-smi &> /dev/null; then
    echo "✅ nvidia-smi found"
    echo ""
    nvidia-smi
    echo ""
else
    echo "❌ nvidia-smi not found"
    echo "   This means NVIDIA drivers are not accessible in the container."
    echo "   Possible reasons:"
    echo "   - Host doesn't have NVIDIA drivers"
    echo "   - NVIDIA Container Runtime not installed on host"
    echo "   - Container needs to be rebuilt after GPU configuration"
    echo ""
fi

# Check PyTorch CUDA
echo "=========================================="
echo "2. Checking PyTorch CUDA support..."
if python3.8 -c "import torch" 2>/dev/null; then
    python3.8 << 'EOF'
import torch
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA version: {torch.version.cuda}")
    print(f"cuDNN version: {torch.backends.cudnn.version()}")
    print(f"GPU count: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
else:
    print("CUDA not available - PyTorch will use CPU")
EOF
else
    echo "❌ PyTorch not installed"
    echo "   Install with: pip install torch"
fi

echo ""
echo "=========================================="
echo "3. Summary"
echo "=========================================="

if command -v nvidia-smi &> /dev/null && python3.8 -c "import torch; exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
    echo "✅ GPU FULLY OPERATIONAL"
    echo "   Your DBMS tuning can use GPU acceleration!"
elif command -v nvidia-smi &> /dev/null; then
    echo "⚠️  GPU detected but PyTorch can't access it"
    echo "   May need to reinstall PyTorch with CUDA support"
    echo "   pip install torch --index-url https://download.pytorch.org/whl/cu118"
else
    echo "ℹ️  GPU not available"
    echo "   DBMS tuning will use CPU (this is fine for most workloads)"
fi

echo ""

