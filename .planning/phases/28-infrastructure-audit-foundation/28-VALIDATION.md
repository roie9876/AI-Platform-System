---
phase: 28
slug: infrastructure-audit-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 28 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (asyncio_mode=auto) |
| **Config file** | `backend/pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `cd backend && python -m pytest tests/ -x --timeout=30` |
| **Full suite command** | `cd backend && python -m pytest tests/ --timeout=60` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x --timeout=30`
- **After every plan wave:** Run full pytest suite + `k8s/scripts/smoke-test.sh aiplatform`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds
- **Phase gate:** `azd up` succeeds on test environment + smoke-test.sh passes + `kubectl diff` shows no drift

---

## Per-Task Verification Map

| Req ID | Requirement | Test Type | Automated Command | File Exists | Status |
|--------|-------------|-----------|-------------------|-------------|--------|
| AUDIT-01 | Provision-from-zero produces working platform | e2e/smoke | `k8s/scripts/smoke-test.sh aiplatform --extended` | ✅ (needs namespace fix) | ⬜ pending |
| AUDIT-02 | Bicep templates match deployed resources | e2e | `az deployment group what-if --resource-group $RG --template-file infra/main.bicep --parameters infra/parameters/prod.bicepparam` | N/A (Azure CLI) | ⬜ pending |
| AUDIT-03 | K8s manifests match running workloads | e2e | `kubectl diff -k k8s/base/ --namespace aiplatform` | N/A (kubectl) | ⬜ pending |
| AUDIT-04 | Wildcard DNS resolves + TLS cert issued | e2e/smoke | `curl -s https://test.agents.${AGENTS_DOMAIN}/ -o /dev/null -w '%{http_code}'` + `kubectl get certificate -n cert-manager` | ❌ Wave 0 | ⬜ pending |
| AUDIT-05 | Platform and tenant secrets in separate vaults | unit | `python -m pytest tests/test_keyvault_separation.py -x` | ❌ Wave 0 | ⬜ pending |
| AUDIT-06 | Tenant secrets migrated with zero downtime | manual | Migration script execution + pod health check | N/A (operational) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_keyvault_separation.py` — unit tests for TENANT_KEY_VAULT_NAME fallback logic (AUDIT-05)
- [ ] DNS/TLS validation script in `hooks/` or `k8s/scripts/` (AUDIT-04)
- [ ] Smoke test namespace fix (`k8s/scripts/smoke-test.sh` → default `aiplatform`) must happen before any validation (AUDIT-01, AUDIT-03)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tenant secrets migrated with zero downtime | AUDIT-06 | Operational procedure requiring production access, pod health monitoring during rollout | 1. Run `scripts/migrate-tenant-secrets.sh` 2. Monitor pod restarts via `kubectl get pods -w` 3. Verify tenant API calls succeed during migration 4. Confirm old secrets can be removed |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
