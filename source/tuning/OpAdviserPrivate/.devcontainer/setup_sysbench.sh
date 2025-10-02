#!/bin/bash
set -e

echo "======================================"
echo "Setting up Sysbench Workloads"
echo "======================================"

# Get current user
CURRENT_USER=$(whoami)
MYSQL_USER=${CURRENT_USER}
echo "Running as system user: $CURRENT_USER"
echo "Using MySQL user: $MYSQL_USER"

# Install Sysbench
echo "Installing Sysbench..."
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

echo "Sysbench installed successfully!"

# Setup Sysbench Read-Write Database
echo "Setting up Sysbench Read-Write database..."
mysql -h localhost -P 3308 -u $MYSQL_USER -ppassword -e"DROP DATABASE IF EXISTS sbrw;"
mysql -h localhost -P 3308 -u $MYSQL_USER -ppassword -e"CREATE DATABASE sbrw;"
sysbench \
    --db-driver=mysql \
    --mysql-host=localhost \
    --mysql-port=3308 \
    --mysql-user=$MYSQL_USER \
    --mysql-password=password \
    --table_size=800000 \
    --tables=300 \
    --events=0 \
    --threads=80 \
    --mysql-db=sbrw \
    oltp_read_write \
    prepare

echo "Sysbench Read-Write database prepared!"

# Setup Sysbench Write-Only Database
echo "Setting up Sysbench Write-Only database..."
mysql -h localhost -P 3308 -u $MYSQL_USER -ppassword -e"DROP DATABASE IF EXISTS sbwrite;"
mysql -h localhost -P 3308 -u $MYSQL_USER -ppassword -e"CREATE DATABASE sbwrite;"
sysbench \
    --db-driver=mysql \
    --mysql-host=localhost \
    --mysql-port=3308 \
    --mysql-user=$MYSQL_USER \
    --mysql-password=password \
    --table_size=800000 \
    --tables=300 \
    --events=0 \
    --threads=80 \
    --mysql-db=sbwrite \
    oltp_write_only \
    prepare

echo "Sysbench Write-Only database prepared!"

# Setup Sysbench Read-Only Database
echo "Setting up Sysbench Read-Only database..."
mysql -h localhost -P 3308 -u $MYSQL_USER -ppassword -e"DROP DATABASE IF EXISTS sbread;"
mysql -h localhost -P 3308 -u $MYSQL_USER -ppassword -e"CREATE DATABASE sbread;"
sysbench \
    --db-driver=mysql \
    --mysql-host=localhost \
    --mysql-port=3308 \
    --mysql-user=$MYSQL_USER \
    --mysql-password=password \
    --table_size=800000 \
    --tables=300 \
    --events=0 \
    --threads=80 \
    --mysql-db=sbread \
    oltp_read_only \
    prepare

echo "Sysbench Read-Only database prepared!"

echo "======================================"
echo "Sysbench Setup Complete!"
echo "======================================"
echo "You can now run:"
echo "  cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate"
echo "  export PYTHONPATH=."
echo "  python scripts/optimize.py --config=scripts/sysbench_rw.ini"
echo "  python scripts/optimize.py --config=scripts/sysbench_wo.ini"
echo "  python scripts/optimize.py --config=scripts/sysbench_ro.ini"

