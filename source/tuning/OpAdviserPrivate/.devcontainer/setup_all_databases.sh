#!/bin/bash
set -e  # Exit on error
set -x  # Print commands as they execute (verbose mode)

# Function to print with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "=========================================="
log "SETTING UP ALL DATABASES FOR BENCHMARKS"
log "=========================================="
log "This will take significant time (30-60 minutes)..."
log ""

# Get current user
CURRENT_USER=${SUDO_USER:-${USER:-vscode}}
export MYSQL_USER=$CURRENT_USER

log "Running as: $CURRENT_USER"
log "MySQL user: $MYSQL_USER"
log ""

# Ensure MySQL is running
log "=========================================="
log "CHECKING MYSQL STATUS"
log "=========================================="
if sudo service mysql status >/dev/null 2>&1; then
    log "✅ MySQL service is already running"
else
    log "MySQL is not running. Starting MySQL service..."
    if sudo service mysql start 2>&1 | tee -a /tmp/mysql_start.log; then
        log "✅ MySQL service started successfully"
        sleep 5
    else
        log "❌ ERROR: Failed to start MySQL service"
        log "Check logs: sudo tail -50 /var/log/mysql/error.log"
        exit 1
    fi
fi

# Wait for MySQL to be ready and accepting connections
log ""
log "Waiting for MySQL to accept connections on port 3306..."
MAX_ATTEMPTS=30
ATTEMPT=1
while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    if mysql -u $MYSQL_USER -ppassword -h localhost -P 3306 -e "SELECT 1 AS status, @@port AS port, @@version AS version" >/dev/null 2>&1; then
        # Get MySQL info
        MYSQL_INFO=$(mysql -u $MYSQL_USER -ppassword -h localhost -P 3306 -e "SELECT @@version AS Version, @@port AS Port" 2>/dev/null | tail -1)
        log "✅ MySQL is ready and accepting connections!"
        log "   MySQL Info: $MYSQL_INFO"
        break
    fi
    
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        log "❌ ERROR: MySQL did not become ready after ${MAX_ATTEMPTS} attempts (60 seconds)"
        log "Troubleshooting steps:"
        log "  1. Check MySQL status: sudo service mysql status"
        log "  2. Check error log: sudo tail -50 /var/log/mysql/error.log"
        log "  3. Check if port 3306 is in use: sudo netstat -tlnp | grep 3306"
        log "  4. Try restarting MySQL: sudo service mysql restart"
        exit 1
    fi
    
    log "  Attempt $ATTEMPT/$MAX_ATTEMPTS: Waiting for MySQL to be ready..."
    sleep 2
    ATTEMPT=$((ATTEMPT + 1))
done
log "=========================================="

log ""
log "=========================================="
log "Step 1/4: Setting up OLTPBench workloads"
log "=========================================="
log "Workloads: twitter, tpcc, ycsb, wikipedia, tatp, voter"
log "Start time: $(date)"
log ""
STEP1_START=$(date +%s)
if [ -f /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_oltpbench.sh ]; then
    bash /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_oltpbench.sh
    STEP1_END=$(date +%s)
    STEP1_TIME=$((STEP1_END - STEP1_START))
    log "✅ OLTPBench workloads completed! (took ${STEP1_TIME}s)"
else
    log "⚠️  setup_oltpbench.sh not found, skipping..."
fi

log ""
log "=========================================="
log "Step 2/4: Setting up TPC-H workload"
log "=========================================="
log "Scale factor: 10"
log "Start time: $(date)"
log ""
STEP2_START=$(date +%s)
if [ -f /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_tpch.sh ]; then
    bash /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_tpch.sh
    STEP2_END=$(date +%s)
    STEP2_TIME=$((STEP2_END - STEP2_START))
    log "✅ TPC-H workload completed! (took ${STEP2_TIME}s)"
else
    log "⚠️  setup_tpch.sh not found, skipping..."
fi

log ""
log "=========================================="
log "Step 3/4: Setting up Sysbench workloads"
log "=========================================="
log "Workloads: read-write, write-only, read-only"
log "Start time: $(date)"
log ""
STEP3_START=$(date +%s)
if [ -f /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_sysbench.sh ]; then
    bash /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_sysbench.sh
    STEP3_END=$(date +%s)
    STEP3_TIME=$((STEP3_END - STEP3_START))
    log "✅ Sysbench workloads completed! (took ${STEP3_TIME}s)"
else
    log "⚠️  setup_sysbench.sh not found, skipping..."
fi

log ""
log "=========================================="
log "Step 4/4: Setting up JOB workload"
log "=========================================="
log "Start time: $(date)"
log ""
STEP4_START=$(date +%s)
if [ -f /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_job.sh ]; then
    bash /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_job.sh
    STEP4_END=$(date +%s)
    STEP4_TIME=$((STEP4_END - STEP4_START))
    log "✅ JOB workload completed! (took ${STEP4_TIME}s)"
else
    log "⚠️  setup_job.sh not found, skipping..."
fi

TOTAL_END=$(date +%s)
TOTAL_TIME=$((TOTAL_END - STEP1_START))
MINUTES=$((TOTAL_TIME / 60))
SECONDS=$((TOTAL_TIME % 60))

log ""
log "=========================================="
log "✅ ALL DATABASES SETUP COMPLETE!"
log "=========================================="
log "Total time: ${MINUTES}m ${SECONDS}s"
log ""
log "📊 Databases created:"
log "  - twitter (OLTPBench)"
log "  - tpcc (OLTPBench)"
log "  - ycsb (OLTPBench)"
log "  - wikipedia (OLTPBench)"
log "  - tatp (OLTPBench)"
log "  - voter (OLTPBench)"
log "  - tpch (TPC-H)"
log "  - sbrw (Sysbench Read-Write)"
log "  - sbwrite (Sysbench Write-Only)"
log "  - sbread (Sysbench Read-Only)"
log "  - imdbload (JOB - if available)"
log ""
log "🚀 You can now run optimization scripts!"
log ""
log "Setup log saved to: /tmp/database_setup.log"
log "Completed at: $(date)"


