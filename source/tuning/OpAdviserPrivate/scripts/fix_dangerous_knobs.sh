#!/bin/bash
################################################################################
# Fix Dangerous Knobs Configuration
# 
# This script checks for dangerous knobs in the MySQL configuration and marks
# them as non-tunable to prevent data loss and system failures.
################################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
KNOB_CONFIG="$PROJECT_ROOT/scripts/experiment/gen_knobs/mysql_all_197_32G.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "Dangerous Knobs Configuration Checker"
echo "========================================"
echo ""
echo "Checking: $KNOB_CONFIG"
echo ""

# Dangerous knobs that should NEVER be tuned
DANGEROUS_KNOBS=(
    "lower_case_table_names"
    "datadir"
    "skip_networking"
    "innodb_data_home_dir"
    "innodb_log_group_home_dir"
)

# Check if config file exists
if [ ! -f "$KNOB_CONFIG" ]; then
    echo -e "${RED}Error: Knob configuration file not found!${NC}"
    echo "Expected: $KNOB_CONFIG"
    exit 1
fi

echo "Checking for dangerous knobs..."
echo ""

FOUND_DANGEROUS=0
NEEDS_FIX=()

for knob in "${DANGEROUS_KNOBS[@]}"; do
    # Check if knob exists in config
    if grep -q "\"$knob\"" "$KNOB_CONFIG"; then
        # Check if it's marked as tunable
        # Extract the knob block and check tunable field
        knob_block=$(sed -n "/\"name\": *\"$knob\"/,/}/p" "$KNOB_CONFIG")
        
        if echo "$knob_block" | grep -q '"tunable": *true'; then
            echo -e "${RED}⚠️  DANGER: $knob is marked as TUNABLE${NC}"
            echo "   This knob can cause DATA LOSS or system failures!"
            FOUND_DANGEROUS=1
            NEEDS_FIX+=("$knob")
        elif echo "$knob_block" | grep -q '"tunable": *false'; then
            echo -e "${GREEN}✓  SAFE: $knob is correctly marked as non-tunable${NC}"
        else
            echo -e "${YELLOW}⚠  WARNING: $knob found but tunable status unclear${NC}"
            NEEDS_FIX+=("$knob")
        fi
    else
        echo -e "${GREEN}✓  Not present: $knob (not in config)${NC}"
    fi
done

echo ""
echo "========================================"

if [ $FOUND_DANGEROUS -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed!${NC}"
    echo "No dangerous knobs are marked as tunable."
    echo ""
    exit 0
fi

echo -e "${RED}❌ DANGEROUS CONFIGURATION DETECTED!${NC}"
echo ""
echo "The following knobs need to be fixed:"
for knob in "${NEEDS_FIX[@]}"; do
    echo "  - $knob"
done
echo ""

# Offer to fix automatically
read -p "Would you like to automatically fix these knobs? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Creating backup..."
    cp "$KNOB_CONFIG" "$KNOB_CONFIG.backup.$(date +%Y%m%d_%H%M%S)"
    echo "Backup created: $KNOB_CONFIG.backup.*"
    echo ""
    
    echo "Fixing dangerous knobs..."
    for knob in "${NEEDS_FIX[@]}"; do
        # Use Python for accurate JSON manipulation
        python3 << EOF
import json
import sys

config_file = "$KNOB_CONFIG"
knob_name = "$knob"

try:
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Find and fix the knob
    if isinstance(config, list):
        for knob_obj in config:
            if knob_obj.get('name') == knob_name:
                knob_obj['tunable'] = False
                if 'comment' not in knob_obj or not knob_obj['comment']:
                    knob_obj['comment'] = 'DANGEROUS: Can cause data loss - marked non-tunable'
                print(f"  Fixed: {knob_name}")
                break
    
    # Write back
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
except Exception as e:
    print(f"  Error fixing {knob_name}: {e}", file=sys.stderr)
    sys.exit(1)
EOF
    done
    
    echo ""
    echo -e "${GREEN}✅ Configuration fixed!${NC}"
    echo ""
    echo "Summary:"
    echo "  - Backup created: $KNOB_CONFIG.backup.*"
    echo "  - Dangerous knobs marked as non-tunable"
    echo "  - Safe to run experiments now"
    echo ""
else
    echo ""
    echo "No changes made. Please manually edit:"
    echo "  $KNOB_CONFIG"
    echo ""
    echo "For each dangerous knob, set:"
    echo '  "tunable": false'
    echo ""
    exit 1
fi

echo "========================================"
echo ""
echo "⚠️  IMPORTANT REMINDER:"
echo ""
echo "If you already lost data due to lower_case_table_names,"
echo "you MUST reload the database:"
echo ""
echo "  bash scripts/quick_init_tpcc.sh"
echo ""
echo "========================================"

