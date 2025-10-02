# OpAdviser DevContainer Setup

This directory contains automated setup scripts for the OpAdviser development environment.

## Overview

The devcontainer configuration automates all setup steps from the main README.md directly in `devcontainer.json`, making it easy to get started with OpAdviser.

## Automatic Setup

When you open this project in a DevContainer-compatible environment (like VS Code with Remote Containers extension or GitHub Codespaces), the following will happen automatically:

1. **Base Environment Setup** (via `devcontainer.json`):
   - ✅ **Python 3.8 Feature**: Installed via official devcontainer feature
   - ✅ **Java 11 Feature**: Installed via official devcontainer feature
   - ✅ **System Packages**: MySQL 5.7, git, ant, build tools, and all dependencies
   - ✅ **MySQL Configuration**: Configured with port 3308, password, and optimal settings
   - ✅ **Python Environment**: pip, setuptools, wheel, and all requirements.txt packages
   - ✅ **Auto-start**: MySQL starts automatically on container startup

2. **MySQL Configuration** (auto-configured):
   - MySQL server runs on port 3308
   - Root password: `password`
   - Max connections: 100,000
   - Auto-starts on container startup

**No shell scripts required for base setup!** Everything is in `devcontainer.json`.

## Workload Setup Scripts

After the container is created, you can set up specific workloads using these **optional** scripts. These are kept as scripts because they take a long time and may not all be needed:

### Sysbench Workloads
```bash
bash /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_sysbench.sh
```
This sets up three Sysbench databases:
- `sbrw` - Read-Write workload
- `sbwrite` - Write-Only workload
- `sbread` - Read-Only workload

**Note:** This can take significant time (800K rows × 300 tables per database).

### OLTPBench Workloads
```bash
bash /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_oltpbench.sh
```
This sets up multiple OLTPBench databases:
- Twitter
- TPC-C
- YCSB
- Wikipedia
- TATP
- Voter

**Note:** This can take a very long time depending on your system.

### TPC-H Workload
```bash
bash /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_tpch.sh
```
Sets up TPC-H benchmark with scale factor 10.

**Note:** This generates ~10GB of data and can take considerable time.

### JOB (Join Order Benchmark)
```bash
bash /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_job.sh
```
Sets up the Join Order Benchmark workload.

## Running Experiments

After setting up the desired workloads, you can run experiments:

```bash
cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate
export PYTHONPATH=.

# Sysbench experiments
python scripts/optimize.py --config=scripts/sysbench_rw.ini
python scripts/optimize.py --config=scripts/sysbench_wo.ini
python scripts/optimize.py --config=scripts/sysbench_ro.ini

# OLTPBench experiments
python scripts/optimize.py --config=scripts/twitter.ini
python scripts/optimize.py --config=scripts/tpcc.ini
python scripts/optimize.py --config=scripts/ycsb.ini
python scripts/optimize.py --config=scripts/wikipedia.ini
python scripts/optimize.py --config=scripts/tatp.ini
python scripts/optimize.py --config=scripts/voter.ini

# TPC-H experiment
python scripts/optimize.py --config=scripts/tpch.ini

# JOB experiment
python scripts/optimize.py --config=scripts/job.ini
```

## Flask Demo Server

To run the demo server:

```bash
cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate
sudo service mysql stop
sudo /usr/sbin/mysqld --defaults-file=initial2.cnf & disown
export PYTHONPATH=.
export FLASK_RUN_PORT=1234
export FLASK_APP=server/app.py
flask run
```

The server will be available on port 1234 (automatically forwarded).

## Container Configuration

The devcontainer is configured with:

- **Memory**: 64GB allocated
- **Network**: Host networking enabled
- **Ports**: 3308 (MySQL), 1234 (Flask) automatically forwarded
- **User**: Running as vscode (uses sudo for privileged operations)
- **Environment**: PYTHONPATH automatically set

## Troubleshooting

### MySQL Not Starting
```bash
sudo service mysql start
sudo service mysql status
```

### Check MySQL Connection
```bash
mysql -ppassword -e "SELECT 1;"
```

### Reset MySQL
```bash
sudo service mysql stop
sudo service mysql start
```

### Check Python Environment
```bash
python --version  # Should show Python 3.8.x
pip list  # Should show installed packages
echo $PYTHONPATH  # Should show workspace path
```

## Manual Setup

If you need to run setup steps manually, you can execute individual commands from the setup scripts or refer to the main README.md for detailed instructions.

## Performance Considerations

- The workload setup scripts can take a **very long time** depending on your system
- Ensure you have **sufficient disk space** (recommend 100GB+ free)
- For best performance, mount workspace to SSD (see `workspaceMount` in devcontainer.json)
- The container requires significant memory (64GB allocated)

## Configuration Reference

### Automatic Setup (in devcontainer.json)
- ✅ **features**: Python 3.8 and Java 11 installation
- ✅ **onCreateCommand**: System packages, MySQL setup, Python configuration (runs as root)
- ✅ **postCreateCommand**: Python requirements installation (runs as user)
- ✅ **postStartCommand**: MySQL auto-start on container startup

### Optional Workload Scripts
| Script | Purpose | Estimated Time |
|--------|---------|----------------|
| `setup_sysbench.sh` | Sysbench workloads | 30-60 minutes |
| `setup_oltpbench.sh` | OLTPBench workloads | 1-3 hours |
| `setup_tpch.sh` | TPC-H workload | 30-90 minutes |
| `setup_job.sh` | JOB workload | 10-30 minutes |

Times are approximate and depend on your system specifications.

**Note**: `setup.sh` is deprecated - all base setup is now in `devcontainer.json`.

