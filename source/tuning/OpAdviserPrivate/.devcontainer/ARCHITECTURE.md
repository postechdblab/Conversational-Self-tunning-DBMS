# DevContainer Architecture

## Design Philosophy

**Minimize shell scripts, maximize devcontainer.json configuration.**

All base setup is now directly in `devcontainer.json` using built-in lifecycle hooks and features. Shell scripts are only used for optional, time-consuming workload setup.

## Structure

```
.devcontainer/
├── devcontainer.json          # Main configuration (ALL base setup here)
├── setup_sysbench.sh          # Optional: Sysbench workload (30-60 min)
├── setup_oltpbench.sh         # Optional: OLTPBench workloads (1-3 hours)
├── setup_tpch.sh              # Optional: TPC-H workload (30-90 min)
├── setup_job.sh               # Optional: JOB workload (10-30 min)
├── README.md                  # Full documentation
├── QUICKSTART.md              # Quick reference
└── ARCHITECTURE.md            # This file
```

## devcontainer.json Configuration

### 1. Features (Official DevContainer Features)

```json
"features": {
  "ghcr.io/devcontainers/features/python:1": {
    "version": "3.8"
  },
  "ghcr.io/devcontainers/features/java:1": {
    "version": "11",
    "installMaven": false,
    "installGradle": false
  }
}
```

**Why features?**
- ✅ Official, maintained solutions
- ✅ Optimized for container builds
- ✅ Cached layers for faster rebuilds
- ✅ No custom scripts needed

### 2. onCreateCommand (Runs as ROOT during creation)

```json
"onCreateCommand": {
  "install-packages": "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y ...",
  "configure-mysql": "echo '[mysqld]...' >> /etc/mysql/my.cnf && service mysql start && ...",
  "setup-python": "update-alternatives --install /usr/bin/python python /usr/bin/python3.8 1 && ..."
}
```

**What it does:**
- Installs system packages (MySQL, build tools, libraries)
- Configures MySQL server
- Sets up MySQL users and permissions
- Configures Python alternatives

**Why onCreateCommand?**
- ✅ Runs as root (no sudo needed)
- ✅ Runs before source code mount
- ✅ Perfect for system-level setup
- ✅ Can be parallelized with named commands

### 3. postCreateCommand (Runs as USER after creation)

```json
"postCreateCommand": "python -m pip install --upgrade pip && pip install --user --upgrade setuptools wheel && cd /workspaces/... && [ -f requirements.txt ] && python -m pip install -r requirements.txt || echo 'No requirements.txt found'"
```

**What it does:**
- Upgrades pip, setuptools, wheel
- Installs Python requirements from requirements.txt

**Why postCreateCommand?**
- ✅ Runs as vscode user (proper permissions)
- ✅ Runs after source code is mounted
- ✅ Perfect for project-specific setup
- ✅ Single-line command (no script needed)

### 4. postStartCommand (Runs on EVERY container start)

```json
"postStartCommand": "sudo service mysql start || true"
```

**What it does:**
- Ensures MySQL is running every time container starts

**Why postStartCommand?**
- ✅ Runs on every attach/restart
- ✅ Ensures services are always running
- ✅ Idempotent (safe to run multiple times)

## Lifecycle Flow

```
Container Creation:
1. Pull base image (mcr.microsoft.com/devcontainers/base:bionic)
2. Apply features (Python 3.8, Java 11)
3. Run onCreateCommand (system setup, MySQL config) [AS ROOT]
4. Mount source code
5. Run postCreateCommand (Python requirements) [AS USER]
   ✅ Container ready!

Container Start:
1. Container starts
2. Run postStartCommand (start MySQL) [AS USER with sudo]
   ✅ Ready to work!
```

## Why Not Use Shell Scripts for Base Setup?

### Before (setup.sh approach):
```bash
#!/bin/bash
set -e
echo "Starting setup..."
sudo apt update
sudo apt install -y mysql-server-5.7 ...
# 100+ lines of bash
```

**Problems:**
- ❌ External file to maintain
- ❌ Harder to version control inline
- ❌ Less visible to users
- ❌ Requires parsing/execution
- ❌ No parallelization

### After (devcontainer.json approach):
```json
"onCreateCommand": {
  "install-packages": "apt-get update && ...",
  "configure-mysql": "echo '[mysqld]...' && ...",
  "setup-python": "update-alternatives ..."
}
```

**Benefits:**
- ✅ Everything in one file
- ✅ Self-documenting
- ✅ Native devcontainer feature
- ✅ Can run in parallel
- ✅ Clear separation of concerns

## When to Use Shell Scripts

Shell scripts are **only** used for:

1. **Long-running workload setup** (30+ minutes)
   - Example: `setup_sysbench.sh` (30-60 min)
   - Reason: Too long for container creation

2. **Optional setup** (not everyone needs)
   - Example: `setup_tpch.sh` (only needed for TPC-H experiments)
   - Reason: Don't want to force everyone to wait hours

3. **Complex multi-step processes** (100+ lines)
   - Example: `setup_oltpbench.sh` (6 different benchmarks)
   - Reason: Better organized as separate script

## User Permissions

- **onCreateCommand**: Runs as **root** (no sudo needed)
- **postCreateCommand**: Runs as **vscode** (uses sudo when needed)
- **postStartCommand**: Runs as **vscode** (uses sudo for MySQL)

This ensures:
- ✅ Proper file ownership
- ✅ Minimal privilege escalation
- ✅ Security best practices

## Extending the Configuration

### To add a system package:

Add to `onCreateCommand.install-packages`:
```json
"install-packages": "apt-get update && ... apt-get install -y YOUR_PACKAGE ..."
```

### To add a Python package:

Add to requirements.txt (automatically installed by `postCreateCommand`)

### To add a workload:

Create a new `setup_workload.sh` script and document it in README.md.

## Benefits of This Architecture

1. **Clarity**: All base setup visible in devcontainer.json
2. **Maintainability**: Single source of truth
3. **Performance**: Parallel execution, cached layers
4. **User Experience**: Fast container creation, optional workloads
5. **Security**: Proper permission separation
6. **Standards**: Uses official devcontainer features where possible

## Migration Path

If you want to eliminate the workload scripts too:

1. Add them to a commented-out `postCreateCommand` (already done)
2. Users can uncomment if they want auto-setup
3. Trade-off: Long container creation time vs manual script execution

Current approach: Keep scripts for flexibility.

## Summary

| Component | Location | Purpose | Runs As | When |
|-----------|----------|---------|---------|------|
| Features | devcontainer.json | Python, Java | root | Creation |
| onCreateCommand | devcontainer.json | System setup | root | Creation |
| postCreateCommand | devcontainer.json | Python deps | vscode | Creation |
| postStartCommand | devcontainer.json | MySQL start | vscode | Every start |
| setup_*.sh | .devcontainer/*.sh | Optional workloads | vscode | Manual |

**Result**: Minimal shell scripts, maximum devcontainer.json usage! 🎉

