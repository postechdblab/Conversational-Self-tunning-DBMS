# 🚨 CRITICAL ISSUE: Data Loss from `lower_case_table_names` During Tuning

**STATUS**: ❌ **DATA LOSS OCCURRED** - TPC-C database is empty and must be reloaded

**DATE**: October 20, 2025

**SEVERITY**: CRITICAL - Production data destroyed, experiments halted

---

## 📋 Quick Summary

Your TPC-C database data was **destroyed during tuning** when the optimizer tried `lower_case_table_names=1`. This is a known MySQL limitation on Linux that causes data loss. The experiment then crashed because all benchmarks failed.

**Current State**:
- ❌ TPC-C: Tables exist but EMPTY (0 rows)
- ✅ Twitter: Still has data (25,000 rows)
- ❌ All TPC-C experiments: FAILING
- ❌ tpcc_ensemble: Crashed with `IndexError`

## 🔥 Immediate Actions Required

### 1️⃣ Reload TPC-C Data (~ 10 minutes)
```bash
cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate
bash scripts/quick_init_tpcc.sh
```

### 2️⃣ Fix Knob Configuration
```bash
bash scripts/fix_dangerous_knobs.sh
```
This will mark `lower_case_table_names` as non-tunable to prevent recurrence.

### 3️⃣ Verify Data Loaded
```bash
mysql -uroot -ppassword -e "SELECT COUNT(*) FROM tpcc.WAREHOUSE;" 2>&1 | grep -v password
# Should show: 10 (quick) or 175 (full)
```

### 4️⃣ Resume Experiments
```bash
bash scripts/run_experiments_machine1.sh
```

---

## 📊 What Happened (Timeline)

1. **✅ Oct 17, 2025**: TPC-C tuning was working perfectly
   - `tpcc_ga` completed 200 iterations successfully
   - Final performance: -6458.39 TPS

2. **❌ Oct 17, Iteration 199**: Genetic algorithm tried this configuration:
   ```python
   'lower_case_table_names': 1  # ⚠️ THE CULPRIT
   ```

3. **💥 After MySQL Restart**: Data became inaccessible
   - Original tables: `WAREHOUSE`, `DISTRICT` (uppercase)
   - With new setting: MySQL looks for `warehouse`, `district` (lowercase)
   - **Result**: Tables exist but contain 0 rows

4. **🛑 Oct 19, 2025**: New experiment suite started
   - All TPC-C benchmarks failed immediately (error 255)
   - 258 benchmark failures logged
   - Final crash: `IndexError: list index out of range`

## 🔍 Root Cause Analysis

### The Problem

**`lower_case_table_names`** is a MySQL system variable that controls:
- How table names are stored on disk
- Whether table names are case-sensitive

### Why It Caused Data Loss

On Linux/Unix systems (case-sensitive filesystems):
1. **Default (`lower_case_table_names=0`)**: Table names are case-sensitive
   - Table `WAREHOUSE` is stored as `WAREHOUSE.ibd` on disk

2. **After changing to 1**: MySQL expects lowercase names
   - MySQL looks for `warehouse.ibd` on disk
   - Can't find it (file is actually `WAREHOUSE.ibd`)
   - **Result**: Table appears empty, data is inaccessible

### From MySQL Documentation

> "You should not set lower_case_table_names to 0 if you are running MySQL on a case-insensitive file system... **It is prohibited to start the server with a lower_case_table_names setting different from when the data directory was initialized.**"

**Translation**: This setting should NEVER change after data is loaded.

## 🛠️ How We Fixed It

### 1. Code Fix: Handle Empty Results Gracefully

**File**: `autotune/optimizer/bo_optimizer.py`

**Added safety check** (lines 447-453):
```python
incumbents = history_container.get_incumbents()
if not incumbents:
    self.logger.error('[BO] No successful runs recorded. All benchmarks have failed.')
    self.logger.error('[BO] This likely means the database is not initialized or benchmarks are failing.')
    self.logger.error('[BO] Falling back to random sampling.')
    return self.sample_random_configs(num_configs=1, excluded_configs=history_container.configurations)[0]

incumbent_value = incumbents[0][1]  # Now safe to access
```

**Impact**: Prevents crashes, provides clear error messages, falls back gracefully.

### 2. Created Recovery Scripts

| Script | Purpose | Time |
|--------|---------|------|
| `scripts/quick_init_tpcc.sh` | Quick TPC-C setup (10 warehouses) | ~10 min |
| `scripts/init_oltpbench_databases.sh` | Full initialization (all workloads) | ~4 hours |
| `scripts/fix_dangerous_knobs.sh` | Automatically fix knob configuration | ~30 sec |

### 3. Created Documentation

| Document | Purpose |
|----------|---------|
| `CRITICAL_ISSUE_README.md` (this file) | Quick reference |
| `SOLUTION_SUMMARY.md` | Step-by-step solution guide |
| `EXPERIMENT_FAILURE_ANALYSIS.md` | Detailed technical analysis |

## ⚠️ Prevention Measures

### Dangerous Knobs to NEVER Tune

These knobs should be marked `"tunable": false` in your configuration:

| Knob | Why Dangerous | Consequence |
|------|---------------|-------------|
| **`lower_case_table_names`** | Changes table name case sensitivity | **DATA LOSS on Linux** |
| `datadir` | Changes data directory location | Database unreachable |
| `skip_networking` | Disables network access | Cannot connect to DB |
| `innodb_data_home_dir` | Changes InnoDB data location | Data inaccessible |
| `innodb_log_group_home_dir` | Changes InnoDB log location | Startup failures |
| `log_bin` | Changes binary logging state | Requires clean restart |

### Run the Fix Script

```bash
bash scripts/fix_dangerous_knobs.sh
```

This will:
- ✅ Check all dangerous knobs in your configuration
- ✅ Automatically mark them as non-tunable
- ✅ Create a backup of your original config
- ✅ Prevent this issue from happening again

### Add Pre-Flight Checks

Before starting experiments, verify data exists:

```python
# Add to your experiment startup code
def verify_database_health():
    """Check that databases have data before starting"""
    checks = [
        ("tpcc", "WAREHOUSE", 10),      # At least 10 warehouses
        ("twitter", "user_profiles", 1000),  # At least 1000 users
    ]
    
    for db, table, min_rows in checks:
        count = execute_query(f"SELECT COUNT(*) FROM {db}.{table}")
        if count < min_rows:
            raise RuntimeError(
                f"Database {db}.{table} has insufficient data "
                f"({count} rows, expected >={min_rows}). "
                f"Run data initialization scripts first!"
            )
    
    logger.info("✓ All databases verified healthy")

# Call before experiment
verify_database_health()
```

### Database Backup Strategy

For long-running experiments:

```bash
# Option 1: mysqldump (slower but portable)
mysqldump -uroot -ppassword tpcc > /backups/tpcc_$(date +%Y%m%d).sql

# Option 2: Filesystem snapshot (faster)
lvcreate -s -n mysql_snap -L 10G /dev/vg/mysql

# Option 3: Physical backup with Percona XtraBackup
xtrabackup --backup --target-dir=/backups/mysql_$(date +%Y%m%d)
```

## 📁 Files Created/Modified

### New Files
- ✅ `CRITICAL_ISSUE_README.md` (this file)
- ✅ `SOLUTION_SUMMARY.md`
- ✅ `EXPERIMENT_FAILURE_ANALYSIS.md`
- ✅ `scripts/quick_init_tpcc.sh`
- ✅ `scripts/init_oltpbench_databases.sh`
- ✅ `scripts/fix_dangerous_knobs.sh`

### Modified Files
- ✅ `autotune/optimizer/bo_optimizer.py` (added safety check)

### Backup Files
- 📦 `scripts/experiment/gen_knobs/mysql_all_197_32G.json.backup.*` (created by fix script)

## 🎯 Action Checklist

Use this checklist to ensure complete recovery:

- [ ] **Run data reload script**
  ```bash
  bash scripts/quick_init_tpcc.sh
  ```

- [ ] **Verify data loaded**
  ```bash
  mysql -uroot -ppassword -e "SELECT COUNT(*) FROM tpcc.WAREHOUSE;"
  # Should show 10 or 175
  ```

- [ ] **Fix knob configuration**
  ```bash
  bash scripts/fix_dangerous_knobs.sh
  ```

- [ ] **Verify knobs are fixed**
  ```bash
  grep -A 5 '"lower_case_table_names"' scripts/experiment/gen_knobs/mysql_all_197_32G.json
  # Should show "tunable": false
  ```

- [ ] **Test single benchmark**
  ```bash
  bash autotune/cli/run_oltpbench.sh tpcc /oltpbench/config/sample_tpcc_config.xml test_$(date +%s)
  # Should complete without errors
  ```

- [ ] **Resume experiments**
  ```bash
  bash scripts/run_experiments_machine1.sh
  ```

- [ ] **Monitor first few iterations**
  ```bash
  tail -f logs/machine1_experiments.log
  # Watch for successful benchmarks
  ```

## ❓ FAQ

### Q: Can the original data be recovered?
**A**: No. The data is not deleted, but it's inaccessible due to the case mismatch. You must reload it.

### Q: Why didn't this affect Twitter/YCSB/Wikipedia?
**A**: Only TPC-C was running when the setting changed. The other databases are fine.

### Q: Will the quick script (10 warehouses) affect my results?
**A**: It will give different absolute TPS values, but relative improvements should be similar. You can upgrade to 175 warehouses later.

### Q: How do I prevent other similar issues?
**A**: 
1. Run `bash scripts/fix_dangerous_knobs.sh`
2. Add pre-flight data checks to your experiments
3. Consider database snapshots before long tuning runs

### Q: Why was this knob even included in tuning?
**A**: It's a valid MySQL parameter that can affect performance. However, it's dangerous to change after initialization, which should have been marked in the configuration.

## 📞 Support

If you encounter issues during recovery:

1. **Check logs**: `logs/machine1_experiments.log`
2. **Check MySQL status**: `ps aux | grep mysqld`
3. **Check disk space**: `df -h`
4. **Verify OLTP-Bench**: `ls -la /oltpbench/oltpbenchmark`

## 🔗 Related Documentation

- MySQL Documentation: [lower_case_table_names](https://dev.mysql.com/doc/refman/5.7/en/identifier-case-sensitivity.html)
- OLTP-Bench: [Loading Data](https://github.com/oltpbenchmark/oltpbench/wiki)
- TPC-C Specification: [www.tpc.org/tpcc](http://www.tpc.org/tpcc/)

---

**Last Updated**: October 20, 2025

**Status**: 🔴 **ACTIVE ISSUE** - Requires immediate action

**Priority**: 🚨 **P0 - CRITICAL** - Data loss, experiments halted

---

## 💡 Lessons Learned

1. **Not all MySQL parameters are safe to tune dynamically**
   - Some require specific initialization states
   - Some cause data loss when changed
   - Need explicit exclusion lists

2. **Data integrity checks are essential**
   - Should verify data exists before each experiment
   - Should monitor for unexpected data loss during tuning
   - Should have backup/recovery procedures

3. **Better error messages save time**
   - The original `IndexError` gave no context
   - New error messages clearly indicate the problem
   - Helps debug issues faster

4. **Documentation prevents repeat issues**
   - Clear identification of dangerous knobs
   - Automated scripts for prevention
   - Comprehensive recovery procedures

---

**Remember**: After fixing this issue, run `bash scripts/fix_dangerous_knobs.sh` to prevent it from happening again!

