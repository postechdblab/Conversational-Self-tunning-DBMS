#!/usr/bin/env bash
set -euo pipefail

# ============================================================
#  DBAdminBot  -  End-to-end Demo Launcher
# ============================================================
#  Starts all required containers (frontend, backend, redis,
#  opadvisor) and launches the application services inside them.
#
#  Usage:
#    bash scripts/run_dbadminbot.sh
# ============================================================

COMPOSE_FILE="docker-compose.yml"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$PROJECT_ROOT"

echo "============================================"
echo "  DBAdminBot Demo Launcher"
echo "============================================"
echo ""

# ----------------------------------------------------------
# 1. Start Docker containers
# ----------------------------------------------------------
echo "[1/5] Starting Docker containers ..."
docker compose -f "$COMPOSE_FILE" up -d \
    DBAdminBot-frontend \
    DBAdminBot-backend \
    DBadminBot-redis \
    DBAdminBot-opadvisor
echo "       Containers started."
echo ""

# ----------------------------------------------------------
# 2. Wait for Redis
# ----------------------------------------------------------
echo "[2/5] Waiting for Redis ..."
for i in $(seq 1 30); do
    if docker exec DBadminBot-redis redis-cli ping 2>/dev/null | grep -q PONG; then
        echo "       Redis is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: Redis did not become ready in time." >&2
        exit 1
    fi
    sleep 2
done
echo ""

# ----------------------------------------------------------
# 3. Wait for OpAdviser health check
# ----------------------------------------------------------
echo "[3/5] Waiting for OpAdviser (may take up to 2 min) ..."
for i in $(seq 1 24); do
    if curl -sf http://localhost:1234/health >/dev/null 2>&1; then
        echo "       OpAdviser is healthy."
        break
    fi
    if [ "$i" -eq 24 ]; then
        echo "WARNING: OpAdviser health check timed out."
        echo "         It may still be initializing. Check logs:"
        echo "         docker logs -f DBAdminBot-opadvisor"
    fi
    sleep 5
done
echo ""

# ----------------------------------------------------------
# 4. Start Frontend services
# ----------------------------------------------------------
echo "[4/5] Starting Frontend (PostgreSQL + Next.js) ..."
docker exec -d DBAdminBot-frontend bash -c \
    "service postgresql start && cd /root/dbadminbot/web && npm run dev > /tmp/frontend.log 2>&1"
echo "       Frontend starting in background."
echo ""

# ----------------------------------------------------------
# 5. Start Backend server
# ----------------------------------------------------------
echo "[5/5] Starting Backend server (auto-starts LLM) ..."
docker exec -d DBAdminBot-backend bash -c \
    "cd /root/dbadminbot && python backend_server_v2.py > /tmp/backend.log 2>&1"
echo "       Backend starting in background."
echo "       Waiting for Backend to be ready (may take several minutes) ..."
for i in $(seq 1 60); do
    if curl -sf http://localhost:7000/health >/dev/null 2>&1; then
        echo "       Backend is ready."
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "WARNING: Backend health check timed out."
        echo "         It may still be initializing. Check logs:"
        echo "         docker exec DBAdminBot-backend tail -f /tmp/backend.log"
    fi
    sleep 10
done
echo ""

# ----------------------------------------------------------
# Summary
# ----------------------------------------------------------
echo "============================================"
echo "  DBAdminBot is ready!"
echo "============================================"
echo ""
echo "  Access URLs:"
echo "    Frontend (Web UI) : http://localhost:3000"
echo "    Backend API       : http://localhost:7000"
echo "    OpAdviser API     : http://localhost:1234"
echo "    LLM (SGLang)      : http://localhost:30000  (started by backend)"
echo ""
echo "  Monitor logs:"
echo "    docker exec DBAdminBot-frontend tail -f /tmp/frontend.log"
echo "    docker exec DBAdminBot-backend  tail -f /tmp/backend.log"
echo "    docker logs -f DBAdminBot-opadvisor"
echo ""
echo "  Stop all:"
echo "    bash scripts/stop_all.sh"
echo "============================================"
