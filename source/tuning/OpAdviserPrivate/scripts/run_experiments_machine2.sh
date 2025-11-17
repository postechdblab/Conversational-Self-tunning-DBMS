#!/bin/bash
################################################################################
# Machine 2 Experiment Runner
# Workloads: tatp, voter, tpch, job, sysbench_wo, sysbench_rw
# Configs per workload: SMAC, DDPG, GA, Ensemble, Augment+SMAC, Augment+DDPG, Augment+GA
# Total: 6 workloads × 7 configs = 42 experiments
################################################################################

# set -e  # Removed to allow experiments to continue even if one fails

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
MACHINE_LOG="$LOG_DIR/machine2_experiments.log"

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
log "MACHINE 2 EXPERIMENT SUITE"
log "=========================================="
log "Workloads: tatp, voter, tpch, job, sysbench_wo, sysbench_rw"
log "Configs: SMAC, DDPG, GA, Ensemble, Augment+SMAC, Augment+DDPG, Augment+GA"
log "Total experiments: 42 (6 workloads × 7 configs each)"
log "Start time: $(date)"
log "=========================================="
log ""

exp_num=1

# TATP experiments (7 configs)
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "TATP WORKLOAD"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if run_experiment "tatp_smac.ini" "Experiment $exp_num: TATP (SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("TATP (SMAC)"); else FAILED_EXPERIMENTS+=("TATP (SMAC)"); fi
((exp_num++))
if run_experiment "tatp_ddpg.ini" "Experiment $exp_num: TATP (DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("TATP (DDPG)"); else FAILED_EXPERIMENTS+=("TATP (DDPG)"); fi
((exp_num++))
if run_experiment "tatp_ga.ini" "Experiment $exp_num: TATP (GA)"; then SUCCESSFUL_EXPERIMENTS+=("TATP (GA)"); else FAILED_EXPERIMENTS+=("TATP (GA)"); fi
((exp_num++))
if run_experiment "tatp_ensemble.ini" "Experiment $exp_num: TATP (Ensemble)"; then SUCCESSFUL_EXPERIMENTS+=("TATP (Ensemble)"); else FAILED_EXPERIMENTS+=("TATP (Ensemble)"); fi
((exp_num++))
if run_experiment "tatp_augment_smac.ini" "Experiment $exp_num: TATP (Augment+SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("TATP (Augment+SMAC)"); else FAILED_EXPERIMENTS+=("TATP (Augment+SMAC)"); fi
((exp_num++))
if run_experiment "tatp_augment_ddpg.ini" "Experiment $exp_num: TATP (Augment+DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("TATP (Augment+DDPG)"); else FAILED_EXPERIMENTS+=("TATP (Augment+DDPG)"); fi
((exp_num++))
if run_experiment "tatp_augment_ga.ini" "Experiment $exp_num: TATP (Augment+GA)"; then SUCCESSFUL_EXPERIMENTS+=("TATP (Augment+GA)"); else FAILED_EXPERIMENTS+=("TATP (Augment+GA)"); fi
((exp_num++))
log ""

# Voter experiments (7 configs)
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "VOTER WORKLOAD"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if run_experiment "voter_smac.ini" "Experiment $exp_num: Voter (SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("Voter (SMAC)"); else FAILED_EXPERIMENTS+=("Voter (SMAC)"); fi
((exp_num++))
if run_experiment "voter_ddpg.ini" "Experiment $exp_num: Voter (DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("Voter (DDPG)"); else FAILED_EXPERIMENTS+=("Voter (DDPG)"); fi
((exp_num++))
if run_experiment "voter_ga.ini" "Experiment $exp_num: Voter (GA)"; then SUCCESSFUL_EXPERIMENTS+=("Voter (GA)"); else FAILED_EXPERIMENTS+=("Voter (GA)"); fi
((exp_num++))
if run_experiment "voter_ensemble.ini" "Experiment $exp_num: Voter (Ensemble)"; then SUCCESSFUL_EXPERIMENTS+=("Voter (Ensemble)"); else FAILED_EXPERIMENTS+=("Voter (Ensemble)"); fi
((exp_num++))
if run_experiment "voter_augment_smac.ini" "Experiment $exp_num: Voter (Augment+SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("Voter (Augment+SMAC)"); else FAILED_EXPERIMENTS+=("Voter (Augment+SMAC)"); fi
((exp_num++))
if run_experiment "voter_augment_ddpg.ini" "Experiment $exp_num: Voter (Augment+DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("Voter (Augment+DDPG)"); else FAILED_EXPERIMENTS+=("Voter (Augment+DDPG)"); fi
((exp_num++))
if run_experiment "voter_augment_ga.ini" "Experiment $exp_num: Voter (Augment+GA)"; then SUCCESSFUL_EXPERIMENTS+=("Voter (Augment+GA)"); else FAILED_EXPERIMENTS+=("Voter (Augment+GA)"); fi
((exp_num++))
log ""

# TPC-H experiments (7 configs)
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "TPC-H WORKLOAD"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if run_experiment "tpch_smac.ini" "Experiment $exp_num: TPC-H (SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("TPC-H (SMAC)"); else FAILED_EXPERIMENTS+=("TPC-H (SMAC)"); fi
((exp_num++))
if run_experiment "tpch_ddpg.ini" "Experiment $exp_num: TPC-H (DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("TPC-H (DDPG)"); else FAILED_EXPERIMENTS+=("TPC-H (DDPG)"); fi
((exp_num++))
if run_experiment "tpch_ga.ini" "Experiment $exp_num: TPC-H (GA)"; then SUCCESSFUL_EXPERIMENTS+=("TPC-H (GA)"); else FAILED_EXPERIMENTS+=("TPC-H (GA)"); fi
((exp_num++))
if run_experiment "tpch_ensemble.ini" "Experiment $exp_num: TPC-H (Ensemble)"; then SUCCESSFUL_EXPERIMENTS+=("TPC-H (Ensemble)"); else FAILED_EXPERIMENTS+=("TPC-H (Ensemble)"); fi
((exp_num++))
if run_experiment "tpch_augment_smac.ini" "Experiment $exp_num: TPC-H (Augment+SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("TPC-H (Augment+SMAC)"); else FAILED_EXPERIMENTS+=("TPC-H (Augment+SMAC)"); fi
((exp_num++))
if run_experiment "tpch_augment_ddpg.ini" "Experiment $exp_num: TPC-H (Augment+DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("TPC-H (Augment+DDPG)"); else FAILED_EXPERIMENTS+=("TPC-H (Augment+DDPG)"); fi
((exp_num++))
if run_experiment "tpch_augment_ga.ini" "Experiment $exp_num: TPC-H (Augment+GA)"; then SUCCESSFUL_EXPERIMENTS+=("TPC-H (Augment+GA)"); else FAILED_EXPERIMENTS+=("TPC-H (Augment+GA)"); fi
((exp_num++))
log ""

# JOB experiments (7 configs)
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "JOB WORKLOAD"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if run_experiment "job_smac.ini" "Experiment $exp_num: JOB (SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("JOB (SMAC)"); else FAILED_EXPERIMENTS+=("JOB (SMAC)"); fi
((exp_num++))
if run_experiment "job_ddpg.ini" "Experiment $exp_num: JOB (DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("JOB (DDPG)"); else FAILED_EXPERIMENTS+=("JOB (DDPG)"); fi
((exp_num++))
if run_experiment "job_ga.ini" "Experiment $exp_num: JOB (GA)"; then SUCCESSFUL_EXPERIMENTS+=("JOB (GA)"); else FAILED_EXPERIMENTS+=("JOB (GA)"); fi
((exp_num++))
if run_experiment "job_ensemble.ini" "Experiment $exp_num: JOB (Ensemble)"; then SUCCESSFUL_EXPERIMENTS+=("JOB (Ensemble)"); else FAILED_EXPERIMENTS+=("JOB (Ensemble)"); fi
((exp_num++))
if run_experiment "job_augment_smac.ini" "Experiment $exp_num: JOB (Augment+SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("JOB (Augment+SMAC)"); else FAILED_EXPERIMENTS+=("JOB (Augment+SMAC)"); fi
((exp_num++))
if run_experiment "job_augment_ddpg.ini" "Experiment $exp_num: JOB (Augment+DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("JOB (Augment+DDPG)"); else FAILED_EXPERIMENTS+=("JOB (Augment+DDPG)"); fi
((exp_num++))
if run_experiment "job_augment_ga.ini" "Experiment $exp_num: JOB (Augment+GA)"; then SUCCESSFUL_EXPERIMENTS+=("JOB (Augment+GA)"); else FAILED_EXPERIMENTS+=("JOB (Augment+GA)"); fi
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
log ""

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
log "  Successful: ${#SUCCESSFUL_EXPERIMENTS[@]}/42"
log "  Failed: ${#FAILED_EXPERIMENTS[@]}/42"
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
