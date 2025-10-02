#!/bin/bash
set -e

echo "=========================================="
echo "POST-CREATE SETUP"
echo "=========================================="
echo ""

# Ensure MySQL is running before proceeding
echo "Checking MySQL status..."
if ! sudo service mysql status >/dev/null 2>&1; then
    echo "MySQL is not running. Starting MySQL..."
    sudo service mysql start
    sleep 5
fi

# Wait for MySQL to be fully ready
echo "Waiting for MySQL to be ready..."
MAX_ATTEMPTS=30
for i in $(seq 1 $MAX_ATTEMPTS); do
    if mysql -u root -ppassword -h localhost -P 3306 -e "SELECT 1" >/dev/null 2>&1; then
        echo "✅ MySQL is ready on port 3306!"
        break
    fi
    if [ $i -eq $MAX_ATTEMPTS ]; then
        echo "❌ ERROR: MySQL did not become ready after ${MAX_ATTEMPTS} attempts"
        echo "Please check MySQL status manually: sudo service mysql status"
        exit 1
    fi
    echo "  Attempt $i/$MAX_ATTEMPTS: MySQL not ready yet, waiting..."
    sleep 2
done
echo ""

# Install/upgrade Python packages from requirements.txt
echo "Installing Python packages..."
if [ -f requirements.txt ]; then
    python3.8 -m pip install --user --upgrade pip setuptools wheel
    python3.8 -m pip install --user -r requirements.txt
    echo "✅ Python packages installed"
else
    echo "⚠️  requirements.txt not found, skipping Python package installation"
fi

echo ""
echo "=========================================="
echo "STARTING DATABASE POPULATION"
echo "=========================================="
echo ""
echo "Databases will be populated in the background."
echo "This process takes 30-60 minutes."
echo ""
echo "To monitor progress:"
echo "  tail -f /tmp/database_setup.log"
echo ""
echo "To check status:"
echo "  bash .devcontainer/check_database_status.sh"
echo ""
echo "=========================================="

# Start database population in background
nohup bash .devcontainer/setup_all_databases.sh > /tmp/database_setup.log 2>&1 &

echo "✅ Database population started (PID: $!)"
echo ""

