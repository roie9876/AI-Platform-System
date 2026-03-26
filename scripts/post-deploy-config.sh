#!/bin/bash
set -euo pipefail

# =============================================================================
# Post-deploy configuration bridge — extracts Bicep deployment outputs and
# populates K8s manifest placeholders (configmap, secret-provider-class)
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
DEPLOYMENT_NAME="main"

usage() {
  echo "Usage: $0 --resource-group <rg> [--deployment-name <name>]"
  echo ""
  echo "Required:"
  echo "  --resource-group <rg>       Azure resource group name"
  echo ""
  echo "Options:"
  echo "  --deployment-name <name>    Bicep deployment name (default: main)"
  echo "  --help                      Show this help"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --resource-group) RESOURCE_GROUP="$2"; shift 2 ;;
    --deployment-name) DEPLOYMENT_NAME="$2"; shift 2 ;;
    --help) usage ;;
    *) echo "Unknown argument: $1"; usage ;;
  esac
done

if [ -z "${RESOURCE_GROUP}" ]; then
  echo -e "${RED}Error: --resource-group is required${NC}"
  usage
fi

echo -e "${BLUE}Post-deploy configuration bridge${NC}"
echo "  Resource Group:  ${RESOURCE_GROUP}"
echo "  Deployment Name: ${DEPLOYMENT_NAME}"
echo ""

# ─── Extract Bicep deployment outputs ────────────────────────────────────────

echo -e "${BLUE}Extracting Bicep deployment outputs...${NC}"

OUTPUTS=$(az deployment group show \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${DEPLOYMENT_NAME}" \
  --query properties.outputs -o json)

ACR_SERVER=$(echo "${OUTPUTS}" | jq -r '.acrLoginServer.value')
AKS_CLUSTER=$(echo "${OUTPUTS}" | jq -r '.aksClusterName.value')
COSMOS_ENDPOINT=$(echo "${OUTPUTS}" | jq -r '.cosmosEndpoint.value')
KEY_VAULT_URI=$(echo "${OUTPUTS}" | jq -r '.keyVaultUri.value')
KEY_VAULT_NAME=$(echo "${OUTPUTS}" | jq -r '.keyVaultName.value // empty')
WORKLOAD_ID=$(echo "${OUTPUTS}" | jq -r '.workloadIdentityClientId.value')
APP_INSIGHTS_CS=$(echo "${OUTPUTS}" | jq -r '.appInsightsConnectionString.value')
AGC_ID=$(echo "${OUTPUTS}" | jq -r '.agcId.value')
AGC_FQDN=$(echo "${OUTPUTS}" | jq -r '.agcFqdn.value')

# Derive Key Vault name from URI if not in outputs
if [ -z "${KEY_VAULT_NAME}" ]; then
  KEY_VAULT_NAME=$(echo "${KEY_VAULT_URI}" | sed 's|https://||;s|\.vault\.azure\.net.*||')
fi

# Get Azure tenant ID
TENANT_ID=$(az account show --query tenantId -o tsv)

echo "  ACR Server:     ${ACR_SERVER}"
echo "  AKS Cluster:    ${AKS_CLUSTER}"
echo "  Cosmos Endpoint: ${COSMOS_ENDPOINT}"
echo "  Key Vault:      ${KEY_VAULT_NAME}"
echo "  Workload ID:    ${WORKLOAD_ID}"
echo "  App Insights:   ${APP_INSIGHTS_CS:0:40}..."
echo "  AGC ID:         ${AGC_ID}"
echo "  AGC FQDN:       ${AGC_FQDN}"
echo "  Tenant ID:      ${TENANT_ID}"
echo ""

# ─── Update K8s ConfigMap ─────────────────────────────────────────────────────

echo -e "${BLUE}Updating K8s ConfigMap...${NC}"

CONFIGMAP_FILE="k8s/base/configmap.yaml"
if [ -f "${CONFIGMAP_FILE}" ]; then
  if grep -q "REPLACE_WITH_APP_INSIGHTS_CONNECTION_STRING" "${CONFIGMAP_FILE}"; then
    # Use temp file for portability (works on both macOS and Linux)
    TMPFILE=$(mktemp)
    sed "s|REPLACE_WITH_APP_INSIGHTS_CONNECTION_STRING|${APP_INSIGHTS_CS}|g" "${CONFIGMAP_FILE}" > "${TMPFILE}"
    mv "${TMPFILE}" "${CONFIGMAP_FILE}"
    echo -e "  ${GREEN}✓${NC} Updated APPLICATIONINSIGHTS_CONNECTION_STRING"
  else
    echo -e "  ${YELLOW}⚠${NC} App Insights connection string already populated (skipping)"
  fi
else
  echo -e "  ${RED}✗${NC} ${CONFIGMAP_FILE} not found"
fi

# ─── Update K8s SecretProviderClass ───────────────────────────────────────────

echo -e "${BLUE}Updating K8s SecretProviderClass...${NC}"

SECRET_FILE="k8s/base/secrets/secret-provider-class.yaml"
if [ -f "${SECRET_FILE}" ]; then
  UPDATED=0

  if grep -q '${WORKLOAD_IDENTITY_CLIENT_ID}' "${SECRET_FILE}"; then
    TMPFILE=$(mktemp)
    sed 's|\${WORKLOAD_IDENTITY_CLIENT_ID}|'"${WORKLOAD_ID}"'|g' "${SECRET_FILE}" > "${TMPFILE}"
    mv "${TMPFILE}" "${SECRET_FILE}"
    echo -e "  ${GREEN}✓${NC} Updated WORKLOAD_IDENTITY_CLIENT_ID → ${WORKLOAD_ID}"
    UPDATED=$((UPDATED + 1))
  else
    echo -e "  ${YELLOW}⚠${NC} WORKLOAD_IDENTITY_CLIENT_ID already populated (skipping)"
  fi

  if grep -q '${KEY_VAULT_NAME}' "${SECRET_FILE}"; then
    TMPFILE=$(mktemp)
    sed 's|\${KEY_VAULT_NAME}|'"${KEY_VAULT_NAME}"'|g' "${SECRET_FILE}" > "${TMPFILE}"
    mv "${TMPFILE}" "${SECRET_FILE}"
    echo -e "  ${GREEN}✓${NC} Updated KEY_VAULT_NAME → ${KEY_VAULT_NAME}"
    UPDATED=$((UPDATED + 1))
  else
    echo -e "  ${YELLOW}⚠${NC} KEY_VAULT_NAME already populated (skipping)"
  fi

  if grep -q '${AZURE_TENANT_ID}' "${SECRET_FILE}"; then
    TMPFILE=$(mktemp)
    sed 's|\${AZURE_TENANT_ID}|'"${TENANT_ID}"'|g' "${SECRET_FILE}" > "${TMPFILE}"
    mv "${TMPFILE}" "${SECRET_FILE}"
    echo -e "  ${GREEN}✓${NC} Updated AZURE_TENANT_ID → ${TENANT_ID}"
    UPDATED=$((UPDATED + 1))
  else
    echo -e "  ${YELLOW}⚠${NC} AZURE_TENANT_ID already populated (skipping)"
  fi

  echo -e "  Updated ${UPDATED} placeholder(s) in SecretProviderClass"
else
  echo -e "  ${RED}✗${NC} ${SECRET_FILE} not found"
fi

# ─── Update K8s Ingress with AGC resource ID ──────────────────────────────────

echo -e "${BLUE}Updating K8s Ingress with AGC values...${NC}"

INGRESS_FILE="k8s/base/ingress.yaml"
if [ -f "${INGRESS_FILE}" ]; then
  if grep -q '${AGC_RESOURCE_ID}' "${INGRESS_FILE}"; then
    TMPFILE=$(mktemp)
    sed 's|\${AGC_RESOURCE_ID}|'"${AGC_ID}"'|g' "${INGRESS_FILE}" > "${TMPFILE}"
    mv "${TMPFILE}" "${INGRESS_FILE}"
    echo -e "  ${GREEN}✓${NC} Updated AGC_RESOURCE_ID → ${AGC_ID}"
  else
    echo -e "  ${YELLOW}⚠${NC} AGC_RESOURCE_ID already populated (skipping)"
  fi
else
  echo -e "  ${RED}✗${NC} ${INGRESS_FILE} not found"
fi

# ─── Update K8s ConfigMap CORS with AGC FQDN ─────────────────────────────────

echo -e "${BLUE}Updating K8s ConfigMap CORS with AGC FQDN...${NC}"

if [ -f "${CONFIGMAP_FILE}" ]; then
  if grep -q '${AGC_FQDN}' "${CONFIGMAP_FILE}"; then
    TMPFILE=$(mktemp)
    sed 's|\${AGC_FQDN}|'"${AGC_FQDN}"'|g' "${CONFIGMAP_FILE}" > "${TMPFILE}"
    mv "${TMPFILE}" "${CONFIGMAP_FILE}"
    echo -e "  ${GREEN}✓${NC} Updated AGC_FQDN → ${AGC_FQDN}"
  else
    echo -e "  ${YELLOW}⚠${NC} AGC_FQDN already populated (skipping)"
  fi
else
  echo -e "  ${RED}✗${NC} ${CONFIGMAP_FILE} not found"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}━━━ Post-deploy configuration complete ━━━${NC}"
echo ""
echo "  Files updated:"
echo "    ${CONFIGMAP_FILE}"
echo "    ${SECRET_FILE}"
echo "    ${INGRESS_FILE}"
echo ""
echo "  Apply to cluster:"
echo "    kubectl apply -k k8s/base"
echo ""
