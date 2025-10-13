#!/bin/bash
# Quick test script for --ensemble-mode and --augment-history features

set -e

cd "$(dirname "$0")/.."

echo "=========================================="
echo "Quick Feature Test"
echo "=========================================="
echo ""

# Check if twitter database exists
echo "Checking database availability..."
if mysql -u root -ppassword -h localhost -P 3306 -e "USE twitter;" 2>/dev/null; then
    echo "✅ Twitter database found"
else
    echo "❌ Twitter database not found"
    echo "   Please run database setup first:"
    echo "   bash .devcontainer/setup_oltpbench.sh"
    exit 1
fi

echo ""
echo "=========================================="
echo "Running Test"
echo "=========================================="
echo "Config: scripts/twitter_test.ini"
echo "Features: ensemble_mode=True, augment_history=True"
echo "Duration: ~15-30 minutes"
echo ""
echo "Press Ctrl+C to cancel, or wait 5 seconds to start..."
sleep 5

echo ""
echo "Starting tuning..."
python scripts/optimize.py --config=scripts/twitter_test.ini

echo ""
echo "=========================================="
echo "Test Complete - Running Verification"
echo "=========================================="
echo ""

# Run verification
bash scripts/verify_features.sh twitter_test_ensemble_augment

echo ""
echo "=========================================="
echo "Quick Test Complete"
echo "=========================================="
echo ""
echo "Log file: logs/twitter_test_ensemble_augment.log"
echo "History: logs/twitter_test_ensemble_augment/"
echo ""
echo "To view full log:"
echo "  cat logs/twitter_test_ensemble_augment.log"
echo ""
echo "To search for specific features:"
echo "  grep '\[Ensemble\]' logs/twitter_test_ensemble_augment.log"
echo "  grep '\[Augmentation\]' logs/twitter_test_ensemble_augment.log"
echo ""

