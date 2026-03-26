---
phase: 22-ci-cd-pipelines-github-actions
plan: 02
subsystem: infra
tags: [github-actions, aks, kustomize, deploy, smoke-tests, tenant-deploy]
provides:
  - AKS deploy workflow triggered after build-push
  - Rolling update with Kustomize image override
  - Smoke test script for post-deploy health verification
  - Per-tenant namespace deployment workflow
  - Frontend deployment to separate frontend/ directory
affects: []
requirements-completed: [DEPLOY-03, DEPLOY-04, DEPLOY-05, DEPLOY-07, DEPLOY-08]
duration: 5min
completed: 2026-03-26
---

# Plan 22-02: Deploy Pipeline, Smoke Tests & Tenant Deploy Summary

**AKS deployment workflow with Kustomize image overrides, rollout monitoring, automated smoke tests, frontend deploy, and per-tenant namespace deployment workflow.**

## Commits
- `9dd9f9a` — feat(22-02): deploy workflow, smoke tests, and tenant deploy

## Files Created
- `.github/workflows/deploy.yml` — Deploy to AKS after build-push, Kustomize overlay, rollout wait, smoke tests, frontend job
- `.github/workflows/deploy-tenant.yml` — Per-tenant namespace deployment via workflow_dispatch
- `k8s/scripts/smoke-test.sh` — Post-deploy health checks for all 5 services (healthz + readyz)

---
*Phase: 22-ci-cd-pipelines-github-actions*
*Completed: 2026-03-26*
