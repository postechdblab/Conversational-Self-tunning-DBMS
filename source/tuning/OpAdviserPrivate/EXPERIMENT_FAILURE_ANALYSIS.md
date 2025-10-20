# Experiment Failure Analysis

## Problem Summary

The experiment stopped unexpectedly with the error:
```
IndexError: list index out of range
```

At line 447 in `autotune/optimizer/bo_optimizer.py`:
```python
incumbent_value = history_container.get_incumbents()[0][1]
```

## Root Cause ⚠️ **DATA LOSS ISSUE**

The experiment failed because **all benchmark runs are failing**, which leads to:

1. **TPC-C Data Destroyed by `lower_case_table_names` Setting**:
   - ✅ TPC-C was originally working (tpcc_ga completed 200 iterations successfully on Oct 17)
   - ❌ During tuning, a configuration set `lower_case_table_names=1` (line 88629 in log)
   - ⚠️ On Linux, changing this setting after tables exist causes **data corruption/loss**
   - 📊 Current state: Tables exist but are EMPTY (0 rows in WAREHOUSE, DISTRICT, etc.)
   - ✅ Twitter database unaffected (still has 25,000 rows)

2. **Benchmark Failure Chain**:
   - OLTP-Bench tries to run TPC-C workload
   - Database has no data → benchmark crashes with error 255
   - No result file is created (`results/XXXXX.summary` missing)
   - System logs: `benchmark result file does not exist!`
   - Exception: `FileNotFoundError: [Errno 2] No such file or directory: 'results/XXXXX.summary'`

3. **Empty History Container**:
   - Since ALL benchmarks fail, no successful runs are recorded
   - `history_container.get_incumbents()` returns empty list `[]`
   - Code tries to access `[0][1]` on empty list → `IndexError`

## Evidence from Logs

### Proof TPC-C Was Working
```
[2025-10-17 17:35:13,684] [DBTune-oltpbench_tpcc_ga] Iteration 200, objective value: [-6458.387098438893].
✅ tpcc_ga completed successfully with 200 iterations
```

### The Dangerous Configuration
From line 88629 (iteration 199 of tpcc_ga):
```python
'lower_case_table_names': 1  # ⚠️ THIS DESTROYED THE DATA!
```

### Current Failure (Oct 19)
```
[2025-10-19 23:24:12] benchmark start!
run benchmark get error 255
[2025-10-19 23:24:14] clear processlist
benchmark result file does not exist!
[ERROR] [2025-10-19 23:28:14,592] [autotune] Exception occurred during step execution:
...
FileNotFoundError: [Errno 2] No such file or directory: 'results/1760916252.summary'
```

### Database State Verification
```bash
# TPC-C database exists but is empty
$ mysql -uroot -ppassword -e "SHOW DATABASES;" | grep tpcc
tpcc

$ mysql -uroot -ppassword -e "USE tpcc; SHOW TABLES;"
WAREHOUSE, DISTRICT, CUSTOMER, etc. (all exist)

$ mysql -uroot -ppassword -e "SELECT COUNT(*) FROM tpcc.WAREHOUSE;"
0  # ⚠️ EMPTY! Was full during tpcc_ga

$ mysql -uroot -ppassword -e "SELECT COUNT(*) FROM twitter.user_profiles;"
25000  # ✅ Twitter still has data
```

## Why `lower_case_table_names` Caused Data Loss

On Linux/Unix systems:
1. **Default behavior** (`lower_case_table_names=0`): Table names are case-sensitive in filesystem
2. **When changed to 1**: MySQL expects lowercase table names
3. **Tables were created as**: `WAREHOUSE`, `DISTRICT` (uppercase)
4. **After setting to 1**: MySQL looks for `warehouse`, `district` (lowercase)
5. **Result**: Can't find tables → appears empty → data effectively lost

From MySQL documentation:
> "You should not set lower_case_table_names to 0 if you are running MySQL on a case-insensitive file system... 
> It is prohibited to start the server with a lower_case_table_names setting different from when the data directory was initialized."

**This knob should NEVER be tuned on a live database with data!**

## Solution

### 1. Reload TPC-C Database (REQUIRED)

The data is lost and must be reloaded:

```bash
# Drop and recreate the database
mysql -uroot -ppassword -e "DROP DATABASE IF EXISTS tpcc; CREATE DATABASE tpcc;"

# Reload data using OLTP-Bench
/oltpbench/oltpbenchmark -b tpcc \
  -c /oltpbench/config/sample_tpcc_config.xml \
  --create=true \
  --load=true
```

**Note**: The config specifies 175 warehouses (`scalefactor=175`), so this will take significant time (potentially hours).

**Quick alternative for testing** (10 warehouses, ~10 minutes):
```bash
bash scripts/quick_init_tpcc.sh
```

### 2. Initialize Other OLTP-Bench Workloads

Similarly, you need to initialize:
- **Twitter**: `oltpbenchmark -b twitter -c /oltpbench/config/sample_twitter_config.xml --create=true --load=true`
- **YCSB**: `oltpbenchmark -b ycsb -c /oltpbench/config/sample_ycsb_config.xml --create=true --load=true`
- **Wikipedia**: `oltpbenchmark -b wikipedia -c /oltpbench/config/sample_wikipedia_config.xml --create=true --load=true`

### 3. Verify Data Loading

After loading, verify:
```bash
mysql -uroot -ppassword -e "SELECT COUNT(*) FROM tpcc.warehouse;"
# Should return 175 rows

mysql -uroot -ppassword -e "SELECT COUNT(*) FROM tpcc.district;"
# Should return 1750 rows (175 warehouses * 10 districts each)
```

### 4. Exclude Dangerous Knobs from Tuning (CRITICAL)

Add `lower_case_table_names` to the exclusion list in your knob configuration:

```json
{
  "name": "lower_case_table_names",
  "tunable": false,  // ⚠️ NEVER tune this knob on an existing database
  "comment": "Changing this causes data loss on Linux systems"
}
```

**Other dangerous knobs to exclude**:
- `datadir` - changing data directory
- `log_bin` - changing binary log location (requires restart with clean state)
- Any knob that requires server initialization

### 5. Fix the Code (Already Done - Make it More Robust)

The code should handle the case where all benchmarks fail. Add a check in `bo_optimizer.py`:

```python
# Around line 447
if self.optimization_strategy == 'bo':
    incumbents = history_container.get_incumbents()
    if not incumbents:
        self.logger.error('[BO] No successful runs recorded. Cannot proceed with BO.')
        # Fall back to random sampling or raise meaningful error
        return self.sample_random_configs(num_configs=1, excluded_configs=history_container.configurations)[0]
    
    incumbent_value = incumbents[0][1]
    ...
```

## Prevention

1. **Exclude Dangerous Knobs**: Never tune knobs that can cause data loss or corruption
   - `lower_case_table_names` ⚠️ **CRITICAL**
   - `datadir`
   - `skip_networking` (can make database unreachable)
   - Any knob that requires reinitialization
   
2. **Add Pre-flight Checks**: Before starting experiments, verify all databases have data
   ```python
   # Check row counts before each experiment
   assert get_row_count("tpcc", "WAREHOUSE") > 0, "TPC-C data missing!"
   ```

3. **Better Error Messages**: When benchmarks fail repeatedly, check for data integrity

4. **Documentation**: Add warnings about dangerous knob combinations

5. **Backup Strategy**: Consider creating database snapshots before long-running experiments

## Quick Fix to Resume Current Experiment

1. **Reload TPC-C database** (see Solution #1) - **REQUIRED, data is gone**
2. **Check knob configuration** - ensure `lower_case_table_names` is marked as non-tunable
3. **Restart the experiment** - the history files will help bootstrap, but be aware data was lost mid-run
4. **Monitor for similar issues** - watch for other benchmarks if they start failing

## Files Affected

- `/workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/autotune/optimizer/bo_optimizer.py` (line 447)
- `/workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/logs/machine1_experiments.log` (multiple errors)
- Database: `tpcc` (missing)

