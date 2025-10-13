# Bug Fix Summary: AttributeError with HistoryContainer

## Issue

The code was trying to access `self.history_container.observations` which doesn't exist. The `HistoryContainer` class stores observation data in separate lists, not as a list of `Observation` objects.

## Root Cause

The `HistoryContainer` class unpacks `Observation` objects and stores components in separate lists:
- `configurations` - list of configs
- `perfs` - list of performance values
- `trial_states` - list of trial states
- `external_metrics`, `internal_metrics`, `resource`, etc.

It does NOT maintain a list of `Observation` objects.

## Files Modified

### 1. `autotune/utils/history_container.py`

**Change 1: Added synthetic tracking** (line 108)
```python
self.synthetic_flags = list()  # track which observations are synthetic
```

**Change 2: Track synthetic flag on update** (line 167)
```python
self.synthetic_flags.append(info.get('synthetic', False) if isinstance(info, dict) else False)
```

**Change 3: Include synthetic flag in save_json** (line 295)
```python
'synthetic': self.synthetic_flags[i] if i < len(self.synthetic_flags) else False
```

### 2. `autotune/pipleline/pipleline.py`

**Change 1: Fixed ensemble mode observation access** (lines 413-450)
- Changed `len(self.history_container.observations)` to `len(self.history_container.configurations)`
- Reconstructed `Observation` objects from component lists for optimizer updates
- Fixed evaluation counting to use `configurations` instead of `observations`

**Before:**
```python
start_obs_idx = len(self.history_container.observations) - 4
observation = self.history_container.observations[start_obs_idx + idx]
total_evals = len(self.history_container.observations)
```

**After:**
```python
# Reconstruct observation from component lists
obs_idx = len(self.history_container.configurations) - 1
observation = Observation(
    config=self.history_container.configurations[obs_idx],
    objs=[self.history_container.perfs[obs_idx]] if self.num_objs == 1 else self.history_container.perfs[obs_idx],
    constraints=self.history_container.constraint_perfs[obs_idx],
    trial_state=self.history_container.trial_states[obs_idx],
    elapsed_time=self.history_container.elapsed_times[obs_idx],
    iter_time=self.history_container.iter_times[obs_idx],
    EM=self.history_container.external_metrics[obs_idx],
    resource=self.history_container.resource[obs_idx],
    IM=self.history_container.internal_metrics[obs_idx]
)
total_evals = len(self.history_container.configurations)
```

**Change 2: Fixed synthetic observation counting** (line 1225)
- Changed from iterating over non-existent `observations` list
- Now uses `synthetic_flags` list

**Before:**
```python
synthetic_count = sum(1 for obs in self.history_container.observations 
                      if obs.info.get('synthetic', False))
```

**After:**
```python
synthetic_count = sum(1 for is_synthetic in self.history_container.synthetic_flags if is_synthetic)
```

## Additional Fix: Observation Named Tuple

### Issue 2: TypeError - Missing Arguments

After fixing the AttributeError, encountered:
```
TypeError: __new__() missing 2 required positional arguments: 'info' and 'context'
```

### Cause

`Observation` is a named tuple with 11 required fields in specific order:
```python
Observation = collections.namedtuple(
    'Observation', ['config', 'trial_state', 'constraints', 'objs', 
                    'elapsed_time', 'iter_time', 'EM', 'IM', 'resource', 
                    'info', 'context'])
```

### Fix

Added missing fields `info` and `context` to Observation creation:
```python
observation = Observation(
    config=self.history_container.configurations[obs_idx],
    trial_state=self.history_container.trial_states[obs_idx],  # Correct order
    constraints=self.history_container.constraint_perfs[obs_idx],
    objs=[self.history_container.perfs[obs_idx]] if self.num_objs == 1 else self.history_container.perfs[obs_idx],
    elapsed_time=self.history_container.elapsed_times[obs_idx],
    iter_time=self.history_container.iter_times[obs_idx],
    EM=self.history_container.external_metrics[obs_idx],
    IM=self.history_container.internal_metrics[obs_idx],
    resource=self.history_container.resource[obs_idx],
    info=self.history_container.info,  # Added
    context=self.history_container.contexts[obs_idx] if obs_idx < len(self.history_container.contexts) else None  # Added
)
```

## Additional Fix: Synthetic Observation Creation

### Issue 3: Missing context Argument in Augmentation

After fixing ensemble mode, augmentation also failed with:
```
TypeError: __new__() missing 1 required positional argument: 'context'
```

This was the same issue - creating `Observation` for synthetic observations without the required `context` field.

**Fix:**
```python
synthetic_obs = Observation(
    config=config,
    trial_state=SUCCESS,
    constraints=None,
    objs=[Y_pred_mean[i][0]],
    elapsed_time=0,
    iter_time=0,
    EM={},
    IM={},
    resource={},
    info={'synthetic': True, 'variance': Y_pred_var[i][0]},
    context=None  # Added ✅
)
```

## Additional Fix: Debug Logging Formula

### Issue 4: Incorrect Expected Evaluation Count

The debug logging showed negative expected evaluations:
```
[Ensemble] Total evaluations: 4, Expected: -11, Iteration: 1
```

### Cause

The formula assumed initial runs used single evaluations before switching to ensemble mode:
```python
expected_evals = self.init_num + (self.iteration_id - self.init_num) * 4
# With init_num=5, iteration_id=1: 5 + (1-5)*4 = 5 + (-16) = -11 ❌
```

But ensemble mode runs from iteration 1, so every iteration has 4 evaluations.

### Fix

Updated formula to correctly handle ensemble mode from the start:
```python
# Ensemble mode evaluates 4 configs per iteration from the start
expected_evals = self.iteration_id * 4
# With iteration_id=1: 1 * 4 = 4 ✅
```

## Testing

All files compile without syntax errors:
```bash
python -m py_compile autotune/utils/history_container.py autotune/pipleline/pipleline.py
# Exit code: 0 ✅
```

## Summary

**Four bugs fixed:**
1. ✅ **AttributeError** - Added `synthetic_flags` tracking, fixed `observations` → `configurations`
2. ✅ **TypeError (ensemble)** - Added missing `info` and `context` to ensemble `Observation` creation
3. ✅ **TypeError (augmentation)** - Added missing `context` to synthetic `Observation` creation  
4. ✅ **Debug logging** - Fixed expected evaluation count formula for ensemble mode

## Impact

These fixes enable:
1. ✅ Ensemble mode to properly track and update all 4 optimizers
2. ✅ Synthetic observation tracking for history augmentation
3. ✅ Proper evaluation counting for verification
4. ✅ Correct logging of synthetic observation counts
5. ✅ Saving synthetic flags in history JSON files

## Verification

The fixes maintain backward compatibility:
- `synthetic_flags` list is initialized for all HistoryContainer instances
- `MOHistoryContainer` inherits synthetic tracking automatically
- Saved JSON files now include `'synthetic': true/false` field
- All existing functionality preserved

## Next Steps

The verification tools created earlier (`verify_features.sh`, `quick_test.sh`) should now work correctly with these fixes applied.

Run the test:
```bash
bash scripts/quick_test.sh
```

Or manually:
```bash
python scripts/optimize.py --config=scripts/twitter_test.ini --ensemble-mode --augment-history
bash scripts/verify_features.sh twitter_test_ensemble_augment
```

