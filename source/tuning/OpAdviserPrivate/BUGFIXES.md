# Bug Fixes - October 15, 2025

## Summary
Fixed critical issues that caused experiment failures during the Twitter ensemble experiments at iteration 47.

## Issues Fixed

### 1. DDPG Batch Normalization Error (CRITICAL)
**Error:** `ValueError: Expected more than 1 value per channel when training, got input size torch.Size([1, 128])`

**Location:** `autotune/optimizer/surrogate/ddpg/ddpg.py:459`

**Root Cause:** 
- Target actor and critic networks were not explicitly set to eval mode before inference during updates
- BatchNorm1d layers require batch size > 1 in training mode
- When batch size is 1, BatchNorm fails in training mode

**Fix:**
- Added explicit `self.target_actor.eval()` and `self.target_critic.eval()` calls before using target networks for inference (lines 457-458)
- Added explicit `self.actor.train()` and `self.critic.train()` calls to ensure main networks are in training mode during updates (lines 461-462)
- Existing safety check at lines 443-446 validates batch size >= 2 before proceeding with update

**Files Modified:**
- `autotune/optimizer/surrogate/ddpg/ddpg.py`

### 2. OLTPBench Parsing Error
**Error:** `IndexError: list index out of range` at `parser.py:164`

**Location:** `autotune/utils/parser.py:164`

**Root Cause:**
- `parse_oltpbench()` function attempted to access `tps_temporal[0]` when the list was empty
- Regular expression patterns failed to match expected format in summary file
- No error handling for malformed or incomplete benchmark result files

**Fix:**
- Added validation checks before accessing list elements
- Return failure metrics `[0, MAXINT, 0, -1, -1, -1]` when parsing fails
- Added error logging with file content preview for debugging
- Imported `MAXINT` constant from `autotune.utils.constants`

**Files Modified:**
- `autotune/utils/parser.py` (lines 165-176, imports)

### 3. Exception Logging in DBEnv
**Enhancement:** Improved exception logging in `dbenv.py`

**Change:**
- Removed redundant `traceback.print_exc()` call
- Now using `logger.exception()` which automatically captures and logs full traceback
- Ensures all errors are properly logged to experiment log files

**Files Modified:**
- `autotune/dbenv.py` (line 506)

### 4. Experiment Runner Resilience
**Enhancement:** Allow experiments to continue even if individual experiments fail

**Change:**
- Commented out `set -e` in all three experiment runner scripts
- Scripts now continue running remaining experiments even if one fails
- Final summary still reports which experiments succeeded/failed
- Exit code reflects overall success/failure state

**Files Modified:**
- `scripts/run_experiments_machine1.sh`
- `scripts/run_experiments_machine2.sh`
- `scripts/run_experiments_machine3.sh`

## Testing Recommendations

1. **DDPG Batch Size Handling:**
   - Verify that experiments can proceed with small batch sizes
   - Check that target networks use eval mode (running statistics) during inference
   - Confirm main networks use train mode during updates

2. **OLTPBench Parsing:**
   - Monitor logs for parsing errors
   - Investigate any cases where parsing fails and adjust regex patterns if needed
   - Verify that malformed result files are handled gracefully

3. **Experiment Continuation:**
   - Run full experiment suites and verify all experiments are attempted
   - Check that failure summary correctly reports which experiments failed
   - Verify logs contain complete information for debugging failures

## Related Issues

The original error occurred during the Twitter ensemble experiment at:
- Iteration: 47/173 (11% complete)
- Runtime: 8h 59m elapsed
- Error cascaded from OLTPBench parsing failure → FAILED trial state → DDPG update with insufficient buffer samples

## Notes

- The timeout wait times for benchmark results were already increased from 60/120 seconds to 240 seconds
- The DDPG model includes BatchNorm layers which require special handling for batch size
- Target networks should always be in eval mode for inference to use running statistics
- Experiment runners now provide better resilience against individual experiment failures

---

# Performance Optimization - October 16, 2025

## Issue: Slow Acquisition Optimization in Ensemble Mode

**Problem:** 
- Twitter ensemble experiment was getting stuck during acquisition optimization
- Each local search was taking 10-60 seconds
- With 10 local searches per iteration and 200 iterations, this was causing extremely slow progress
- At iteration 47, the experiment had run for 5+ hours and gotten stuck

**Root Cause:**
- Default `LocalSearch` parameters were too aggressive for large configuration spaces (197 knobs)
- `max_steps=300`: Way too many steps per local search
- `neighbor_cap=1000`: Evaluating too many neighbors per iteration
- `small_gain_patience=50`: Taking too long to recognize diminishing returns
- Each acquisition function evaluation is expensive with GP surrogate on 752 configs (132 real + 620 synthetic)

**Fix:**
Optimized `LocalSearch` parameters in `autotune/optimizer/acq_maximizer/ei_optimization.py`:
- `max_steps`: 300 → **50** (6x faster termination)
- `neighbor_cap`: 1000 → **150** (6.7x fewer evaluations per step)
- `small_gain_patience`: 50 → **15** (3.3x faster early stopping)

**Expected Impact:**
- ~10x speedup in acquisition optimization
- Reduced time per iteration from ~5 minutes to ~30 seconds
- Should complete 200 iterations in ~2-3 hours instead of 15+ hours
- Minimal impact on solution quality (local search still effective with 50 steps)

**Files Modified:**
- `autotune/optimizer/acq_maximizer/ei_optimization.py` (lines 250, 255, 258)

---

# Enhanced Diagnostic Logging - October 16, 2025

## Issue: Need visibility into acquisition optimization bottlenecks

**Problem:**
- Cannot diagnose why experiments get stuck without detailed logging
- Need to identify which phase is slow: neighbor generation vs acquisition evaluation
- Need to detect infinite loops or slow convergence early

**Solution:**
Added comprehensive logging to `LocalSearch` in `autotune/optimizer/acq_maximizer/ei_optimization.py`:

### Logging Enhancements:

1. **Start of each local search:**
   - Initial acquisition value and evaluation time
   - Configuration parameters (max_steps, neighbor_cap)

2. **Progress logging every 5 steps:**
   - Current step, acquisition value, improvements
   - Neighbors evaluated, average times
   - Total elapsed time

3. **Warning every 20 steps:**
   - Detects if search is taking too long
   - Shows detailed status (plateau, small gains, etc.)

4. **Individual slow evaluations:**
   - Warns if any single acquisition evaluation takes >2 seconds
   - Helps identify specific slow configurations

5. **Completion summary:**
   - Total time and breakdown by phase
   - Time in acquisition evaluation vs neighbor generation
   - Percentage breakdown showing bottlenecks

6. **Overall acquisition optimization:**
   - Time for each of the N local searches
   - Total time and average per search

### Example Log Output:
```
[AcqOpt] Starting acquisition optimization: 10 local searches, max_steps=50, neighbor_cap=150
[AcqOpt] Starting local search 1/10
[AcqOpt] Starting local search from init_acq=156.234 (eval took 1.234s)
[AcqOpt] Step 5/50: acq=178.456, impr=3, plateau=0, neighbors=15, avg_acq=1.123s, avg_neighgen=0.012s, elapsed=18.5s
[AcqOpt] Step 10/50: acq=185.678, impr=5, plateau=2, neighbors=30, avg_acq=1.089s, avg_neighgen=0.011s, elapsed=35.2s
[AcqOpt] Local search completed: steps=13, improvements=6, final_acq=189.234
[AcqOpt] Time breakdown: total=42.1s, acq_eval=38.5s (91.4%), neighbor_gen=0.3s (0.7%), avg_per_acq=1.103s, avg_per_neighgen=0.011s
[AcqOpt] Completed local search 1/10 in 42.1s
...
[AcqOpt] Acquisition optimization completed in 389.5s (38.9s per search)
```

**Benefits:**
- Can identify exact bottleneck (acquisition eval vs neighbor generation)
- Early detection of stuck searches
- Progress visibility for long-running optimizations
- Performance profiling data for further optimization

**Files Modified:**
- `autotune/optimizer/acq_maximizer/ei_optimization.py` (multiple locations)

