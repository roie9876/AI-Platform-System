---
phase: 22
slug: ci-cd-pipelines-github-actions
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | N/A — GitHub Actions YAML, declarative |
| **Config file** | N/A |
| **Quick run command** | `yamllint .github/workflows/*.yml` (if yamllint installed) |
| **Full suite command** | N/A |
| **Estimated runtime** | N/A |

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 22-01-01 | 01 | 1 | DEPLOY-01 | artifact | `ls .github/workflows/build-push.yml` | ✅ | ✅ green |
| 22-01-01 | 01 | 1 | DEPLOY-02 | artifact | `grep -c 'github.sha' .github/workflows/build-push.yml` | ✅ | ✅ green |
| 22-01-01 | 01 | 1 | DEPLOY-06 | artifact | `ls k8s/base/secrets/secret-provider-class.yaml` | ✅ | ✅ green |
| 22-02-01 | 02 | 2 | DEPLOY-03 | artifact | `ls .github/workflows/deploy.yml` | ✅ | ✅ green |
| 22-02-01 | 02 | 2 | DEPLOY-04 | artifact | `grep -c 'rollout' .github/workflows/deploy.yml` | ✅ | ✅ green |
| 22-02-01 | 02 | 2 | DEPLOY-05 | artifact | `ls k8s/scripts/smoke-test.sh` | ✅ | ✅ green |
| 22-02-01 | 02 | 2 | DEPLOY-07 | artifact | `grep -c 'frontend' .github/workflows/deploy.yml` | ✅ | ✅ green |
| 22-02-01 | 02 | 2 | DEPLOY-08 | artifact | `ls .github/workflows/deploy-tenant.yml` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Build-push workflow executes | DEPLOY-01 | GitHub Actions runner required | Push to main, verify workflow run in GitHub Actions tab |
| Deploy workflow deploys to AKS | DEPLOY-03 | AKS cluster + GitHub OIDC required | Trigger deploy workflow, verify pods updated |
| Rolling update zero-downtime | DEPLOY-04 | AKS cluster required | Deploy during load test, verify no 5xx |
| Smoke tests pass after deploy | DEPLOY-05 | AKS cluster required | Check smoke-test step in deploy workflow run |
| Frontend deployment | DEPLOY-07 | AKS cluster required | Verify frontend pod running after deploy |
| Per-tenant deploy | DEPLOY-08 | AKS cluster required | Trigger deploy-tenant workflow for specific namespace |

*Note: All DEPLOY requirements are artifact-verified (files exist with correct content). Runtime verification requires deployed infrastructure.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Wave 0 covers all MISSING references
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending — artifact-verified only, runtime testing blocked by deployment
