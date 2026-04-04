#!/bin/bash
set -euo pipefail

echo "=== Post-provision: Configuring cluster ==="

# Load azd environment variables
eval "$(azd env get-values | sed 's/^/export /')"

# Get AKS credentials
echo "Getting AKS credentials..."
az aks get-credentials \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --name "${AKS_CLUSTER_NAME}" \
  --overwrite-existing

# Install cluster dependencies (KEDA, CSI, OpenClaw operator, conditional cert-manager)
echo "Installing cluster dependencies..."
./scripts/install-cluster-deps.sh

# Create aiplatform namespace if it doesn't exist
kubectl create namespace aiplatform --dry-run=client -o yaml | kubectl apply -f -

# Apply platform K8s manifests
echo "Applying K8s manifests..."

# Substitute environment variables in configmap before applying
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# Get AGC frontend FQDN from deployment outputs for CORS parameterization
AGC_FQDN=$(az network alb frontend show \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --alb-name "stumsft-aiplatform-${AZURE_ENV_NAME}-agc" \
  --name "default-frontend" \
  --query "fqdn" -o tsv 2>/dev/null || echo "")

# Build CORS origins
CORS_ORIGINS='["http://localhost:3000"'
if [ -n "$AGC_FQDN" ]; then
  CORS_ORIGINS="${CORS_ORIGINS},\"https://${AGC_FQDN}\",\"http://${AGC_FQDN}\""
fi
AGENTS_DOMAIN="${AGENTS_DOMAIN:-}"
if [ -n "$AGENTS_DOMAIN" ]; then
  CORS_ORIGINS="${CORS_ORIGINS},\"https://${AGENTS_DOMAIN}\""
fi
CORS_ORIGINS="${CORS_ORIGINS}]"

# Substitute configmap variables
export KEY_VAULT_NAME="${KEY_VAULT_NAME:-stumsft-aiplat-${AZURE_ENV_NAME}-kv}"
export TENANT_KEY_VAULT_NAME="${TENANT_KEY_VAULT_NAME:-${KEY_VAULT_NAME}}"
export CORS_ORIGINS

cp -r k8s/base/ "$TEMP_DIR/base/"
sed -i.bak "s|\${KEY_VAULT_NAME}|${KEY_VAULT_NAME}|g" "$TEMP_DIR/base/configmap.yaml"
sed -i.bak "s|\${TENANT_KEY_VAULT_NAME}|${TENANT_KEY_VAULT_NAME}|g" "$TEMP_DIR/base/configmap.yaml"
sed -i.bak "s|\${CORS_ORIGINS}|${CORS_ORIGINS}|g" "$TEMP_DIR/base/configmap.yaml"
rm -f "$TEMP_DIR/base/"*.bak "$TEMP_DIR/base/"**/*.bak 2>/dev/null || true

# Substitute secret-provider-class variables
WORKLOAD_IDENTITY_CLIENT_ID="${WORKLOAD_IDENTITY_CLIENT_ID:-}"
AZURE_TENANT_ID="${AZURE_TENANT_ID:-$(az account show --query tenantId -o tsv)}"
export WORKLOAD_IDENTITY_CLIENT_ID AZURE_TENANT_ID
find "$TEMP_DIR/base/secrets/" -name "*.yaml" -exec sed -i.bak \
  -e "s|\${WORKLOAD_IDENTITY_CLIENT_ID}|${WORKLOAD_IDENTITY_CLIENT_ID}|g" \
  -e "s|\${KEY_VAULT_NAME}|${KEY_VAULT_NAME}|g" \
  -e "s|\${AZURE_TENANT_ID}|${AZURE_TENANT_ID}|g" {} \;
rm -f "$TEMP_DIR/base/secrets/"*.bak 2>/dev/null || true

kubectl apply -k "$TEMP_DIR/base/" --namespace aiplatform

# Conditional: cert-manager resources (only when AGENTS_DOMAIN is set, per D-07)
if [ -n "$AGENTS_DOMAIN" ]; then
  echo "Agents domain configured: $AGENTS_DOMAIN"
  echo "Applying cert-manager ClusterIssuer and Certificate..."

  AZURE_SUBSCRIPTION_ID=$(az account show --query id -o tsv)
  CERT_MANAGER_IDENTITY_CLIENT_ID="${WORKLOAD_IDENTITY_CLIENT_ID}"

  export AGENTS_DOMAIN AZURE_RESOURCE_GROUP AZURE_SUBSCRIPTION_ID CERT_MANAGER_IDENTITY_CLIENT_ID

  for f in k8s/cert-manager/*.yaml; do
    envsubst < "$f" | kubectl apply -f -
  done

  echo "Waiting for wildcard certificate to be issued..."
  kubectl wait --for=condition=Ready certificate/wildcard-agents-tls \
    --namespace cert-manager --timeout=300s 2>/dev/null || \
    echo "WARNING: Certificate not ready yet. DNS may need NS record delegation."
fi

echo "Post-provision complete."
