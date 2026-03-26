---
phase: 21-tenant-lifecycle-provisioning
plan: 02
subsystem: api
tags: [kubernetes, provisioning, seeding, middleware, tenant-isolation]

requires:
  - phase: 21-tenant-lifecycle-provisioning
    plan: 01
    provides: TenantService with lifecycle state machine and tenant API
  - phase: 20-microservice-extraction-aks-deployment
    provides: K8s tenant template and setup-tenant.sh script

provides:
  - TenantProvisioningService orchestrating K8s + seeding + admin user creation
  - Enhanced TenantMiddleware blocking suspended/deactivated/deleted tenants
  - Auto-transition from provisioning → active after successful provisioning
  - In-memory tenant status cache (60s TTL) for middleware performance

affects: [22-ci-cd, 23-observability, 24-tenant-admin-ui]

tech-stack:
  added: []
  patterns: [async-subprocess-exec, middleware-status-cache, seed-data-pattern]

key-files:
  created:
    - backend/app/services/tenant_provisioning.py
  modified:
    - backend/app/middleware/tenant.py

key-decisions:
  - "K8s provisioning via subprocess to existing setup-tenant.sh — reuse Phase 20 script"
  - "Provisioning failure leaves tenant in 'provisioning' state for manual retry"
  - "60-second TTL cache for tenant status in middleware — acceptable latency for suspension enforcement"
  - "Platform admin /tenants endpoints bypass tenant status check"
  - "Seed data uses existing repositories (ToolRepository, CatalogEntryRepository, UserRepository)"

patterns-established:
  - "Provisioning pipeline: DB record → K8s namespace → seed data → admin user → activate"
  - "Middleware status check: cache-first → Cosmos DB fallback → response mapping"
  - "Status response mapping: dict of status → (code, detail) for clean error handling"

requirements-completed: [TENANT-02, TENANT-04, TENANT-06, TENANT-07]

duration: 5min
completed: 2026-03-26
---

# Plan 21-02: Provisioning, Seeding & Middleware Summary

**End-to-end tenant provisioning pipeline with K8s namespace, seed data, admin user, and middleware-level suspension blocking.**

## Performance

- **Duration:** 5 min
- **Tasks:** 2/2 completed
- **Files created:** 1
- **Files modified:** 1

## Accomplishments
- Created TenantProvisioningService orchestrating full provisioning pipeline (K8s → seed → admin → activate)
- K8s namespace provisioning via asyncio.create_subprocess_exec calling existing setup-tenant.sh
- Default data seeding: 2 built-in tools (web_search, code_interpreter) + 1 catalog template
- Admin user auto-creation with email mapping and duplicate check
- Enhanced TenantMiddleware to block suspended/deactivated/deleted/provisioning tenants
- Added 60-second TTL in-memory cache for tenant status to avoid per-request Cosmos queries
- Platform admin /tenants endpoints bypass tenant status check

## Task Commits

1. **Task 1: Create TenantProvisioningService** — `064977e` (feat)
2. **Task 2: Enhance TenantMiddleware** — `064977e` (feat)

## Files Created/Modified
- `backend/app/services/tenant_provisioning.py` — Full provisioning pipeline: K8s namespace + seed data + admin user + state transition
- `backend/app/middleware/tenant.py` — Added tenant status check with cache, blocks non-active tenants, bypasses /tenants endpoints

## Decisions Made
None beyond plan — followed specification exactly.

## Deviations from Plan
None.

## Issues Encountered
None.

## User Setup Required
None.

## Next Phase Readiness
- Full tenant lifecycle operational for Phase 22 (CI/CD) and Phase 23 (Observability)
- Tenant API ready for Phase 24 (Tenant Admin UI) to build wizard on top of

---
*Phase: 21-tenant-lifecycle-provisioning*
*Completed: 2026-03-26*
