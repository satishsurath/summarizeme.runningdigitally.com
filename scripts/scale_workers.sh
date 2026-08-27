#!/usr/bin/env bash
# ==============================================================================
# scripts/scale_workers.sh — PostgreSQL Queue Depth Autoscaler for Stage Workers
#
# Usage:
#   ./scripts/scale_workers.sh [--compose-file docker-compose.prod.yml]
#
# Logic:
#   1. Query PostgreSQL for pending/running work_items count.
#   2. If pending/running > 0: ensure worker containers are started. Reset idle marker.
#   3. If pending/running == 0: check idle marker file (/tmp/summarizeme_worker_idle).
#      If idle for > 300 seconds (5 minutes), gracefully stop worker containers.
# ==============================================================================

set -euo pipefail

COMPOSE_FILE="${1:-docker-compose.prod.yml}"
IDLE_MARKER="/tmp/summarizeme_worker_idle"
IDLE_GRACE_SECONDS=300

# Database URL from env or default
DB_URL="${DATABASE_URL:-postgresql://summarizeme:summarizeme_pass@localhost:55432/summarizeme}"

# Query pending / running work items
PENDING_COUNT=$(python3 -c "
import os, sys
from sqlalchemy import create_engine, text
try:
    engine = create_engine('${DB_URL}')
    with engine.connect() as conn:
        res = conn.execute(text(\"SELECT count(*) FROM work_items WHERE status IN ('pending', 'running');\")).scalar()
        print(int(res or 0))
except Exception as e:
    # If connection fails or table doesn't exist yet, report 0
    print(0)
" 2>/dev/null || echo 0)

echo "[$(date -u +'%Y-%m-%d %H:%M:%SZ')] Queue check: ${PENDING_COUNT} active work item(s)."

WORKER_SERVICES="worker-control worker-transcript worker-summary worker-embedding"

if [ "${PENDING_COUNT}" -gt 0 ]; then
  # Work present: clear idle marker and ensure workers running
  if [ -f "${IDLE_MARKER}" ]; then
    rm -f "${IDLE_MARKER}"
  fi
  echo "[Scale-Up] Active jobs detected (${PENDING_COUNT}). Starting worker containers..."
  docker compose -f "${COMPOSE_FILE}" up -d ${WORKER_SERVICES}
else
  # No work: track idle time
  NOW=$(date +%s)
  if [ ! -f "${IDLE_MARKER}" ]; then
    echo "${NOW}" > "${IDLE_MARKER}"
    echo "[Idle] Queue empty. Starting ${IDLE_GRACE_SECONDS}s idle grace period..."
  else
    IDLE_START=$(cat "${IDLE_MARKER}")
    ELAPSED=$((NOW - IDLE_START))
    if [ "${ELAPSED}" -ge "${IDLE_GRACE_SECONDS}" ]; then
      echo "[Scale-To-Zero] Queue idle for ${ELAPSED}s (>= ${IDLE_GRACE_SECONDS}s). Stopping worker containers..."
      docker compose -f "${COMPOSE_FILE}" stop ${WORKER_SERVICES} || true
    else
      REMAINING=$((IDLE_GRACE_SECONDS - ELAPSED))
      echo "[Idle] Queue empty for ${ELAPSED}s. ${REMAINING}s remaining before scale-to-zero."
    fi
  fi
fi
