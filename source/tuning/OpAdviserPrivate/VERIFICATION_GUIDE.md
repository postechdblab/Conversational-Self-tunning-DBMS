# Verification Guide: --ensemble-mode and --augment-history

This guide explains how to verify that the `--ensemble-mode` and `--augment-history` features are working correctly.

## Quick Start

### 1. Run a Test

```bash
cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate

# Option A: Using the test config file (features pre-enabled)
python scripts/optimize.py --config=scripts/twitter_test.ini

# Option B: Using CLI flags (overrides config file)
python scripts/optimize.py --config=scripts/twitter.ini --ensemble-mode --augment-history

# Option C: Using an existing config with CLI flags
python scripts/optimize.py --config=scripts/twitter.ini --ensemble-mode --augment-history
```

### 2. Verify Results

```bash
# Run verification script on test logs
bash scripts/verify_features.sh twitter_test_ensemble_augment

# Or specify a custom log file
bash scripts/verify_features.sh logs/my_task.log

# Or use default (twitter_test_ensemble_augment)
bash scripts/verify_features.sh
```

## Understanding the Features

### --ensemble-mode

**What it does:**
- Runs all 4 optimizers (SMAC, MBO, DDPG, GA) in parallel per iteration
- Evaluates 4 configurations per iteration (one from each optimizer)
- Uses the best result among the 4 for space exploration decisions

**Expected behavior:**
- After initial random runs, each iteration evaluates 4 configurations
- Logs show `[Ensemble][SMAC/MBO/DDPG/GA]` prefixes
- Total evaluations = initial_runs + (max_runs - initial_runs) × 4
- Example: 5 initial + 15 ensemble iterations = 5 + (15 × 4) = 65 evaluations

**Log indicators:**
```
[Ensemble][SMAC] Iteration 6, objective value: [123.45]
[Ensemble][MBO] Iteration 6, objective value: [125.67]
[Ensemble][DDPG] Iteration 6, objective value: [120.34]
[Ensemble][GA] Iteration 6, objective value: [128.90]
[Ensemble] Total evaluations: 24, Expected: 24, Iteration: 6
```

### --augment-history

**What it does:**
- Augments training history with synthetic observations
- Generates configurations near top-performing regions
- Uses surrogate model to predict performance
- Adds synthetic observations with `{'synthetic': True}` metadata flag

**Expected behavior:**
- Activates after iteration 0 (needs ≥ initial_runs real observations)
- Generates `augment_samples` synthetic observations per iteration (default: 10)
- Perturbs top 5 incumbent configurations with Gaussian noise
- Adds predictions to history for improved surrogate training

**Log indicators:**
```
[Augmentation] Added 10 synthetic observations to history
[Augmentation] Total synthetic observations in history: 10
[Augmentation] Added 10 synthetic observations to history
[Augmentation] Total synthetic observations in history: 20
```

## Test Configuration

The `scripts/twitter_test.ini` file is pre-configured for quick testing:

```ini
[tune]
task_id = twitter_test_ensemble_augment
max_runs = 20              # Reduced for faster testing
initial_runs = 5           # Reduced initial phase
ensemble_mode = True       # Enable ensemble
augment_history = True     # Enable augmentation
augment_samples = 10       # Synthetic obs per iteration
workload_time = 60         # Faster workload runs
```

Expected runtime: ~15-30 minutes depending on hardware.

## Verification Checklist

### Ensemble Mode Verification

- [ ] Log contains `[Ensemble][SMAC]` messages
- [ ] Log contains `[Ensemble][MBO]` messages
- [ ] Log contains `[Ensemble][DDPG]` messages
- [ ] Log contains `[Ensemble][GA]` messages
- [ ] Each iteration after initial runs has 4 objective logs
- [ ] All optimizer counts are equal
- [ ] Total evaluations = initial_runs + (iterations × 4)

### History Augmentation Verification

- [ ] Log contains `[Augmentation] Added N synthetic observations` 
- [ ] Augmentation starts after iteration 0
- [ ] N matches `augment_samples` parameter
- [ ] Augmentation happens each iteration
- [ ] Total synthetic count increases monotonically

## Manual Verification Commands

### Check Ensemble Mode

```bash
# Count total ensemble evaluations
grep -c "\[Ensemble\]" logs/twitter_test_ensemble_augment.log

# Count per optimizer
grep -c "\[Ensemble\]\[SMAC\]" logs/twitter_test_ensemble_augment.log
grep -c "\[Ensemble\]\[MBO\]" logs/twitter_test_ensemble_augment.log
grep -c "\[Ensemble\]\[DDPG\]" logs/twitter_test_ensemble_augment.log
grep -c "\[Ensemble\]\[GA\]" logs/twitter_test_ensemble_augment.log

# Show sample logs
grep "\[Ensemble\]" logs/twitter_test_ensemble_augment.log | head -20
```

### Check History Augmentation

```bash
# Find augmentation messages
grep "\[Augmentation\]" logs/twitter_test_ensemble_augment.log

# Count augmentation events
grep -c "Added.*synthetic observations" logs/twitter_test_ensemble_augment.log

# Extract synthetic observation counts
grep -oP 'Added \K\d+' logs/twitter_test_ensemble_augment.log
```

### Check Configuration Loading

```bash
# Verify ensemble_mode was detected
grep "ensemble_mode" logs/twitter_test_ensemble_augment.log

# Check what parameters were loaded
grep "args_tune" logs/twitter_test_ensemble_augment.log
```

## Troubleshooting

### Ensemble Mode Not Working

**Symptom:** No `[Ensemble]` markers in logs

**Possible causes:**
1. `ensemble_mode = False` in config file (check line 121 in config)
2. CLI flag `--ensemble-mode` not used
3. Tuning hasn't progressed past initial runs yet

**Solutions:**
```bash
# Verify config file
grep "ensemble_mode" scripts/twitter_test.ini

# Use CLI flag explicitly
python scripts/optimize.py --config=scripts/twitter.ini --ensemble-mode

# Check if tuning is running
tail -f logs/twitter_test_ensemble_augment.log
```

### Augmentation Not Running

**Symptom:** No `[Augmentation]` messages in logs

**Possible causes:**
1. `augment_history = False` in config
2. Not enough initial runs completed yet (needs > 0 iterations)
3. Surrogate model training failed
4. `len(configurations) < init_num`

**Solutions:**
```bash
# Check if initial runs completed
grep "Iteration" logs/twitter_test_ensemble_augment.log | tail -1

# Look for surrogate training errors
grep -i "surrogate" logs/twitter_test_ensemble_augment.log
grep -i "failed to train" logs/twitter_test_ensemble_augment.log

# Verify augment_history setting
grep "augment" scripts/twitter_test.ini
```

### Synthetic Observations Not in History

**Symptom:** Augmentation logs appear but count doesn't increase

**Check:**
```bash
# Verify synthetic observations are being added
grep "Total synthetic observations in history" logs/twitter_test_ensemble_augment.log

# Check for errors in observation updates
grep -i "error\|warning\|failed" logs/twitter_test_ensemble_augment.log
```

## Log File Locations

Default locations:
```
logs/
├── {task_id}.log                    # Main log file
├── {task_id}/
│   ├── history_container.json       # History with all observations
│   ├── incumbent_config.json        # Best configuration
│   └── ...
└── ...
```

For test config: `logs/twitter_test_ensemble_augment.log`

## Advanced Verification

### Check History Container

You can inspect the history container JSON to verify synthetic observations:

```python
import json

with open('logs/twitter_test_ensemble_augment/history_container.json', 'r') as f:
    history = json.load(f)

# Count synthetic observations
synthetic_count = sum(1 for obs in history['observations'] 
                      if obs['info'].get('synthetic', False))

print(f"Total observations: {len(history['observations'])}")
print(f"Synthetic observations: {synthetic_count}")
print(f"Real observations: {len(history['observations']) - synthetic_count}")

# Show sample synthetic observation
for obs in history['observations']:
    if obs['info'].get('synthetic', False):
        print(f"\nSynthetic observation:")
        print(f"  Performance: {obs['objs']}")
        print(f"  Variance: {obs['info']['variance']}")
        break
```

### Monitor Live Execution

```bash
# Watch logs in real-time
tail -f logs/twitter_test_ensemble_augment.log | grep --line-buffered -E "\[Ensemble\]|\[Augmentation\]"

# Count evaluations periodically
watch -n 5 'grep -c "objective value" logs/twitter_test_ensemble_augment.log'
```

## Expected Test Results

For `scripts/twitter_test.ini` with default settings:

```
Configuration:
- max_runs: 20
- initial_runs: 5
- augment_samples: 10
- ensemble_mode: True
- augment_history: True

Expected Results:
- Initial phase: 5 random configurations
- Ensemble phase: 15 iterations × 4 optimizers = 60 configurations
- Total evaluations: 65
- Augmentation events: 15 (one per ensemble iteration)
- Total synthetic observations: 150 (15 iterations × 10 samples)
```

## Integration with CI/CD

You can use the verification script in automated testing:

```bash
#!/bin/bash
# run_and_verify.sh

# Run tuning
python scripts/optimize.py --config=scripts/twitter_test.ini

# Verify results
bash scripts/verify_features.sh twitter_test_ensemble_augment

# Check exit code
if [ $? -eq 0 ]; then
    echo "✅ Verification passed"
    exit 0
else
    echo "❌ Verification failed"
    exit 1
fi
```

## Additional Resources

- Implementation: `autotune/pipleline/pipleline.py`
  - Ensemble mode: lines 573-585, 410-434
  - History augmentation: lines 1134-1231
- CLI argument parsing: `scripts/optimize.py` lines 29-33, 51-62
- Tuner initialization: `autotune/tuner.py` lines 21, 200-202

## Support

If you encounter issues not covered in this guide:

1. Check the main log file for error messages
2. Verify configuration file syntax
3. Ensure database is set up correctly
4. Check that required DDPG model files exist (for ensemble mode)
5. Review the code implementation in the files listed above

