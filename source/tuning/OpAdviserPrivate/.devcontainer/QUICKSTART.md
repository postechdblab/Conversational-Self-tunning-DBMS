# Quick Start Guide

## 🚀 Get Started in 3 Steps

### 1. Open in DevContainer
Open this project in VS Code and select "Reopen in Container" when prompted.

The base setup will run automatically (~5-10 minutes).

### 2. Setup a Workload (Choose One)

**Quick Start (Recommended):**
```bash
# Setup Sysbench Read-Write only (fastest)
cd /workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate
bash .devcontainer/setup_sysbench.sh
```

**Other Options:**
```bash
# All OLTPBench workloads (slowest, ~1-3 hours)
bash .devcontainer/setup_oltpbench.sh

# TPC-H workload (~30-90 minutes)
bash .devcontainer/setup_tpch.sh

# JOB workload (~10-30 minutes)
bash .devcontainer/setup_job.sh
```

### 3. Run an Experiment
```bash
export PYTHONPATH=.
python scripts/optimize.py --config=scripts/sysbench_rw.ini
```

## 📝 What Got Automated

Everything from the README.md is now automated **directly in devcontainer.json**:

✅ **DevContainer Features**
- Python 3.8 (official feature)
- Java 11 (official feature)

✅ **System Packages** (onCreateCommand)
- MySQL Server 5.7
- Build tools and all dependencies
- Configured automatically

✅ **MySQL Configuration** (onCreateCommand)
- Port: 3308
- Password: `password`
- Max connections: 100,000
- Slow query log enabled
- Auto-starts on container startup

✅ **Python Environment** (postCreateCommand)
- Python 3.8 as default
- All requirements.txt packages installed
- PYTHONPATH configured automatically

✅ **Optional Workload Setups** (run manually)
- Sysbench (3 databases) - via setup_sysbench.sh
- OLTPBench (6 benchmarks) - via setup_oltpbench.sh
- TPC-H - via setup_tpch.sh
- JOB - via setup_job.sh

**No shell scripts required for base setup!**

## 🎯 Common Commands

### Check MySQL Status
```bash
sudo service mysql status
mysql -ppassword -e "SHOW DATABASES;"
```

### Run Different Experiments
```bash
# Sysbench experiments
python scripts/optimize.py --config=scripts/sysbench_rw.ini
python scripts/optimize.py --config=scripts/sysbench_wo.ini
python scripts/optimize.py --config=scripts/sysbench_ro.ini

# Twitter benchmark
python scripts/optimize.py --config=scripts/twitter.ini

# TPC-C benchmark
python scripts/optimize.py --config=scripts/tpcc.ini
```

### Start Flask Demo
```bash
sudo service mysql stop
sudo /usr/sbin/mysqld --defaults-file=initial2.cnf & disown
export FLASK_APP=server/app.py
export FLASK_RUN_PORT=1234
flask run
```
Access at: http://localhost:1234

## 🔧 Troubleshooting

**MySQL won't start:**
```bash
sudo service mysql restart
sudo tail -f /var/log/mysql/error.log
```

**Python import errors:**
```bash
export PYTHONPATH=/workspaces/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate
```

**Need to reinstall packages:**
```bash
pip install -r requirements.txt
```

## 📚 More Details

See [README.md](.devcontainer/README.md) for comprehensive documentation.

