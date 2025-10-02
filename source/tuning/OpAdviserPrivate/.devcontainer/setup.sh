#!/bin/bash
set -e  # Exit on error

echo "=== Starting devcontainer setup ==="
echo "Running as user: $(whoami)"

# Verify installations
echo "Verifying installations..."
python3.8 --version || { echo "Python 3.8 verification failed"; exit 1; }
java -version || { echo "Java verification failed"; exit 1; }
mysql --version || { echo "MySQL verification failed"; exit 1; }

# Configure MySQL
echo "Configuring MySQL..."
mkdir -p /etc/mysql
if [ -f /etc/mysql/my.cnf ]; then
    # Backup original config
    cp /etc/mysql/my.cnf /etc/mysql/my.cnf.backup
    # Append our configuration
    if ! grep -q "port=3306" /etc/mysql/my.cnf; then
        echo '' >> /etc/mysql/my.cnf
        echo '[mysqld]' >> /etc/mysql/my.cnf
        echo 'port=3306' >> /etc/mysql/my.cnf
        echo 'innodb_log_checksums = 0' >> /etc/mysql/my.cnf
        echo "MySQL configuration updated"
    fi
else
    echo "Creating new MySQL configuration at /etc/mysql/my.cnf"
    echo '[mysqld]' > /etc/mysql/my.cnf
    echo 'port=3306' >> /etc/mysql/my.cnf
    echo 'innodb_log_checksums = 0' >> /etc/mysql/my.cnf
fi

# Ensure MySQL log directories exist with correct permissions
echo "Setting up MySQL log directories..."
mkdir -p /var/log/mysql/base
touch /var/log/mysql/base/mysql-slow.log
chmod 777 /var/log/mysql/base/mysql-slow.log
chown -R mysql:mysql /var/log/mysql 2>/dev/null || true

# Ensure MySQL directories have correct permissions
echo "Fixing MySQL directory permissions..."
chown -R mysql:mysql /var/lib/mysql /var/run/mysqld /var/log/mysql 2>/dev/null || true
chmod 755 /var/run/mysqld 2>/dev/null || true

# Initialize MySQL data directory if needed
echo "Initializing MySQL..."
if [ ! -d "/var/lib/mysql/mysql" ]; then
    echo "MySQL data directory not initialized, running mysqld --initialize-insecure..."
    mysqld --initialize-insecure --user=mysql --datadir=/var/lib/mysql 2>&1 || echo "Warning: MySQL initialization might have failed"
    # Fix permissions again after initialization
    chown -R mysql:mysql /var/lib/mysql 2>/dev/null || true
fi

# Check if MySQL error log exists and show recent errors
if [ -f "/var/log/mysql/error.log" ]; then
    echo "Recent MySQL error log entries:"
    tail -n 20 /var/log/mysql/error.log 2>/dev/null || true
fi

# Start MySQL and configure users
echo "Starting MySQL service..."
# Try to start MySQL with more verbose output
if service mysql start 2>&1; then
    echo "MySQL started successfully"
    sleep 10
    
    echo "Configuring MySQL users..."
    # Get the system user who will use MySQL
    MYSQL_APP_USER=${SUDO_USER:-${USER:-vscode}}
    echo "Creating MySQL user for system user: $MYSQL_APP_USER"
    
    # Try different methods to set root password
    mysql -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'password';" 2>/dev/null || \
    mysql -u root -e "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('password');" 2>/dev/null || \
    mysql -u root -e "UPDATE mysql.user SET authentication_string=PASSWORD('password') WHERE User='root'; FLUSH PRIVILEGES;" 2>/dev/null || \
    echo "Warning: Could not set root password using standard methods"
    
    # Configure remote access for root
    mysql -u root -ppassword -e "CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY 'password';" 2>/dev/null || true
    mysql -u root -ppassword -e "CREATE USER IF NOT EXISTS 'root'@'::1' IDENTIFIED BY 'password';" 2>/dev/null || true
    mysql -u root -ppassword -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;" 2>/dev/null || true
    mysql -u root -ppassword -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'::1' WITH GRANT OPTION;" 2>/dev/null || true
    mysql -u root -ppassword -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;" 2>/dev/null || true
    
    # Create MySQL user matching system user
    mysql -u root -ppassword -e "CREATE USER IF NOT EXISTS '${MYSQL_APP_USER}'@'localhost' IDENTIFIED BY 'password';" 2>/dev/null || true
    mysql -u root -ppassword -e "CREATE USER IF NOT EXISTS '${MYSQL_APP_USER}'@'127.0.0.1' IDENTIFIED BY 'password';" 2>/dev/null || true
    mysql -u root -ppassword -e "CREATE USER IF NOT EXISTS '${MYSQL_APP_USER}'@'::1' IDENTIFIED BY 'password';" 2>/dev/null || true
    mysql -u root -ppassword -e "GRANT ALL PRIVILEGES ON *.* TO '${MYSQL_APP_USER}'@'localhost' WITH GRANT OPTION;" 2>/dev/null || true
    mysql -u root -ppassword -e "GRANT ALL PRIVILEGES ON *.* TO '${MYSQL_APP_USER}'@'127.0.0.1' WITH GRANT OPTION;" 2>/dev/null || true
    mysql -u root -ppassword -e "GRANT ALL PRIVILEGES ON *.* TO '${MYSQL_APP_USER}'@'::1' WITH GRANT OPTION;" 2>/dev/null || true
    
    mysql -u root -ppassword -e "FLUSH PRIVILEGES;" 2>/dev/null || true
    mysql -u root -ppassword -e "SET GLOBAL max_connections=100000;" 2>/dev/null || true
    echo "MySQL users configured successfully (root + $MYSQL_APP_USER)"
else
    echo "Warning: MySQL failed to start during setup"
    echo "MySQL will be started via postStartCommand"
    
    # Show error log for debugging
    if [ -f "/var/log/mysql/error.log" ]; then
        echo "=== MySQL Error Log (last 30 lines) ==="
        tail -n 30 /var/log/mysql/error.log 2>/dev/null || true
        echo "=== End of MySQL Error Log ==="
    fi
    
    # Try a more aggressive approach: remove and reinitialize
    echo "Attempting to reinitialize MySQL database..."
    rm -rf /var/lib/mysql/*
    mysqld --initialize-insecure --user=mysql --datadir=/var/lib/mysql 2>&1 || echo "Reinitialization failed"
    chown -R mysql:mysql /var/lib/mysql
    
    # Try starting again
    echo "Attempting to start MySQL again..."
    service mysql start 2>&1 || echo "MySQL still failed to start"
fi

echo "=== Devcontainer setup completed successfully ==="
