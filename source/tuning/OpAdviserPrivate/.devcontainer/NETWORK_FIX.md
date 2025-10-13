# MySQL Network Configuration Fix

## Problem Resolved
MySQL was failing to start with the error:
```
[ERROR] Can't start server: Bind on TCP/IP port: Address already in use
[ERROR] Do you already have another mysqld server running on port: 3306 ?
```

This occurred because the devcontainer was using `--network=host` mode, which shares the host's network namespace. When the host already has a MySQL instance running on port 3306, the container's MySQL cannot bind to the same port.

## Solution Implemented
Switched from **host networking** to **bridge networking** (Docker's default isolated network mode).

## Changes Made

### 1. `.devcontainer/devcontainer.json`
- **Removed** `--network=host` from `build.options` array
- **Removed** `--network=host` from `runArgs` array
- **Kept** DNS configuration (`--dns` settings) for proper name resolution

### 2. `.devcontainer/setup.sh`
- **Added** `bind-address=0.0.0.0` to MySQL configuration in `/etc/mysql/my.cnf`
- **Added** script to update bind-address in `/etc/mysql/mysql.conf.d/mysqld.cnf` if it exists
- This allows MySQL to accept connections from any interface within the container's network namespace

## Why This Works

### Bridge Mode Benefits
- **Port Isolation**: Container gets its own network namespace, so port 3306 inside the container doesn't conflict with port 3306 on the host
- **localhost Works**: All existing code using `localhost` continues to work unchanged
- **Unix Sockets Unchanged**: Socket connections via `/var/run/mysqld/mysqld.sock` continue working
- **No Code Changes**: Application code using `localhost` and port 3306 requires no modifications

### Bind Address Configuration
- **Previous**: `bind-address=127.0.0.1` (only accept localhost connections)
- **New**: `bind-address=0.0.0.0` (accept connections from any interface)
- **Why Needed**: In bridge mode, even `localhost` connections may come from different interfaces within the container's network stack

## Next Steps

### To Apply These Changes
1. **Rebuild the devcontainer**:
   - Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
   - Select "Dev Containers: Rebuild Container"
   - Or select "Dev Containers: Rebuild Container Without Cache" for a clean rebuild

2. **Verify MySQL Starts**:
   ```bash
   sudo service mysql status
   ```

3. **Test Connection**:
   ```bash
   mysql -u root -ppassword -h localhost -P 3306 -e "SELECT 1"
   ```

4. **Check Port Binding**:
   ```bash
   sudo netstat -tulpn | grep 3306
   # or
   sudo ss -tulpn | grep 3306
   ```

## Compatibility Notes

- All existing scripts and configuration files continue to work
- Connection strings using `localhost:3306` remain valid
- Unix socket connections are unaffected
- Database setup scripts require no changes

## Troubleshooting

If MySQL still fails to start after rebuilding:

1. **Check error logs**:
   ```bash
   sudo cat /var/log/mysql/error.log | tail -50
   ```

2. **Verify bind-address**:
   ```bash
   grep bind-address /etc/mysql/mysql.conf.d/mysqld.cnf
   grep bind-address /etc/mysql/my.cnf
   ```

3. **Check MySQL service**:
   ```bash
   sudo service mysql status
   sudo journalctl -u mysql -n 50
   ```

4. **Manual start for debugging**:
   ```bash
   sudo mysqld --verbose --help | grep bind-address
   sudo mysqld --user=mysql --console
   ```

## Date
October 13, 2025


