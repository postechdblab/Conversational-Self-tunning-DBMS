#!/bin/bash
# Utility script to ensure MySQL is running and ready
# Can be called from any other script

set -e

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "Checking MySQL status..."

# Check if MySQL service is running
if ! sudo service mysql status >/dev/null 2>&1; then
    log "MySQL is not running. Starting MySQL service..."
    if ! sudo service mysql start 2>&1; then
        log "❌ ERROR: Failed to start MySQL service"
        log "Checking MySQL error log:"
        sudo tail -20 /var/log/mysql/error.log 2>/dev/null || log "Could not read error log"
        exit 1
    fi
    log "✅ MySQL service started"
    sleep 3
else
    log "✅ MySQL service is running"
fi

# Wait for MySQL to accept connections
log "Verifying MySQL is accepting connections on port 3306..."
MAX_ATTEMPTS=30
ATTEMPT=1

while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    if mysql -u root -ppassword -h localhost -P 3306 -e "SELECT 1" >/dev/null 2>&1; then
        # Get MySQL version and port
        MYSQL_VERSION=$(mysql -u root -ppassword -h localhost -P 3306 -e "SELECT @@version" 2>/dev/null | tail -1)
        MYSQL_PORT=$(mysql -u root -ppassword -h localhost -P 3306 -e "SELECT @@port" 2>/dev/null | tail -1)
        log "✅ MySQL is ready!"
        log "   Version: $MYSQL_VERSION"
        log "   Port: $MYSQL_PORT"
        exit 0
    fi
    
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        log "❌ ERROR: MySQL did not become ready after ${MAX_ATTEMPTS} attempts"
        log ""
        log "Troubleshooting information:"
        log "----------------------------------------"
        
        # Service status
        log "MySQL service status:"
        sudo service mysql status 2>&1 | head -10 || log "  Could not get status"
        
        # Port check
        log ""
        log "Port 3306 status:"
        sudo netstat -tlnp 2>/dev/null | grep 3306 || log "  Port 3306 not listening"
        
        # Error log
        log ""
        log "Recent MySQL errors:"
        sudo tail -20 /var/log/mysql/error.log 2>/dev/null || log "  Could not read error log"
        
        exit 1
    fi
    
    log "  Attempt $ATTEMPT/$MAX_ATTEMPTS: Waiting for MySQL..."
    sleep 2
    ATTEMPT=$((ATTEMPT + 1))
done

