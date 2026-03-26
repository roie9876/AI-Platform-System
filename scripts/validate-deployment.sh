#!/bin/bash
set -euo pipefail

# =============================================================================
# Pre-deployment validation — run before deploying to Azure
# Validates: prerequisites, Azure login, Bicep, K8s manifests, Docker builds
# =============================================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

pass() {
  echo -e "  ${GREEN}✓${NC} $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
  echo -e "  ${RED}✗${NC} $1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

warn() {
  echo -e "  ${YELLOW}⚠${NC} $1"
  WARN_COUNT=$((WARN_COUNT + 1))
}

banner() {
  echo ""
  echo -e "${BLUE}━━━ $1 ━━━${NC}"
}

# Navigate to project root (parent of scripts/)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# ─── 1. Prerequisites ────────────────────────────────────────────────────────

banner "1/6 Checking prerequisites"

for CMD in az kubectl docker kustomize jq; do
  if command -v "$CMD" &>/dev/null; then
    pass "$CMD found ($(command -v "$CMD"))"
  else
    fail "$CMD not found — install before deploying"
  fi
done

# ─── 2. Azure login ──────────────────────────────────────────────────────────

banner "2/6 Verifying Azure login"

if az account show &>/dev/null; then
  ACCOUNT=$(az account show --query "{name:name, id:id}" -o tsv 2>/dev/null)
  pass "Azure CLI authenticated — ${ACCOUNT}"
else
  fail "Not logged in to Azure CLI — run 'az login'"
fi

# ─── 3. Bicep validation ─────────────────────────────────────────────────────

banner "3/6 Validating Bicep templates"

if [ -f infra/main.bicep ]; then
  if az bicep build --file infra/main.bicep --stdout >/dev/null 2>&1; then
    pass "infra/main.bicep compiles successfully"
  else
    fail "infra/main.bicep has compilation errors"
  fi

  # Check parameter files
  if [ -f infra/parameters/prod.bicepparam ]; then
    pass "infra/parameters/prod.bicepparam exists"
  else
    fail "infra/parameters/prod.bicepparam missing"
  fi
else
  fail "infra/main.bicep not found"
fi

# ─── 4. Kubernetes manifest validation ───────────────────────────────────────

banner "4/6 Validating Kubernetes manifests"

if [ -d k8s/base ]; then
  if kubectl kustomize k8s/base >/dev/null 2>&1; then
    pass "k8s/base kustomize build succeeds"
  else
    fail "k8s/base kustomize build failed"
  fi

  # Check key files exist
  for MANIFEST in configmap.yaml ingress.yaml kustomization.yaml; do
    if [ -f "k8s/base/${MANIFEST}" ]; then
      pass "k8s/base/${MANIFEST} exists"
    else
      fail "k8s/base/${MANIFEST} missing"
    fi
  done

  # Check service deployments exist
  SERVICES=("api-gateway" "agent-executor" "workflow-engine" "tool-executor" "mcp-proxy")
  for SVC in "${SERVICES[@]}"; do
    if [ -f "k8s/base/${SVC}/deployment.yaml" ] && [ -f "k8s/base/${SVC}/service.yaml" ]; then
      pass "${SVC} deployment + service manifests exist"
    else
      fail "${SVC} missing deployment.yaml or service.yaml"
    fi
  done
else
  fail "k8s/base directory not found"
fi

# ─── 5. Docker build validation ──────────────────────────────────────────────

banner "5/6 Validating Docker builds"

MICROSERVICES=("api_gateway" "agent_executor" "workflow_engine" "tool_executor" "mcp_proxy")
MICROSERVICE_NAMES=("api-gateway" "agent-executor" "workflow-engine" "tool-executor" "mcp-proxy")

for i in "${!MICROSERVICES[@]}"; do
  SVC_DIR="${MICROSERVICES[$i]}"
  SVC_NAME="${MICROSERVICE_NAMES[$i]}"
  DOCKERFILE="backend/microservices/${SVC_DIR}/Dockerfile"

  if [ -f "${DOCKERFILE}" ]; then
    if docker build --no-cache -f "${DOCKERFILE}" backend/ -t "test-${SVC_NAME}:validate" -q >/dev/null 2>&1; then
      pass "${SVC_NAME} Docker build succeeded"
      # Clean up test image
      docker rmi "test-${SVC_NAME}:validate" >/dev/null 2>&1 || true
    else
      fail "${SVC_NAME} Docker build failed"
    fi
  else
    fail "${DOCKERFILE} not found"
  fi
done

# Frontend
if [ -f frontend/Dockerfile ]; then
  if docker build -f frontend/Dockerfile frontend/ -t "test-frontend:validate" -q >/dev/null 2>&1; then
    pass "frontend Docker build succeeded"
    docker rmi "test-frontend:validate" >/dev/null 2>&1 || true
  else
    fail "frontend Docker build failed"
  fi
else
  fail "frontend/Dockerfile not found"
fi

# ─── 6. Environment documentation ────────────────────────────────────────────

banner "6/6 Checking environment documentation"

REQUIRED_OUTPUTS=("aksClusterName" "acrLoginServer" "cosmosEndpoint" "keyVaultUri" "workloadIdentityClientId" "appInsightsConnectionString")
for OUTPUT in "${REQUIRED_OUTPUTS[@]}"; do
  if grep -q "${OUTPUT}" infra/main.bicep 2>/dev/null; then
    pass "Bicep output '${OUTPUT}' defined"
  else
    warn "Bicep output '${OUTPUT}' not found in main.bicep"
  fi
done

# ─── Summary ─────────────────────────────────────────────────────────────────

echo ""
echo -e "${BLUE}━━━ Summary ━━━${NC}"
echo -e "  ${GREEN}Passed:${NC}  ${PASS_COUNT}"
echo -e "  ${RED}Failed:${NC}  ${FAIL_COUNT}"
echo -e "  ${YELLOW}Warnings:${NC} ${WARN_COUNT}"
echo ""

if [ "${FAIL_COUNT}" -gt 0 ]; then
  echo -e "${RED}Pre-deployment validation FAILED — fix issues before deploying${NC}"
  exit 1
fi

echo -e "${GREEN}Pre-deployment validation PASSED — ready to deploy${NC}"
exit 0
