# 🚀 Quick Start Guide

## After Dev Container Rebuild

### 1. Check GPU Availability (Optional)
```bash
./check_gpu.sh
# or
nvidia-smi
```

### 2. Check Database Setup Progress
Databases are being populated automatically in the background (30-60 minutes):

```bash
# Live progress
tail -f /tmp/database_setup.log

# Status check
bash .devcontainer/check_database_status.sh
```

### 3. Connect to MySQL (Port 3306)
```bash
# Using helper script
./mysql-connect.sh

# Direct connection
mysql -u root -ppassword -h localhost -P 3306

# List databases
./mysql-connect.sh -e "SHOW DATABASES;"
```

### 4. Run Optimization Scripts
After databases are ready:

```bash
export PYTHONPATH=/workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate

# Twitter workload
python scripts/optimize.py --config=scripts/twitter.ini

# TPC-C
python scripts/optimize.py --config=scripts/tpcc.ini

# TPC-H
python scripts/optimize.py --config=scripts/tpch.ini

# Sysbench Read-Write
python scripts/optimize.py --config=scripts/sysbench_rw.ini
```

## Available Databases

After setup completes:
- `twitter`, `tpcc`, `ycsb`, `wikipedia`, `tatp`, `voter` (OLTPBench)
- `tpch` (TPC-H, scale factor 10)
- `sbrw`, `sbwrite`, `sbread` (Sysbench)
- `imdbload` (JOB)

## Manual Setup

```bash
# All databases
bash .devcontainer/setup_all_databases.sh

# Individual benchmarks
bash .devcontainer/setup_oltpbench.sh
bash .devcontainer/setup_tpch.sh
bash .devcontainer/setup_sysbench.sh
bash .devcontainer/setup_job.sh
```

## Troubleshooting

```bash
# Check MySQL
sudo service mysql status
sudo service mysql start

# View setup logs
cat /tmp/database_setup.log
tail -50 /tmp/database_setup.log

# Restart database setup
pkill -f setup_all_databases.sh
bash .devcontainer/setup_all_databases.sh > /tmp/database_setup.log 2>&1 &
```

## 📖 Full Documentation

- **Database Setup**: `.devcontainer/DATABASES.md`
- **Setup Summary**: `.devcontainer/SETUP_SUMMARY.md`
- **Main README**: `README.md`

---

**MySQL Configuration:**
- Host: `localhost` (or `127.0.0.1`)
- Port: `3306`
- User: `root`
- Password: `password`


