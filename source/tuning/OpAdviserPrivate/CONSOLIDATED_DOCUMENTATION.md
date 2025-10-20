# Consolidated Documentation - OpAdviser Project

This document consolidates all markdown documentation files from the OpAdviser project into a single comprehensive guide.

## Table of Contents

1. [Gaussian Process Training Optimization](#gaussian-process-training-optimization)
2. [Solution Summary - Experiment Issues](#solution-summary---experiment-issues)
3. [Experiment Failure Analysis](#experiment-failure-analysis)
4. [Critical Issue README](#critical-issue-readme)
5. [Bug Fixes](#bug-fixes)
6. [Project Documentation](#project-documentation)
7. [Workload Preparation](#workload-preparation)
8. [Tuning Settings](#tuning-settings)
9. [Database Settings](#database-settings)

---

## Gaussian Process Training Optimization

### Overview
This implementation modifies the ensemble mode to train the Gaussian Process model using only the **best optimizer result from each iteration** (1 out of 4), instead of using all 4 results.

### What Was Implemented

**Files Modified:**
- `autotune/pipleline/pipleline.py` - Modified `evaluate()` and `iterate()` methods

**Files Created:**
- `verify_gp_training.py` - Automated verification script
- `GP_TRAINING_DOCUMENTATION.md` - Comprehensive documentation

### How It Works

**Before (Old Behavior):**
- Ensemble mode evaluates 4 configurations per iteration
- All 4 results are added to history as "real" observations
- GP trains on all 4 results per iteration
- After N iterations: GP trains on 4×N data points

**After (New Behavior):**
- Ensemble mode evaluates 4 configurations per iteration
- System identifies which configuration has the best (lowest) objective value
- Only the best result is marked as "real" (is_synthetic=False)
- The other 3 results are marked as "synthetic" (is_synthetic=True)
- GP training filters out synthetic observations
- After N iterations: GP trains on N data points (1 best per iteration)

### Benefits

| Aspect | Before | After |
|--------|--------|-------|
| Training Samples | 4N | N |
| GP Training Time | O((4N)³) | O(N³) |
| Data Quality | Mixed | Best only |
| Exploration | 4 optimizers | 4 optimizers (unchanged) |
| Convergence | Slower | Faster |

### Usage
No code changes needed in experiment scripts. The modification is transparent:

```python
pipeline = PipleLine(
    objective_function=your_function,
    config_space=your_config_space,
    ensemble_mode=True,  # Just enable ensemble mode
    # ... other parameters
)
pipeline.run()
```

---

## Solution Summary - Experiment Issues

### Problem Identified
The experiment crashed with `IndexError: list index out of range` because **all benchmark runs were failing** after the TPC-C database data was destroyed.

### Root Cause ⚠️ **CRITICAL DATA LOSS ISSUE**
The `lower_case_table_names=1` setting **destroyed your TPC-C data** during tuning!

**What Happened:**
1. **✅ Oct 17**: TPC-C was working perfectly (tpcc_ga completed 200 iterations successfully)
2. **❌ During iteration 199**: The GA optimizer tried a configuration with `lower_case_table_names: 1`
3. **⚠️ After MySQL restart**: This setting change caused data loss on Linux
4. **📊 Current State**: TPC-C tables exist but are EMPTY (0 rows)

### What You MUST Do

**STEP 1: Reload TPC-C Data (REQUIRED)**
```bash
cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate
bash scripts/quick_init_tpcc.sh
```

**STEP 2: Fix Knob Configuration (CRITICAL!)**
Check current configuration:
```bash
grep -A 5 '"lower_case_table_names"' scripts/experiment/gen_knobs/mysql_all_197_32G.json
```

If it shows as tunable, disable it:
```json
{
  "name": "lower_case_table_names",
  "tunable": false,  // ⚠️ SET TO FALSE!
  "comment": "NEVER tune - causes data loss on Linux"
}
```

**STEP 3: Verify Data Loaded Correctly**
```bash
mysql -uroot -ppassword -e "SELECT COUNT(*) as warehouses FROM tpcc.WAREHOUSE;"
# Should show: 10 (quick) or 175 (full)
```

**STEP 4: Restart Your Experiment**
```bash
bash scripts/run_experiments_machine1.sh
```

### Prevention for Future ⚠️

**Dangerous Knobs to NEVER Tune:**
| Knob | Why Dangerous | Impact |
|------|---------------|--------|
| `lower_case_table_names` | Changes table name case sensitivity | **DATA LOSS on Linux** |
| `datadir` | Changes data directory location | Database becomes unreachable |
| `skip_networking` | Disables network access | Cannot connect to DB |
| `log_bin` | Changes binary logging state | Requires clean restart |

---

## Experiment Failure Analysis

### Problem Summary
The experiment stopped unexpectedly with the error:
```
IndexError: list index out of range
```

At line 447 in `autotune/optimizer/bo_optimizer.py`:
```python
incumbent_value = history_container.get_incumbents()[0][1]
```

### Root Cause ⚠️ **DATA LOSS ISSUE**

**TPC-C Data Destroyed by `lower_case_table_names` Setting:**
- ✅ TPC-C was originally working (tpcc_ga completed 200 iterations successfully on Oct 17)
- ❌ During tuning, a configuration set `lower_case_table_names=1`
- ⚠️ On Linux, changing this setting after tables exist causes **data corruption/loss**
- 📊 Current state: Tables exist but are EMPTY (0 rows in WAREHOUSE, DISTRICT, etc.)

**Benchmark Failure Chain:**
1. OLTP-Bench tries to run TPC-C workload
2. Database has no data → benchmark crashes with error 255
3. No result file is created (`results/XXXXX.summary` missing)
4. System logs: `benchmark result file does not exist!`
5. Exception: `FileNotFoundError: [Errno 2] No such file or directory: 'results/XXXXX.summary'`

**Empty History Container:**
- Since ALL benchmarks fail, no successful runs are recorded
- `history_container.get_incumbents()` returns empty list `[]`
- Code tries to access `[0][1]` on empty list → `IndexError`

### Solution

**1. Reload TPC-C Database (REQUIRED)**
```bash
# Drop and recreate the database
mysql -uroot -ppassword -e "DROP DATABASE IF EXISTS tpcc; CREATE DATABASE tpcc;"

# Reload data using OLTP-Bench
/oltpbench/oltpbenchmark -b tpcc \
  -c /oltpbench/config/sample_tpcc_config.xml \
  --create=true \
  --load=true
```

**2. Exclude Dangerous Knobs from Tuning (CRITICAL)**
Add `lower_case_table_names` to the exclusion list:
```json
{
  "name": "lower_case_table_names",
  "tunable": false,  // ⚠️ NEVER tune this knob on an existing database
  "comment": "Changing this causes data loss on Linux systems"
}
```

**3. Fix the Code (Already Done)**
Added safety check in `bo_optimizer.py`:
```python
incumbents = history_container.get_incumbents()
if not incumbents:
    self.logger.error('[BO] No successful runs recorded. Cannot proceed with BO.')
    return self.sample_random_configs(num_configs=1, excluded_configs=history_container.configurations)[0]

incumbent_value = incumbents[0][1]
```

---

## Critical Issue README

### 🚨 CRITICAL ISSUE: Data Loss from `lower_case_table_names` During Tuning

**STATUS**: ❌ **DATA LOSS OCCURRED** - TPC-C database is empty and must be reloaded

**SEVERITY**: CRITICAL - Production data destroyed, experiments halted

### 📋 Quick Summary
Your TPC-C database data was **destroyed during tuning** when the optimizer tried `lower_case_table_names=1`. This is a known MySQL limitation on Linux that causes data loss.

**Current State:**
- ❌ TPC-C: Tables exist but EMPTY (0 rows)
- ✅ Twitter: Still has data (25,000 rows)
- ❌ All TPC-C experiments: FAILING
- ❌ tpcc_ensemble: Crashed with `IndexError`

### 🔥 Immediate Actions Required

**1️⃣ Reload TPC-C Data (~ 10 minutes)**
```bash
cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate
bash scripts/quick_init_tpcc.sh
```

**2️⃣ Fix Knob Configuration**
```bash
bash scripts/fix_dangerous_knobs.sh
```

**3️⃣ Verify Data Loaded**
```bash
mysql -uroot -ppassword -e "SELECT COUNT(*) FROM tpcc.WAREHOUSE;" 2>&1 | grep -v password
# Should show: 10 (quick) or 175 (full)
```

**4️⃣ Resume Experiments**
```bash
bash scripts/run_experiments_machine1.sh
```

### 🔍 Root Cause Analysis

**Why It Caused Data Loss:**
On Linux/Unix systems (case-sensitive filesystems):
1. **Default (`lower_case_table_names=0`)**: Table names are case-sensitive
   - Table `WAREHOUSE` is stored as `WAREHOUSE.ibd` on disk
2. **After changing to 1**: MySQL expects lowercase names
   - MySQL looks for `warehouse.ibd` on disk
   - Can't find it (file is actually `WAREHOUSE.ibd`)
   - **Result**: Table appears empty, data is inaccessible

### ⚠️ Prevention Measures

**Dangerous Knobs to NEVER Tune:**
| Knob | Why Dangerous | Consequence |
|------|---------------|-------------|
| **`lower_case_table_names`** | Changes table name case sensitivity | **DATA LOSS on Linux** |
| `datadir` | Changes data directory location | Database unreachable |
| `skip_networking` | Disables network access | Cannot connect to DB |
| `innodb_data_home_dir` | Changes InnoDB data location | Data inaccessible |

---

## Bug Fixes

### Summary
Fixed critical issues that caused experiment failures during the Twitter ensemble experiments at iteration 47.

### Issues Fixed

**1. DDPG Batch Normalization Error (CRITICAL)**
- **Error:** `ValueError: Expected more than 1 value per channel when training, got input size torch.Size([1, 128])`
- **Location:** `autotune/optimizer/surrogate/ddpg/ddpg.py:459`
- **Fix:** Added explicit `self.target_actor.eval()` and `self.target_critic.eval()` calls before using target networks for inference

**2. OLTPBench Parsing Error**
- **Error:** `IndexError: list index out of range` at `parser.py:164`
- **Location:** `autotune/utils/parser.py:164`
- **Fix:** Added validation checks before accessing list elements and return failure metrics when parsing fails

**3. Exception Logging in DBEnv**
- **Enhancement:** Improved exception logging in `dbenv.py`
- **Change:** Removed redundant `traceback.print_exc()` call, now using `logger.exception()`

**4. Experiment Runner Resilience**
- **Enhancement:** Allow experiments to continue even if individual experiments fail
- **Change:** Commented out `set -e` in all three experiment runner scripts

### Performance Optimization - October 16, 2025

**Issue: Slow Acquisition Optimization in Ensemble Mode**
- **Problem:** Twitter ensemble experiment was getting stuck during acquisition optimization
- **Root Cause:** Default `LocalSearch` parameters were too aggressive for large configuration spaces (197 knobs)
- **Fix:** Optimized `LocalSearch` parameters:
  - `max_steps`: 300 → **50** (6x faster termination)
  - `neighbor_cap`: 1000 → **150** (6.7x fewer evaluations per step)
  - `small_gain_patience`: 50 → **15** (3.3x faster early stopping)

**Expected Impact:**
- ~10x speedup in acquisition optimization
- Reduced time per iteration from ~5 minutes to ~30 seconds
- Should complete 200 iterations in ~2-3 hours instead of 15+ hours

---

## Project Documentation

### UniTune
This is the source code to the paper "A Unified and Efficient Coordinating Framework for Autonomous DBMS Tuning".

### Installation
1. **Preparations:** Python == 3.7
2. **Install packages:**
   ```shell
   pip install -r requirements.txt
   ```

### Benchmark Preparation

**Join-Order-Benchmark (JOB)**
- Download IMDB Data Set from http://homepages.cwi.nl/~boncz/job/imdb.tgz
- Follow instructions: https://github.com/winkyao/join-order-benchmark

**TPC-H**
- Download TPC-H Data Set from https://www.tpc.org/
- Follow instructions: https://github.com/catarinaribeir0/queries-tpch-dbgen-mysql

### Experimental Evaluation

**Setup**
Modify user-specified parameters in `config.ini`:

```ini
[database]
dbtype = mysql
host = 127.0.0.1
port = 3306
user = root
passwd =
dbname = tpch
sock = /mysql/base/mysql.sock
cnf = /MultiTune/default.cnf
mysqld = mysql/mysqlInstall/bin/mysqld
knob_config_file = /MultiTune/knob_configs/mysql_new.json
knob_num = 50
workload_name = TPCH
workload_timeout = 600
workload_qlist_file = /MultiTune/scripts/tpch_queries_list_0.txt
workload_qdir = /MultiTune/queries/tpch_queries_mysql_0/
scripts_dir = /MultiTune/scripts/
q_mv_file = /MultiTune/advisor/av_files/trainset/q_mv_list.txt
mv_trainset_dir = /MultiTune/advisor/av_files/trainset

[tuning]
task_id = tpch_test
components = {'knob': 'OtterTune', 'index':'DBA-Bandit', 'query':'LearnedRewrite'}
tuning_budget = 108000
sub_budget = 1200
context = True
context_type = im
context_pca_components = 5
output_file = optimize_history/tpch_test.res
index_budget = 6500
arm_method = ts
ts_use_window = True
window_size = 7
cost_aware = True
max_runs = 200
block_runs = 2
init_runs = 10
converage_judge = False
test = False
```

**Run**
To start a training session:
```python
python main.py
```

---

## Workload Preparation

### SYSBENCH

**Download and install:**
```shell
git clone https://github.com/akopytov/sysbench.git
./autogen.sh
./configure
make && make install
```

**Load data:**
```shell
sysbench --db-driver=mysql --mysql-host=$HOST --mysql-socket=$SOCK --mysql-port=$MYSQL_PORT --mysql-user=root --mysql-password=$PASSWD --mysql-db=sbtest --table_size=800000 --tables=300 --events=0 --threads=32 oltp_read_write prepare > sysbench_prepare.out
```

### OLTP-Bench

We install OLTP-Bench to use the following workload: TPC-C, SEATS, Smallbank, TATP, Voter, Twitter, SIBench.

**Download:**
```
git clone https://github.com/oltpbenchmark/oltpbench.git
```

**To run `oltpbenchmark` outside the folder, modify:**
- `./src/com/oltpbenchmark/DBWorkload.java` (Line 85)
- `./oltpbenchmark`
- `./classpath.sh`

**Install:**
```shell
ant bootstrap
ant resolve
ant build
```

---

## Tuning Settings

DBTune provides automatic algorithm selection and knowledge transfer modules so that users do not need to disturb themselves with choosing the proper algorithm to solve a specific problem.

### Automatic Algorithm Selection

DBTune currently supports 9 performance metrics, including tps, lat, qps, cpu, IO, readIO, writeIO, virtualMem, physical.

**Performance tuning (maximizing throughputs):**
```ini
task_id = performance1
performance_metric = ['tps']
```

**Resource-oriented tuning:**
```ini
task_id = resource1
performance_metric = ['-cpu']
constraints = ["200 - tps", "latency - 60"]
```

**Multiple objective tuning:**
```ini
task_id = mutiple1
performance_metric = ['tps', '-cpu]
reference_point = [0, 100]
```

### Continuous Tuning and Automatic Knowledge Transfer

**Continuous Tuning:**
- Each tuning task is identified via its task id
- Using the same task_id leads to tuning based on previous tuning data
- Set a different task_id when setting up a new tuning task

**Automatic Knowledge Transfer:**
- Tuning history for each task is stored in `DBTune_history` by default
- Historical knowledge is extracted to speed up target tuning

### Specific Tuning Setting

**Knob Selection Algorithms:**
We have implemented 5 knob selection algorithms: SHAP, fANOVA, LASSO, Gini Score, and Ablation Analysis.

```ini
knob_config_file = ~/DBTuner/scripts/experiment/gen_knobs/JOB_shap.json
knob_num = 20
selector_type = shap
initial_tunable_knob_num = 20
incremental = increase
incremental_every = 10
incremental_num = 2
```

**Configuration Optimization Algorithms:**
DBTune currently supports 6 configuration optimizers: MBO, SMAC, TPE, DDPG, TurBO and GA.

```ini
optimize_method = SMAC
```

**Knowledge Transfer:**
```ini
transfer_framework = rgpe
data_repo = /logs/bo_history
```

DBTune supports 3 transfer frameworks: workload_map, rgpe, finetune.

---

## Database Settings

DBTune supports tuning remote/local database, tuning non-dynamic knobs with restart, and tuning with resource isolation.

### Remote / Local Database

**Local host tuning:**
```ini
remote_mode = False
db = mysql
host = 127.0.0.1
port = 3306
user = root
passwd =
sock = ~/mysql/base/mysql.sock
cnf = ~/cnf/mysql.cnf
```

**Remote host tuning:**
```ini
remote_mode = True
ssh_user = 
# ... other parameters set according to remote database
```

**SSH Passwordless Login Setup:**
1. Create public and private keys: `ssh-keygen-t rsa`
2. Copy public key to `~/.ssh/authorized_keys` in remote-host
3. Test connection: `ssh -l SSH_USERNAME HOST`
4. Start remote resource monitor: `python script/remote_resource_monitor.py`

### Tuning non-dynamic knobs

```ini
online_mode = False
```

### Tuning with resource isolation

```ini
isolation_mode = True
pid = 4110
online_mode = False
```

**Setup cgroup:**
```bash
sudo cgcreate -g memory:server;
sudo cgset -r memory.limit_in_bytes='16G' server
sudo cgget -r memory.limit_in_bytes server
cgclassify -g memory:server 122220
sudo cgcreate -g cpuset:server
sudo cgset -r cpuset.cpus=0-7 server
```

---

## Summary

This consolidated documentation provides comprehensive coverage of:

1. **Gaussian Process Training Optimization** - Performance improvements for ensemble mode
2. **Critical Data Loss Issues** - Analysis and solutions for MySQL configuration problems
3. **Bug Fixes** - Resolution of DDPG, OLTPBench, and other system issues
4. **Project Setup** - Installation, benchmark preparation, and configuration
5. **Workload Preparation** - SYSBENCH and OLTP-Bench setup procedures
6. **Tuning Settings** - Algorithm selection, knowledge transfer, and optimization
7. **Database Settings** - Remote/local tuning, resource isolation, and configuration

All original content has been preserved and organized into logical sections for easy navigation and reference.
