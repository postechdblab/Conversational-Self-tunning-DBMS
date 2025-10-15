#!/bin/bash
################################################################################
# Machine 3 Experiment Runner
# Workloads: sysbench_rw, sysbench_wo, sysbench_ro (both single and ensemble modes)
################################################################################

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
MACHINE_LOG="$LOG_DIR/machine3_experiments.log"

# Create log directory
mkdir -p "$LOG_DIR"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$MACHINE_LOG"
}

# Function to run a single experiment
run_experiment() {
    local config_file=$1
    local experiment_name=$2
    local start_time=$(date +%s)
    
    log "========================================"
    log "Starting: $experiment_name"
    log "Config: $config_file"
    log "========================================"
    
    # Set PYTHONPATH
    export PYTHONPATH="$PROJECT_ROOT"
    
    # Run the experiment (redirect output directly to avoid pipe hanging issues)
    python "$SCRIPT_DIR/optimize.py" --config="$SCRIPT_DIR/$config_file" >> "$MACHINE_LOG" 2>&1
    local exit_code=$?
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [ $exit_code -eq 0 ]; then
        local hours=$((duration / 3600))
        local minutes=$(((duration % 3600) / 60))
        local seconds=$((duration % 60))
        
        log "✅ SUCCESS: $experiment_name completed in ${hours}h ${minutes}m ${seconds}s"
        return 0
    else
        log "❌ FAILED: $experiment_name (ran for ${duration}s)"
        return 1
    fi
}

# Track results
declare -a SUCCESSFUL_EXPERIMENTS
declare -a FAILED_EXPERIMENTS
TOTAL_START_TIME=$(date +%s)

log "=========================================="
log "MACHINE 3 EXPERIMENT SUITE"
log "=========================================="
log "Workloads: sysbench_rw, sysbench_wo, sysbench_ro"
log "Modes: Single-optimizer + Ensemble"
log "Total experiments: 6"
log "Start time: $(date)"
log "=========================================="
log ""

# Experiment 1: Sysbench Read-Write (Single Optimizer)
if run_experiment "sysbench_rw.ini" "Sysbench-RW (Single-Optimizer)"; then
    SUCCESSFUL_EXPERIMENTS+=("Sysbench-RW (Single-Optimizer)")
else
    FAILED_EXPERIMENTS+=("Sysbench-RW (Single-Optimizer)")
fi
log ""

# Experiment 2: Sysbench Read-Write (Ensemble)
if run_experiment "sysbench_rw_ensemble.ini" "Sysbench-RW (Ensemble)"; then
    SUCCESSFUL_EXPERIMENTS+=("Sysbench-RW (Ensemble)")
else
    FAILED_EXPERIMENTS+=("Sysbench-RW (Ensemble)")
fi
log ""

# Experiment 3: Sysbench Write-Only (Single Optimizer)
if run_experiment "sysbench_wo.ini" "Sysbench-WO (Single-Optimizer)"; then
    SUCCESSFUL_EXPERIMENTS+=("Sysbench-WO (Single-Optimizer)")
else
    FAILED_EXPERIMENTS+=("Sysbench-WO (Single-Optimizer)")
fi
log ""

# Experiment 4: Sysbench Write-Only (Ensemble)
if run_experiment "sysbench_wo_ensemble.ini" "Sysbench-WO (Ensemble)"; then
    SUCCESSFUL_EXPERIMENTS+=("Sysbench-WO (Ensemble)")
else
    FAILED_EXPERIMENTS+=("Sysbench-WO (Ensemble)")
fi
log ""

# Experiment 5: Sysbench Read-Only (Single Optimizer)
if run_experiment "sysbench_ro.ini" "Sysbench-RO (Single-Optimizer)"; then
    SUCCESSFUL_EXPERIMENTS+=("Sysbench-RO (Single-Optimizer)")
else
    FAILED_EXPERIMENTS+=("Sysbench-RO (Single-Optimizer)")
fi
log ""

# Experiment 6: Sysbench Read-Only (Ensemble)
if run_experiment "sysbench_ro_ensemble.ini" "Sysbench-RO (Ensemble)"; then
    SUCCESSFUL_EXPERIMENTS+=("Sysbench-RO (Ensemble)")
else
    FAILED_EXPERIMENTS+=("Sysbench-RO (Ensemble)")
fi
log ""

# Calculate total time
TOTAL_END_TIME=$(date +%s)
TOTAL_DURATION=$((TOTAL_END_TIME - TOTAL_START_TIME))
TOTAL_HOURS=$((TOTAL_DURATION / 3600))
TOTAL_MINUTES=$(((TOTAL_DURATION % 3600) / 60))
TOTAL_SECONDS=$((TOTAL_DURATION % 60))

# Print summary
log ""
log "=========================================="
log "MACHINE 3 EXPERIMENT SUITE COMPLETED"
log "=========================================="
log "End time: $(date)"
log "Total duration: ${TOTAL_HOURS}h ${TOTAL_MINUTES}m ${TOTAL_SECONDS}s"
log ""
log "Results:"
log "  Successful: ${#SUCCESSFUL_EXPERIMENTS[@]}/6"
log "  Failed: ${#FAILED_EXPERIMENTS[@]}/6"
log ""

if [ ${#SUCCESSFUL_EXPERIMENTS[@]} -gt 0 ]; then
    log "✅ Successful experiments:"
    for exp in "${SUCCESSFUL_EXPERIMENTS[@]}"; do
        log "   - $exp"
    done
    log ""
fi

if [ ${#FAILED_EXPERIMENTS[@]} -gt 0 ]; then
    log "❌ Failed experiments:"
    for exp in "${FAILED_EXPERIMENTS[@]}"; do
        log "   - $exp"
    done
    log ""
fi

log "Full log: $MACHINE_LOG"
log "=========================================="

# Exit with appropriate code
if [ ${#FAILED_EXPERIMENTS[@]} -eq 0 ]; then
    exit 0
else
    exit 1
fi

