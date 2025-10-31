#!/bin/bash
################################################################################
# Machine 1 Experiment Runner
# Workloads: twitter, tpcc, ycsb, wikipedia
# Configs per workload: SMAC, DDPG, GA, Ensemble, Augment+SMAC, Augment+DDPG, Augment+GA
# Total: 4 workloads × 7 configs = 28 experiments
################################################################################

# set -e  # Removed to allow experiments to continue even if one fails

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
MACHINE_LOG="$LOG_DIR/machine1_experiments.log"

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
log "MACHINE 1 EXPERIMENT SUITE"
log "=========================================="
log "Workloads: twitter, tpcc, ycsb, wikipedia"
log "Configs: SMAC, DDPG, GA, Ensemble, Augment+SMAC, Augment+DDPG, Augment+GA"
log "Total experiments: 28 (4 workloads × 7 configs each)"
log "Start time: $(date)"
log "=========================================="
log ""

exp_num=1

# Twitter experiments (7 configs)
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "TWITTER WORKLOAD"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if run_experiment "twitter_smac.ini" "Experiment $exp_num: Twitter (SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("Twitter (SMAC)"); else FAILED_EXPERIMENTS+=("Twitter (SMAC)"); fi
((exp_num++))
if run_experiment "twitter_ddpg.ini" "Experiment $exp_num: Twitter (DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("Twitter (DDPG)"); else FAILED_EXPERIMENTS+=("Twitter (DDPG)"); fi
((exp_num++))
if run_experiment "twitter_ga.ini" "Experiment $exp_num: Twitter (GA)"; then SUCCESSFUL_EXPERIMENTS+=("Twitter (GA)"); else FAILED_EXPERIMENTS+=("Twitter (GA)"); fi
((exp_num++))
if run_experiment "twitter_ensemble.ini" "Experiment $exp_num: Twitter (Ensemble)"; then SUCCESSFUL_EXPERIMENTS+=("Twitter (Ensemble)"); else FAILED_EXPERIMENTS+=("Twitter (Ensemble)"); fi
((exp_num++))
if run_experiment "twitter_augment_smac.ini" "Experiment $exp_num: Twitter (Augment+SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("Twitter (Augment+SMAC)"); else FAILED_EXPERIMENTS+=("Twitter (Augment+SMAC)"); fi
((exp_num++))
if run_experiment "twitter_augment_ddpg.ini" "Experiment $exp_num: Twitter (Augment+DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("Twitter (Augment+DDPG)"); else FAILED_EXPERIMENTS+=("Twitter (Augment+DDPG)"); fi
((exp_num++))
if run_experiment "twitter_augment_ga.ini" "Experiment $exp_num: Twitter (Augment+GA)"; then SUCCESSFUL_EXPERIMENTS+=("Twitter (Augment+GA)"); else FAILED_EXPERIMENTS+=("Twitter (Augment+GA)"); fi
((exp_num++))
log ""

# TPC-C experiments (7 configs)
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "TPC-C WORKLOAD"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if run_experiment "tpcc_smac.ini" "Experiment $exp_num: TPC-C (SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("TPC-C (SMAC)"); else FAILED_EXPERIMENTS+=("TPC-C (SMAC)"); fi
((exp_num++))
if run_experiment "tpcc_ddpg.ini" "Experiment $exp_num: TPC-C (DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("TPC-C (DDPG)"); else FAILED_EXPERIMENTS+=("TPC-C (DDPG)"); fi
((exp_num++))
if run_experiment "tpcc_ga.ini" "Experiment $exp_num: TPC-C (GA)"; then SUCCESSFUL_EXPERIMENTS+=("TPC-C (GA)"); else FAILED_EXPERIMENTS+=("TPC-C (GA)"); fi
((exp_num++))
if run_experiment "tpcc_ensemble.ini" "Experiment $exp_num: TPC-C (Ensemble)"; then SUCCESSFUL_EXPERIMENTS+=("TPC-C (Ensemble)"); else FAILED_EXPERIMENTS+=("TPC-C (Ensemble)"); fi
((exp_num++))
if run_experiment "tpcc_augment_smac.ini" "Experiment $exp_num: TPC-C (Augment+SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("TPC-C (Augment+SMAC)"); else FAILED_EXPERIMENTS+=("TPC-C (Augment+SMAC)"); fi
((exp_num++))
if run_experiment "tpcc_augment_ddpg.ini" "Experiment $exp_num: TPC-C (Augment+DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("TPC-C (Augment+DDPG)"); else FAILED_EXPERIMENTS+=("TPC-C (Augment+DDPG)"); fi
((exp_num++))
if run_experiment "tpcc_augment_ga.ini" "Experiment $exp_num: TPC-C (Augment+GA)"; then SUCCESSFUL_EXPERIMENTS+=("TPC-C (Augment+GA)"); else FAILED_EXPERIMENTS+=("TPC-C (Augment+GA)"); fi
((exp_num++))
log ""

# YCSB experiments (7 configs)
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "YCSB WORKLOAD"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if run_experiment "ycsb_smac.ini" "Experiment $exp_num: YCSB (SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("YCSB (SMAC)"); else FAILED_EXPERIMENTS+=("YCSB (SMAC)"); fi
((exp_num++))
if run_experiment "ycsb_ddpg.ini" "Experiment $exp_num: YCSB (DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("YCSB (DDPG)"); else FAILED_EXPERIMENTS+=("YCSB (DDPG)"); fi
((exp_num++))
if run_experiment "ycsb_ga.ini" "Experiment $exp_num: YCSB (GA)"; then SUCCESSFUL_EXPERIMENTS+=("YCSB (GA)"); else FAILED_EXPERIMENTS+=("YCSB (GA)"); fi
((exp_num++))
if run_experiment "ycsb_ensemble.ini" "Experiment $exp_num: YCSB (Ensemble)"; then SUCCESSFUL_EXPERIMENTS+=("YCSB (Ensemble)"); else FAILED_EXPERIMENTS+=("YCSB (Ensemble)"); fi
((exp_num++))
if run_experiment "ycsb_augment_smac.ini" "Experiment $exp_num: YCSB (Augment+SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("YCSB (Augment+SMAC)"); else FAILED_EXPERIMENTS+=("YCSB (Augment+SMAC)"); fi
((exp_num++))
if run_experiment "ycsb_augment_ddpg.ini" "Experiment $exp_num: YCSB (Augment+DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("YCSB (Augment+DDPG)"); else FAILED_EXPERIMENTS+=("YCSB (Augment+DDPG)"); fi
((exp_num++))
if run_experiment "ycsb_augment_ga.ini" "Experiment $exp_num: YCSB (Augment+GA)"; then SUCCESSFUL_EXPERIMENTS+=("YCSB (Augment+GA)"); else FAILED_EXPERIMENTS+=("YCSB (Augment+GA)"); fi
((exp_num++))
log ""

# Wikipedia experiments (7 configs)
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "WIKIPEDIA WORKLOAD"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if run_experiment "wikipedia_smac.ini" "Experiment $exp_num: Wikipedia (SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("Wikipedia (SMAC)"); else FAILED_EXPERIMENTS+=("Wikipedia (SMAC)"); fi
((exp_num++))
if run_experiment "wikipedia_ddpg.ini" "Experiment $exp_num: Wikipedia (DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("Wikipedia (DDPG)"); else FAILED_EXPERIMENTS+=("Wikipedia (DDPG)"); fi
((exp_num++))
if run_experiment "wikipedia_ga.ini" "Experiment $exp_num: Wikipedia (GA)"; then SUCCESSFUL_EXPERIMENTS+=("Wikipedia (GA)"); else FAILED_EXPERIMENTS+=("Wikipedia (GA)"); fi
((exp_num++))
if run_experiment "wikipedia_ensemble.ini" "Experiment $exp_num: Wikipedia (Ensemble)"; then SUCCESSFUL_EXPERIMENTS+=("Wikipedia (Ensemble)"); else FAILED_EXPERIMENTS+=("Wikipedia (Ensemble)"); fi
((exp_num++))
if run_experiment "wikipedia_augment_smac.ini" "Experiment $exp_num: Wikipedia (Augment+SMAC)"; then SUCCESSFUL_EXPERIMENTS+=("Wikipedia (Augment+SMAC)"); else FAILED_EXPERIMENTS+=("Wikipedia (Augment+SMAC)"); fi
((exp_num++))
if run_experiment "wikipedia_augment_ddpg.ini" "Experiment $exp_num: Wikipedia (Augment+DDPG)"; then SUCCESSFUL_EXPERIMENTS+=("Wikipedia (Augment+DDPG)"); else FAILED_EXPERIMENTS+=("Wikipedia (Augment+DDPG)"); fi
((exp_num++))
if run_experiment "wikipedia_augment_ga.ini" "Experiment $exp_num: Wikipedia (Augment+GA)"; then SUCCESSFUL_EXPERIMENTS+=("Wikipedia (Augment+GA)"); else FAILED_EXPERIMENTS+=("Wikipedia (Augment+GA)"); fi
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
log "MACHINE 1 EXPERIMENT SUITE COMPLETED"
log "=========================================="
log "End time: $(date)"
log "Total duration: ${TOTAL_HOURS}h ${TOTAL_MINUTES}m ${TOTAL_SECONDS}s"
log ""
log "Results:"
log "  Successful: ${#SUCCESSFUL_EXPERIMENTS[@]}/28"
log "  Failed: ${#FAILED_EXPERIMENTS[@]}/28"
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
