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

# Query pending, leased, and retry work items and active leases
STATUS_JSON=$(DB_URL="${DB_URL}" python3 -c "
import os, sys, json
from sqlalchemy import create_engine, text
try:
    engine = create_engine(os.environ['DB_URL'])
    with engine.connect() as conn:
        active_items = conn.execute(text(\"SELECT count(*) FROM work_items WHERE status IN ('pending', 'leased', 'retry');\")).scalar() or 0
        active_leases = conn.execute(text(\"SELECT count(*) FROM resource_leases WHERE expires_at > CURRENT_TIMESTAMP;\")).scalar() or 0
        gen_items = conn.execute(text(\"SELECT count(*) FROM work_items WHERE stage = 'summarize' AND status IN ('pending', 'leased', 'retry');\")).scalar() or 0
        print(json.dumps({'status': 'ok', 'active_items': int(active_items), 'active_leases': int(active_leases), 'gen_items': int(gen_items)}))
except Exception as e:
    print(json.dumps({'status': 'error', 'error': str(e)}))
" 2>/dev/null || echo '{"status": "error", "error": "execution_failed"}')

DB_STATUS=$(echo "${STATUS_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'error'))")
if [ "${DB_STATUS}" != "ok" ]; then
  echo "[$(date -u +'%Y-%m-%d %H:%M:%SZ')] [ERROR] Database check failed during worker scaling check. Refusing to scale down."
  exit 0
fi

PENDING_COUNT=$(echo "${STATUS_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('active_items', 0))")
ACTIVE_LEASES=$(echo "${STATUS_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('active_leases', 0))")

echo "[$(date -u +'%Y-%m-%d %H:%M:%SZ')] Queue check: ${PENDING_COUNT} active work item(s), ${ACTIVE_LEASES} active lease(s)."

WORKER_SERVICES="worker-control worker-transcript worker-summary worker-embedding"

if [ "${PENDING_COUNT}" -gt 0 ] || [ "${ACTIVE_LEASES}" -gt 0 ]; then
  # Work present: clear idle marker and ensure workers running
  if [ -f "${IDLE_MARKER}" ]; then
    rm -f "${IDLE_MARKER}"
  fi
  echo "[Scale-Up] Active work detected (items=${PENDING_COUNT}, leases=${ACTIVE_LEASES}). Starting worker containers..."
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
      if [ "${ACTIVE_LEASES}" -eq 0 ]; then
        echo "[Scale-To-Zero] Queue idle for ${ELAPSED}s (>= ${IDLE_GRACE_SECONDS}s). Gracefully stopping worker containers..."
        docker compose -f "${COMPOSE_FILE}" stop ${WORKER_SERVICES} || true
      else
        echo "[Scale-To-Zero Deferred] Active leases still running (${ACTIVE_LEASES}). Allowing work to finish."
      fi
    else
      REMAINING=$((IDLE_GRACE_SECONDS - ELAPSED))
      echo "[Idle] Queue empty for ${ELAPSED}s. ${REMAINING}s remaining before scale-to-zero."
    fi
  fi
fi
