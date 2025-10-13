# Ensemble Mode Implementation Summary

## Overview
Implemented `--ensemble-mode` flag that runs all 4 optimizers (SMAC, MBO, DDPG, GA) in parallel. Each iteration gets 4 suggestions (one from each optimizer), evaluates all 4 configurations, and adds all observations to the shared history.

## Changes Made

### 1. scripts/optimize.py
- Added `--ensemble-mode` command-line argument
- Passed `ensemble_mode` parameter to DBTuner constructor

### 2. autotune/tuner.py
- Added `ensemble_mode` parameter to `__init__` method
- Stored `ensemble_mode` as instance variable
- Passed `ensemble_mode` to PipleLine constructor in `tune()` method

### 3. autotune/pipleline/pipleline.py
**Key changes:**

- **__init__**: Added `ensemble_mode` parameter
- **Optimizer initialization**: Modified condition to create all 4 optimizers when `ensemble_mode=True` (similar to `auto_optimizer` mode)
- **iterate()**: Added ensemble mode logic to:
  - Get suggestions from all 4 optimizers
  - Evaluate all 4 configurations
  - Return list of results instead of single result
- **run()**: Added ensemble mode handling to:
  - Process list of results from iterate()
  - Log each optimizer's performance
  - Update DDPG and GA optimizers
  - Increment iteration_id once per iteration (not per optimizer)
  - Track best result for space exploration decisions
- **evaluate()**: Modified to skip iteration_id increment and optimizer updates when in ensemble mode (handled in run() instead)
- **Space transfer conditions**: Updated all conditions to include `ensemble_mode`

### 4. scripts/twitter_ensemble.ini
- Created new config file by copying twitter.ini
- Changed `task_id` to `oltpbench_twitter_ensemble`
- Added comment explaining ensemble mode usage

## Usage

```bash
# Run with ensemble mode
python scripts/optimize.py --config scripts/twitter_ensemble.ini --ensemble-mode

# Or use with any other config
python scripts/optimize.py --config scripts/cluster.ini --ensemble-mode
```

## Expected Behavior

- **Iterations**: For `max_runs=200`, there will be 200 iterations
- **Evaluations**: Each iteration evaluates 4 configurations = 800 total evaluations
- **History**: All 4 observations per iteration are added to history
- **Optimizers**: All 4 optimizers learn from all observations (shared history)
- **Logging**: Each optimizer's result is logged separately:
  ```
  [Ensemble][SMAC] Iteration 1, objective value: [1234.5].
  [Ensemble][MBO] Iteration 1, objective value: [1220.3].
  [Ensemble][DDPG] Iteration 1, objective value: [1198.7].
  [Ensemble][GA] Iteration 1, objective value: [1205.2].
  ```

## Key Design Decisions

1. **Shared History**: All 4 optimizers share the same `history_container`, learning from each other's observations
2. **Optimizer Order**: SMAC, MBO, DDPG, GA (matches `optimizer_list` order)
3. **DDPG/GA Updates**: These optimizers need special `update()` calls with observations
4. **Iteration Counting**: `iteration_id` increments once per run() iteration, not per evaluate() call
5. **Space Transfer Compatible**: Ensemble mode works with `space_transfer` if both enabled
6. **Best Tracking**: Uses the best result among 4 optimizers for space exploration decisions

## Testing

To verify the implementation works:

```bash
# Quick test with small max_runs
cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate

# Check that the flag is recognized
python scripts/optimize.py --help | grep ensemble

# Run a short test (if MySQL is ready and databases are populated)
# python scripts/optimize.py --config scripts/twitter_ensemble.ini --ensemble-mode
```

## Files Modified

1. `scripts/optimize.py` - Added CLI argument and passed to tuner
2. `autotune/tuner.py` - Added parameter and passed to pipeline
3. `autotune/pipleline/pipleline.py` - Main implementation
4. `scripts/twitter_ensemble.ini` - New config file (created)

## Performance Expectations

- **Exploration**: 4× more configurations explored per iteration
- **Convergence**: Potentially faster convergence due to parallel exploration by different algorithms
- **Runtime**: Each iteration takes ~4× longer (sequential evaluation of 4 configs)
- **Total Time**: For same number of iterations, ~4× runtime vs single optimizer mode
