---
phase: 18-authentication-migration-entra-id
plan: 01
subsystem: auth
tags: [entra-id, jwt, rbac, azure, bearer-token]

requires:
  - phase: 17-infrastructure-foundation-bicep-iac
    provides: Workload Identity and identity.bicep for Managed Identity

provides:
  - Entra ID JWT token validation with JWKS
  - RBAC dependency system (require_role, require_any_role)
  - get_current_user returns dict from token claims
  - TenantMiddleware reads Bearer Authorization header
  - DefaultAzureCredential helper for service-to-service auth
  - All 19 API route files migrated to Entra ID auth

affects: [18-02-frontend-msal, 19-data-layer-migration, 20-microservice-extraction]

tech-stack:
  added: [python-jose, azure-identity]
  patterns: [Bearer token auth, JWKS validation, role-based dependencies]

key-files:
  created:
    - backend/app/api/v1/dependencies.py
    - backend/tests/test_entra_auth.py
  modified:
    - backend/app/core/security.py
    - backend/app/core/config.py
    - backend/app/middleware/tenant.py
    - backend/app/api/v1/auth.py
    - backend/app/api/v1/agents.py
    - backend/app/api/v1/agent_mcp_tools.py
    - backend/app/api/v1/ai_services.py
    - backend/app/api/v1/azure_connections.py
    - backend/app/api/v1/azure_subscriptions.py
    - backend/app/api/v1/catalog.py
    - backend/app/api/v1/chat.py
    - backend/app/api/v1/data_sources.py
    - backend/app/api/v1/evaluations.py
    - backend/app/api/v1/knowledge.py
    - backend/app/api/v1/marketplace.py
    - backend/app/api/v1/mcp_discovery.py
    - backend/app/api/v1/mcp_servers.py
    - backend/app/api/v1/memories.py
    - backend/app/api/v1/model_endpoints.py
    - backend/app/api/v1/observability.py
    - backend/app/api/v1/threads.py
    - backend/app/api/v1/tools.py
    - backend/app/api/v1/workflows.py
    - backend/requirements.txt

key-decisions:
  - "Used python-jose for JWKS JWT validation (RS256) replacing PyJWT (HS256)"
  - "current_user is dict from token claims, not SQLAlchemy User model"
  - "Kept hash_password/verify_password deprecated for migration compat"
  - "DefaultAzureCredential singleton for service-to-service auth"

patterns-established:
  - "Bearer token auth: TenantMiddleware extracts from Authorization header, validates via JWKS"
  - "RBAC via dependencies: require_role/require_any_role as FastAPI Depends"
  - "User context as dict: {user_id, tenant_id, email, name, roles} from token claims"
  - "JWKS cache: 24h TTL, lazy fetch on first request"

requirements-completed: [AUTH-02, AUTH-03, AUTH-04, AUTH-06, AUTH-07]

duration: 12min
completed: 2026-03-26
---

# Phase 18 Plan 01: Backend Entra ID Token Validation and Route Migration

**Replaced cookie-based HS256 JWT auth with Entra ID RS256 JWKS validation, created RBAC dependency system, and migrated all 21 API route files to Bearer token auth.**

## What Was Built

1. **Entra ID token validation** (`security.py`): `validate_entra_token()` fetches JWKS keys, validates RS256 signatures, checks issuer/audience/expiry. `extract_user_context()` maps claims to user dict.

2. **RBAC dependencies** (`dependencies.py`): `get_current_user()` reads `request.state.user_context` (set by middleware). `require_role(role)` and `require_any_role(*roles)` enforce role checks. Four role constants defined.

3. **Middleware migration** (`tenant.py`): Reads `Authorization: Bearer {token}` header instead of cookies. Calls `validate_entra_token` + `extract_user_context`, sets both `user_context` dict and backward-compat `user_id`/`tenant_id` on request state.

4. **Auth endpoint cleanup** (`auth.py`): Removed register, login, refresh, logout endpoints. Kept `/me` returning user context from token claims.

5. **Route migration**: All 19 consumer files changed `from app.api.v1.auth import get_current_user` → `from app.api.v1.dependencies import get_current_user`, `User` type → `dict`, `.id` → `["user_id"]`, `.tenant_id` → `["tenant_id"]`.

6. **Managed Identity** (`security.py`): `get_azure_credential()` singleton returns `DefaultAzureCredential`. `get_service_token(scope)` acquires tokens for downstream Azure services.

## Verification

- 8/8 tests pass (`test_entra_auth.py`): token rejection (wrong issuer, expired), claim extraction (tenant_id, roles), RBAC checks (allow/deny), get_current_user (success/401)
- `from app.main import app` loads without errors
- Zero files contain old `from app.api.v1.auth import get_current_user` import

## Self-Check: PASSED
