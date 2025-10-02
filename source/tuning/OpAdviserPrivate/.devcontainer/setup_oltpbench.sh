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
sudo rm -rf oltpbench
sudo git clone https://github.com/seokjeongeum/oltpbench.git
sudo chown -R $CURRENT_USER:$CURRENT_USER /oltpbench
cd /oltpbench
ant bootstrap
ant resolve
ant build
chmod 777 /oltpbench/*

log "✅ OLTPBench built successfully!"

# Function to setup a workload
setup_workload() {
    local WORKLOAD_NAME=$1
    local CONFIG_FILE=$2
    
    log "=========================================="
    log "Setting up ${WORKLOAD_NAME} workload..."
    log "Start: $(date)"
    log "Dropping existing database ${WORKLOAD_NAME} (if exists)..."
    mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"DROP DATABASE IF EXISTS ${WORKLOAD_NAME};"
    log "Creating database ${WORKLOAD_NAME}..."
    mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"CREATE DATABASE ${WORKLOAD_NAME};"
    log "Loading data into ${WORKLOAD_NAME}..."
    /oltpbench/oltpbenchmark -b ${WORKLOAD_NAME} -c ${CONFIG_FILE} --create=true --load=true
    log "✅ ${WORKLOAD_NAME} workload prepared!"
    log "End: $(date)"
    log "=========================================="
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
echo "You can now run:"
echo "  cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate"
echo "  export PYTHONPATH=."
echo "  python scripts/optimize.py --config=scripts/twitter.ini"
echo "  python scripts/optimize.py --config=scripts/tpcc.ini"
echo "  python scripts/optimize.py --config=scripts/ycsb.ini"
echo "  python scripts/optimize.py --config=scripts/wikipedia.ini"
echo "  python scripts/optimize.py --config=scripts/tatp.ini"
echo "  python scripts/optimize.py --config=scripts/voter.ini"

