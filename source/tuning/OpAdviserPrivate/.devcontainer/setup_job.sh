#!/bin/bash
set -e

echo "======================================"
echo "Setting up JOB (Join Order Benchmark)"
echo "======================================"

cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate

# Make job.sh executable and run it
if [ -f ./job.sh ]; then
    chmod +x ./job.sh
    ./job.sh
    echo "JOB setup completed!"
else
    echo "Warning: job.sh not found!"
fi

echo "======================================"
echo "JOB Setup Complete!"
echo "======================================"
echo "You can now run:"
echo "  cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate"
echo "  export PYTHONPATH=."
echo "  python scripts/optimize.py --config=scripts/job.ini"

