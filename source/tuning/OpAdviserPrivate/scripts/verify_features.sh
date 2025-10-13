#!/bin/bash

# Verification script for --ensemble-mode and --augment-history features
# Usage: bash scripts/verify_features.sh [log_file_or_task_id]

set -e

# Determine log file location
if [ $# -eq 0 ]; then
    # Default: use test task id
    TASK_ID="twitter_test_ensemble_augment"
    LOG_FILE="logs/${TASK_ID}.log"
else
    # Check if argument is a file or task_id
    if [ -f "$1" ]; then
        LOG_FILE="$1"
    else
        LOG_FILE="logs/$1.log"
    fi
fi

echo "=========================================="
echo "Feature Verification Script"
echo "=========================================="
echo "Log file: $LOG_FILE"
echo ""

# Check if log file exists
if [ ! -f "$LOG_FILE" ]; then
    echo "ERROR: Log file not found: $LOG_FILE"
    echo ""
    echo "Available log files:"
    ls -lh logs/*.log 2>/dev/null || echo "  No log files found in logs/"
    echo ""
    echo "Usage: $0 [log_file_or_task_id]"
    echo "Examples:"
    echo "  $0                                    # Uses default test task"
    echo "  $0 twitter_test_ensemble_augment     # Uses task_id"
    echo "  $0 logs/my_task.log                  # Uses specific file"
    exit 1
fi

echo "=========================================="
echo "VERIFYING --ensemble-mode"
echo "=========================================="

ENSEMBLE_COUNT=$(grep -c "\[Ensemble\]" "$LOG_FILE" 2>/dev/null || echo "0")

if [ "$ENSEMBLE_COUNT" -eq 0 ]; then
    echo "❌ ENSEMBLE MODE NOT DETECTED"
    echo "   No [Ensemble] markers found in log"
    echo ""
    echo "   Possible reasons:"
    echo "   1. ensemble_mode not enabled in config"
    echo "   2. --ensemble-mode flag not used"
    echo "   3. Tuning hasn't started yet"
else
    echo "✅ ENSEMBLE MODE DETECTED"
    echo "   Total ensemble evaluations: $ENSEMBLE_COUNT"
    echo ""
    
    SMAC_COUNT=$(grep -c "\[Ensemble\]\[SMAC\]" "$LOG_FILE" 2>/dev/null || echo "0")
    MBO_COUNT=$(grep -c "\[Ensemble\]\[MBO\]" "$LOG_FILE" 2>/dev/null || echo "0")
    DDPG_COUNT=$(grep -c "\[Ensemble\]\[DDPG\]" "$LOG_FILE" 2>/dev/null || echo "0")
    GA_COUNT=$(grep -c "\[Ensemble\]\[GA\]" "$LOG_FILE" 2>/dev/null || echo "0")
    
    echo "   Optimizer breakdown:"
    echo "   - SMAC: $SMAC_COUNT evaluations"
    echo "   - MBO:  $MBO_COUNT evaluations"
    echo "   - DDPG: $DDPG_COUNT evaluations"
    echo "   - GA:   $GA_COUNT evaluations"
    echo ""
    
    # Verify all optimizers have equal counts
    if [ "$SMAC_COUNT" -eq "$MBO_COUNT" ] && [ "$MBO_COUNT" -eq "$DDPG_COUNT" ] && [ "$DDPG_COUNT" -eq "$GA_COUNT" ]; then
        echo "   ✅ All optimizers called equally (as expected)"
    else
        echo "   ⚠️  WARNING: Optimizer counts not equal"
        echo "      This may indicate an issue or incomplete run"
    fi
    
    # Show sample ensemble logs
    echo ""
    echo "   Sample log entries:"
    grep "\[Ensemble\]" "$LOG_FILE" | head -4 | sed 's/^/   | /'
fi

echo ""
echo "=========================================="
echo "VERIFYING --augment-history"
echo "=========================================="

AUGMENT_LINES=$(grep "\[Augmentation\]" "$LOG_FILE" 2>/dev/null || echo "")

if [ -z "$AUGMENT_LINES" ]; then
    echo "❌ HISTORY AUGMENTATION NOT DETECTED"
    echo "   No [Augmentation] messages found in log"
    echo ""
    echo "   Possible reasons:"
    echo "   1. augment_history not enabled in config"
    echo "   2. --augment-history flag not used"
    echo "   3. Not enough initial runs yet (needs > 0 iterations)"
    echo "   4. Surrogate model training failed"
else
    echo "✅ HISTORY AUGMENTATION DETECTED"
    echo ""
    
    AUGMENT_COUNT=$(echo "$AUGMENT_LINES" | wc -l)
    echo "   Augmentation events: $AUGMENT_COUNT"
    echo ""
    
    echo "   Augmentation log entries:"
    echo "$AUGMENT_LINES" | sed 's/^/   | /'
    echo ""
    
    # Extract and verify synthetic observation counts
    echo "   Synthetic observations added per iteration:"
    grep "\[Augmentation\]" "$LOG_FILE" | grep -oP 'Added \K\d+' | while read count; do
        echo "   - $count observations"
    done
fi

echo ""
echo "=========================================="
echo "SUMMARY & STATISTICS"
echo "=========================================="

# Count total iterations
ITERATION_COUNT=$(grep -oP 'Iteration \K\d+' "$LOG_FILE" 2>/dev/null | sort -n | tail -1 || echo "0")
echo "Total iterations completed: $ITERATION_COUNT"

# Count total objective value logs
OBJ_COUNT=$(grep -c "objective value:" "$LOG_FILE" 2>/dev/null || echo "0")
echo "Total objective evaluations: $OBJ_COUNT"

# Calculate expected evaluations for ensemble mode
if [ "$ENSEMBLE_COUNT" -gt 0 ] && [ "$ITERATION_COUNT" -gt 0 ]; then
    # Try to extract initial_runs from log
    INITIAL_RUNS=$(grep -oP 'initial_runs.*?=.*?\K\d+' "$LOG_FILE" | head -1 || echo "5")
    ENSEMBLE_ITERS=$((ITERATION_COUNT - INITIAL_RUNS))
    if [ "$ENSEMBLE_ITERS" -lt 0 ]; then
        ENSEMBLE_ITERS=0
    fi
    EXPECTED_EVALS=$((INITIAL_RUNS + ENSEMBLE_ITERS * 4))
    
    echo ""
    echo "Ensemble mode calculations:"
    echo "  Initial runs: $INITIAL_RUNS"
    echo "  Ensemble iterations: $ENSEMBLE_ITERS"
    echo "  Expected evaluations: $EXPECTED_EVALS"
    echo "  Actual evaluations: $OBJ_COUNT"
    
    if [ "$OBJ_COUNT" -eq "$EXPECTED_EVALS" ]; then
        echo "  ✅ Evaluation count matches expected"
    else
        DIFF=$((OBJ_COUNT - EXPECTED_EVALS))
        echo "  ⚠️  Difference: $DIFF (may indicate incomplete run)"
    fi
fi

echo ""
echo "=========================================="
echo "LOG FILE INFORMATION"
echo "=========================================="
echo "File: $LOG_FILE"
echo "Size: $(du -h "$LOG_FILE" | cut -f1)"
echo "Lines: $(wc -l < "$LOG_FILE")"
echo "Last modified: $(stat -c %y "$LOG_FILE" 2>/dev/null || stat -f %Sm "$LOG_FILE" 2>/dev/null || echo "unknown")"

echo ""
echo "=========================================="
echo "VERIFICATION COMPLETE"
echo "=========================================="

