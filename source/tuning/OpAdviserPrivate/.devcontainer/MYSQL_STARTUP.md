# MySQL Startup and Readiness Checks

## Overview

All database setup scripts now include **robust MySQL startup checks** to ensure MySQL is running and ready before any database operations begin.

## What Was Added

### 1. Automatic MySQL Startup
If MySQL is not running, it will be automatically started with error handling:
```bash
if ! sudo service mysql status >/dev/null 2>&1; then
    echo "MySQL is not running. Starting MySQL..."
    sudo service mysql start
fi
```

### 2. Connection Readiness Check
Scripts wait up to 60 seconds for MySQL to accept connections:
```bash
for i in $(seq 1 30); do
    if mysql -u root -ppassword -h localhost -P 3306 -e "SELECT 1" >/dev/null 2>&1; then
        echo "✅ MySQL is ready on port 3306!"
        break
    fi
    sleep 2
done
```

### 3. Comprehensive Error Reporting
If MySQL fails to start or become ready, you get detailed troubleshooting information:
- Service status
- Port availability check
- Recent error log entries
- Suggested troubleshooting steps

## Files Updated

### ✅ `.devcontainer/post_create.sh`
- Checks MySQL status before installing packages
- Ensures MySQL is ready before starting database population
- Exits with error if MySQL can't be started

### ✅ `.devcontainer/setup_all_databases.sh`
- Enhanced MySQL readiness check with detailed logging
- Shows MySQL version and port when ready
- Provides troubleshooting steps if MySQL fails

### ✅ `.devcontainer/devcontainer.json`
- `postStartCommand` now waits for MySQL to be ready
- Runs every time container starts
- Quick 10-second check with status reporting

### ✅ `.devcontainer/ensure_mysql.sh` (NEW)
- Standalone utility script to check/start MySQL
- Can be called from any other script
- Comprehensive error reporting and diagnostics

## Usage

### Manual MySQL Check
```bash
# Check and start MySQL if needed
bash .devcontainer/ensure_mysql.sh

# Or use the connection helper
./mysql-connect.sh -e "SELECT 'MySQL is working!' AS Status;"
```

### Automatic Checks
MySQL is automatically checked and started in these scenarios:

1. **Container Start** (`postStartCommand`)
   - Every time the container starts or restarts
   - Quick 10-second check

2. **Post-Create** (`postCreateCommand`)
   - After container is created
   - Before Python package installation
   - Before database population starts

3. **Database Population** (`setup_all_databases.sh`)
   - Before setting up any benchmark databases
   - Comprehensive 60-second check with detailed logging

## Error Messages

### MySQL Not Starting
```
❌ ERROR: Failed to start MySQL service
Check logs: sudo tail -50 /var/log/mysql/error.log
```

**Solution:**
```bash
# Check what's wrong
sudo tail -50 /var/log/mysql/error.log

# Try restarting
sudo service mysql restart

# Check if port is in use
sudo netstat -tlnp | grep 3306
```

### MySQL Not Accepting Connections
```
❌ ERROR: MySQL did not become ready after 30 attempts (60 seconds)
Troubleshooting steps:
  1. Check MySQL status: sudo service mysql status
  2. Check error log: sudo tail -50 /var/log/mysql/error.log
  3. Check if port 3306 is in use: sudo netstat -tlnp | grep 3306
  4. Try restarting MySQL: sudo service mysql restart
```

**Solution:** Follow the provided troubleshooting steps in order.

## Verification

### Check MySQL Status
```bash
# Quick check
./mysql-connect.sh -e "SELECT @@version, @@port;"

# Detailed check
bash .devcontainer/ensure_mysql.sh

# Service status
sudo service mysql status
```

### Expected Output
```
[2025-10-02 07:49:20] ✅ MySQL service is running
[2025-10-02 07:49:20] ✅ MySQL is ready!
[2025-10-02 07:49:20]    Version: 5.7.42-0ubuntu0.18.04.1
[2025-10-02 07:49:20]    Port: 3306
```

## Benefits

✅ **No More Failed Setups**: Database population won't start if MySQL isn't ready

✅ **Automatic Recovery**: MySQL is automatically started if not running

✅ **Clear Error Messages**: Detailed diagnostics if something goes wrong

✅ **Fast Feedback**: Know immediately if there's a MySQL problem

✅ **Consistent Behavior**: All scripts use the same robust checking logic

## Timeline

| Stage | Check | Timeout | Exits on Failure |
|-------|-------|---------|------------------|
| Container Start | Quick check | 10 sec | No (continues) |
| Post-Create | Standard check | 60 sec | Yes |
| Database Setup | Enhanced check | 60 sec | Yes |

## Manual Troubleshooting

If MySQL won't start:

```bash
# 1. Check service status
sudo service mysql status

# 2. View error log
sudo tail -100 /var/log/mysql/error.log

# 3. Check port availability
sudo netstat -tlnp | grep 3306

# 4. Check MySQL processes
ps aux | grep mysqld

# 5. Try manual start with verbose output
sudo mysqld --verbose --help

# 6. Restart MySQL
sudo service mysql restart

# 7. Check permissions
ls -la /var/run/mysqld/
ls -la /var/lib/mysql/

# 8. Re-run setup
sudo bash .devcontainer/setup.sh
```

## Summary

With these improvements, you can be confident that:
- MySQL will always be running before database operations
- Clear error messages help diagnose problems quickly
- Automatic startup handles most common scenarios
- Database population won't fail due to MySQL not being ready

🎉 **Result**: Reliable, automated database setup with built-in resilience!

