---
phase: 18-authentication-migration-entra-id
plan: 03
subsystem: auth
tags: [managed-identity, azure-identity, defaultazurecredential]

requires:
  - phase: 18-authentication-migration-entra-id
    provides: azure-identity already in requirements.txt (Plan 01)

provides:
  - DefaultAzureCredential singleton for service-to-service auth
  - get_service_token helper for downstream Azure services

affects: [19-data-layer-migration, 20-microservice-extraction]

tech-stack:
  added: []
  patterns: [DefaultAzureCredential singleton, get_service_token]

key-files:
  created:
    - backend/tests/test_managed_identity.py
  modified:
    - backend/app/core/security.py

key-decisions:
  - "Singleton pattern for credential to prevent object proliferation"
  - "get_service_token as async helper for any Azure service scope"

patterns-established:
  - "Service auth: get_azure_credential() singleton, get_service_token(scope) for tokens"

requirements-completed: [AUTH-06]

duration: 3min
completed: 2026-03-26
---

# Phase 18 Plan 03: Managed Identity Support

**Added DefaultAzureCredential helper and get_service_token for service-to-service authentication — works locally via Azure CLI and on AKS via Workload Identity.**

## What Was Built

1. **Credential singleton** (`security.py`): `get_azure_credential()` returns a shared `DefaultAzureCredential` instance. Works with Azure CLI locally and Workload Identity on AKS.

2. **Token helper** (`security.py`): `get_service_token(scope)` acquires tokens for any downstream Azure service (Cosmos DB, Key Vault, etc.) using the credential.

3. **Tests** (`test_managed_identity.py`): 3 tests verify singleton behavior and token acquisition with mocked credential.

## Verification

- 3/3 tests pass (`test_managed_identity.py`)
- `from app.core.security import get_azure_credential, get_service_token` imports without error

## Self-Check: PASSED
