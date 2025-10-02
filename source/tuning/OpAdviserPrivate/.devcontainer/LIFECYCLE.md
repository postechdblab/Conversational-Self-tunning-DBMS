# Dev Container Lifecycle - Optimized Structure

## 🏗️ Build & Initialization Stages

The dev container setup is optimized across **4 stages** for better performance and maintainability:

```
┌─────────────────────────────────────────────────────────────┐
│ Stage 1: BUILD (Dockerfile)                                 │
│ ─────────────────────────────────────────────────────────── │
│ Runs: Once when image is built (cached for rebuilds)        │
│ User: root                                                   │
│ Source Code: NOT available                                  │
│                                                              │
│ ✅ Install system packages (apt-get)                        │
│ ✅ Install Python 3.8, Java 11, MySQL 5.7                   │
│ ✅ Install common Python packages (numpy, pandas, etc.)     │
│ ✅ Install PyTorch with CUDA support                        │
│ ✅ Configure system users and permissions                   │
│                                                              │
│ 💡 Best for: System-level dependencies that rarely change   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage 2: ON CREATE (onCreateCommand)                        │
│ ─────────────────────────────────────────────────────────── │
│ Runs: Once when container is first created                  │
│ User: root (via sudo)                                        │
│ Source Code: Mounting in progress                           │
│ Script: .devcontainer/setup.sh                              │
│ Log: /tmp/setup.log                                         │
│                                                              │
│ ✅ Configure MySQL (port 3306)                              │
│ ✅ Initialize MySQL data directory                          │
│ ✅ Start MySQL service                                      │
│ ✅ Create MySQL users (root + vscode)                       │
│ ✅ Set up MySQL log directories                             │
│                                                              │
│ 💡 Best for: System configuration that needs root access    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage 3: POST CREATE (postCreateCommand)                    │
│ ─────────────────────────────────────────────────────────── │
│ Runs: Once after source code is fully available             │
│ User: vscode (non-root)                                      │
│ Source Code: AVAILABLE                                       │
│ Script: .devcontainer/post_create.sh                        │
│ Log: /tmp/post_create.log                                   │
│                                                              │
│ ✅ Install project-specific Python packages                 │
│    (from requirements.txt)                                   │
│ ✅ Start database population in background                  │
│    └─> Calls setup_all_databases.sh                         │
│        └─> Logs to /tmp/database_setup.log                  │
│                                                              │
│ 💡 Best for: Project-specific setup needing source code     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage 4: POST START (postStartCommand)                      │
│ ─────────────────────────────────────────────────────────── │
│ Runs: Every time container starts (including restarts)      │
│ User: vscode (non-root, but uses sudo)                      │
│                                                              │
│ ✅ Start MySQL service (if not running)                     │
│                                                              │
│ 💡 Best for: Services that need to run on every start       │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Key Files

### Build Stage
- **`Dockerfile`** - Image definition with system packages and common Python libs

### Runtime Stage
- **`devcontainer.json`** - Orchestrates all lifecycle commands
- **`setup.sh`** - MySQL and system configuration (onCreateCommand)
- **`post_create.sh`** - Python packages and database population (postCreateCommand)
- **`setup_all_databases.sh`** - Master database population script

### Helper Scripts
- **`check_database_status.sh`** - Check database setup progress
- **`check_gpu.sh`** - Verify GPU availability
- **`mysql-connect.sh`** - Quick MySQL connection

## 🎯 Why This Structure?

### 1. **Better Caching**
- Common packages in Dockerfile → cached across rebuilds
- Only project-specific packages reinstall on source changes

### 2. **Faster Rebuilds**
- Docker layers cache system packages
- Only stages 2-4 rerun on rebuild (not stage 1)

### 3. **Clear Separation**
```
Dockerfile        → System & common dependencies
onCreateCommand   → MySQL & system config (root)
postCreateCommand → Project packages & data (user)
postStartCommand  → Services on every start
```

### 4. **Better Maintainability**
- Each script has a single responsibility
- Easy to debug (separate log files)
- Simple to extend or modify

## 📊 Performance Comparison

### Before Optimization
```
postCreateCommand: 
  - Install pip, setuptools, wheel ⏱️
  - Install 50+ packages from requirements.txt ⏱️⏱️⏱️
  - Start database population ⏱️⏱️⏱️
  
Total: ~10-15 minutes before databases start
```

### After Optimization
```
Dockerfile (cached after first build):
  - Common packages pre-installed ✅
  - PyTorch with CUDA pre-installed ✅
  
postCreateCommand:
  - Only project-specific packages ⏱️
  - Start database population immediately ⏱️
  
Total: ~2-3 minutes before databases start
```

## 🔧 Troubleshooting

### View Logs
```bash
# Build/system setup
cat /tmp/setup.log

# Post-create (Python packages)
cat /tmp/post_create.log

# Database population
tail -f /tmp/database_setup.log
```

### Manual Execution
```bash
# Run setup scripts manually if needed
sudo bash .devcontainer/setup.sh
bash .devcontainer/post_create.sh
bash .devcontainer/setup_all_databases.sh
```

### Check Status
```bash
# Database setup progress
bash .devcontainer/check_database_status.sh

# GPU availability
./check_gpu.sh

# MySQL status
sudo service mysql status
```

## 🚀 Modifying the Setup

### Add System Package
→ Edit **`Dockerfile`** (requires rebuild)

### Add Python Package
→ Add to **`requirements.txt`** (auto-installed in postCreateCommand)

### Change MySQL Configuration
→ Edit **`.devcontainer/setup.sh`**

### Add Database Benchmark
→ Create new setup script, call from **`setup_all_databases.sh`**

## 📝 Summary

| Stage | Script | Runs When | User | Source Code | Log |
|-------|--------|-----------|------|-------------|-----|
| Build | Dockerfile | Image build | root | ❌ No | Build output |
| onCreate | setup.sh | First create | root | 🔄 Mounting | /tmp/setup.log |
| postCreate | post_create.sh | After create | vscode | ✅ Yes | /tmp/post_create.log |
| postStart | (inline) | Every start | vscode | ✅ Yes | Terminal |

This optimized structure provides **faster rebuilds**, **better caching**, and **easier maintenance**! 🎉

