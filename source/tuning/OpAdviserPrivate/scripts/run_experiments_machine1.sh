#!/bin/bash
################################################################################
# Machine 1 Experiment Runner
# Workloads: twitter, tpcc, ycsb, wikipedia (both single and ensemble modes)
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
    # Start Python process with tee, monitor it, and auto-kill tee if it hangs
    python "$SCRIPT_DIR/optimize.py" --config="$SCRIPT_DIR/$config_file" 2>&1 | tee -a "$MACHINE_LOG" &
    local pipeline_pid=$!
    
    # Find the actual Python process (first process in the pipeline)
    local python_pid=$(ps -o pid= --ppid $pipeline_pid | head -1 | tr -d ' ')
    
    # Wait for Python to complete
    local exit_code=1
    if [ -n "$python_pid" ]; then
        wait $python_pid 2>/dev/null && exit_code=0 || exit_code=$?
    fi
    
    # Give tee 3 seconds to flush and exit, then force kill the entire pipeline
    sleep 3
    kill -9 -$pipeline_pid 2>/dev/null || true
    wait $pipeline_pid 2>/dev/null || true
    
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
log "Modes: Single-optimizer + Ensemble"
log "Total experiments: 8"
log "Start time: $(date)"
log "=========================================="
log ""

# Experiment 1: Twitter (Single Optimizer)
if run_experiment "twitter.ini" "Twitter (Single-Optimizer)"; then
    SUCCESSFUL_EXPERIMENTS+=("Twitter (Single-Optimizer)")
else
    FAILED_EXPERIMENTS+=("Twitter (Single-Optimizer)")
fi
log ""

# Experiment 2: Twitter (Ensemble)
if run_experiment "twitter_ensemble.ini" "Twitter (Ensemble)"; then
    SUCCESSFUL_EXPERIMENTS+=("Twitter (Ensemble)")
else
    FAILED_EXPERIMENTS+=("Twitter (Ensemble)")
fi
log ""

# Experiment 3: TPC-C (Single Optimizer)
if run_experiment "tpcc.ini" "TPC-C (Single-Optimizer)"; then
    SUCCESSFUL_EXPERIMENTS+=("TPC-C (Single-Optimizer)")
else
    FAILED_EXPERIMENTS+=("TPC-C (Single-Optimizer)")
fi
log ""

# Experiment 4: TPC-C (Ensemble)
if run_experiment "tpcc_ensemble.ini" "TPC-C (Ensemble)"; then
    SUCCESSFUL_EXPERIMENTS+=("TPC-C (Ensemble)")
else
    FAILED_EXPERIMENTS+=("TPC-C (Ensemble)")
fi
log ""

# Experiment 5: YCSB (Single Optimizer)
if run_experiment "ycsb.ini" "YCSB (Single-Optimizer)"; then
    SUCCESSFUL_EXPERIMENTS+=("YCSB (Single-Optimizer)")
else
    FAILED_EXPERIMENTS+=("YCSB (Single-Optimizer)")
fi
log ""

# Experiment 6: YCSB (Ensemble)
if run_experiment "ycsb_ensemble.ini" "YCSB (Ensemble)"; then
    SUCCESSFUL_EXPERIMENTS+=("YCSB (Ensemble)")
else
    FAILED_EXPERIMENTS+=("YCSB (Ensemble)")
fi
log ""

# Experiment 7: Wikipedia (Single Optimizer)
if run_experiment "wikipedia.ini" "Wikipedia (Single-Optimizer)"; then
    SUCCESSFUL_EXPERIMENTS+=("Wikipedia (Single-Optimizer)")
else
    FAILED_EXPERIMENTS+=("Wikipedia (Single-Optimizer)")
fi
log ""

# Experiment 8: Wikipedia (Ensemble)
if run_experiment "wikipedia_ensemble.ini" "Wikipedia (Ensemble)"; then
    SUCCESSFUL_EXPERIMENTS+=("Wikipedia (Ensemble)")
else
    FAILED_EXPERIMENTS+=("Wikipedia (Ensemble)")
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
log "MACHINE 1 EXPERIMENT SUITE COMPLETED"
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

