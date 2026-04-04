#!/bin/bash
set -euo pipefail

# migrate-tenant-secrets.sh — Copy tenant secrets from platform vault to tenant vault
#
# Part of AUDIT-06: Migrate existing tenant secrets with zero downtime.
# Safe rollout per D-18:
#   1. Tenant vault already deployed (via Bicep)
#   2. Backend already has TENANT_KEY_VAULT_NAME fallback (backward-compatible)
#   3. This script COPIES secrets (does NOT delete from source)
#   4. After verification, manually remove old secrets from platform vault
#
# Usage: ./scripts/migrate-tenant-secrets.sh [--env prod] [--dry-run]

ENV="prod"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --env) ENV="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --help)
      echo "Usage: $0 [--env prod|staging] [--dry-run]"
      echo ""
      echo "Copies tenant-specific secrets from platform vault to tenant vault."
      echo "Does NOT delete source secrets (manual cleanup after verification)."
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

PLATFORM_VAULT="stumsft-aiplat-${ENV}-kv"
TENANT_VAULT="stumsft-aiplat-${ENV}-tkv"

echo "=== Tenant Secret Migration ==="
echo "Source:      $PLATFORM_VAULT"
echo "Destination: $TENANT_VAULT"
echo "Dry run:     $DRY_RUN"
echo ""

# Verify both vaults exist
echo "Verifying vault access..."
az keyvault show --name "$PLATFORM_VAULT" --query "name" -o tsv >/dev/null
az keyvault show --name "$TENANT_VAULT" --query "name" -o tsv >/dev/null
echo "Both vaults accessible."

# Tenant-specific secret patterns (these belong in the tenant vault)
# Platform secrets (cosmos-endpoint, entra-*, etc.) stay in platform vault
TENANT_SECRET_PATTERNS=(
  "azure-openai-api-key"
  "TELEGRAMBOTTOKEN"
  "telegram-bot-token"
  "gmail-"
  "slack-"
)

# List all secrets in platform vault
echo ""
echo "Scanning platform vault for tenant secrets..."
ALL_SECRETS=$(az keyvault secret list --vault-name "$PLATFORM_VAULT" --query "[].name" -o tsv)

MIGRATE_COUNT=0
SKIP_COUNT=0

for secret_name in $ALL_SECRETS; do
  IS_TENANT_SECRET=false
  for pattern in "${TENANT_SECRET_PATTERNS[@]}"; do
    if [[ "$secret_name" == *"$pattern"* ]]; then
      IS_TENANT_SECRET=true
      break
    fi
  done

  if [ "$IS_TENANT_SECRET" = true ]; then
    MIGRATE_COUNT=$((MIGRATE_COUNT + 1))
    if [ "$DRY_RUN" = true ]; then
      echo "  [DRY RUN] Would copy: $secret_name"
    else
      echo "  Copying: $secret_name"
      # Get secret value from platform vault
      SECRET_VALUE=$(az keyvault secret show \
        --vault-name "$PLATFORM_VAULT" \
        --name "$secret_name" \
        --query "value" -o tsv)

      # Set in tenant vault (idempotent — overwrites if exists)
      az keyvault secret set \
        --vault-name "$TENANT_VAULT" \
        --name "$secret_name" \
        --value "$SECRET_VALUE" \
        --output none

      echo "    Done."
    fi
  else
    SKIP_COUNT=$((SKIP_COUNT + 1))
  fi
done

echo ""
echo "=== Migration Summary ==="
echo "Copied:  $MIGRATE_COUNT secrets"
echo "Skipped: $SKIP_COUNT secrets (platform-only)"
echo ""

if [ "$DRY_RUN" = true ]; then
  echo "This was a dry run. Run without --dry-run to execute."
else
  echo "Secrets copied successfully. Source secrets NOT deleted."
  echo ""
  echo "Next steps (D-18 ordering):"
  echo "  1. Update TENANT_KEY_VAULT_NAME in configmap to: $TENANT_VAULT"
  echo "  2. Restart tenant pods: kubectl rollout restart deployment -n tenant-*"
  echo "  3. Verify tenant API calls succeed"
  echo "  4. Manually remove migrated secrets from $PLATFORM_VAULT"
fi
