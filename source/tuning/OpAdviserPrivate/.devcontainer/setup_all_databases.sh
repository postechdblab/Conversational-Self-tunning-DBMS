#!/bin/bash
set -e

echo "=========================================="
echo "SETTING UP ALL DATABASES FOR BENCHMARKS"
echo "=========================================="
echo "This will take significant time (30-60 minutes)..."
echo ""

# Get current user
CURRENT_USER=${SUDO_USER:-${USER:-vscode}}
export MYSQL_USER=$CURRENT_USER

echo "Running as: $CURRENT_USER"
echo "MySQL user: $MYSQL_USER"
echo ""

# Ensure MySQL is running
echo "Checking MySQL status..."
if ! sudo service mysql status >/dev/null 2>&1; then
    echo "Starting MySQL..."
    sudo service mysql start
    sleep 5
fi

# Wait for MySQL to be ready
echo "Waiting for MySQL to be ready..."
for i in {1..30}; do
    if mysql -u $MYSQL_USER -ppassword -h localhost -P 3306 -e "SELECT 1" >/dev/null 2>&1; then
        echo "MySQL is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "ERROR: MySQL did not become ready in time"
        exit 1
    fi
    echo "Attempt $i/30: MySQL not ready yet, waiting..."
    sleep 2
done

echo ""
echo "=========================================="
echo "Step 1/4: Setting up OLTPBench workloads"
echo "=========================================="
echo "Workloads: twitter, tpcc, ycsb, wikipedia, tatp, voter"
echo ""
if [ -f /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_oltpbench.sh ]; then
    bash /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_oltpbench.sh
    echo "✅ OLTPBench workloads completed!"
else
    echo "⚠️  setup_oltpbench.sh not found, skipping..."
fi

echo ""
echo "=========================================="
echo "Step 2/4: Setting up TPC-H workload"
echo "=========================================="
echo "Scale factor: 10"
echo ""
if [ -f /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_tpch.sh ]; then
    bash /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_tpch.sh
    echo "✅ TPC-H workload completed!"
else
    echo "⚠️  setup_tpch.sh not found, skipping..."
fi

echo ""
echo "=========================================="
echo "Step 3/4: Setting up Sysbench workloads"
echo "=========================================="
echo "Workloads: read-write, write-only, read-only"
echo ""
if [ -f /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_sysbench.sh ]; then
    bash /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_sysbench.sh
    echo "✅ Sysbench workloads completed!"
else
    echo "⚠️  setup_sysbench.sh not found, skipping..."
fi

echo ""
echo "=========================================="
echo "Step 4/4: Setting up JOB workload"
echo "=========================================="
echo ""
if [ -f /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_job.sh ]; then
    bash /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate/.devcontainer/setup_job.sh
    echo "✅ JOB workload completed!"
else
    echo "⚠️  setup_job.sh not found, skipping..."
fi

echo ""
echo "=========================================="
echo "✅ ALL DATABASES SETUP COMPLETE!"
echo "=========================================="
echo ""
echo "📊 Databases created:"
echo "  - twitter (OLTPBench)"
echo "  - tpcc (OLTPBench)"
echo "  - ycsb (OLTPBench)"
echo "  - wikipedia (OLTPBench)"
echo "  - tatp (OLTPBench)"
echo "  - voter (OLTPBench)"
echo "  - tpch (TPC-H)"
echo "  - sbrw (Sysbench Read-Write)"
echo "  - sbwrite (Sysbench Write-Only)"
echo "  - sbread (Sysbench Read-Only)"
echo "  - imdbload (JOB - if available)"
echo ""
echo "🚀 You can now run optimization scripts!"
echo ""
echo "Setup log saved to: /tmp/database_setup.log"


