#!/bin/bash
set -e  # Exit on error
set -x  # Verbose mode - show commands

# Function to print with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "======================================"
log "Setting up OLTPBench"
log "======================================"

# Get current user
CURRENT_USER=$(whoami)
MYSQL_USER=${CURRENT_USER}
log "Running as system user: $CURRENT_USER"
log "Using MySQL user: $MYSQL_USER"

# Clone and build OLTPBench
log "Cloning and building OLTPBench..."
cd /
log "  → Removing old oltpbench directory (if exists)..."
sudo rm -rf oltpbench
log "  → Cloning oltpbench from GitHub..."
sudo git clone --depth 1 --verbose https://github.com/seokjeongeum/oltpbench.git 2>&1 | tee -a /tmp/oltpbench_setup.log
log "  → Setting ownership to $CURRENT_USER..."
sudo chown -R $CURRENT_USER:$CURRENT_USER /oltpbench
cd /oltpbench
log "  → Running ant bootstrap..."
ant bootstrap 2>&1 | tee -a /tmp/oltpbench_setup.log || { log "ERROR: ant bootstrap failed"; exit 1; }
log "  → Running ant resolve..."
ant resolve 2>&1 | tee -a /tmp/oltpbench_setup.log || { log "ERROR: ant resolve failed"; exit 1; }
log "  → Running ant build..."
ant build 2>&1 | tee -a /tmp/oltpbench_setup.log || { log "ERROR: ant build failed"; exit 1; }
log "  → Setting permissions..."
chmod 777 /oltpbench/*

log "✅ OLTPBench built successfully!"
log "   Build log saved to: /tmp/oltpbench_setup.log"

# Function to setup a workload
setup_workload() {
    local WORKLOAD_NAME=$1
    local CONFIG_FILE=$2
    local START_TIME=$(date +%s)
    
    log "=========================================="
    log "Setting up ${WORKLOAD_NAME} workload..."
    log "Start time: $(date)"
    log "Config file: ${CONFIG_FILE}"
    log "  → Step 1/3: Dropping existing database ${WORKLOAD_NAME} (if exists)..."
    mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"DROP DATABASE IF EXISTS ${WORKLOAD_NAME};" 2>&1 | tee -a /tmp/${WORKLOAD_NAME}_setup.log
    log "  → Step 2/3: Creating database ${WORKLOAD_NAME}..."
    mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"CREATE DATABASE ${WORKLOAD_NAME};" 2>&1 | tee -a /tmp/${WORKLOAD_NAME}_setup.log
    log "  → Step 3/3: Loading data into ${WORKLOAD_NAME} (this may take several minutes)..."
    log "     Command: /oltpbench/oltpbenchmark -b ${WORKLOAD_NAME} -c ${CONFIG_FILE} --create=true --load=true --verbose"
    /oltpbench/oltpbenchmark -b ${WORKLOAD_NAME} -c ${CONFIG_FILE} --create=true --load=true --verbose 2>&1 | tee -a /tmp/${WORKLOAD_NAME}_setup.log
    
    local END_TIME=$(date +%s)
    local DURATION=$((END_TIME - START_TIME))
    local MINUTES=$((DURATION / 60))
    local SECONDS=$((DURATION % 60))
    
    log "✅ ${WORKLOAD_NAME} workload prepared!"
    log "   Duration: ${MINUTES}m ${SECONDS}s"
    log "   Setup log: /tmp/${WORKLOAD_NAME}_setup.log"
    log "   End time: $(date)"
    log "=========================================="
    log ""
}

# Setup Twitter workload
setup_workload "twitter" "/oltpbench/config/sample_twitter_config.xml"

# Setup TPCC workload
setup_workload "tpcc" "/oltpbench/config/sample_tpcc_config.xml"

# Setup YCSB workload
setup_workload "ycsb" "/oltpbench/config/sample_ycsb_config.xml"

# Setup Wikipedia workload
setup_workload "wikipedia" "/oltpbench/config/sample_wikipedia_config.xml"

# Setup TATP workload
setup_workload "tatp" "/oltpbench/config/sample_tatp_config.xml"

# Setup Voter workload
setup_workload "voter" "/oltpbench/config/sample_voter_config.xml"

log ""
log "======================================"
log "✅ OLTPBench Setup Complete!"
log "======================================"
log ""
log "Summary of completed workloads:"
log "  1. ✅ twitter"
log "  2. ✅ tpcc"
log "  3. ✅ ycsb"
log "  4. ✅ wikipedia"
log "  5. ✅ tatp"
log "  6. ✅ voter"
log ""
log "Setup logs available at:"
log "  • OLTPBench build: /tmp/oltpbench_setup.log"
log "  • Twitter:   /tmp/twitter_setup.log"
log "  • TPCC:      /tmp/tpcc_setup.log"
log "  • YCSB:      /tmp/ycsb_setup.log"
log "  • Wikipedia: /tmp/wikipedia_setup.log"
log "  • TATP:      /tmp/tatp_setup.log"
log "  • Voter:     /tmp/voter_setup.log"
log ""
log "Verify databases:"
log "  mysql -u vscode -ppassword -e 'SHOW DATABASES;'"
log ""
log "You can now run optimization scripts:"
log "  cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate"
log "  export PYTHONPATH=."
log "  python scripts/optimize.py --config=scripts/twitter.ini"
log "  python scripts/optimize.py --config=scripts/tpcc.ini"
log "  python scripts/optimize.py --config=scripts/ycsb.ini"
log "  python scripts/optimize.py --config=scripts/wikipedia.ini"
log "  python scripts/optimize.py --config=scripts/tatp.ini"
log "  python scripts/optimize.py --config=scripts/voter.ini"
log ""
log "======================================"

