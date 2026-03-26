---
phase: 19
slug: data-layer-migration-cosmos-db
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | backend/pyproject.toml |
| **Quick run command** | `cd backend && python -m pytest tests/test_cosmos_repositories.py tests/test_data_migration.py -x` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | DATA-01 | unit | `pytest tests/test_cosmos_repositories.py -k "test_create"` | ❌ W0 | ⬜ pending |
| 19-01-01 | 01 | 1 | DATA-02 | unit | `pytest tests/test_cosmos_repositories.py -k "test_tenant_isolation"` | ❌ W0 | ⬜ pending |
| 19-01-01 | 01 | 1 | DATA-06 | infra | `az bicep build --file infra/modules/cosmos.bicep` | ❌ W0 | ⬜ pending |
| 19-01-01 | 01 | 1 | DATA-07 | unit | `pytest tests/test_cosmos_repositories.py -k "test_etag"` | ❌ W0 | ⬜ pending |
| 19-02-01 | 02 | 1 | DATA-04 | unit | `pytest tests/test_cosmos_repositories.py -k "test_registry"` | ❌ W0 | ⬜ pending |
| 19-02-01 | 02 | 1 | DATA-03 | unit | `pytest tests/test_cosmos_repositories.py -k "test_cross_partition"` | ❌ W0 | ⬜ pending |
| 19-03-01 | 03 | 2 | DATA-05 | unit | `pytest tests/test_data_migration.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_cosmos_repositories.py` — stubs for DATA-01, DATA-02, DATA-03, DATA-04, DATA-07
- [ ] `backend/tests/test_data_migration.py` — stubs for DATA-05

*Covered by Phase 25 Plan 25-01 (fixtures) and Plan 25-02 (tests).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cosmos DB autoscale/serverless config | DATA-08 | IaC deployment required | Deploy with `az deployment group create`, verify account capabilities in portal |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
