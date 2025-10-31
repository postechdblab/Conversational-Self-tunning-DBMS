#!/bin/bash
################################################################################
# Machine 3 Experiment Runner
# Workloads: sysbench_rw, sysbench_wo, sysbench_ro
# Configs per workload: SMAC, DDPG, GA, Ensemble, Augment+SMAC, Augment+DDPG, Augment+GA
# Total: 3 workloads × 7 configs = 21 experiments
################################################################################

# set -e  # Removed to allow experiments to continue even if one fails

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
MACHINE_LOG="$LOG_DIR/machine3_experiments.log"

# Create log directory
mkdir -p "$LOG_DIR"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$MACHINE_LOG"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
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
    
    # Run the experiment with live output using tee
    python "$SCRIPT_DIR/optimize.py" --config="$SCRIPT_DIR/$config_file" 2>&1 | tee -a "$MACHINE_LOG"
    local exit_code=${PIPESTATUS[0]}
    
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
log "Configs: SMAC, DDPG, GA, Ensemble, Augment+SMAC, Augment+DDPG, Augment+GA"
log "Total experiments: 21 (3 workloads × 7 configs each)"
log "Start time: $(date)"
log "=========================================="
log ""

exp_num=1

# Sysbench Read-Write experiments (7 configs)
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "SYSBENCH READ-WRITE WORKLOAD"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if run_experiment "sysbench_rw_smac.ini" "Experiment $exp_num: Sysbench-RW (SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-RW (SMAC)"); else FAILED_EXPERIMENTS+=("Sysbench-RW (SMAC)"); fi
((exp_num++))
if run_experiment "sysbench_rw_ddpg.ini" "Experiment $exp_num: Sysbench-RW (DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-RW (DDPG)"); else FAILED_EXPERIMENTS+=("Sysbench-RW (DDPG)"); fi
((exp_num++))
if run_experiment "sysbench_rw_ga.ini" "Experiment $exp_num: Sysbench-RW (GA)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-RW (GA)"); else FAILED_EXPERIMENTS+=("Sysbench-RW (GA)"); fi
((exp_num++))
if run_experiment "sysbench_rw_ensemble.ini" "Experiment $exp_num: Sysbench-RW (Ensemble)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-RW (Ensemble)"); else FAILED_EXPERIMENTS+=("Sysbench-RW (Ensemble)"); fi
((exp_num++))
if run_experiment "sysbench_rw_augment_smac.ini" "Experiment $exp_num: Sysbench-RW (Augment+SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-RW (Augment+SMAC)"); else FAILED_EXPERIMENTS+=("Sysbench-RW (Augment+SMAC)"); fi
((exp_num++))
if run_experiment "sysbench_rw_augment_ddpg.ini" "Experiment $exp_num: Sysbench-RW (Augment+DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-RW (Augment+DDPG)"); else FAILED_EXPERIMENTS+=("Sysbench-RW (Augment+DDPG)"); fi
((exp_num++))
if run_experiment "sysbench_rw_augment_ga.ini" "Experiment $exp_num: Sysbench-RW (Augment+GA)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-RW (Augment+GA)"); else FAILED_EXPERIMENTS+=("Sysbench-RW (Augment+GA)"); fi
((exp_num++))
log ""

# Sysbench Write-Only experiments (7 configs)
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "SYSBENCH WRITE-ONLY WORKLOAD"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if run_experiment "sysbench_wo_smac.ini" "Experiment $exp_num: Sysbench-WO (SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-WO (SMAC)"); else FAILED_EXPERIMENTS+=("Sysbench-WO (SMAC)"); fi
((exp_num++))
if run_experiment "sysbench_wo_ddpg.ini" "Experiment $exp_num: Sysbench-WO (DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-WO (DDPG)"); else FAILED_EXPERIMENTS+=("Sysbench-WO (DDPG)"); fi
((exp_num++))
if run_experiment "sysbench_wo_ga.ini" "Experiment $exp_num: Sysbench-WO (GA)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-WO (GA)"); else FAILED_EXPERIMENTS+=("Sysbench-WO (GA)"); fi
((exp_num++))
if run_experiment "sysbench_wo_ensemble.ini" "Experiment $exp_num: Sysbench-WO (Ensemble)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-WO (Ensemble)"); else FAILED_EXPERIMENTS+=("Sysbench-WO (Ensemble)"); fi
((exp_num++))
if run_experiment "sysbench_wo_augment_smac.ini" "Experiment $exp_num: Sysbench-WO (Augment+SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-WO (Augment+SMAC)"); else FAILED_EXPERIMENTS+=("Sysbench-WO (Augment+SMAC)"); fi
((exp_num++))
if run_experiment "sysbench_wo_augment_ddpg.ini" "Experiment $exp_num: Sysbench-WO (Augment+DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-WO (Augment+DDPG)"); else FAILED_EXPERIMENTS+=("Sysbench-WO (Augment+DDPG)"); fi
((exp_num++))
if run_experiment "sysbench_wo_augment_ga.ini" "Experiment $exp_num: Sysbench-WO (Augment+GA)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-WO (Augment+GA)"); else FAILED_EXPERIMENTS+=("Sysbench-WO (Augment+GA)"); fi
((exp_num++))
log ""

# Sysbench Read-Only experiments (7 configs)
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "SYSBENCH READ-ONLY WORKLOAD"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if run_experiment "sysbench_ro_smac.ini" "Experiment $exp_num: Sysbench-RO (SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-RO (SMAC)"); else FAILED_EXPERIMENTS+=("Sysbench-RO (SMAC)"); fi
((exp_num++))
if run_experiment "sysbench_ro_ddpg.ini" "Experiment $exp_num: Sysbench-RO (DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-RO (DDPG)"); else FAILED_EXPERIMENTS+=("Sysbench-RO (DDPG)"); fi
((exp_num++))
if run_experiment "sysbench_ro_ga.ini" "Experiment $exp_num: Sysbench-RO (GA)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-RO (GA)"); else FAILED_EXPERIMENTS+=("Sysbench-RO (GA)"); fi
((exp_num++))
if run_experiment "sysbench_ro_ensemble.ini" "Experiment $exp_num: Sysbench-RO (Ensemble)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-RO (Ensemble)"); else FAILED_EXPERIMENTS+=("Sysbench-RO (Ensemble)"); fi
((exp_num++))
if run_experiment "sysbench_ro_augment_smac.ini" "Experiment $exp_num: Sysbench-RO (Augment+SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-RO (Augment+SMAC)"); else FAILED_EXPERIMENTS+=("Sysbench-RO (Augment+SMAC)"); fi
((exp_num++))
if run_experiment "sysbench_ro_augment_ddpg.ini" "Experiment $exp_num: Sysbench-RO (Augment+DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-RO (Augment+DDPG)"); else FAILED_EXPERIMENTS+=("Sysbench-RO (Augment+DDPG)"); fi
((exp_num++))
if run_experiment "sysbench_ro_augment_ga.ini" "Experiment $exp_num: Sysbench-RO (Augment+GA)"; then SUCCESSFUL_EXPERIMENTS+=("Sysbench-RO (Augment+GA)"); else FAILED_EXPERIMENTS+=("Sysbench-RO (Augment+GA)"); fi
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
log "  Successful: ${#SUCCESSFUL_EXPERIMENTS[@]}/21"
log "  Failed: ${#FAILED_EXPERIMENTS[@]}/21"
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
