#!/usr/bin/env bash
set -euo pipefail

# ============================================================
#  EDAframework  -  End-to-end Demo Launcher
# ============================================================
#  Starts the DBEDA server and client containers, launches
#  PostgreSQL, Flask API, and Jupyter Lab.
#
#  Usage:
#    bash scripts/run_edaframework.sh
# ============================================================

COMPOSE_FILE="docker-compose.yml"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$PROJECT_ROOT"

echo "============================================"
echo "  EDAframework Demo Launcher"
echo "============================================"
echo ""

# ----------------------------------------------------------
# 1. Start Docker containers
# ----------------------------------------------------------
echo "[1/6] Starting Docker containers ..."
docker compose -f "$COMPOSE_FILE" up -d \
    DBEDA-server \
    DBEDA-client
echo "       Containers started."
echo ""

# ----------------------------------------------------------
# 2. Start Server services (PostgreSQL + Flask API)
# ----------------------------------------------------------
echo "[2/6] Starting Server (PostgreSQL + Flask API) ..."
docker exec -d dbeda_server bash -c \
    "service postgresql start && cd /root/DBEDA/server && PYTHONPATH=/root/DBEDA/server:/root/DBEDA python3 server.py > /tmp/server.log 2>&1"
echo "       Server starting in background."
echo ""

# ----------------------------------------------------------
# 3. Wait for Server API
# ----------------------------------------------------------
echo "[3/6] Waiting for Server API at :85 ..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:85 >/dev/null 2>&1; then
        echo "       Server API is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "WARNING: Server API did not respond in time."
        echo "         Check logs: docker exec dbeda_server cat /tmp/server.log"
    fi
    sleep 2
done
echo ""

# ----------------------------------------------------------
# 4. Load demo data (DBSherlock)
# ----------------------------------------------------------
echo "[4/6] Loading DBSherlock demo data ..."
# Terminate any idle-in-transaction sessions that may hold locks
docker exec dbeda_server bash -c \
    "PGPASSWORD=postgres psql -U postgres -h localhost -p 5437 -d dbeda -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND datname='dbeda' AND state='idle in transaction';\"" >/dev/null 2>&1 || true
docker exec dbeda_server python3 /root/DBEDA/load_dbsherlock_setup.py
echo "       DBSherlock data loaded."
echo ""

# ----------------------------------------------------------
# 5. Run anomaly prediction
# ----------------------------------------------------------
echo "[5/6] Running anomaly prediction ..."
docker exec dbeda_server bash -c \
    "cd /root/DBEDA && PYTHONPATH=/root/DBEDA/server:/root/DBEDA python3 run_anomaly_prediction.py"
echo "       Anomaly prediction complete."
echo ""

# ----------------------------------------------------------
# 6. Start Client services (PostgreSQL + Jupyter Lab)
# ----------------------------------------------------------
echo "[6/6] Starting Client (PostgreSQL + Jupyter Lab) ..."
docker exec -d dbeda_client bash -c \
    "service postgresql start && cd /root/DBEDA/client && PYTHONPATH=/root/DBEDA:/root/DBEDA/client jupyter lab --allow-root --ip=0.0.0.0 --port=8888 --no-browser --ServerApp.token='' > /tmp/jupyter.log 2>&1"
echo "       Jupyter Lab starting in background."
echo ""

# ----------------------------------------------------------
# Summary
# ----------------------------------------------------------
echo "============================================"
echo "  EDAframework is launching!"
echo "============================================"
echo ""
echo "  Access URLs:"
echo "    Jupyter Lab (Client) : http://localhost:8888"
echo "    Flask API (Server)   : http://localhost:85"
echo ""
echo "  Monitor logs:"
echo "    docker exec dbeda_server cat /tmp/server.log"
echo "    docker exec dbeda_client cat /tmp/jupyter.log"
echo ""
echo "  Open DBEDA.ipynb in Jupyter Lab to start the demo."
echo ""
echo "  Stop all:"
echo "    bash scripts/stop_all.sh"
echo "============================================"
