#!/bin/bash
set -euo pipefail

# Validate prerequisites for azd up
echo "=== Pre-provision: Validating prerequisites ==="

# Check required CLI tools
for cmd in az kubectl helm jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: $cmd is required but not installed."
    exit 1
  fi
done

# Validate Azure login
if ! az account show &>/dev/null; then
  echo "ERROR: Not logged in to Azure. Run 'az login' first."
  exit 1
fi

# Copy environment-specific Bicep parameter file
eval "$(azd env get-values | sed 's/^/export /')"
AZURE_ENV_NAME="${AZURE_ENV_NAME:-prod}"
PARAM_FILE="infra/parameters/${AZURE_ENV_NAME}.bicepparam"
if [ -f "${PARAM_FILE}" ]; then
  cp "${PARAM_FILE}" infra/main.bicepparam
  echo "Using parameter file for environment: ${AZURE_ENV_NAME}"
else
  echo "ERROR: Parameter file not found: ${PARAM_FILE}"
  echo "Available environments: $(ls infra/parameters/*.bicepparam 2>/dev/null | xargs -I{} basename {} .bicepparam)"
  exit 1
fi

echo "Pre-provision complete."

echo "All prerequisites satisfied."
