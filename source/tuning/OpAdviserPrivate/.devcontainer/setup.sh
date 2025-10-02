#!/bin/bash
set -e  # Exit on error, but we'll handle errors explicitly

echo "=== Starting devcontainer setup ==="
echo "Running as user: $(whoami)"

# Update package list with retries
echo "Updating package list..."
for i in {1..3}; do
    if apt-get update; then
        break
    else
        echo "Retry $i: apt-get update failed, retrying..."
        sleep 2
    fi
done

# Install basic dependencies
echo "Installing basic dependencies..."
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git \
    ant \
    build-essential \
    openssh-client \
    cgroup-tools \
    libaio1 \
    libaio-dev \
    autoconf \
    pkg-config \
    libtool \
    automake \
    sudo \
    unzip \
    wget \
    curl \
    gnupg \
    ca-certificates \
    software-properties-common || { echo "Failed to install basic dependencies"; exit 1; }

# Add deadsnakes PPA for Python 3.8
echo "Adding Python PPA and installing Python 3.8..."
if ! add-apt-repository -y ppa:deadsnakes/ppa 2>&1; then
    echo "Warning: Could not add deadsnakes PPA, trying to continue with system Python..."
fi
apt-get update || true

# Try to install Python 3.8
echo "Installing Python 3.8..."
if DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3.8 \
    python3.8-dev \
    python3.8-distutils \
    python3-pip \
    python3-setuptools; then
    echo "Python 3.8 installed successfully"
else
    echo "Error: Failed to install Python 3.8"
    exit 1
fi

# Set up Python alternatives and symlinks
echo "Setting up Python alternatives..."
update-alternatives --install /usr/bin/python python /usr/bin/python3.8 1 || true
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.8 1 || true
ln -sf /usr/bin/python3.8 /usr/local/bin/python || true
ln -sf /usr/bin/pip3 /usr/local/bin/pip || true

# Verify Python installation
python3.8 --version || { echo "Python 3.8 verification failed"; exit 1; }

# Install Java 11
echo "Installing Java 11..."
DEBIAN_FRONTEND=noninteractive apt-get install -y openjdk-11-jdk || { echo "Failed to install Java 11"; exit 1; }

# Verify Java installation
java -version || { echo "Java verification failed"; exit 1; }

# Install MySQL 5.7 with proper repo setup for Bionic
echo "Installing MySQL 5.7..."
# For Ubuntu Bionic (18.04), MySQL 5.7 should be available in default repos
if DEBIAN_FRONTEND=noninteractive apt-get install -y \
    mysql-server-5.7 \
    mysql-client-5.7 \
    libmysqlclient-dev 2>&1; then
    echo "MySQL 5.7 installed successfully"
else
    echo "Error: Failed to install MySQL 5.7"
    echo "Checking available MySQL packages..."
    apt-cache search mysql-server || true
    exit 1
fi

# Configure MySQL
echo "Configuring MySQL..."
mkdir -p /etc/mysql
if [ -f /etc/mysql/my.cnf ]; then
    # Backup original config
    cp /etc/mysql/my.cnf /etc/mysql/my.cnf.backup
    # Append our configuration
    if ! grep -q "port=3308" /etc/mysql/my.cnf; then
        echo '' >> /etc/mysql/my.cnf
        echo '[mysqld]' >> /etc/mysql/my.cnf
        echo 'port=3308' >> /etc/mysql/my.cnf
        echo 'innodb_log_checksums = 0' >> /etc/mysql/my.cnf
        echo "MySQL configuration updated"
    fi
else
    echo "Creating new MySQL configuration at /etc/mysql/my.cnf"
    echo '[mysqld]' > /etc/mysql/my.cnf
    echo 'port=3308' >> /etc/mysql/my.cnf
    echo 'innodb_log_checksums = 0' >> /etc/mysql/my.cnf
fi

# Create MySQL log directories
echo "Setting up MySQL log directories..."
mkdir -p /var/log/mysql/base
touch /var/log/mysql/base/mysql-slow.log
chmod 777 /var/log/mysql/base/mysql-slow.log
chown -R mysql:mysql /var/log/mysql 2>/dev/null || true

# Set up sudo permissions for current user
echo "Setting up sudo permissions for current user..."
SETUP_USER=${SUDO_USER:-${USER:-vscode}}
echo "Configuring sudo for user: $SETUP_USER"
if id "$SETUP_USER" &>/dev/null; then
    usermod -aG sudo $SETUP_USER 2>/dev/null || echo "Warning: Could not add $SETUP_USER to sudo group"
    # Use sudoers.d for better practice
    echo "$SETUP_USER ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/$SETUP_USER
    chmod 0440 /etc/sudoers.d/$SETUP_USER
    echo "$SETUP_USER user configured successfully"
else
    echo "Warning: $SETUP_USER user does not exist yet, will be created by devcontainer"
fi

# Initialize MySQL data directory if needed
echo "Initializing MySQL..."
if [ ! -d "/var/lib/mysql/mysql" ]; then
    echo "MySQL data directory not initialized, running mysqld --initialize-insecure..."
    mysqld --initialize-insecure --user=mysql 2>&1 || echo "Warning: MySQL initialization might have failed"
fi

# Start MySQL and configure users
echo "Starting MySQL service..."
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
fi

echo "=== Devcontainer setup completed successfully ==="
