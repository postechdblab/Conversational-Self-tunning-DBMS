# MySQL and CMake Fixes

## Issues Addressed

### 1. **MySQL Failing to Start**
**Error:** `Starting MySQL database server mysqld [fail]` and `No directory, logging in with HOME=/`

**Root Causes:**
- MySQL runtime directory (`/var/run/mysqld`) was missing or had incorrect permissions
- MySQL user's HOME directory was not properly set
- Permission issues with MySQL data directories

**Solutions Applied:**
1. Created `/var/run/mysqld` with correct ownership (mysql:mysql) and permissions (755)
2. Set MySQL user's HOME directory to `/var/lib/mysql` using `usermod`
3. Added permission fixes in setup.sh to ensure all MySQL directories are accessible
4. Ensured data directory is properly initialized before starting MySQL

### 2. **LightGBM Build Failure - CMake Version Too Old**
**Error:** `CMakeNotFoundError: Could not find CMake with version >=3.18`

**Root Cause:**
- `lightgbm==4.4.0` requires CMake >= 3.18
- Ubuntu Bionic (18.04) default repos only provide CMake 3.10.x
- The system cmake package is too old for building modern Python packages with C++ extensions

**Solutions Applied:**
1. Added system `cmake` package to Dockerfile (provides basic cmake for other tools)
2. Installed CMake >= 3.18 via pip in the Dockerfile: `python3.8 -m pip install cmake>=3.18`
3. This provides the newer CMake version that scikit-build-core can find for building lightgbm

## Changes Made

### Dockerfile Updates:
```dockerfile
# Added cmake to system packages (line 33)
cmake \

# Installed newer CMake via pip after Python setup (lines 53-55)
RUN python3.8 -m pip install --upgrade pip && \
    python3.8 -m pip install cmake>=3.18

# Fixed MySQL directories and permissions (lines 67-74)
RUN mkdir -p /var/log/mysql/base && \
    touch /var/log/mysql/base/mysql-slow.log && \
    chmod 777 /var/log/mysql/base/mysql-slow.log && \
    chown -R mysql:mysql /var/log/mysql && \
    mkdir -p /var/run/mysqld && \
    chown -R mysql:mysql /var/run/mysqld && \
    chmod 755 /var/run/mysqld && \
    usermod -d /var/lib/mysql mysql
```

### setup.sh Updates:
```bash
# Added explicit permission fixing before MySQL operations
chown -R mysql:mysql /var/lib/mysql /var/run/mysqld /var/log/mysql 2>/dev/null || true
chmod 755 /var/run/mysqld 2>/dev/null || true

# Added --datadir flag to mysqld initialization
mysqld --initialize-insecure --user=mysql --datadir=/var/lib/mysql
```

## Rebuild Required

These changes require rebuilding the container to take effect:

### Option 1: Clean Rebuild (Recommended)
```bash
# In VS Code
F1 > "Dev Containers: Rebuild Container Without Cache"
```

This will:
1. Build new image with CMake >= 3.18
2. Fix all MySQL directories and permissions
3. Successfully install all Python packages including lightgbm
4. Start MySQL service without errors

### Option 2: Command Line
```bash
docker stop <container_name>
docker rm <container_name>
cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate
# Rebuild from devcontainer.json directory
docker build --no-cache -f .devcontainer/Dockerfile .
```

## Verification After Rebuild

Run these commands to verify everything works:

```bash
# Verify CMake version
cmake --version
# Should show version >= 3.18

# Verify Python packages
python3.8 -c "import lightgbm; print(f'LightGBM version: {lightgbm.__version__}')"
# Should print: LightGBM version: 4.4.0

# Verify MySQL is running
sudo service mysql status
# Should show: mysql is running

# Connect to MySQL
mysql -u root -ppassword -e "SELECT VERSION();"
# Should show MySQL version 5.7.x

# Check MySQL logs
tail -f /var/log/mysql/error.log
# Should not show permission errors
```

## Additional Notes

### Why Two CMake Installations?
- **System cmake (apt)**: Basic version for system tools and dependencies
- **Pip cmake (>=3.18)**: Newer version that Python build tools (scikit-build-core) can find and use

This is a common pattern when the system package manager provides older versions but Python packages need newer ones.

### MySQL HOME Directory
The MySQL user needs a valid HOME directory to start properly. We set it to `/var/lib/mysql` which is the standard MySQL data directory, ensuring MySQL can:
- Create temporary files
- Store socket files
- Access its configuration properly

### Network Configuration
The devcontainer.json includes `--network=host` to fix DNS resolution issues that may occur in some Docker setups.

## Troubleshooting

If MySQL still fails to start after rebuild:

1. **Check MySQL error log:**
   ```bash
   sudo cat /var/log/mysql/error.log
   ```

2. **Manually initialize MySQL:**
   ```bash
   sudo rm -rf /var/lib/mysql/*
   sudo mysqld --initialize-insecure --user=mysql --datadir=/var/lib/mysql
   sudo service mysql start
   ```

3. **Check permissions:**
   ```bash
   ls -la /var/run/mysqld
   ls -la /var/lib/mysql
   # Both should be owned by mysql:mysql
   ```

If LightGBM installation still fails:

1. **Check CMake version in build environment:**
   ```bash
   python3.8 -c "from cmake import CMAKE_BIN_DIR; import os; print(os.popen(f'{CMAKE_BIN_DIR}/cmake --version').read())"
   ```

2. **Try manual installation:**
   ```bash
   python3.8 -m pip install --no-cache-dir lightgbm==4.4.0
   ```

3. **Check build logs carefully** - they will show which CMake is being used


