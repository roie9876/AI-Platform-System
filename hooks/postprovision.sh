#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

step() { echo ""; echo -e "${BLUE}══════ $1 ══════${NC}"; }

echo "=== Post-provision: Configuring cluster and deploying workloads ==="

# ─── Load azd environment variables ──────────────────────────────────────────

eval "$(azd env get-values | sed 's/^/export /')"

AZURE_ENV_NAME="${AZURE_ENV_NAME:-prod}"
AZURE_RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP not set}"

# azd stores Bicep outputs in camelCase — map to UPPER_SNAKE_CASE
ACR_LOGIN_SERVER="${ACR_LOGIN_SERVER:-${acrLoginServer:-}}"
AKS_CLUSTER_NAME="${AKS_CLUSTER_NAME:-${aksClusterName:-}}"
KEY_VAULT_NAME="${KEY_VAULT_NAME:-${keyVaultName:-}}"
TENANT_KEY_VAULT_NAME="${TENANT_KEY_VAULT_NAME:-${tenantKeyVaultName:-}}"
WORKLOAD_IDENTITY_CLIENT_ID="${WORKLOAD_IDENTITY_CLIENT_ID:-${workloadIdentityClientId:-}}"
AGC_FQDN_FROM_BICEP="${AGC_FQDN_FROM_BICEP:-${agcFqdn:-}}"
AGENTS_DOMAIN="${AGENTS_DOMAIN:-${agentsDomain:-}}"

# Map Bicep outputs to local variables
ACR_SERVER="${ACR_LOGIN_SERVER:?ACR_LOGIN_SERVER not set from Bicep outputs}"
ACR_NAME=$(echo "${ACR_SERVER}" | cut -d. -f1)
AKS_CLUSTER="${AKS_CLUSTER_NAME:?AKS_CLUSTER_NAME not set from Bicep outputs}"
KEY_VAULT_NAME="${KEY_VAULT_NAME:-stumsft-aiplat-${AZURE_ENV_NAME}-kv}"
TENANT_KEY_VAULT_NAME="${TENANT_KEY_VAULT_NAME:-${KEY_VAULT_NAME}}"
AZURE_TENANT_ID="${AZURE_TENANT_ID:-$(az account show --query tenantId -o tsv)}"
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")

echo "  Environment:    ${AZURE_ENV_NAME}"
echo "  Resource Group: ${AZURE_RESOURCE_GROUP}"
echo "  ACR Server:     ${ACR_SERVER}"
echo "  AKS Cluster:    ${AKS_CLUSTER}"
echo "  Git SHA:        ${GIT_SHA}"

# ─── Step 1: Get AKS credentials ─────────────────────────────────────────────

step "Step 1: Get AKS Credentials"

az aks get-credentials \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --name "${AKS_CLUSTER}" \
  --overwrite-existing

echo -e "  ${GREEN}✓ kubectl context set to ${AKS_CLUSTER}${NC}"

# ─── Step 2: Install cluster dependencies ─────────────────────────────────────

step "Step 2: Install Cluster Dependencies (CSI, KEDA, OpenClaw)"

./scripts/install-cluster-deps.sh

echo -e "  ${GREEN}✓ Cluster dependencies installed${NC}"

# ─── Step 3: Enable ALB Controller ───────────────────────────────────────────

step "Step 3: Enable ALB Controller (Application Gateway for Containers)"

az aks update \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --name "${AKS_CLUSTER}" \
  --enable-application-load-balancer \
  --enable-gateway-api \
  --only-show-errors || echo -e "  ${YELLOW}ALB Controller already enabled or update in progress${NC}"

echo -e "  ${GREEN}✓ ALB Controller enabled${NC}"

# ─── Step 3.1: ALB Controller RBAC on AGC ─────────────────────────────────────

step "Step 3.1: ALB Controller RBAC for AGC"

# Get ALB controller managed identity principal ID
ALB_IDENTITY_OBJECT_ID=$(az aks show \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --name "${AKS_CLUSTER}" \
  --query "ingressProfile.webAppRouting.identity.objectId // properties.ingressProfile.webAppRouting.identity.objectId" \
  -o tsv 2>/dev/null || echo "")

# Try ALBC-specific identity if webAppRouting didn't return it
if [ -z "$ALB_IDENTITY_OBJECT_ID" ] || [ "$ALB_IDENTITY_OBJECT_ID" = "null" ]; then
  # The ALB identity is in the MC_ resource group as a managed identity
  MC_RG=$(az aks show --resource-group "${AZURE_RESOURCE_GROUP}" --name "${AKS_CLUSTER}" \
    --query "nodeResourceGroup" -o tsv)
  ALB_IDENTITY_OBJECT_ID=$(az identity list --resource-group "${MC_RG}" \
    --query "[?contains(name, 'applicationloadbalancer')].principalId" -o tsv 2>/dev/null || echo "")
fi

if [ -z "$ALB_IDENTITY_OBJECT_ID" ] || [ "$ALB_IDENTITY_OBJECT_ID" = "null" ]; then
  echo -e "  ${YELLOW}⚠  Could not find ALB controller identity — skipping RBAC${NC}"
else
  echo "  ALB Identity Object ID: ${ALB_IDENTITY_OBJECT_ID}"

  # AGC resource ID from Bicep output
  AGC_RESOURCE_ID="${agcId:-}"
  if [ -z "$AGC_RESOURCE_ID" ]; then
    AGC_RESOURCE_ID=$(az network alb show \
      --resource-group "${AZURE_RESOURCE_GROUP}" \
      --name "stumsft-aiplatform-${AZURE_ENV_NAME}-agc" \
      --query "id" -o tsv 2>/dev/null || echo "")
  fi

  # AGC subnet resource ID
  VNET_NAME="stumsft-aiplatform-${AZURE_ENV_NAME}-vnet"
  AGC_SUBNET_ID=$(az network vnet subnet show \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --vnet-name "${VNET_NAME}" \
    --name "agc-subnet" \
    --query "id" -o tsv 2>/dev/null || echo "")

  # AppGw for Containers Configuration Manager on the AGC Traffic Controller
  if [ -n "$AGC_RESOURCE_ID" ]; then
    az role assignment create \
      --assignee-object-id "${ALB_IDENTITY_OBJECT_ID}" \
      --assignee-principal-type ServicePrincipal \
      --role "fbc52c3f-28ad-4303-a892-8a056630b8f1" \
      --scope "${AGC_RESOURCE_ID}" \
      --only-show-errors 2>/dev/null || true
    echo -e "  ${GREEN}✓ AppGw for Containers Configuration Manager role assigned${NC}"
  fi

  # Network Contributor on the AGC subnet
  if [ -n "$AGC_SUBNET_ID" ]; then
    az role assignment create \
      --assignee-object-id "${ALB_IDENTITY_OBJECT_ID}" \
      --assignee-principal-type ServicePrincipal \
      --role "4d97b98b-1d4f-4787-a291-c67834d212e7" \
      --scope "${AGC_SUBNET_ID}" \
      --only-show-errors 2>/dev/null || true
    echo -e "  ${GREEN}✓ Network Contributor role assigned on AGC subnet${NC}"
  fi
fi

# ─── Step 4: Build and Push Docker Images ─────────────────────────────────────

step "Step 4: Build and Push Docker Images via ACR Build"

az acr login --name "${ACR_NAME}"

# Helper: skip build if image:tag already exists in ACR
acr_build_if_needed() {
  local image_name="$1" dockerfile="$2" context="$3"
  if az acr manifest show-metadata "${ACR_NAME}.azurecr.io/${image_name}:${GIT_SHA}" \
       --registry "${ACR_NAME}" --only-show-errors &>/dev/null; then
    echo -e "  ${GREEN}✓ ${image_name}:${GIT_SHA} already exists — skipping build${NC}"
    return 0
  fi
  echo -e "  ${BLUE}Building ${image_name}...${NC}"
  az acr build \
    --registry "${ACR_NAME}" \
    --image "${image_name}:${GIT_SHA}" \
    --image "${image_name}:latest" \
    --file "${dockerfile}" \
    --platform linux/amd64 \
    "${context}"
  echo -e "  ${GREEN}✓ ${image_name}${NC}"
}

# Microservice images (build context: backend/)
MS_IMAGES=("api-gateway" "agent-executor" "workflow-engine" "tool-executor" "mcp-proxy")
MS_DIRS=("api_gateway" "agent_executor" "workflow_engine" "tool_executor" "mcp_proxy")

for i in "${!MS_IMAGES[@]}"; do
  acr_build_if_needed "aiplatform-${MS_IMAGES[$i]}" \
    "backend/microservices/${MS_DIRS[$i]}/Dockerfile" "backend/"
done

# Token proxy (Dockerfile in llm_proxy, build context: backend/)
acr_build_if_needed "aiplatform-token-proxy" \
  "backend/microservices/llm_proxy/Dockerfile" "backend/"

# MCP server images (build context: backend/)
for MCP_SVC in atlassian github sharepoint platform-tools; do
  acr_build_if_needed "aiplatform-mcp-${MCP_SVC}" \
    "backend/Dockerfile.mcp-${MCP_SVC}" "backend/"
done

# Auth gateway (build context: backend/)
acr_build_if_needed "aiplatform-auth-gateway" \
  "backend/microservices/auth_gateway/Dockerfile" "backend/"

# Frontend (build context: frontend/)
acr_build_if_needed "aiplatform-frontend" \
  "frontend/Dockerfile" "frontend/"

echo ""
echo -e "  ${GREEN}✓ All images ready in ${ACR_SERVER}${NC}"

# ─── Step 5: Prepare K8s manifests (temp dir — repo stays clean) ──────────────

step "Step 5: Prepare K8s Manifests"

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

kubectl create namespace aiplatform --dry-run=client -o yaml | kubectl apply -f -

cp -r k8s/base/ "$TEMP_DIR/base/"

# Get AGC frontend FQDN — prefer Bicep output, fall back to Azure query
AGC_FQDN="${AGC_FQDN_FROM_BICEP:-}"
if [ -z "$AGC_FQDN" ]; then
  AGC_FQDN=$(az network alb frontend show \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --alb-name "stumsft-aiplatform-${AZURE_ENV_NAME}-agc" \
    --name "default-frontend" \
    --query "fqdn" -o tsv 2>/dev/null || echo "")
fi

CORS_ORIGINS='["http://localhost:3000"'
if [ -n "$AGC_FQDN" ]; then
  CORS_ORIGINS="${CORS_ORIGINS},\"https://${AGC_FQDN}\",\"http://${AGC_FQDN}\""
fi
if [ -n "$AGENTS_DOMAIN" ]; then
  CORS_ORIGINS="${CORS_ORIGINS},\"https://${AGENTS_DOMAIN}\""
fi
CORS_ORIGINS="${CORS_ORIGINS}]"
export CORS_ORIGINS

# Substitute configmap variables
sed -i.bak "s|\${KEY_VAULT_NAME}|${KEY_VAULT_NAME}|g" "$TEMP_DIR/base/configmap.yaml"
sed -i.bak "s|\${TENANT_KEY_VAULT_NAME}|${TENANT_KEY_VAULT_NAME}|g" "$TEMP_DIR/base/configmap.yaml"
sed -i.bak "s|\${CORS_ORIGINS}|${CORS_ORIGINS}|g" "$TEMP_DIR/base/configmap.yaml"
sed -i.bak "s|\${AGENTS_DOMAIN}|${AGENTS_DOMAIN:-}|g" "$TEMP_DIR/base/configmap.yaml"

# Substitute secret-provider-class variables
find "$TEMP_DIR/base/secrets/" -name "*.yaml" -exec sed -i.bak \
  -e "s|\${WORKLOAD_IDENTITY_CLIENT_ID}|${WORKLOAD_IDENTITY_CLIENT_ID}|g" \
  -e "s|\${KEY_VAULT_NAME}|${KEY_VAULT_NAME}|g" \
  -e "s|\${AZURE_TENANT_ID}|${AZURE_TENANT_ID}|g" {} \;

# Substitute ${ACR_SERVER} in ALL deployment manifests
find "$TEMP_DIR/base/" -name "deployment.yaml" -exec sed -i.bak \
  "s|\${ACR_SERVER}|${ACR_SERVER}|g" {} \;

# Substitute ${WORKLOAD_IDENTITY_CLIENT_ID} in service-account.yaml
sed -i.bak "s|\${WORKLOAD_IDENTITY_CLIENT_ID}|${WORKLOAD_IDENTITY_CLIENT_ID}|g" "$TEMP_DIR/base/service-account.yaml"

# Substitute ingress variables (AGC resource ID)
AGC_RESOURCE_ID="${agcId:-}"
if [ -n "$AGC_RESOURCE_ID" ]; then
  sed -i.bak -e "s|\${AGC_RESOURCE_ID}|${AGC_RESOURCE_ID}|g" \
    "$TEMP_DIR/base/ingress.yaml"
else
  echo -e "  ${YELLOW}⚠  AGC not ready — removing ingress.yaml from deployment${NC}"
  rm -f "$TEMP_DIR/base/ingress.yaml"
  sed -i.bak '/ingress\.yaml/d' "$TEMP_DIR/base/kustomization.yaml"
fi

# Clean up .bak files
find "$TEMP_DIR" -name "*.bak" -delete

echo -e "  ${GREEN}✓ All variables substituted${NC}"

# ─── Step 6: Deploy to AKS ───────────────────────────────────────────────────

step "Step 6: Deploy to AKS"

kubectl apply -k "$TEMP_DIR/base/" --namespace aiplatform

echo -e "  ${GREEN}✓ K8s manifests applied to namespace aiplatform${NC}"

# ─── Step 6.1: Generate TLS secret for AGC FQDN ─────────────────────────────

if [ -n "$AGC_FQDN" ]; then
  if kubectl get secret agc-tls-secret -n aiplatform &>/dev/null; then
    echo -e "  ${GREEN}✓ agc-tls-secret already exists — skipping${NC}"
  else
    step "Step 6.1: Generate TLS Certificate for AGC"
    CERT_DIR=$(mktemp -d)
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout "$CERT_DIR/tls.key" -out "$CERT_DIR/tls.crt" \
      -subj "/CN=${AGC_FQDN}" \
      -addext "subjectAltName=DNS:${AGC_FQDN}" 2>/dev/null
    kubectl create secret tls agc-tls-secret \
      --cert="$CERT_DIR/tls.crt" --key="$CERT_DIR/tls.key" \
      --namespace aiplatform
    rm -rf "$CERT_DIR"
    echo -e "  ${GREEN}✓ Self-signed TLS certificate created for ${AGC_FQDN}${NC}"
  fi
fi

# ─── Step 7: Wait for rollouts ───────────────────────────────────────────────

step "Step 7: Wait for Rollouts"

ALL_DEPLOYMENTS=("api-gateway" "agent-executor" "workflow-engine" "tool-executor" "mcp-proxy" "token-proxy" "frontend" "mcp-atlassian" "mcp-github" "mcp-sharepoint" "mcp-platform-tools")

for SVC in "${ALL_DEPLOYMENTS[@]}"; do
  echo -n "  Waiting for ${SVC}... "
  if kubectl rollout status "deployment/${SVC}" -n aiplatform --timeout=300s 2>/dev/null; then
    echo -e "${GREEN}ready${NC}"
  else
    echo -e "${YELLOW}timeout (may need secrets configured)${NC}"
  fi
done

# ─── Step 8: Conditional cert-manager resources ──────────────────────────────

if [ -n "$AGENTS_DOMAIN" ]; then
  step "Step 8: Cert-Manager (Custom Domain)"
  echo "Agents domain configured: $AGENTS_DOMAIN"

  AZURE_SUBSCRIPTION_ID=$(az account show --query id -o tsv)
  CERT_MANAGER_IDENTITY_CLIENT_ID="${WORKLOAD_IDENTITY_CLIENT_ID}"
  export AGENTS_DOMAIN AZURE_RESOURCE_GROUP AZURE_SUBSCRIPTION_ID CERT_MANAGER_IDENTITY_CLIENT_ID

  for f in k8s/cert-manager/*.yaml; do
    envsubst < "$f" | kubectl apply -f -
  done

  kubectl wait --for=condition=Ready certificate/wildcard-agents-tls \
    --namespace aiplatform --timeout=300s 2>/dev/null || \
    echo -e "  ${YELLOW}Certificate not ready yet. DNS may need NS record delegation.${NC}"

  # Deploy auth-gateway manifests
  step "Step 8.1: Auth Gateway (Custom Domain)"

  TEMP_AUTH_DIR="$TEMP_DIR/auth-gateway"
  mkdir -p "$TEMP_AUTH_DIR"
  cp k8s/base/auth-gateway/*.yaml "$TEMP_AUTH_DIR/"

  # Substitute variables in auth-gateway manifests
  find "$TEMP_AUTH_DIR" -name "*.yaml" -exec sed -i.bak \
    -e "s|\${ACR_SERVER}|${ACR_SERVER}|g" \
    -e "s|\${AGENTS_DOMAIN}|${AGENTS_DOMAIN}|g" \
    -e "s|\${AGC_RESOURCE_ID}|${AGC_RESOURCE_ID}|g" {} \;
  find "$TEMP_AUTH_DIR" -name "*.bak" -delete

  kubectl apply -f "$TEMP_AUTH_DIR/" --namespace aiplatform
  echo -e "  ${GREEN}✓ Auth gateway deployed${NC}"

  echo -n "  Waiting for auth-gateway... "
  if kubectl rollout status "deployment/auth-gateway" -n aiplatform --timeout=300s 2>/dev/null; then
    echo -e "${GREEN}ready${NC}"
  else
    echo -e "${YELLOW}timeout (may need secrets configured)${NC}"
  fi
fi

# ─── Step 8.5: Seed Entra Client Secret into Key Vault ───────────────────────

ENTRA_CLIENT_SECRET="${ENTRA_CLIENT_SECRET:-}"
if [ -n "${ENTRA_CLIENT_SECRET}" ] && [ "${ENTRA_CLIENT_SECRET}" != "PLACEHOLDER_UPDATE_AFTER_DEPLOY" ]; then
  step "Step 8.5: Seed Entra Client Secret into Key Vault"
  az keyvault secret set \
    --vault-name "${KEY_VAULT_NAME}" \
    --name "entra-client-secret" \
    --value "${ENTRA_CLIENT_SECRET}" \
    --only-show-errors >/dev/null
  echo -e "  ${GREEN}✓ Entra client secret seeded into Key Vault${NC}"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Post-provision Complete${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  AKS Cluster:  ${AKS_CLUSTER}"
echo "  ACR Server:   ${ACR_SERVER}"
echo "  Image Tag:    ${GIT_SHA}"
echo "  Key Vault:    ${KEY_VAULT_NAME}"
echo "  Namespace:    aiplatform"
if [ -n "$AGC_FQDN" ]; then
echo ""
echo -e "  ${GREEN}┌──────────────────────────────────────────────────────┐${NC}"
echo -e "  ${GREEN}│                                                      │${NC}"
echo -e "  ${GREEN}│   Platform URL:  https://${AGC_FQDN}${NC}"
echo -e "  ${GREEN}│                                                      │${NC}"
echo -e "  ${GREEN}│   ⚠  Self-signed cert — browser will show a warning  │${NC}"
echo -e "  ${GREEN}│   Bypass: click Advanced → Proceed (unsafe)          │${NC}"
echo -e "  ${GREEN}│                                                      │${NC}"
echo -e "  ${GREEN}└──────────────────────────────────────────────────────┘${NC}"
fi
echo ""
echo "  Post-deploy actions needed:"
echo "    1. Set Azure OpenAI secrets (required for agent LLM calls):"
echo "       az keyvault secret set --vault-name ${KEY_VAULT_NAME} --name azure-openai-endpoint --value '<ENDPOINT>'"
echo "       az keyvault secret set --vault-name ${KEY_VAULT_NAME} --name azure-openai-key --value '<KEY>'"
if [ -z "${ENTRA_CLIENT_SECRET}" ] || [ "${ENTRA_CLIENT_SECRET}" = "PLACEHOLDER_UPDATE_AFTER_DEPLOY" ]; then
echo "    2. Set Entra client secret (if using existing App Registration):"
echo "       az keyvault secret set --vault-name ${KEY_VAULT_NAME} --name entra-client-secret --value '<YOUR_SECRET>'"
fi
echo "    3. Optional: Set Jira token for MCP integration:"
echo "       az keyvault secret set --vault-name ${KEY_VAULT_NAME} --name jira --value '<YOUR_JIRA_TOKEN>'"
echo "    4. Restart pods to pick up secrets:"
echo "       kubectl rollout restart deployment -n aiplatform"
echo "    5. Run smoke tests:  bash k8s/scripts/smoke-test.sh aiplatform"
echo "    6. Provision tenant: bash k8s/scripts/setup-tenant.sh default"
echo ""
