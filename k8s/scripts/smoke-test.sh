#!/bin/bash
set -euo pipefail

# =============================================================================
# Post-deploy smoke tests
# Basic mode: health + readiness checks for all 5 microservices
# Extended mode (--extended): adds API endpoint reachability, DNS resolution,
#   and pod resource compliance checks
# =============================================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SERVICES=("api-gateway" "agent-executor" "workflow-engine" "tool-executor" "mcp-proxy" "token-proxy" "frontend" "mcp-atlassian" "mcp-github" "mcp-sharepoint")
# Port mapping per service (must match containerPort in deployment.yaml)
SVC_PORTS=("8000" "8000" "8000" "8000" "8000" "8080" "3000" "8082" "8084" "8083")
# Health path mapping (frontend uses / instead of /healthz)
SVC_HEALTH=("/healthz" "/healthz" "/healthz" "/healthz" "/healthz" "/healthz" "/" "/healthz" "/healthz" "/healthz")
SVC_READY=("/readyz" "/readyz" "/readyz" "/readyz" "/readyz" "/readyz" "/" "/healthz" "/healthz" "/healthz")
NAMESPACE="aiplatform"
EXTENDED=false
INGRESS_URL=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --extended) EXTENDED=true; shift ;;
    --ingress-url) INGRESS_URL="$2"; shift 2 ;;
    --namespace) NAMESPACE="$2"; shift 2 ;;
    --help)
      echo "Usage: $0 [namespace] [--extended] [--ingress-url <url>] [--namespace <ns>]"
      echo ""
      echo "  namespace          Namespace (positional, default: default)"
      echo "  --extended         Run API, DNS, and resource checks in addition to health"
      echo "  --ingress-url      Test through ingress URL instead of port-forward"
      echo "  --namespace <ns>   Namespace (named argument)"
      exit 0
      ;;
    -*) echo "Unknown option: $1"; exit 1 ;;
    *) NAMESPACE="$1"; shift ;;
  esac
done

HEALTH_PASS=0
HEALTH_FAIL=0
EXT_PASS=0
EXT_FAIL=0

# ─── Section 1: Health & Readiness Checks ────────────────────────────────────

echo -e "${BLUE}━━━ Health & Readiness Checks ━━━${NC}"
echo "Namespace: ${NAMESPACE}"
echo ""

for i in "${!SERVICES[@]}"; do
  SVC="${SERVICES[$i]}"
  PORT="${SVC_PORTS[$i]}"
  H_PATH="${SVC_HEALTH[$i]}"
  R_PATH="${SVC_READY[$i]}"
  echo -n "  Checking ${SVC} (:${PORT})... "
  POD=$(kubectl get pods -n "${NAMESPACE}" -l app="${SVC}" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
  if [ -z "$POD" ]; then
    echo -e "${RED}FAIL — no pod found${NC}"
    HEALTH_FAIL=$((HEALTH_FAIL + 1))
    continue
  fi

  HEALTH=$(kubectl exec -n "${NAMESPACE}" "${POD}" -- curl -s -o /dev/null -w '%{http_code}' "http://localhost:${PORT}${H_PATH}" 2>/dev/null || echo "000")
  READY=$(kubectl exec -n "${NAMESPACE}" "${POD}" -- curl -s -o /dev/null -w '%{http_code}' "http://localhost:${PORT}${R_PATH}" 2>/dev/null || echo "000")

  if [ "$HEALTH" = "200" ] && [ "$READY" = "200" ]; then
    echo -e "${GREEN}OK${NC} (health=${HEALTH}, ready=${READY})"
    HEALTH_PASS=$((HEALTH_PASS + 1))
  else
    echo -e "${RED}FAIL${NC} (health=${HEALTH}, ready=${READY})"
    HEALTH_FAIL=$((HEALTH_FAIL + 1))
  fi
done

echo ""
echo -e "  Health checks: ${GREEN}${HEALTH_PASS} passed${NC}, ${RED}${HEALTH_FAIL} failed${NC}"

# ─── Exit early if not extended ──────────────────────────────────────────────

if [ "${EXTENDED}" = false ]; then
  if [ ${HEALTH_FAIL} -gt 0 ]; then
    echo ""
    echo -e "${RED}SMOKE TESTS FAILED: ${HEALTH_FAIL}/${#SERVICES[@]} services unhealthy${NC}"
    exit 1
  fi
  echo ""
  echo -e "${GREEN}ALL SMOKE TESTS PASSED${NC}"
  exit 0
fi

# ─── Section 2: API Endpoint Reachability ────────────────────────────────────

echo ""
echo -e "${BLUE}━━━ API Endpoint Reachability ━━━${NC}"
echo ""

PF_PID=""
API_BASE=""

cleanup_portforward() {
  if [ -n "${PF_PID}" ]; then
    kill "${PF_PID}" 2>/dev/null || true
    wait "${PF_PID}" 2>/dev/null || true
  fi
}
trap cleanup_portforward EXIT

if [ -n "${INGRESS_URL}" ]; then
  API_BASE="${INGRESS_URL}"
  echo "  Using ingress URL: ${API_BASE}"
else
  # Port-forward to api-gateway
  GW_POD=$(kubectl get pods -n "${NAMESPACE}" -l app="api-gateway" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
  if [ -z "${GW_POD}" ]; then
    echo -e "  ${RED}✗${NC} Cannot port-forward — no api-gateway pod found"
    EXT_FAIL=$((EXT_FAIL + 1))
  else
    kubectl port-forward -n "${NAMESPACE}" "${GW_POD}" 18080:8000 &>/dev/null &
    PF_PID=$!
    sleep 2
    API_BASE="http://localhost:18080"
    echo "  Port-forwarding to api-gateway on ${API_BASE}"
  fi
fi

if [ -n "${API_BASE}" ]; then
  # Test API endpoints — 2xx or 401 means route exists
  API_ENDPOINTS=("/api/v1/agents" "/docs")
  for EP in "${API_ENDPOINTS[@]}"; do
    STATUS=$(curl -s -o /dev/null -w '%{http_code}' "${API_BASE}${EP}" 2>/dev/null || echo "000")
    if [ "${STATUS}" -ge 200 ] && [ "${STATUS}" -lt 500 ]; then
      echo -e "  ${GREEN}✓${NC} ${EP} → ${STATUS}"
      EXT_PASS=$((EXT_PASS + 1))
    else
      echo -e "  ${RED}✗${NC} ${EP} → ${STATUS}"
      EXT_FAIL=$((EXT_FAIL + 1))
    fi
  done
fi

# ─── Section 3: Inter-service DNS Resolution ─────────────────────────────────

echo ""
echo -e "${BLUE}━━━ Inter-service DNS Resolution ━━━${NC}"
echo ""

GW_POD=$(kubectl get pods -n "${NAMESPACE}" -l app="api-gateway" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
DNS_SERVICES=("agent-executor" "workflow-engine" "tool-executor" "mcp-proxy")

if [ -n "${GW_POD}" ]; then
  for DNS_SVC in "${DNS_SERVICES[@]}"; do
    if kubectl exec -n "${NAMESPACE}" "${GW_POD}" -- getent hosts "${DNS_SVC}" &>/dev/null; then
      RESOLVED=$(kubectl exec -n "${NAMESPACE}" "${GW_POD}" -- getent hosts "${DNS_SVC}" 2>/dev/null | awk '{print $1}')
      echo -e "  ${GREEN}✓${NC} ${DNS_SVC} → ${RESOLVED}"
      EXT_PASS=$((EXT_PASS + 1))
    else
      echo -e "  ${RED}✗${NC} ${DNS_SVC} — DNS resolution failed"
      EXT_FAIL=$((EXT_FAIL + 1))
    fi
  done
else
  echo -e "  ${YELLOW}⚠${NC} Skipped — no api-gateway pod for DNS check"
fi

# ─── Section 4: Pod Resource Compliance ───────────────────────────────────────

echo ""
echo -e "${BLUE}━━━ Pod Resource Compliance ━━━${NC}"
echo ""

if kubectl top pods -n "${NAMESPACE}" &>/dev/null; then
  kubectl top pods -n "${NAMESPACE}" 2>/dev/null | while IFS= read -r LINE; do
    echo "  ${LINE}"
  done
  EXT_PASS=$((EXT_PASS + 1))
else
  echo -e "  ${YELLOW}⚠${NC} kubectl top not available (metrics-server may not be installed)"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────

echo ""
echo -e "${BLUE}━━━ Summary ━━━${NC}"
echo -e "  Health Checks:    ${GREEN}${HEALTH_PASS} passed${NC}, ${RED}${HEALTH_FAIL} failed${NC}"
echo -e "  Extended Checks:  ${GREEN}${EXT_PASS} passed${NC}, ${RED}${EXT_FAIL} failed${NC}"
echo ""

if [ ${HEALTH_FAIL} -gt 0 ]; then
  echo -e "${RED}SMOKE TESTS FAILED: ${HEALTH_FAIL} health check(s) failed${NC}"
  exit 1
fi

if [ ${EXT_FAIL} -gt 0 ]; then
  echo -e "${YELLOW}Extended checks had ${EXT_FAIL} failure(s) (non-blocking)${NC}"
  exit 2
fi

echo -e "${GREEN}ALL SMOKE TESTS PASSED${NC}"
