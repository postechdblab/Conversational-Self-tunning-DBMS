#!/bin/bash
################################################################################
# Machine 2 Experiment Runner
# Workloads: tatp, voter, tpch, job (both single and ensemble modes)
################################################################################

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
MACHINE_LOG="$LOG_DIR/machine2_experiments.log"

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
    
    # Run the experiment
    if python "$SCRIPT_DIR/optimize.py" --config="$SCRIPT_DIR/$config_file" 2>&1 | tee -a "$MACHINE_LOG"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        local hours=$((duration / 3600))
        local minutes=$(((duration % 3600) / 60))
        local seconds=$((duration % 60))
        
        log "✅ SUCCESS: $experiment_name completed in ${hours}h ${minutes}m ${seconds}s"
        return 0
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        log "❌ FAILED: $experiment_name (ran for ${duration}s)"
        return 1
    fi
}

# Track results
declare -a SUCCESSFUL_EXPERIMENTS
declare -a FAILED_EXPERIMENTS
TOTAL_START_TIME=$(date +%s)

log "=========================================="
log "MACHINE 2 EXPERIMENT SUITE"
log "=========================================="
log "Workloads: tatp, voter, tpch, job"
log "Modes: Single-optimizer + Ensemble"
log "Total experiments: 8"
log "Start time: $(date)"
log "=========================================="
log ""

# Experiment 1: TATP (Single Optimizer)
if run_experiment "tatp.ini" "TATP (Single-Optimizer)"; then
    SUCCESSFUL_EXPERIMENTS+=("TATP (Single-Optimizer)")
else
    FAILED_EXPERIMENTS+=("TATP (Single-Optimizer)")
fi
log ""

# Experiment 2: TATP (Ensemble)
if run_experiment "tatp_ensemble.ini" "TATP (Ensemble)"; then
    SUCCESSFUL_EXPERIMENTS+=("TATP (Ensemble)")
else
    FAILED_EXPERIMENTS+=("TATP (Ensemble)")
fi
log ""

# Experiment 3: Voter (Single Optimizer)
if run_experiment "voter.ini" "Voter (Single-Optimizer)"; then
    SUCCESSFUL_EXPERIMENTS+=("Voter (Single-Optimizer)")
else
    FAILED_EXPERIMENTS+=("Voter (Single-Optimizer)")
fi
log ""

# Experiment 4: Voter (Ensemble)
if run_experiment "voter_ensemble.ini" "Voter (Ensemble)"; then
    SUCCESSFUL_EXPERIMENTS+=("Voter (Ensemble)")
else
    FAILED_EXPERIMENTS+=("Voter (Ensemble)")
fi
log ""

# Experiment 5: TPC-H (Single Optimizer)
if run_experiment "tpch.ini" "TPC-H (Single-Optimizer)"; then
    SUCCESSFUL_EXPERIMENTS+=("TPC-H (Single-Optimizer)")
else
    FAILED_EXPERIMENTS+=("TPC-H (Single-Optimizer)")
fi
log ""

# Experiment 6: TPC-H (Ensemble)
if run_experiment "tpch_ensemble.ini" "TPC-H (Ensemble)"; then
    SUCCESSFUL_EXPERIMENTS+=("TPC-H (Ensemble)")
else
    FAILED_EXPERIMENTS+=("TPC-H (Ensemble)")
fi
log ""

# Experiment 7: JOB (Single Optimizer)
if run_experiment "job.ini" "JOB (Single-Optimizer)"; then
    SUCCESSFUL_EXPERIMENTS+=("JOB (Single-Optimizer)")
else
    FAILED_EXPERIMENTS+=("JOB (Single-Optimizer)")
fi
log ""

# Experiment 8: JOB (Ensemble)
if run_experiment "job_ensemble.ini" "JOB (Ensemble)"; then
    SUCCESSFUL_EXPERIMENTS+=("JOB (Ensemble)")
else
    FAILED_EXPERIMENTS+=("JOB (Ensemble)")
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
log "MACHINE 2 EXPERIMENT SUITE COMPLETED"
log "=========================================="
log "End time: $(date)"
log "Total duration: ${TOTAL_HOURS}h ${TOTAL_MINUTES}m ${TOTAL_SECONDS}s"
log ""
log "Results:"
log "  Successful: ${#SUCCESSFUL_EXPERIMENTS[@]}/8"
log "  Failed: ${#FAILED_EXPERIMENTS[@]}/8"
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

