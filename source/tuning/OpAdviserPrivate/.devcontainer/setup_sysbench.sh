#!/bin/bash
set -e  # Exit on error
set -x  # Verbose mode

# Function to print with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "======================================"
log "Setting up Sysbench Workloads"
log "======================================"

# Get current user
CURRENT_USER=$(whoami)
MYSQL_USER=${CURRENT_USER}
log "Running as system user: $CURRENT_USER"
log "Using MySQL user: $MYSQL_USER"

# Install Sysbench
INSTALL_START=$(date +%s)
log "Installing Sysbench (this may take 5-10 minutes)..."
cd /
log "  → Removing old sysbench directory (if exists)..."
sudo rm -rf sysbench
log "  → Cloning sysbench from GitHub..."
sudo git clone --verbose https://github.com/akopytov/sysbench.git 2>&1 | tee -a /tmp/sysbench_setup.log
sudo chown -R $CURRENT_USER:$CURRENT_USER sysbench
cd sysbench
log "  → Checking out specific commit..."
git checkout ead2689ac6f61c5e7ba7c6e19198b86bd3a51d3c 2>&1 | tee -a /tmp/sysbench_setup.log
log "  → Running autogen.sh..."
./autogen.sh 2>&1 | tee -a /tmp/sysbench_setup.log
log "  → Configuring build..."
./configure 2>&1 | tee -a /tmp/sysbench_setup.log
log "  → Compiling sysbench..."
make 2>&1 | tee -a /tmp/sysbench_setup.log
log "  → Installing sysbench..."
sudo make install 2>&1 | tee -a /tmp/sysbench_setup.log
INSTALL_END=$(date +%s)
INSTALL_TIME=$((INSTALL_END - INSTALL_START))
INSTALL_MIN=$((INSTALL_TIME / 60))
INSTALL_SEC=$((INSTALL_TIME % 60))

log "✅ Sysbench installed successfully! (took ${INSTALL_MIN}m ${INSTALL_SEC}s)"

# Setup Sysbench Read-Write Database
SBRW_START=$(date +%s)
log "=========================================="
log "Setting up Sysbench Read-Write database..."
log "This will create 300 tables with 800K rows each"
log "Estimated time: 10-15 minutes"
log "=========================================="
log "  → Dropping existing database (if exists)..."
mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"DROP DATABASE IF EXISTS sbrw;" 2>&1 | tee -a /tmp/sysbench_setup.log
log "  → Creating database 'sbrw'..."
mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"CREATE DATABASE sbrw;" 2>&1 | tee -a /tmp/sysbench_setup.log
log "  → Preparing tables and loading data..."
sysbench \
    --db-driver=mysql \
    --mysql-host=localhost \
    --mysql-port=3306 \
    --mysql-user=$MYSQL_USER \
    --mysql-password=password \
    --table_size=800000 \
    --tables=300 \
    --events=0 \
    --threads=80 \
    --mysql-db=sbrw \
    oltp_read_write \
    prepare 2>&1 | tee -a /tmp/sysbench_sbrw.log
SBRW_END=$(date +%s)
SBRW_TIME=$((SBRW_END - SBRW_START))
SBRW_MIN=$((SBRW_TIME / 60))
SBRW_SEC=$((SBRW_TIME % 60))

log "✅ Sysbench Read-Write database prepared! (took ${SBRW_MIN}m ${SBRW_SEC}s)"

# Setup Sysbench Write-Only Database
SBWRITE_START=$(date +%s)
log "=========================================="
log "Setting up Sysbench Write-Only database..."
log "This will create 300 tables with 800K rows each"
log "Estimated time: 10-15 minutes"
log "=========================================="
log "  → Dropping existing database (if exists)..."
mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"DROP DATABASE IF EXISTS sbwrite;" 2>&1 | tee -a /tmp/sysbench_setup.log
log "  → Creating database 'sbwrite'..."
mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"CREATE DATABASE sbwrite;" 2>&1 | tee -a /tmp/sysbench_setup.log
log "  → Preparing tables and loading data..."
sysbench \
    --db-driver=mysql \
    --mysql-host=localhost \
    --mysql-port=3306 \
    --mysql-user=$MYSQL_USER \
    --mysql-password=password \
    --table_size=800000 \
    --tables=300 \
    --events=0 \
    --threads=80 \
    --mysql-db=sbwrite \
    oltp_write_only \
    prepare 2>&1 | tee -a /tmp/sysbench_sbwrite.log
SBWRITE_END=$(date +%s)
SBWRITE_TIME=$((SBWRITE_END - SBWRITE_START))
SBWRITE_MIN=$((SBWRITE_TIME / 60))
SBWRITE_SEC=$((SBWRITE_TIME % 60))

log "✅ Sysbench Write-Only database prepared! (took ${SBWRITE_MIN}m ${SBWRITE_SEC}s)"

# Setup Sysbench Read-Only Database
SBREAD_START=$(date +%s)
log "=========================================="
log "Setting up Sysbench Read-Only database..."
log "This will create 300 tables with 800K rows each"
log "Estimated time: 10-15 minutes"
log "=========================================="
log "  → Dropping existing database (if exists)..."
mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"DROP DATABASE IF EXISTS sbread;" 2>&1 | tee -a /tmp/sysbench_setup.log
log "  → Creating database 'sbread'..."
mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"CREATE DATABASE sbread;" 2>&1 | tee -a /tmp/sysbench_setup.log
log "  → Preparing tables and loading data..."
sysbench \
    --db-driver=mysql \
    --mysql-host=localhost \
    --mysql-port=3306 \
    --mysql-user=$MYSQL_USER \
    --mysql-password=password \
    --table_size=800000 \
    --tables=300 \
    --events=0 \
    --threads=80 \
    --mysql-db=sbread \
    oltp_read_only \
    prepare 2>&1 | tee -a /tmp/sysbench_sbread.log
SBREAD_END=$(date +%s)
SBREAD_TIME=$((SBREAD_END - SBREAD_START))
SBREAD_MIN=$((SBREAD_TIME / 60))
SBREAD_SEC=$((SBREAD_TIME % 60))

log "✅ Sysbench Read-Only database prepared! (took ${SBREAD_MIN}m ${SBREAD_SEC}s)"

log ""
log "======================================"
log "✅ Sysbench Setup Complete!"
log "======================================"
log ""
log "Summary of databases created:"
log "  1. ✅ sbrw (Read-Write workload)"
log "  2. ✅ sbwrite (Write-Only workload)"
log "  3. ✅ sbread (Read-Only workload)"
log ""
log "Setup logs available at:"
log "  • Install:      /tmp/sysbench_setup.log"
log "  • Read-Write:   /tmp/sysbench_sbrw.log"
log "  • Write-Only:   /tmp/sysbench_sbwrite.log"
log "  • Read-Only:    /tmp/sysbench_sbread.log"
log ""
log "You can now run:"
log "  cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate"
log "  export PYTHONPATH=."
log "  python scripts/optimize.py --config=scripts/sysbench_rw.ini"
log "  python scripts/optimize.py --config=scripts/sysbench_wo.ini"
log "  python scripts/optimize.py --config=scripts/sysbench_ro.ini"
log ""

