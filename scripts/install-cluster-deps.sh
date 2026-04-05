#!/bin/bash
set -euo pipefail

# Install cluster dependencies via Helm
# Called by hooks/postprovision.sh after Azure infra is provisioned
# Per D-03: These were previously "invisible" — installed manually, not tracked in repo.

echo "=== Installing Cluster Dependencies ==="

# Load azd env if available
if command -v azd &>/dev/null; then
  eval "$(azd env get-values 2>/dev/null | sed 's/^/export /' || true)"
fi

AGENTS_DOMAIN="${AGENTS_DOMAIN:-}"

# --- 1. CSI Secrets Store Driver ---
# AKS addon 'azureKeyvaultSecretsProvider' manages the driver and CRDs.
# Only install via Helm if the addon is NOT present.
if kubectl get crd secretproviderclasses.secrets-store.csi.x-k8s.io -o jsonpath='{.metadata.labels.kubernetes\.azure\.com/managedby}' 2>/dev/null | grep -q aks; then
  echo "[1/4] CSI Secrets Store Driver — SKIPPED (managed by AKS addon)"
else
  echo "[1/4] CSI Secrets Store Driver (Helm)..."
  helm repo add csi-secrets-store-provider-azure https://azure.github.io/secrets-store-csi-driver-provider-azure/charts 2>/dev/null || true
  helm repo add secrets-store-csi-driver https://kubernetes-sigs.github.io/secrets-store-csi-driver/charts 2>/dev/null || true
  helm repo update

  helm upgrade --install csi-secrets-store-driver secrets-store-csi-driver/secrets-store-csi-driver \
    --namespace kube-system \
    --set syncSecret.enabled=true \
    --set enableSecretRotation=true \
    --wait --timeout 5m

  helm upgrade --install csi-secrets-store-provider-azure csi-secrets-store-provider-azure/csi-secrets-store-provider-azure \
    --namespace kube-system \
    --wait --timeout 5m
fi

# --- 2. KEDA ---
echo "[2/4] KEDA autoscaler..."
helm repo add kedacore https://kedacore.github.io/charts 2>/dev/null || true
helm repo update

kubectl create namespace keda --dry-run=client -o yaml | kubectl apply -f -

# KEDA webhook may conflict with AKS Gatekeeper admissionsenforcer
# which modifies webhook namespaceSelector. Delete stale webhook before upgrade.
kubectl delete validatingwebhookconfiguration keda-admission 2>/dev/null || true

helm upgrade --install keda kedacore/keda \
  --namespace keda \
  --set podIdentity.azureWorkload.enabled=true \
  --wait --timeout 5m

# --- 3. OpenClaw Operator ---
echo "[3/4] OpenClaw operator..."
kubectl create namespace openclaw-system --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install openclaw-operator oci://registry.openclaw.rocks/charts/openclaw-operator \
  --namespace openclaw-system \
  --wait --timeout 5m 2>/dev/null || \
  echo "WARNING: OpenClaw operator install failed. Verify OCI registry access."

# --- 4. cert-manager (conditional — only when AGENTS_DOMAIN is set, per D-07) ---
if [ -n "$AGENTS_DOMAIN" ]; then
  echo "[4/4] cert-manager (domain: $AGENTS_DOMAIN)..."
  helm repo add jetstack https://charts.jetstack.io 2>/dev/null || true
  helm repo update

  kubectl create namespace cert-manager --dry-run=client -o yaml | kubectl apply -f -
  helm upgrade --install cert-manager jetstack/cert-manager \
    --namespace cert-manager \
    --set crds.enabled=true \
    --set podLabels."azure\.workload\.identity/use"="true" \
    --wait --timeout 5m
else
  echo "[4/4] cert-manager — SKIPPED (no AGENTS_DOMAIN configured)"
fi

echo "=== Cluster dependencies installed ==="
