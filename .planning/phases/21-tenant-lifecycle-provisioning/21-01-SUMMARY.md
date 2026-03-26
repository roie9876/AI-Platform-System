---
phase: 21-tenant-lifecycle-provisioning
plan: 01
subsystem: api
tags: [fastapi, cosmos-db, tenant-management, lifecycle-state-machine]

requires:
  - phase: 19-data-layer-migration-cosmos-db
    provides: Cosmos DB repositories and client singleton
  - phase: 18-authentication-migration-entra-id
    provides: Entra ID auth middleware with user context

provides:
  - TenantService with lifecycle state machine (5 states, validated transitions)
  - TenantRepository with cross-partition list and status queries
  - REST API endpoints for tenant CRUD, lifecycle transitions, and settings management
  - Tenant Pydantic schemas (create, update, settings, state transition, response)
  - Platform admin role enforcement on all tenant endpoints

affects: [21-02, 24-tenant-admin-ui]

tech-stack:
  added: []
  patterns: [lifecycle-state-machine, platform-admin-role-check, self-partitioned-cosmos-doc]

key-files:
  created:
    - backend/app/services/tenant_service.py
    - backend/app/api/v1/tenants.py
  modified:
    - backend/app/repositories/tenant_repo.py
    - backend/app/api/v1/schemas.py
    - backend/app/api/v1/router.py

key-decisions:
  - "Tenants are self-partitioned in Cosmos DB — tenant_id equals the document id"
  - "Lifecycle state machine enforced in service layer, not at DB level"
  - "Soft delete — 'deleted' is a state, records remain in DB"
  - "Platform admin role check as a helper function, not a FastAPI dependency (simpler)"
  - "Settings stored as nested dict in tenant document, not separate container"

patterns-established:
  - "Lifecycle state machine: VALID_TRANSITIONS dict mapping current → allowed next states"
  - "Platform admin endpoints: _require_platform_admin(request) at top of each handler"
  - "Cross-partition queries: enable_cross_partition_query=True for admin operations"

requirements-completed: [TENANT-01, TENANT-03, TENANT-05]

duration: 5min
completed: 2026-03-26
---

# Plan 21-01: Tenant Model, Service & API Summary

**Tenant management API with lifecycle state machine, per-tenant settings, and platform admin authorization.**

## Performance

- **Duration:** 5 min
- **Tasks:** 2/2 completed
- **Files created:** 2
- **Files modified:** 3

## Accomplishments
- Enhanced TenantRepository with cross-partition list_all_tenants() and get_by_status() queries for admin operations
- Created TenantService with 5-state lifecycle machine (provisioning → active → suspended → deactivated → deleted) and validated transitions
- Built complete REST API at /api/v1/tenants with CRUD, state transitions, and settings management
- Added Pydantic schemas with slug validation (lowercase alphanumeric + hyphens) and state pattern enforcement
- All endpoints protected by platform_admin role check

## Task Commits

1. **Task 1: Enhance TenantRepository and create TenantService** — `96f8c34` (feat)
2. **Task 2: Create Tenant API endpoints and schemas** — `96f8c34` (feat)

## Files Created/Modified
- `backend/app/services/tenant_service.py` — TenantService with lifecycle state machine, CRUD, settings management
- `backend/app/api/v1/tenants.py` — REST endpoints: POST, GET, PATCH, DELETE, /state, /settings
- `backend/app/repositories/tenant_repo.py` — Added list_all_tenants() and get_by_status() cross-partition queries
- `backend/app/api/v1/schemas.py` — Tenant schemas: create, update, settings, state transition, response
- `backend/app/api/v1/router.py` — Wired tenants_router at /tenants prefix

## Decisions Made
None beyond plan — followed specification exactly.

## Deviations from Plan
None.

## Issues Encountered
None.

## User Setup Required
None.

## Next Phase Readiness
- TenantService ready for Plan 21-02 to add provisioning integration
- API endpoints ready for Plan 24 (Tenant Admin UI) to consume

---
*Phase: 21-tenant-lifecycle-provisioning*
*Completed: 2026-03-26*
