#!/bin/bash
set -euo pipefail

SERVICES=("api-gateway" "agent-executor" "workflow-engine" "tool-executor" "mcp-proxy")
NAMESPACE="${1:-default}"
FAILED=0

echo "Running post-deploy smoke tests in namespace: ${NAMESPACE}"

for SVC in "${SERVICES[@]}"; do
  echo -n "Checking ${SVC}... "
  POD=$(kubectl get pods -n "${NAMESPACE}" -l app="${SVC}" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
  if [ -z "$POD" ]; then
    echo "FAIL — no pod found"
    FAILED=$((FAILED + 1))
    continue
  fi

  HEALTH=$(kubectl exec -n "${NAMESPACE}" "${POD}" -- curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/healthz 2>/dev/null || echo "000")
  READY=$(kubectl exec -n "${NAMESPACE}" "${POD}" -- curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/readyz 2>/dev/null || echo "000")

  if [ "$HEALTH" = "200" ] && [ "$READY" = "200" ]; then
    echo "OK (health=${HEALTH}, ready=${READY})"
  else
    echo "FAIL (health=${HEALTH}, ready=${READY})"
    FAILED=$((FAILED + 1))
  fi
done

if [ $FAILED -gt 0 ]; then
  echo "SMOKE TESTS FAILED: ${FAILED}/${#SERVICES[@]} services unhealthy"
  exit 1
fi

echo "ALL SMOKE TESTS PASSED"
