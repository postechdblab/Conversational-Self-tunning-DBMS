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
log "Installing Sysbench (this may take 5-10 minutes)..."
cd /
sudo rm -rf sysbench
sudo git clone https://github.com/akopytov/sysbench.git
sudo chown -R $CURRENT_USER:$CURRENT_USER sysbench
cd sysbench
git checkout ead2689ac6f61c5e7ba7c6e19198b86bd3a51d3c
./autogen.sh
./configure
make
sudo make install

log "✅ Sysbench installed successfully!"

# Setup Sysbench Read-Write Database
log "=========================================="
log "Setting up Sysbench Read-Write database..."
log "This will create 300 tables with 800K rows each"
log "Estimated time: 10-15 minutes"
log "=========================================="
mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"DROP DATABASE IF EXISTS sbrw;"
mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"CREATE DATABASE sbrw;"
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
    prepare

log "✅ Sysbench Read-Write database prepared!"

# Setup Sysbench Write-Only Database
log "=========================================="
log "Setting up Sysbench Write-Only database..."
log "This will create 300 tables with 800K rows each"
log "Estimated time: 10-15 minutes"
log "=========================================="
mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"DROP DATABASE IF EXISTS sbwrite;"
mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"CREATE DATABASE sbwrite;"
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
    prepare

log "✅ Sysbench Write-Only database prepared!"

# Setup Sysbench Read-Only Database
log "=========================================="
log "Setting up Sysbench Read-Only database..."
log "This will create 300 tables with 800K rows each"
log "Estimated time: 10-15 minutes"
log "=========================================="
mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"DROP DATABASE IF EXISTS sbread;"
mysql -h localhost -P 3306 -u $MYSQL_USER -ppassword -e"CREATE DATABASE sbread;"
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
    prepare

log "✅ Sysbench Read-Only database prepared!"

log ""
log "======================================"
log "✅ Sysbench Setup Complete!"
log "======================================"
echo "You can now run:"
echo "  cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate"
echo "  export PYTHONPATH=."
echo "  python scripts/optimize.py --config=scripts/sysbench_rw.ini"
echo "  python scripts/optimize.py --config=scripts/sysbench_wo.ini"
echo "  python scripts/optimize.py --config=scripts/sysbench_ro.ini"

