# Plan 28-03 Summary: Key Vault Separation Wiring + Migration

## Status: Complete

## Changes Made

### Task 1: Backend TENANT_KEY_VAULT_NAME + SecretProviderClass Update + Tests
- **Modified** `backend/app/services/openclaw_service.py`:
  - Added `TENANT_KEY_VAULT_NAME = os.getenv("TENANT_KEY_VAULT_NAME", KEY_VAULT_NAME)` with fallback
  - Changed `_build_secret_provider_class()` to use `TENANT_KEY_VAULT_NAME` instead of `KEY_VAULT_NAME` for per-tenant SecretProviderClass keyvaultName
- **Created** `backend/tests/test_keyvault_separation.py`: 4 unit tests
  - `test_tenant_keyvault_uses_env_when_set` — explicit env var wins
  - `test_tenant_keyvault_falls_back_to_platform` — fallback to KEY_VAULT_NAME
  - `test_tenant_keyvault_empty_when_neither_set` — both empty
  - `test_spc_uses_tenant_keyvault_name` — SPC references tenant vault

### Task 2: Tenant Secret Migration Script
- **Created** `scripts/migrate-tenant-secrets.sh`:
  - Copies tenant-specific secrets (azure-openai-api-key, TELEGRAMBOTTOKEN, etc.) from platform vault to tenant vault
  - Supports `--dry-run` for safe preview and `--env` for environment selection
  - Does NOT delete source secrets (D-18 safe rollout ordering)
  - Prints next steps after migration (configmap update, pod restart, verification, cleanup)

## Verification
- All 4 unit tests pass: `pytest tests/test_keyvault_separation.py -v` (75 tests total in suite, 0 regressions)
- Migration script exists, executable, contains expected patterns
- grep confirms TENANT_KEY_VAULT_NAME in openclaw_service.py

## Requirements Covered
- AUDIT-05: Tenant pods reference tenant-only Key Vault via TENANT_KEY_VAULT_NAME
- AUDIT-06: Migration script provides safe rollout path for existing secrets
