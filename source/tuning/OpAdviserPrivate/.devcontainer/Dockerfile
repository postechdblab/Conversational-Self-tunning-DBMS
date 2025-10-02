FROM mcr.microsoft.com/devcontainers/base:bionic

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Fix /tmp permissions FIRST - critical for apt-get to work during build
RUN chmod 1777 /tmp

# Fix sudo permissions - this is critical for devcontainers
RUN chown root:root /usr/bin/sudo && \
    chmod 4755 /usr/bin/sudo

# Update package list and install basic dependencies including CMake
RUN apt-get update && apt-get install -y \
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
    software-properties-common \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Add deadsnakes PPA and install Python 3.8
RUN add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y \
    python3.8 \
    python3.8-dev \
    python3.8-distutils \
    python3-pip \
    python3-setuptools \
    && rm -rf /var/lib/apt/lists/*

# Set up Python alternatives
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.8 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.8 1 && \
    ln -sf /usr/bin/python3.8 /usr/local/bin/python && \
    ln -sf /usr/bin/pip3 /usr/local/bin/pip

# Upgrade pip and install common Python packages
RUN python3.8 -m pip install --upgrade pip setuptools wheel

# Install common Python packages for better layer caching
# These rarely change, so installing them here speeds up rebuilds
# Note: Avoiding specific versions here to prevent conflicts with requirements.txt
RUN python3.8 -m pip install --no-cache-dir \
    scipy \
    scikit-learn \
    matplotlib

# Install CMake >= 3.18 from Kitware's official repository (more reliable than pip)
RUN wget -O - https://apt.kitware.com/keys/kitware-archive-latest.asc 2>/dev/null | gpg --dearmor - | tee /usr/share/keyrings/kitware-archive-keyring.gpg >/dev/null && \
    echo 'deb [signed-by=/usr/share/keyrings/kitware-archive-keyring.gpg] https://apt.kitware.com/ubuntu/ bionic main' | tee /etc/apt/sources.list.d/kitware.list >/dev/null && \
    apt-get update && \
    apt-get install -y cmake && \
    rm -rf /var/lib/apt/lists/*

# Install Java 11
RUN apt-get update && \
    apt-get install -y openjdk-11-jdk && \
    rm -rf /var/lib/apt/lists/*

# Install MySQL 5.7
RUN apt-get update && \
    apt-get install -y \
    mysql-server-5.7 \
    mysql-client-5.7 \
    libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Install NVIDIA utilities for GPU monitoring
# This provides nvidia-smi and other NVIDIA tools
# Note: Requires host to have NVIDIA drivers and container runtime
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    nvidia-utils-525 || \
    apt-get install -y --no-install-recommends \
    nvidia-utils-520 || \
    apt-get install -y --no-install-recommends \
    nvidia-utils-510 || \
    echo "Warning: Could not install nvidia-utils, nvidia-smi may not be available" && \
    rm -rf /var/lib/apt/lists/*

# Create MySQL directories and fix permissions
RUN mkdir -p /var/log/mysql/base && \
    touch /var/log/mysql/base/mysql-slow.log && \
    chmod 777 /var/log/mysql/base/mysql-slow.log && \
    chown -R mysql:mysql /var/log/mysql && \
    mkdir -p /var/run/mysqld && \
    chown -R mysql:mysql /var/run/mysqld && \
    chmod 755 /var/run/mysqld && \
    usermod -d /var/lib/mysql mysql

# Configure vscode user for sudo access
RUN echo "vscode ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/vscode && \
    chmod 0440 /etc/sudoers.d/vscode

# Install PyTorch with CUDA support for GPU acceleration
# Using CUDA 11.8 compatible version
RUN python3.8 -m pip install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Verify installations
RUN python3.8 --version && java -version && mysql --version && \
    python3.8 -c "import torch; print(f'PyTorch {torch.__version__} installed')"

# Reset environment
ENV DEBIAN_FRONTEND=dialog

