---
phase: 03-agent-core-model-abstraction
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, alembic, pydantic, fernet, crud]

requires:
  - phase: 01-foundation
    provides: Base model mixins (UUIDMixin, TimestampMixin), auth system, tenant middleware, database config

provides:
  - Agent CRUD API at /api/v1/agents with create, list, get, update, delete
  - ModelEndpoint CRUD API at /api/v1/model-endpoints with encrypted API key storage
  - AgentConfigVersion auto-tracking on create/update/rollback
  - Agent, ModelEndpoint, AgentConfigVersion SQLAlchemy models
  - Alembic migration 002 for all three tables
  - Pydantic request/response schemas for all entities

affects: [03-02, 03-03, 03-04, 04-tools-data-rag]

tech-stack:
  added: [cryptography==44.0.0]
  patterns: [fernet-encryption-for-api-keys, config-version-snapshots, tenant-scoped-crud]

key-files:
  created:
    - backend/app/models/agent.py
    - backend/app/models/model_endpoint.py
    - backend/app/models/agent_config_version.py
    - backend/alembic/versions/002_agent_model_endpoint_schema.py
    - backend/app/api/v1/agents.py
    - backend/app/api/v1/model_endpoints.py
  modified:
    - backend/app/models/__init__.py
    - backend/app/core/config.py
    - backend/app/api/v1/schemas.py
    - backend/app/api/v1/router.py
    - backend/requirements.txt

key-decisions:
  - "Fernet symmetric encryption for API keys in PoC (production uses Azure Key Vault per D-07)"
  - "Hard delete for agents with CASCADE to config versions (PoC simplicity)"
  - "Config snapshots store system_prompt, temperature, max_tokens, timeout_seconds, model_endpoint_id"
  - "Python 3.9 compatibility: must use Optional[X] and List[X] from typing, not str | None or list[X]"

patterns-established:
  - "CRUD router pattern: APIRouter with get_current_user + get_tenant_id dependencies on every endpoint"
  - "Config versioning: auto-create AgentConfigVersion on create/update/rollback with _build_config_snapshot helper"
  - "API key security: encrypt on write, never expose in responses (ModelEndpointResponse omits api_key)"
  - "Validation pattern: check provider_type and auth_type against VALID_* sets in schemas.py"

requirements-completed: [AGNT-01, AGNT-02, AGNT-03, MODL-01]

duration: 45min
completed: 2026-03-23
---

# Plan 03-01: Backend Models + CRUD APIs Summary

**Agent, ModelEndpoint, and AgentConfigVersion models with full CRUD APIs, Fernet-encrypted API key storage, and automatic config versioning**

## Performance

- **Duration:** ~45 min
- **Tasks:** 2 completed
- **Files created:** 6
- **Files modified:** 5

## Accomplishments

- Created Agent model (name, description, system_prompt, status, temperature, max_tokens, timeout_seconds, tenant_id, model_endpoint_id)
- Created ModelEndpoint model (name, provider_type, endpoint_url, model_name, api_key_encrypted, auth_type, is_active, priority, tenant_id)
- Created AgentConfigVersion model (agent_id, version_number, config_snapshot JSON, change_description, tenant_id) with unique constraint on (agent_id, version_number)
- Alembic migration 002 creates model_endpoints → agents → agent_config_versions tables
- Agent CRUD endpoints: POST, GET list, GET by ID, PUT, DELETE — all tenant-scoped
- Agent versioning endpoints: GET /{id}/versions (history), POST /{id}/rollback/{version} (restore snapshot)
- ModelEndpoint CRUD endpoints: POST, GET list, GET by ID, PUT, DELETE — all tenant-scoped
- Fernet encryption for API keys using SHA-256 key derivation from ENCRYPTION_KEY config setting
- API keys never exposed in any API response

## Files Created/Modified

- `backend/app/models/agent.py` — Agent SQLAlchemy model with UUIDMixin, TimestampMixin
- `backend/app/models/model_endpoint.py` — ModelEndpoint model with encrypted API key field
- `backend/app/models/agent_config_version.py` — Config version tracking with JSON snapshots
- `backend/alembic/versions/002_agent_model_endpoint_schema.py` — Migration for 3 new tables
- `backend/app/api/v1/agents.py` — Agent CRUD router (7 endpoints including versioning/rollback)
- `backend/app/api/v1/model_endpoints.py` — ModelEndpoint CRUD router (5 endpoints) with Fernet encryption
- `backend/app/models/__init__.py` — Added new model imports
- `backend/app/core/config.py` — Added ENCRYPTION_KEY setting
- `backend/app/api/v1/schemas.py` — Agent, ModelEndpoint, AgentConfigVersion, Chat Pydantic schemas
- `backend/app/api/v1/router.py` — Registered agents + model-endpoints routers
- `backend/requirements.txt` — Added cryptography==44.0.0

## Decisions Made

- Used `Optional[X]` / `List[X]` from typing instead of `X | None` / `list[X]` for Python 3.9 compatibility (Pydantic evaluates annotations at runtime, so `from __future__ import annotations` doesn't work)
- Fernet encryption derives key from ENCRYPTION_KEY via SHA-256 → base64, not raw Fernet key format
- Agent rollback creates a NEW config version (doesn't revert version_number), maintaining full audit trail

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Blocking] Python 3.9 type annotation compatibility**
- **Found during:** Task 2 (Pydantic schemas)
- **Issue:** `str | None` union syntax requires Python 3.10+. Active interpreter is Python 3.9.21.
- **Fix:** Replaced all union types with `Optional[str]`, `Optional[UUID]`, `Optional[float]`, `Optional[int]`, `List[X]`, `Optional[List[X]]` from typing across schemas.py
- **Files modified:** backend/app/api/v1/schemas.py
- **Verification:** All three module imports pass
- **Committed in:** 6a812d7

---

**Total deviations:** 1 auto-fixed (blocking)
**Impact on plan:** No scope change, syntax adjustment only.

## Next Phase Readiness

- Agent + ModelEndpoint CRUD APIs ready for frontend consumption (Plan 03-03)
- Models and schemas ready for model abstraction service (Plan 03-02)
- All future backend code must use `Optional[X]` syntax for Python 3.9

---
*Plan: 03-01 of phase 03-agent-core-model-abstraction*
*Completed: 2026-03-23*
