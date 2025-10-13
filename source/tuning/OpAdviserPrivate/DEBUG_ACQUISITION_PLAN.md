# Debug Plan: Acquisition Optimization Slowness

## Problem
Local search in acquisition optimization takes >1000 iterations and warns about infinite loop.

## Investigation Points

### 1. Verify Synthetic Exclusion
**Where**: `autotune/optimizer/acq_maximizer/ei_optimization.py` line 309
**What**: Check if `get_all_configs()` includes synthetics
**Log**: 
- Total configs from runhistory
- How many are synthetic
- Which configs are selected as init_points

### 2. Initial Points Selection  
**Where**: `_get_initial_points()` line 302-323
**What**: Log initial points and their acquisition values
**Log**:
- Number of configs from previous runs
- Top N configs selected
- Their acquisition values

### 3. Acquisition Function Values
**Where**: `_one_iter()` line 325+ and local search loop line 338+
**What**: Track acquisition values during optimization
**Log**:
- Starting acq_val_incumbent
- Best acq_val found
- How many iterations without improvement
- Why it's not converging

### 4. Performance vs Acquisition Mismatch
**Where**: After acquisition optimization completes
**What**: Compare predicted performance with acquisition value
**Log**:
- Config selected by acquisition
- Its acquisition value
- Its predicted performance (from surrogate)
- Actual performance (after evaluation)

## Implementation

### File 1: `autotune/utils/history_container.py`
Add method to get only real (non-synthetic) configs:
```python
def get_real_configs(self):
    """Get only real (non-synthetic) configurations."""
    real_configs = []
    for i, config in enumerate(self.configurations):
        if i < len(self.synthetic_flags) and not self.synthetic_flags[i]:
            if config in self.data:  # Only configs that went through add()
                real_configs.append(config)
    return real_configs
```

### File 2: `autotune/optimizer/acq_maximizer/ei_optimization.py`

#### A. Log initial points (line 282-283)
```python
init_points = self._get_initial_points(num_points, runhistory)

# Debug logging
self.logger.info(f"[AcqOpt] Got {len(init_points)} initial points for local search")
if hasattr(runhistory, 'synthetic_flags'):
    total_configs = len(runhistory.configurations)
    synthetic_count = sum(runhistory.synthetic_flags)
    real_count = total_configs - synthetic_count
    self.logger.info(f"[AcqOpt] History contains {total_configs} configs: {real_count} real, {synthetic_count} synthetic")
    self.logger.info(f"[AcqOpt] get_all_configs() returned {len(runhistory.get_all_configs())} configs (should be real only)")
```

#### B. Log acquisition values for init points (line 285-288)
```python
acq_configs = []
# Start N local search from different random start points
for idx, start_point in enumerate(init_points):
    init_acq_val = self.acquisition_function([start_point], **kwargs)
    self.logger.debug(f"[AcqOpt] Init point {idx}: acq_val={init_acq_val}")
    
    acq_val, configuration = self._one_iter(start_point, **kwargs)
```

#### C. Enhanced logging in _one_iter (line 338-345)
```python
local_search_steps = 0
neighbors_looked_at = 0
time_n = []
improvements = 0  # Track improvements
plateau_steps = 0  # Track steps without improvement

while True:
    local_search_steps += 1
    if local_search_steps % 100 == 0:
        self.logger.info(
            f"[AcqOpt] Local search step {local_search_steps}: "
            f"current_acq={acq_val_incumbent:.6f}, improvements={improvements}, "
            f"plateau={plateau_steps}, neighbors_checked={neighbors_looked_at}"
        )
    if local_search_steps % 1000 == 0:
        self.logger.warning(
            "Local search took already %d iterations. Is it maybe "
            "stuck in a infinite loop?", local_search_steps
        )
        self.logger.warning(
            f"[AcqOpt] Stuck details: acq_val={acq_val_incumbent:.6f}, "
            f"improvements={improvements}, neighbors_checked={neighbors_looked_at}"
        )
```

#### D. Track improvements (after line 362)
```python
if acq_val > acq_val_incumbent:
    self.logger.debug("Switch to one of the neighbors")
    incumbent = neighbor
    acq_val_incumbent = acq_val
    improvements += 1
    plateau_steps = 0
    changed_inc = True
    break
else:
    plateau_steps += 1
```

### File 3: `autotune/pipleline/pipleline.py`

#### After augmentation (line 1237)
```python
self.logger.info(f"[Augmentation] Added {len(augmented_configs)} synthetic observations to history")
self.logger.info(f"[Augmentation] Total synthetic observations in history: {synthetic_count}")
self.logger.info(f"[Augmentation] Total configs in history.data: {len(self.history_container.data)}")
self.logger.info(f"[Augmentation] Verify synthetics excluded: {len(self.history_container.get_all_configs())} configs available for acquisition opt")
```

## Testing

1. Run with `--augment-history` 
2. Check logs for:
   - Are synthetics in get_all_configs()? (should be NO)
   - How many init_points?
   - What are their acquisition values?
   - Why is local search not converging?
   - Is acq_val changing or stuck?

3. Compare:
   - Number of real observations
   - Number returned by get_all_configs()
   - Should match!

