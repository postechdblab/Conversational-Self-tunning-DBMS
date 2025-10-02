#!/bin/bash

echo "=========================================="
echo "DATABASE SETUP STATUS"
echo "=========================================="
echo ""

# Check if setup is running
if pgrep -f "setup_all_databases.sh" > /dev/null; then
    echo "✅ Database setup is currently RUNNING"
    echo ""
    echo "📊 Progress (last 20 lines):"
    echo "----------------------------------------"
    if [ -f /tmp/database_setup.log ]; then
        tail -20 /tmp/database_setup.log
    else
        echo "Log file not found yet..."
    fi
    echo ""
    echo "To view live progress: tail -f /tmp/database_setup.log"
else
    if [ -f /tmp/database_setup.log ]; then
        if grep -q "ALL DATABASES SETUP COMPLETE" /tmp/database_setup.log; then
            echo "✅ Database setup COMPLETED successfully!"
            echo ""
            echo "📊 Summary:"
            grep "Databases created:" -A 15 /tmp/database_setup.log | head -16
        else
            echo "⚠️  Database setup appears to have STOPPED"
            echo ""
            echo "Last 30 lines of log:"
            echo "----------------------------------------"
            tail -30 /tmp/database_setup.log
            echo ""
            echo "To restart: bash .devcontainer/setup_all_databases.sh"
        fi
    else
        echo "❌ Database setup has NOT been run yet"
        echo ""
        echo "To start: bash .devcontainer/setup_all_databases.sh"
    fi
fi

echo ""
echo "=========================================="
echo "MYSQL DATABASES"
echo "=========================================="
if mysql -u root -ppassword -h localhost -P 3306 -e "SHOW DATABASES;" 2>/dev/null | grep -v "information_schema\|performance_schema\|mysql\|sys\|Database"; then
    echo ""
    echo "To connect to MySQL:"
    echo "  ./mysql-connect.sh"
    echo "  or: mysql -u root -ppassword -h localhost -P 3306"
else
    echo "⚠️  Could not connect to MySQL"
    echo "Make sure MySQL is running: sudo service mysql start"
fi

echo ""


