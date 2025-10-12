# Common Utilities in Dev Container

## Overview

The dev container now includes the **common-utils** feature, which provides essential debugging and networking tools that are often missing from minimal container images.

## What's Included

The `ghcr.io/devcontainers/features/common-utils:2` feature provides:

### Network Utilities
- **`ping`** - Test if hosts are reachable
- **`curl`** - Transfer data from/to URLs (HTTP, HTTPS, FTP, etc.)
- **`wget`** - Download files from the web
- **`netcat` (nc)** - Network utility for debugging and testing TCP/UDP connections
- **`telnet`** - Interactive communication with other hosts
- **`dig`** - DNS lookup utility
- **`nslookup`** - Query DNS servers

### System Utilities
- **`ps`** - Process status
- **`top`** - Real-time process monitoring
- **`htop`** - Interactive process viewer
- **`vim`** - Text editor
- **`nano`** - Simple text editor
- **`less`** - File viewer
- **`tar`** - Archive utility
- **`zip`/`unzip`** - Compression utilities
- **`git`** - Version control

### Shell Enhancements
- **`zsh`** - Z shell (installed but not set as default)
- **`bash-completion`** - Tab completion for bash

## Usage Examples

### Test Host Connectivity

```bash
# Ping a host
ping -c 4 host.docker.internal

# Ping Google DNS
ping -c 4 8.8.8.8
```

### Test Port Connectivity

```bash
# Using netcat (recommended)
nc -zv host.docker.internal 3306  # Test MySQL port
nc -zv host.docker.internal 5432  # Test PostgreSQL port

# Using curl
curl -v telnet://host.docker.internal:3306

# Using telnet
telnet host.docker.internal 3306
```

### Check DNS Resolution

```bash
# Using dig (detailed)
dig host.docker.internal

# Using nslookup (simple)
nslookup host.docker.internal

# Check which DNS servers are being used
cat /etc/resolv.conf
```

### Download Files

```bash
# Using curl
curl -O https://example.com/file.tar.gz

# Using wget
wget https://example.com/file.tar.gz

# Follow redirects with curl
curl -L https://example.com/download
```

### Monitor Processes

```bash
# List all processes
ps aux

# Real-time monitoring
top

# Interactive process viewer (better than top)
htop
```

## Why These Tools Matter

### The Problem: Minimal Container Images

Dev containers are built on minimal base images (like `debian-slim`) to keep them small and fast. These images only include the bare essentials. Common utilities like `ping`, `curl`, and `vim` are considered "extras" and are **not included by default**.

### The Impact

Without these tools, you can't:
- ❌ Test network connectivity (`ping`)
- ❌ Debug API endpoints (`curl`)
- ❌ Check if ports are open (`nc`)
- ❌ Download files easily (`wget`)
- ❌ Edit files in the terminal (`vim`, `nano`)

### The Solution

By adding the `common-utils` feature to `devcontainer.json`, these tools are **automatically installed** every time the container is built.

## Configuration

### Current Settings

```json
"features": {
    "ghcr.io/devcontainers/features/common-utils:2": {
        "installZsh": "true",
        "configureZshAsDefaultShell": "false",
        "installOhMyZsh": "false",
        "upgradePackages": "true",
        "username": "vscode"
    }
}
```

### Options Explained

| Option | Value | Description |
|--------|-------|-------------|
| `installZsh` | `true` | Install zsh shell (available but not default) |
| `configureZshAsDefaultShell` | `false` | Keep bash as default shell |
| `installOhMyZsh` | `false` | Don't install Oh My Zsh framework |
| `upgradePackages` | `true` | Update packages during installation |
| `username` | `vscode` | Install for the vscode user |

### Switching to Zsh (Optional)

If you want to use zsh instead of bash:

```bash
# Switch for current session
zsh

# Set as default shell permanently
chsh -s $(which zsh)
```

## Testing Connectivity Examples

### Test MySQL on Host

```bash
# Check if MySQL port is open on host
nc -zv host.docker.internal 3306

# Or test from container to localhost
nc -zv localhost 3306
```

### Test Internet Connectivity

```bash
# Ping Google DNS
ping -c 4 8.8.8.8

# Check if you can reach the web
curl -I https://www.google.com

# Test DNS resolution
dig google.com
```

### Debug Network Issues

```bash
# Check DNS configuration
cat /etc/resolv.conf

# Test specific DNS server
dig @8.8.8.8 google.com

# Check routing
ip route

# Check network interfaces
ip addr
```

## Applying Changes

After modifying `devcontainer.json` to add features:

1. **Open Command Palette**: `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. **Run**: `Dev Containers: Rebuild Container`
3. **Wait**: Container will rebuild with new utilities installed

The utilities will then be available in all future container sessions.

## Alternative: Temporary Installation

If you need a tool just once and don't want to rebuild:

```bash
# Update package list
sudo apt-get update

# Install specific tools
sudo apt-get install -y iputils-ping  # ping
sudo apt-get install -y curl          # curl
sudo apt-get install -y netcat-openbsd # netcat
sudo apt-get install -y dnsutils      # dig, nslookup
sudo apt-get install -y telnet        # telnet
sudo apt-get install -y vim           # vim

# Or install all at once
sudo apt-get install -y iputils-ping curl netcat-openbsd dnsutils telnet vim
```

**Note**: Temporary installations are **lost when the container is rebuilt**.

## Troubleshooting

### Tool Not Found After Rebuild

```bash
# Verify the feature was applied
cat .devcontainer/devcontainer.json | grep -A 5 "features"

# Check if the tool exists
which ping
which curl
which nc

# If still missing, try manual install
sudo apt-get update && sudo apt-get install -y iputils-ping curl netcat-openbsd
```

### Permission Denied

```bash
# Some tools need sudo
sudo ping host.docker.internal

# Or fix permissions for specific commands
# (usually not needed with common-utils)
```

## Summary

✅ **Installed**: Common networking and debugging utilities  
✅ **Automatic**: Installed every time container is built  
✅ **Essential**: Makes debugging and testing much easier  
✅ **Minimal Impact**: Small size increase for major convenience gain  

🎉 **Result**: You now have a fully-equipped development environment!



