#!/bin/bash
set -e

echo "=========================================="
echo "POST-CREATE SETUP"
echo "=========================================="
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

