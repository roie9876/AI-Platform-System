---
status: passed
phase: 22-ci-cd-pipelines-github-actions
verified: 2026-03-26
---

# Phase 22: CI/CD Pipelines (GitHub Actions) — Verification

## Must-Have Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Build-push workflow exists with matrix for 5+1 services | ✓ PASS | `matrix:` strategy at line 25 covering 5 services + frontend |
| 2 | OIDC auth used (no service principal secrets) | ✓ PASS | `azure/login@v2` at lines 37, 66 in build-push.yml |
| 3 | Images tagged with git SHA | ✓ PASS | `-t "${IMAGE}:${{ github.sha }}"` at line 52 |
| 4 | Deploy workflow triggers after build-push | ✓ PASS | `workflow_run:` trigger at line 4 in deploy.yml |
| 5 | Kustomize used for deployment | ✓ PASS | `kustomize edit set image` at line 68 in deploy.yml |
| 6 | Rolling update with rollout status | ✓ PASS | `kubectl rollout status deployment` at line 80 |
| 7 | Smoke tests run post-deploy | ✓ PASS | "Run smoke tests" step at line 83 in deploy.yml |
| 8 | Key Vault CSI SecretProviderClass exists | ✓ PASS | `k8s/base/secrets/secret-provider-class.yaml` exists |
| 9 | Per-tenant deploy workflow exists | ✓ PASS | `.github/workflows/deploy-tenant.yml` exists |
| 10 | Frontend deploy job exists | ✓ PASS | `deploy-frontend:` job at line 87 in deploy.yml |

## Requirement Coverage

| Requirement | Description | Plan | Status |
|-------------|-------------|------|--------|
| DEPLOY-01 | GitHub Actions builds Docker images on push to main | 22-01 | ✓ PASS — build-push.yml with matrix build on push to main |
| DEPLOY-02 | Images tagged with git SHA, pushed to ACR | 22-01 | ✓ PASS — `${{ github.sha }}` tag, ACR login server |
| DEPLOY-03 | Deploy to AKS using Kustomize | 22-02 | ✓ PASS — `kustomize edit set image` in deploy.yml |
| DEPLOY-04 | Rolling update ensures zero-downtime | 22-02 | ✓ PASS — `kubectl rollout status` with 300s timeout |
| DEPLOY-05 | Smoke tests after deploy | 22-02 | ✓ PASS — smoke-test.sh called post-deploy |
| DEPLOY-06 | Secrets via Key Vault CSI driver | 22-01 | ✓ PASS — SecretProviderClass maps 4 Key Vault secrets |
| DEPLOY-07 | Frontend deployed | 22-02 | ✓ PASS — deploy-frontend job in deploy.yml |
| DEPLOY-08 | Per-tenant namespace deploy support | 22-02 | ✓ PASS — deploy-tenant.yml with workflow_dispatch |

## Artifacts

| File | Exists | Purpose |
|------|--------|---------|
| .github/workflows/build-push.yml | ✓ | Matrix build for 5 services + frontend |
| .github/workflows/deploy.yml | ✓ | AKS deploy with Kustomize, rollouts, smoke tests |
| .github/workflows/deploy-tenant.yml | ✓ | Per-tenant namespace deployment |
| k8s/base/secrets/secret-provider-class.yaml | ✓ | Key Vault CSI SecretProviderClass |
| k8s/scripts/smoke-test.sh | ✓ | Post-deploy health verification |

## Key Links

| From | To | Via | Status |
|------|----|-----|--------|
| build-push.yml | ACR | docker push with OIDC auth | ✓ Wired |
| deploy.yml | build-push.yml | workflow_run trigger | ✓ Wired |
| deploy.yml | k8s/base/ | kustomize edit set image | ✓ Wired |
| deploy.yml | smoke-test.sh | Run smoke tests step | ✓ Wired |
| secret-provider-class.yaml | Key Vault | CSI driver mapping | ✓ Wired |

## Result

**PASSED** — All 8 DEPLOY requirements covered, all 10 must-have truths verified, all artifacts exist, all key links wired correctly.
