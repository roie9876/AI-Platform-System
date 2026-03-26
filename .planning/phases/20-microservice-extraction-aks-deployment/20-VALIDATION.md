---
phase: 20
slug: microservice-extraction-aks-deployment
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | backend/pyproject.toml |
| **Quick run command** | `cd backend && python -m pytest tests/test_health_endpoints.py -x` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 20-01-01 | 01 | 1 | COMPUTE-07 | unit | `pytest tests/test_health_endpoints.py` | ❌ W0 | ⬜ pending |
| 20-01-01 | 01 | 1 | COMPUTE-08 | artifact | `ls backend/microservices/*/main.py` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_health_endpoints.py` — stubs for COMPUTE-07

*Covered by Phase 25 Plan 25-03 (tests).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dedicated K8s namespace per tenant | COMPUTE-01 | AKS cluster required | Run `setup-tenant.sh`, verify namespace created with `kubectl get ns` |
| NetworkPolicy blocks cross-namespace | COMPUTE-02 | AKS cluster required | Deploy 2 tenant namespaces, test cross-namespace curl fails |
| ResourceQuota limits per tenant | COMPUTE-03 | AKS cluster required | Deploy tenant, verify `kubectl describe quota` shows limits |
| LimitRange per container | COMPUTE-04 | AKS cluster required | Deploy pod without requests, verify defaults applied |
| Kustomize overlays generate manifests | COMPUTE-05 | K8s tooling | `kustomize build k8s/overlays/tenant-template/` succeeds |
| HPA scales on CPU/memory | COMPUTE-06 | AKS cluster required | Load test, observe HPA scaling |
| Ingress routes to tenant | COMPUTE-09 | AKS + ingress controller | Deploy ingress, verify path routing |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Wave 0 covers all MISSING references
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
