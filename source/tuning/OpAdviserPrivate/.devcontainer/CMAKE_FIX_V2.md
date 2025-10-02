# CMake Permission Fix - v2

## Problem Identified

The previous fix attempted to install CMake via pip, but this caused a **permission error**:

```
PermissionError: [Errno 13] Permission denied
```

**Root Cause:** When CMake is installed via pip globally (as root), the wrapper scripts don't have proper execute permissions when accessed from user-space pip builds.

## New Solution

**Install CMake from Kitware's official APT repository** instead of pip.

### Why This Works Better

1. **Proper permissions**: System packages have correct permissions set automatically
2. **Native installation**: No Python wrapper layer that can have permission issues  
3. **Official source**: Kitware maintains the official CMake repository for Ubuntu
4. **Version control**: Can specify exactly which version we need

### Changes Made

```dockerfile
# Instead of: python3.8 -m pip install cmake>=3.18
# Now using Kitware's official repository:

RUN wget -O - https://apt.kitware.com/keys/kitware-archive-latest.asc 2>/dev/null | gpg --dearmor - | tee /usr/share/keyrings/kitware-archive-keyring.gpg >/dev/null && \
    echo 'deb [signed-by=/usr/share/keyrings/kitware-archive-keyring.gpg] https://apt.kitware.com/ubuntu/ bionic main' | tee /etc/apt/sources.list.d/kitware.list >/dev/null && \
    apt-get update && \
    apt-get install -y cmake && \
    rm -rf /var/lib/apt/lists/*
```

This installs CMake 3.27+ (latest for bionic), which is well above the required 3.18+.

## MySQL Improvements

Also improved MySQL startup with:
- Better error logging (shows last 30 lines of error log on failure)
- Automatic reinitialization if first start fails
- Fixed permissions after initialization

## Next Steps

**You MUST rebuild the container** for these changes to take effect:

```
F1 > "Dev Containers: Rebuild Container Without Cache"
```

## Expected Results

After rebuild:

```bash
# CMake should work properly
cmake --version
# CMake version 3.27.x or higher

# LightGBM should install without errors
python3.8 -m pip install lightgbm==4.4.0
# Should complete successfully

# MySQL should start
sudo service mysql status
# Should show: mysql is running
```

## Alternative: Skip LightGBM (If Still Problematic)

If lightgbm continues to cause issues, you can temporarily skip it:

### Option 1: Comment out in requirements.txt
```bash
# Edit requirements.txt, change line 26:
# lightgbm==4.4.0  # Temporarily disabled, install manually later
```

### Option 2: Install manually after container starts
```bash
# After container is running, try:
python3.8 -m pip install --no-build-isolation lightgbm==4.4.0

# Or use an older version that doesn't need CMake 3.18+:
python3.8 -m pip install lightgbm==3.3.5
```

### Option 3: Use pre-built wheel
```bash
# Install from pre-built wheel (faster, no compilation):
python3.8 -m pip install --only-binary :all: lightgbm==4.4.0
```

## Verification Commands

After successful rebuild:

```bash
# Check all critical components
echo "=== Python ==="
python3.8 --version

echo "=== CMake ==="
cmake --version
which cmake

echo "=== MySQL ==="
sudo service mysql status
mysql -u root -ppassword -e "SELECT VERSION();"

echo "=== Python Packages ==="
python3.8 -c "import pandas; print(f'pandas: {pandas.__version__}')"
python3.8 -c "import numpy; print(f'numpy: {numpy.__version__}')"
python3.8 -c "import torch; print(f'torch: {torch.__version__}')"

echo "=== LightGBM (if installed) ==="
python3.8 -c "import lightgbm; print(f'lightgbm: {lightgbm.__version__}')" || echo "LightGBM not yet installed"
```

## Troubleshooting

### If CMake still shows permission errors:
```bash
# Check CMake location and permissions
which cmake
ls -la $(which cmake)

# Should show something like:
# -rwxr-xr-x 1 root root ... /usr/bin/cmake
```

### If MySQL still won't start:
```bash
# Check error log
sudo cat /var/log/mysql/error.log

# Try manual start with verbose output
sudo mysqld --user=mysql --verbose --help 2>&1 | head -50

# Check data directory
ls -la /var/lib/mysql/

# Reinitialize completely
sudo rm -rf /var/lib/mysql/*
sudo mysqld --initialize-insecure --user=mysql
sudo chown -R mysql:mysql /var/lib/mysql
sudo service mysql start
```

### If LightGBM build still fails:
```bash
# Check what CMake pip sees
python3.8 -c "import subprocess; print(subprocess.run(['cmake', '--version'], capture_output=True, text=True).stdout)"

# Try with system PATH explicitly
export PATH="/usr/bin:$PATH"
python3.8 -m pip install --no-cache-dir lightgbm==4.4.0

# Or install a version that works with older build systems
python3.8 -m pip install lightgbm==3.3.5
```

## Summary

- ✅ CMake now installed from Kitware's official APT repo (not pip)
- ✅ Proper permissions on all binaries
- ✅ MySQL initialization improved with better error handling
- ✅ Should install lightgbm 4.4.0 without issues

**Action Required:** Rebuild container to apply fixes!


