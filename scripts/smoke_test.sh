#!/usr/bin/env bash
# ==============================================================================
# SummarizeMe Durable Smoke Test Runner
#
# Validates Flask backend, Next.js frontend, worker readiness, database, and Redis.
# Can be run locally, in Docker, in CI, or against remote staging/production VMs.
#
# Usage:
#   ./scripts/smoke_test.sh [options]
#
# Options:
#   --api-url URL        Flask API base URL (default: http://localhost:5001)
#   --frontend-url URL   Next.js Frontend base URL (default: http://localhost:3000)
#   --dev-user EMAIL     Dev user header (default: smoketest@runningdigitally.com)
#   --skip-frontend      Skip frontend HTTP checks
#   --skip-docker        Skip docker container health checks
#   --timeout SECONDS    Curl connect timeout (default: 5)
#   -h, --help           Show this help message
# ==============================================================================

set -euo pipefail

# Default configuration
API_URL="${API_URL:-http://localhost:5001}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
DEV_USER="${DEV_USER:-smoketest@runningdigitally.com}"
SKIP_FRONTEND="${SKIP_FRONTEND:-false}"
SKIP_DOCKER="${SKIP_DOCKER:-false}"
TIMEOUT="${TIMEOUT:-5}"

# Colors
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
CYAN="\033[0;36m"
BOLD="\033[1m"
NC="\033[0m"

# Parse CLI args
while [[ $# -gt 0 ]]; do
  case $1 in
    --api-url)
      API_URL="$2"
      shift 2
      ;;
    --frontend-url)
      FRONTEND_URL="$2"
      shift 2
      ;;
    --dev-user)
      DEV_USER="$2"
      shift 2
      ;;
    --skip-frontend)
      SKIP_FRONTEND=true
      shift
      ;;
    --skip-docker)
      SKIP_DOCKER=true
      shift
      ;;
    --timeout)
      TIMEOUT="$2"
      shift 2
      ;;
    -h|--help)
      sed -ne 's/^# /* /p; s/^#$//p' "$0" | sed -n '1,/^===/p'
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown argument: $1${NC}"
      exit 1
      ;;
  esac
done

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

report_test() {
  local name="$1"
  local expected="$2"
  local actual="$3"
  local details="${4:-}"
  
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  
  if [[ "$actual" == "$expected" || "$expected" == "ANY_2XX" && "$actual" =~ ^2[0-9][0-9]$ ]]; then
    PASSED_TESTS=$((PASSED_TESTS + 1))
    printf "  %-42s ${GREEN}PASS${NC} (HTTP %s) %s\n" "$name" "$actual" "$details"
  else
    FAILED_TESTS=$((FAILED_TESTS + 1))
    printf "  %-42s ${RED}FAIL${NC} (Expected: %s, Got: %s) %s\n" "$name" "$expected" "$actual" "$details"
  fi
}

echo -e "\n${BOLD}${BLUE}======================================================${NC}"
echo -e "${BOLD}${CYAN}   SummarizeMe Smoke Test Suite${NC}"
echo -e "${BOLD}${BLUE}======================================================${NC}"
echo -e "  Flask API Target:     ${CYAN}${API_URL}${NC}"
echo -e "  Frontend Target:      ${CYAN}${FRONTEND_URL}${NC}"
echo -e "  Auth Mode:            ${CYAN}X-Dev-User: ${DEV_USER}${NC}"
echo -e "  Connect Timeout:      ${CYAN}${TIMEOUT}s${NC}\n"

# ------------------------------------------------------------------------------
# 1. Flask API Smoke Checks
# ------------------------------------------------------------------------------
echo -e "${BOLD}1. Flask API Endpoints (${API_URL})${NC}"

# Health check
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$TIMEOUT" "${API_URL}/health" || echo "000")
report_test "GET /health" "200" "$HTTP_CODE"

# Root HTML
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$TIMEOUT" "${API_URL}/" || echo "000")
report_test "GET / (Web Root)" "ANY_2XX" "$HTTP_CODE"

# Channels API
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$TIMEOUT" -H "X-Dev-User: ${DEV_USER}" "${API_URL}/api/channels" || echo "000")
report_test "GET /api/channels" "200" "$HTTP_CODE"

# Models API
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$TIMEOUT" -H "X-Dev-User: ${DEV_USER}" "${API_URL}/api/models" || echo "000")
report_test "GET /api/models" "200" "$HTTP_CODE"

# vLLM Models Proxy
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$TIMEOUT" -H "X-Dev-User: ${DEV_USER}" "${API_URL}/api/vllm/models" || echo "000")
report_test "GET /api/vllm/models" "200" "$HTTP_CODE"

# User AI Preference
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$TIMEOUT" -H "X-Dev-User: ${DEV_USER}" "${API_URL}/api/user/preference" || echo "000")
report_test "GET /api/user/preference" "200" "$HTTP_CODE"

# Active Tasks
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$TIMEOUT" -H "X-Dev-User: ${DEV_USER}" "${API_URL}/api/active-tasks" || echo "000")
report_test "GET /api/active-tasks" "200" "$HTTP_CODE"

# All Tasks
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$TIMEOUT" -H "X-Dev-User: ${DEV_USER}" "${API_URL}/api/all-tasks" || echo "000")
report_test "GET /api/all-tasks" "200" "$HTTP_CODE"

# Status Page
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$TIMEOUT" -H "X-Dev-User: ${DEV_USER}" "${API_URL}/status" || echo "000")
report_test "GET /status" "200" "$HTTP_CODE"

# OpenAPI Docs
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$TIMEOUT" "${API_URL}/openapi/openapi.json" || echo "000")
report_test "GET /openapi/openapi.json" "200" "$HTTP_CODE"

# ------------------------------------------------------------------------------
# 2. Next.js Frontend Smoke Checks
# ------------------------------------------------------------------------------
if [[ "$SKIP_FRONTEND" != "true" ]]; then
  echo -e "\n${BOLD}2. Next.js Frontend Pages (${FRONTEND_URL})${NC}"

  # Home Page
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$TIMEOUT" "${FRONTEND_URL}/" || echo "000")
  report_test "GET / (Frontend Home)" "200" "$HTTP_CODE"

  # Status Page
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$TIMEOUT" "${FRONTEND_URL}/status" || echo "000")
  report_test "GET /status (Frontend Status)" "200" "$HTTP_CODE"

  # Admin Overview
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$TIMEOUT" "${FRONTEND_URL}/admin" || echo "000")
  report_test "GET /admin (Admin Console)" "200" "$HTTP_CODE"

  # Admin Model Registry
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$TIMEOUT" "${FRONTEND_URL}/admin/models" || echo "000")
  report_test "GET /admin/models (Model Registry UI)" "200" "$HTTP_CODE"
fi

# ------------------------------------------------------------------------------
# 3. Docker Container State (if Docker daemon is reachable)
# ------------------------------------------------------------------------------
if [[ "$SKIP_DOCKER" != "true" ]] && command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo -e "\n${BOLD}3. Docker Services State${NC}"
  
  COMPOSE_SERVICES=("app" "db" "redis" "worker" "frontend")
  for svc in "${COMPOSE_SERVICES[@]}"; do
    CONTAINER_STATUS=$(docker compose -f docker-compose.dev.yml ps --format '{{.State}}' "$svc" 2>/dev/null || echo "not-found")
    if [[ "$CONTAINER_STATUS" == "running" ]]; then
      TOTAL_TESTS=$((TOTAL_TESTS + 1))
      PASSED_TESTS=$((PASSED_TESTS + 1))
      printf "  %-42s ${GREEN}RUNNING${NC}\n" "Service: $svc"
    elif [[ "$CONTAINER_STATUS" == "not-found" ]]; then
      # If compose stack isn't named or using prod compose, skip gently
      true
    else
      TOTAL_TESTS=$((TOTAL_TESTS + 1))
      FAILED_TESTS=$((FAILED_TESTS + 1))
      printf "  %-42s ${RED}NOT RUNNING${NC} (State: %s)\n" "Service: $svc" "$CONTAINER_STATUS"
    fi
  done
fi

# ------------------------------------------------------------------------------
# Summary & Exit Code
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}${BLUE}======================================================${NC}"
if [[ $FAILED_TESTS -eq 0 ]]; then
  echo -e "${BOLD}${GREEN}  ALL SMOKE CHECKS PASSED (${PASSED_TESTS}/${TOTAL_TESTS})${NC}"
  echo -e "${BOLD}${BLUE}======================================================${NC}\n"
  exit 0
else
  echo -e "${BOLD}${RED}  SMOKE CHECKS FAILED: ${FAILED_TESTS}/${TOTAL_TESTS} failed (${PASSED_TESTS} passed)${NC}"
  echo -e "${BOLD}${BLUE}======================================================${NC}\n"
  exit 1
fi
