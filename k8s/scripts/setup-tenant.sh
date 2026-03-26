#!/bin/bash
set -euo pipefail

TENANT_SLUG="${1:?Usage: setup-tenant.sh <tenant-slug>}"
TENANT_NS="tenant-${TENANT_SLUG}"
TEMPLATE_DIR="$(dirname "$0")/../overlays/tenant-template"
WORK_DIR=$(mktemp -d)

echo "Provisioning tenant namespace: ${TENANT_NS}"

# Copy template and substitute placeholders
cp -r "${TEMPLATE_DIR}/"* "${WORK_DIR}/"
find "${WORK_DIR}" -type f -name "*.yaml" -exec sed -i '' "s/TENANT_NAMESPACE/${TENANT_NS}/g" {} \;
find "${WORK_DIR}" -type f -name "*.yaml" -exec sed -i '' "s/TENANT_SLUG/${TENANT_SLUG}/g" {} \;

# Apply via kustomize
kubectl apply -k "${WORK_DIR}"

echo "Tenant ${TENANT_SLUG} provisioned in namespace ${TENANT_NS}"
rm -rf "${WORK_DIR}"
