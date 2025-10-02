# Database Population Monitoring Guide

## 📊 Verbose Logging Features

All database setup scripts now include **verbose logging** with the following features:

### 1. Timestamped Messages
Every log entry includes a timestamp:
```
[2025-10-02 14:23:15] Setting up twitter workload...
[2025-10-02 14:25:42] ✅ twitter workload prepared!
```

### 2. Command Tracing (`set -x`)
All bash commands are printed as they execute:
```
+ mysql -h localhost -P 3306 -u vscode -ppassword -e 'CREATE DATABASE twitter;'
+ /oltpbench/oltpbenchmark -b twitter -c /oltpbench/config/sample_twitter_config.xml --create=true --load=true
```

### 3. Progress Indicators
Clear status messages with emojis:
- ✅ Success messages
- ⚠️  Warning messages
- ❌ Error messages
- 📊 Information messages

### 4. Execution Time Tracking
Each step reports how long it took:
```
[2025-10-02 14:30:00] ✅ OLTPBench workloads completed! (took 425s)
[2025-10-02 14:45:00] ✅ TPC-H workload completed! (took 900s)
Total time: 45m 25s
```

## 📺 Monitoring Progress

### Real-time Log Tail
```bash
# Follow the log in real-time
tail -f /tmp/database_setup.log

# With color highlighting (if you have ccze)
tail -f /tmp/database_setup.log | ccze -A
```

### Check Current Status
```bash
# Quick status check
bash .devcontainer/check_database_status.sh

# See last 50 lines
tail -50 /tmp/database_setup.log

# See last 100 lines with timestamps
tail -100 /tmp/database_setup.log | grep "^\["
```

### Search for Specific Events
```bash
# Find when each database completed
grep "✅.*completed" /tmp/database_setup.log

# Check for errors
grep -i "error\|fail\|❌" /tmp/database_setup.log

# See time statistics
grep "took" /tmp/database_setup.log

# Check MySQL operations
grep "mysql -h" /tmp/database_setup.log
```

### Monitor by Step
```bash
# Step 1: OLTPBench
grep "Step 1/4" -A 50 /tmp/database_setup.log

# Step 2: TPC-H
grep "Step 2/4" -A 50 /tmp/database_setup.log

# Step 3: Sysbench
grep "Step 3/4" -A 50 /tmp/database_setup.log

# Step 4: JOB
grep "Step 4/4" -A 50 /tmp/database_setup.log
```

## 📈 Typical Timeline

Based on standard hardware, expect these durations:

| Step | Benchmark | Duration | Details |
|------|-----------|----------|---------|
| 1 | OLTPBench | 15-25 min | 6 databases (twitter, tpcc, ycsb, etc.) |
| 2 | TPC-H | 15-20 min | Scale factor 10 (~10GB data) |
| 3 | Sysbench | 30-40 min | 3 databases × 300 tables × 800K rows |
| 4 | JOB | 5-10 min | IMDB dataset (if available) |
| **Total** | **All** | **65-95 min** | **~1-1.5 hours** |

## 🔍 Troubleshooting

### Setup Appears Stuck

Check if a process is actually running:
```bash
# Check for active setup processes
ps aux | grep setup_

# Check MySQL activity
mysqladmin -u root -ppassword processlist

# Check disk I/O
iostat -x 2
```

### Check Database Sizes
```bash
# List databases and their sizes
./mysql-connect.sh -e "
SELECT 
    table_schema AS 'Database',
    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'Size (MB)'
FROM information_schema.tables
GROUP BY table_schema;
"
```

### View Specific Workload Progress
```bash
# For sysbench (shows table creation progress)
./mysql-connect.sh -e "
SELECT COUNT(*) as tables_created 
FROM information_schema.tables 
WHERE table_schema = 'sbrw';
"

# For TPC-H (check if data is loading)
./mysql-connect.sh -e "
SELECT table_name, table_rows 
FROM information_schema.tables 
WHERE table_schema = 'tpch';
"
```

## 📝 Log Levels Explained

### Command Trace Lines (set -x)
```
+ mysql -h localhost ...
```
These show every command being executed (bash's `-x` flag).

### Timestamped Messages
```
[2025-10-02 14:23:15] Setting up...
```
Custom log messages with timestamps for major steps.

### Tool Output
```
Creating table sbtest1...
```
Direct output from tools (oltpbench, sysbench, etc.).

## 🎯 Quick Commands

```bash
# Is it running?
pgrep -a setup_all_databases

# How far along?
bash .devcontainer/check_database_status.sh

# Live tail
tail -f /tmp/database_setup.log

# Summary of completed steps
grep "✅.*completed" /tmp/database_setup.log

# Total time so far
grep "Total time:" /tmp/database_setup.log

# Any errors?
grep -i "error" /tmp/database_setup.log
```

## 📊 Example Verbose Output

```
[2025-10-02 14:00:00] ==========================================
[2025-10-02 14:00:00] SETTING UP ALL DATABASES FOR BENCHMARKS
[2025-10-02 14:00:00] ==========================================
[2025-10-02 14:00:00] Running as: vscode
[2025-10-02 14:00:00] ✅ MySQL is ready!
[2025-10-02 14:00:00] 
[2025-10-02 14:00:00] ==========================================
[2025-10-02 14:00:00] Step 1/4: Setting up OLTPBench workloads
[2025-10-02 14:00:00] ==========================================
[2025-10-02 14:00:00] Start time: Wed Oct  2 14:00:00 UTC 2025
+ cd /
+ sudo rm -rf oltpbench
+ sudo git clone https://github.com/seokjeongeum/oltpbench.git
...
[2025-10-02 14:25:30] ✅ OLTPBench workloads completed! (took 1530s)
```

---

**Pro Tip:** Open a split terminal in VS Code and run `tail -f /tmp/database_setup.log` to watch progress in real-time while you work! 🚀

