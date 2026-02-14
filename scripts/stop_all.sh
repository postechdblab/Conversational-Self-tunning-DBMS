#!/usr/bin/env bash
set -euo pipefail

# ============================================================
#  Stop All Services
# ============================================================
#  Stops all Docker containers managed by docker-compose.
#
#  Usage:
#    bash scripts/stop_all.sh
# ============================================================

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$PROJECT_ROOT"

echo "Stopping all containers ..."
docker compose down
echo "All containers stopped."
