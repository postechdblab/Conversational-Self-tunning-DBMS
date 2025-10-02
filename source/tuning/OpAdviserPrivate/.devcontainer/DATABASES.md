# Database Setup Guide

## Automatic Setup

When you create or rebuild the dev container, databases are **automatically populated in the background**. This process takes 30-60 minutes.

### Check Setup Progress

```bash
# View live progress
tail -f /tmp/database_setup.log

# Check status
bash .devcontainer/check_database_status.sh
```

## Available Databases

After setup completes, the following databases will be available:

### OLTPBench Workloads
- **twitter** - Twitter social network workload
- **tpcc** - TPC-C OLTP benchmark
- **ycsb** - Yahoo! Cloud Serving Benchmark
- **wikipedia** - Wikipedia workload
- **tatp** - Telecom Application Transaction Processing
- **voter** - Voter application workload

### TPC-H
- **tpch** - TPC-H decision support benchmark (scale factor 10)

### Sysbench
- **sbrw** - Sysbench read-write workload (800K rows, 300 tables)
- **sbwrite** - Sysbench write-only workload (800K rows, 300 tables)
- **sbread** - Sysbench read-only workload (800K rows, 300 tables)

### JOB (Join Order Benchmark)
- **imdbload** - IMDB database (if available)

## Manual Setup

### Setup All Databases
```bash
bash .devcontainer/setup_all_databases.sh
```

### Setup Individual Benchmarks

```bash
# OLTPBench (twitter, tpcc, ycsb, wikipedia, tatp, voter)
bash .devcontainer/setup_oltpbench.sh

# TPC-H
bash .devcontainer/setup_tpch.sh

# Sysbench (read-write, write-only, read-only)
bash .devcontainer/setup_sysbench.sh

# JOB
bash .devcontainer/setup_job.sh
```

## Connecting to MySQL

```bash
# Using the connection script
./mysql-connect.sh

# Or directly
mysql -u root -ppassword -h localhost -P 3306

# List all databases
./mysql-connect.sh -e "SHOW DATABASES;"
```

## Running Optimization Scripts

After databases are populated:

```bash
cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate
export PYTHONPATH=.

# Run optimization for different workloads
python scripts/optimize.py --config=scripts/twitter.ini
python scripts/optimize.py --config=scripts/tpcc.ini
python scripts/optimize.py --config=scripts/ycsb.ini
python scripts/optimize.py --config=scripts/tpch.ini
python scripts/optimize.py --config=scripts/sysbench_rw.ini
```

## Troubleshooting

### Check if MySQL is Running
```bash
sudo service mysql status
# If not running:
sudo service mysql start
```

### View Setup Logs
```bash
# Full log
cat /tmp/database_setup.log

# Last 50 lines
tail -50 /tmp/database_setup.log

# Live tail
tail -f /tmp/database_setup.log
```

### Check Setup Status
```bash
bash .devcontainer/check_database_status.sh
```

### Restart Setup
If setup fails or is interrupted:
```bash
# Stop any running setup
pkill -f setup_all_databases.sh

# Restart
bash .devcontainer/setup_all_databases.sh
```

## Configuration

All setup scripts use:
- **MySQL Host:** localhost
- **MySQL Port:** 3306
- **MySQL User:** vscode (or your username)
- **MySQL Password:** password

To modify these, edit the individual setup scripts in `.devcontainer/`.


