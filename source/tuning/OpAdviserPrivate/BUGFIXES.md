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

