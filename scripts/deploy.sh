#!/bin/bash
set -euo pipefail

# =============================================================================
# End-to-end Azure deployment orchestration
# Infra (Bicep) → Build & Push (Docker/ACR) → Deploy (AKS/K8s) → Smoke Test
# =============================================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Navigate to project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# ─── Argument parsing ────────────────────────────────────────────────────────

RESOURCE_GROUP=""
ENVIRONMENT="prod"
SKIP_INFRA=false
SKIP_BUILD=false
DRY_RUN=false
DEPLOYMENT_NAME="main"

usage() {
  echo "Usage: $0 --resource-group <rg> [options]"
  echo ""
  echo "Required:"
  echo "  --resource-group <rg>    Azure resource group name"
  echo ""
  echo "Options:"
  echo "  --environment <env>      Environment (default: prod)"
  echo "  --deployment-name <name> Bicep deployment name (default: main)"
  echo "  --skip-infra             Skip Bicep infrastructure deployment"
  echo "  --skip-build             Skip Docker build and push"
  echo "  --dry-run                Validate only, print what would be executed"
  echo "  --help                   Show this help"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --resource-group) RESOURCE_GROUP="$2"; shift 2 ;;
    --environment) ENVIRONMENT="$2"; shift 2 ;;
    --deployment-name) DEPLOYMENT_NAME="$2"; shift 2 ;;
    --skip-infra) SKIP_INFRA=true; shift ;;
    --skip-build) SKIP_BUILD=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    --help) usage ;;
    *) echo "Unknown argument: $1"; usage ;;
  esac
done

if [ -z "${RESOURCE_GROUP}" ]; then
  echo -e "${RED}Error: --resource-group is required${NC}"
  usage
fi

# ─── Helpers ──────────────────────────────────────────────────────────────────

STEP=0
step() {
  STEP=$((STEP + 1))
  echo ""
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}  Step ${STEP}: $1${NC}"
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
}

dry_run_cmd() {
  if [ "${DRY_RUN}" = true ]; then
    echo -e "  ${YELLOW}[DRY-RUN]${NC} $*"
    return 0
  fi
  "$@"
}

GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")

# Service name mapping: image-name → directory-name
declare -A SVC_MAP=(
  ["api-gateway"]="api_gateway"
  ["agent-executor"]="agent_executor"
  ["workflow-engine"]="workflow_engine"
  ["tool-executor"]="tool_executor"
  ["mcp-proxy"]="mcp_proxy"
)

# ─── Dry-run mode ────────────────────────────────────────────────────────────

if [ "${DRY_RUN}" = true ]; then
  echo -e "${YELLOW}DRY-RUN MODE — no changes will be made${NC}"
  echo ""
  echo "Configuration:"
  echo "  Resource Group:  ${RESOURCE_GROUP}"
  echo "  Environment:     ${ENVIRONMENT}"
  echo "  Deployment Name: ${DEPLOYMENT_NAME}"
  echo "  Git SHA:         ${GIT_SHA}"
  echo "  Skip Infra:      ${SKIP_INFRA}"
  echo "  Skip Build:      ${SKIP_BUILD}"
  echo ""

  # Run validation
  bash scripts/validate-deployment.sh || true

  echo ""
  echo "Planned steps:"
  [ "${SKIP_INFRA}" = false ] && echo "  1. Deploy Bicep infrastructure to ${RESOURCE_GROUP}"
  echo "  2. Capture deployment outputs (ACR, AKS, Cosmos, KeyVault)"
  echo "  3. Configure AKS credentials"
  [ "${SKIP_BUILD}" = false ] && echo "  4. Build and push 5 microservice + frontend images to ACR"
  echo "  5. Update K8s configmap with App Insights connection string"
  echo "  6. Update K8s secrets with workload identity values"
  echo "  7. Deploy to AKS via kustomize"
  echo "  8. Wait for rollouts"
  echo "  9. Run smoke tests"
  echo "  10. Provision default tenant"
  echo ""
  echo -e "${GREEN}Dry-run complete — no actions taken${NC}"
  exit 0
fi

echo -e "${BLUE}Starting deployment to ${RESOURCE_GROUP} (env=${ENVIRONMENT})${NC}"
echo "  Git SHA: ${GIT_SHA}"
echo ""

# ─── Step 1: Infrastructure ──────────────────────────────────────────────────

if [ "${SKIP_INFRA}" = false ]; then
  step "Deploy Infrastructure (Bicep)"

  PARAM_FILE="infra/parameters/${ENVIRONMENT}.bicepparam"
  if [ ! -f "${PARAM_FILE}" ]; then
    echo -e "${RED}Parameter file not found: ${PARAM_FILE}${NC}"
    exit 1
  fi

  az deployment group create \
    --resource-group "${RESOURCE_GROUP}" \
    --template-file infra/main.bicep \
    --parameters "${PARAM_FILE}" \
    --name "${DEPLOYMENT_NAME}" \
    --verbose
else
  step "Infrastructure (Skipped)"
  echo "  --skip-infra set, using existing deployment '${DEPLOYMENT_NAME}'"
fi

# ─── Step 2: Capture outputs ─────────────────────────────────────────────────

step "Capture Deployment Outputs"

OUTPUTS=$(az deployment group show \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${DEPLOYMENT_NAME}" \
  --query properties.outputs -o json)

ACR_SERVER=$(echo "${OUTPUTS}" | jq -r '.acrLoginServer.value')
AKS_CLUSTER=$(echo "${OUTPUTS}" | jq -r '.aksClusterName.value')
COSMOS_ENDPOINT=$(echo "${OUTPUTS}" | jq -r '.cosmosEndpoint.value')
KEY_VAULT_URI=$(echo "${OUTPUTS}" | jq -r '.keyVaultUri.value')
KEY_VAULT_NAME=$(echo "${OUTPUTS}" | jq -r '.keyVaultName.value')
WORKLOAD_ID=$(echo "${OUTPUTS}" | jq -r '.workloadIdentityClientId.value')
APP_INSIGHTS_CS=$(echo "${OUTPUTS}" | jq -r '.appInsightsConnectionString.value')
AGC_ID=$(echo "${OUTPUTS}" | jq -r '.agcId.value')
AGC_FQDN=$(echo "${OUTPUTS}" | jq -r '.agcFqdn.value')

echo "  ACR Server:     ${ACR_SERVER}"
echo "  AKS Cluster:    ${AKS_CLUSTER}"
echo "  Cosmos Endpoint: ${COSMOS_ENDPOINT}"
echo "  Key Vault:      ${KEY_VAULT_NAME} (${KEY_VAULT_URI})"
echo "  Workload ID:    ${WORKLOAD_ID}"
echo "  App Insights:   ${APP_INSIGHTS_CS:0:40}..."
echo "  AGC ID:         ${AGC_ID}"
echo "  AGC FQDN:       ${AGC_FQDN}"

TENANT_ID=$(az account show --query tenantId -o tsv)
echo "  Tenant ID:      ${TENANT_ID}"

# ─── Step 3: Configure AKS ───────────────────────────────────────────────────

step "Configure AKS Credentials"

az aks get-credentials \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${AKS_CLUSTER}" \
  --overwrite-existing

echo "  kubectl context set to ${AKS_CLUSTER}"

# ─── Step 3b: Enable ALB Controller ──────────────────────────────────────────

step "Enable ALB Controller (Application Gateway for Containers)"

echo "  Enabling ALB Controller addon on AKS..."
az aks update \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${AKS_CLUSTER}" \
  --enable-alb-controller \
  --only-show-errors || echo -e "  ${YELLOW}ALB Controller already enabled or update in progress${NC}"

echo -e "  ${GREEN}✓ ALB Controller enabled${NC}"

# ─── Step 4: ACR Login ───────────────────────────────────────────────────────

if [ "${SKIP_BUILD}" = false ]; then
  step "ACR Login"
  ACR_NAME=$(echo "${ACR_SERVER}" | cut -d. -f1)
  az acr login --name "${ACR_NAME}"
fi

# ─── Step 5: Build and Push Images ───────────────────────────────────────────

if [ "${SKIP_BUILD}" = false ]; then
  step "Build and Push Docker Images"

  for SVC_IMAGE in "${!SVC_MAP[@]}"; do
    SVC_DIR="${SVC_MAP[$SVC_IMAGE]}"
    echo ""
    echo -e "  ${BLUE}Building ${SVC_IMAGE}...${NC}"
    docker build \
      -t "${ACR_SERVER}/aiplatform-${SVC_IMAGE}:${GIT_SHA}" \
      -t "${ACR_SERVER}/aiplatform-${SVC_IMAGE}:latest" \
      -f "backend/microservices/${SVC_DIR}/Dockerfile" \
      backend/
    docker push "${ACR_SERVER}/aiplatform-${SVC_IMAGE}:${GIT_SHA}"
    docker push "${ACR_SERVER}/aiplatform-${SVC_IMAGE}:latest"
    echo -e "  ${GREEN}✓ ${SVC_IMAGE} pushed${NC}"
  done

  # Frontend
  echo ""
  echo -e "  ${BLUE}Building frontend...${NC}"
  docker build \
    -t "${ACR_SERVER}/aiplatform-frontend:${GIT_SHA}" \
    -t "${ACR_SERVER}/aiplatform-frontend:latest" \
    -f frontend/Dockerfile \
    frontend/
  docker push "${ACR_SERVER}/aiplatform-frontend:${GIT_SHA}"
  docker push "${ACR_SERVER}/aiplatform-frontend:latest"
  echo -e "  ${GREEN}✓ frontend pushed${NC}"
else
  step "Build and Push (Skipped)"
  echo "  --skip-build set, using existing images"
fi

# ─── Step 6: Update K8s ConfigMap ─────────────────────────────────────────────

step "Update K8s ConfigMap"

CONFIGMAP_FILE="k8s/base/configmap.yaml"
if grep -q "REPLACE_WITH_APP_INSIGHTS_CONNECTION_STRING" "${CONFIGMAP_FILE}"; then
  sed -i '' "s|REPLACE_WITH_APP_INSIGHTS_CONNECTION_STRING|${APP_INSIGHTS_CS}|g" "${CONFIGMAP_FILE}"
  echo "  Updated App Insights connection string in configmap"
else
  echo "  App Insights connection string already populated (skipping)"
fi

# ─── Step 6b: Update K8s Ingress & ConfigMap with AGC values ──────────────────

step "Update K8s Ingress & ConfigMap with AGC values"

INGRESS_FILE="k8s/base/ingress.yaml"
if grep -q '${AGC_RESOURCE_ID}' "${INGRESS_FILE}"; then
  sed -i '' "s|\${AGC_RESOURCE_ID}|${AGC_ID}|g" "${INGRESS_FILE}"
  echo "  Updated AGC resource ID in ingress"
else
  echo "  AGC resource ID already populated (skipping)"
fi

if grep -q '${AGC_FQDN}' "${CONFIGMAP_FILE}"; then
  sed -i '' "s|\${AGC_FQDN}|${AGC_FQDN}|g" "${CONFIGMAP_FILE}"
  echo "  Updated AGC FQDN in configmap CORS_ORIGINS"
else
  echo "  AGC FQDN already populated (skipping)"
fi

# ─── Step 7: Update K8s Secrets ───────────────────────────────────────────────

step "Update K8s Secrets Provider Class"

SECRET_FILE="k8s/base/secrets/secret-provider-class.yaml"
if grep -q '${WORKLOAD_IDENTITY_CLIENT_ID}' "${SECRET_FILE}"; then
  sed -i '' "s|\${WORKLOAD_IDENTITY_CLIENT_ID}|${WORKLOAD_ID}|g" "${SECRET_FILE}"
  echo "  Updated workload identity client ID"
else
  echo "  Workload identity client ID already populated (skipping)"
fi

if grep -q '${KEY_VAULT_NAME}' "${SECRET_FILE}"; then
  sed -i '' "s|\${KEY_VAULT_NAME}|${KEY_VAULT_NAME}|g" "${SECRET_FILE}"
  echo "  Updated Key Vault name"
else
  echo "  Key Vault name already populated (skipping)"
fi

if grep -q '${AZURE_TENANT_ID}' "${SECRET_FILE}"; then
  sed -i '' "s|\${AZURE_TENANT_ID}|${TENANT_ID}|g" "${SECRET_FILE}"
  echo "  Updated Azure tenant ID"
else
  echo "  Azure tenant ID already populated (skipping)"
fi

# ─── Step 8: Deploy to AKS ───────────────────────────────────────────────────

step "Deploy to AKS"

cd k8s/base

# Update image tags to current git SHA
for SVC_IMAGE in api-gateway agent-executor workflow-engine tool-executor mcp-proxy; do
  kustomize edit set image "${ACR_SERVER}/aiplatform-${SVC_IMAGE}:${GIT_SHA}" 2>/dev/null || \
    echo "  Note: kustomize edit set image for ${SVC_IMAGE} — may need manual image config"
done

kubectl apply -k .
cd "${PROJECT_ROOT}"

echo -e "  ${GREEN}✓ K8s manifests applied${NC}"

# ─── Step 9: Wait for Rollouts ───────────────────────────────────────────────

step "Waiting for Rollouts"

for SVC_IMAGE in api-gateway agent-executor workflow-engine tool-executor mcp-proxy; do
  echo -n "  Waiting for ${SVC_IMAGE}... "
  if kubectl rollout status "deployment/${SVC_IMAGE}" --timeout=300s 2>/dev/null; then
    echo -e "${GREEN}ready${NC}"
  else
    echo -e "${RED}timeout or error${NC}"
  fi
done

# ─── Step 10: Smoke Tests ────────────────────────────────────────────────────

step "Running Smoke Tests"

bash k8s/scripts/smoke-test.sh default

# ─── Step 11: Provision Default Tenant ────────────────────────────────────────

step "Provisioning Default Tenant"

bash k8s/scripts/setup-tenant.sh default

# ─── Summary ─────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Deployment Complete${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Resource Group:  ${RESOURCE_GROUP}"
echo "  Environment:     ${ENVIRONMENT}"
echo "  AKS Cluster:     ${AKS_CLUSTER}"
echo "  ACR Server:      ${ACR_SERVER}"
echo "  Image Tag:       ${GIT_SHA}"
echo "  Cosmos Endpoint: ${COSMOS_ENDPOINT}"
echo "  Key Vault:       ${KEY_VAULT_NAME}"
echo ""
echo "  Next steps:"
echo "    kubectl get pods                     # Check pod status"
echo "    kubectl get ingress                  # Check ingress URL"
echo "    bash k8s/scripts/smoke-test.sh       # Re-run smoke tests"
echo ""
