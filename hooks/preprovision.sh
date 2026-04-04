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

echo "All prerequisites satisfied."
