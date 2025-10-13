# Ensemble Mode Usage Guide

## Overview

Ensemble mode can now be configured in two ways:
1. **Config file** - Set `ensemble_mode` in the `.ini` file
2. **CLI flag** - Use `--ensemble-mode` flag (overrides config)

## Configuration Files

### twitter.ini (Single Optimizer Mode)
```ini
[tune]
ensemble_mode = False
```
- Runs with a single optimizer (specified by `optimize_method`)
- Standard tuning mode

### twitter_ensemble.ini (Ensemble Mode)
```ini
[tune]
ensemble_mode = True
```
- Automatically runs all 4 optimizers (SMAC, MBO, DDPG, GA)
- No need to specify CLI flag

## Usage Examples

### 1. Using Config File Setting

```bash
# Single optimizer mode (from twitter.ini)
python scripts/optimize.py --config scripts/twitter.ini

# Ensemble mode (from twitter_ensemble.ini)
python scripts/optimize.py --config scripts/twitter_ensemble.ini
```

### 2. Using CLI Flag Override

```bash
# Override twitter.ini: False → True
python scripts/optimize.py --config scripts/twitter.ini --ensemble-mode

# Override any config to enable ensemble mode
python scripts/optimize.py --config scripts/cluster.ini --ensemble-mode
```

## Configuration Priority

The system resolves `ensemble_mode` in this order (highest to lowest priority):

1. **CLI flag** (`--ensemble-mode`) - if provided → `True`
2. **INI file setting** (`ensemble_mode = True/False`)
3. **Default value** (`False`)

## Quick Reference

| Config File | ensemble_mode Setting | CLI Flag | Result |
|-------------|----------------------|----------|---------|
| twitter.ini | False | (none) | Single optimizer |
| twitter.ini | False | --ensemble-mode | **Ensemble mode** |
| twitter_ensemble.ini | True | (none) | **Ensemble mode** |
| twitter_ensemble.ini | True | --ensemble-mode | **Ensemble mode** |

## Expected Behavior

### Single Optimizer Mode (ensemble_mode=False)
- Runs 1 optimizer per iteration
- max_runs=200 → 200 evaluations total
- Uses optimizer specified by `optimize_method` in config

### Ensemble Mode (ensemble_mode=True)
- Runs 4 optimizers per iteration (SMAC, MBO, DDPG, GA)
- max_runs=200 → 800 evaluations total (200 × 4)
- All optimizers share history and learn from each other
- Log output shows each optimizer's result:
  ```
  [Ensemble][SMAC] Iteration 1, objective value: [X].
  [Ensemble][MBO] Iteration 1, objective value: [Y].
  [Ensemble][DDPG] Iteration 1, objective value: [Z].
  [Ensemble][GA] Iteration 1, objective value: [W].
  ```

## Files Modified

1. `scripts/twitter.ini` - Added `ensemble_mode = False`
2. `scripts/twitter_ensemble.ini` - Added `ensemble_mode = True`
3. `autotune/utils/config.py` - Added default value for `ensemble_mode`
4. `scripts/optimize.py` - Added logic to read from config with CLI override

## Recommendation

**Use config file setting** for most cases:
- More explicit and self-documenting
- No need to remember CLI flags
- Easy to track which mode was used in experiments

**Use CLI flag** for:
- Quick tests without modifying config files
- Overriding existing configs for comparison
- Ad-hoc ensemble mode trials
