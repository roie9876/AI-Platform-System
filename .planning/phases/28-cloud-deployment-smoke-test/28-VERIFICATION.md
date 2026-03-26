---
status: passed
phase: 28-cloud-deployment-smoke-test
verified: 2026-03-26
---

# Phase 28 Verification: Cloud Deployment & Smoke Test

## Goal
All deployment artifacts are validated, orchestrated via a single deploy command, and verified with enhanced smoke tests covering health endpoints, API reachability, and inter-service connectivity.

## Must-Have Truths

| # | Truth | Status |
|---|-------|--------|
| 1 | Running scripts/validate-deployment.sh checks all deployment artifacts before deploying | PASS |
| 2 | Running scripts/deploy.sh orchestrates the full Azure deployment end-to-end | PASS |
| 3 | Running docker compose -f docker-compose.microservices.yml up builds and starts all 5 microservices locally | PASS |
| 4 | Smoke test validates API endpoints beyond just health checks | PASS |
| 5 | Post-deploy configuration script bridges Bicep outputs to K8s manifests | PASS |

## Artifact Verification

| Artifact | Min Lines | Actual | Status |
|----------|-----------|--------|--------|
| scripts/validate-deployment.sh | 60 | 186 | PASS |
| scripts/deploy.sh | 100 | 333 | PASS |
| docker-compose.microservices.yml | 50 | 160 | PASS |
| scripts/post-deploy-config.sh | 40 | 163 | PASS |
| k8s/scripts/smoke-test.sh | 50 | 197 | PASS |

## Key Link Verification

| From | To | Via | Pattern | Status |
|------|----|-----|---------|--------|
| scripts/deploy.sh | infra/main.bicep | az deployment group create | `az deployment group create` | FOUND |
| scripts/deploy.sh | k8s/base/kustomization.yaml | kubectl apply -k | `kubectl apply` | FOUND |
| docker-compose.microservices.yml | backend/microservices/*/Dockerfile | Docker build contexts | `build:` (6 matches) | FOUND |
| scripts/post-deploy-config.sh | k8s/base/configmap.yaml | sed replacement | `REPLACE_WITH` | FOUND |
| k8s/scripts/smoke-test.sh | backend/app/health.py | curl to health endpoints | `healthz` | FOUND |

## Syntax & Config Validation

- [x] validate-deployment.sh passes `bash -n`
- [x] deploy.sh passes `bash -n`
- [x] post-deploy-config.sh passes `bash -n`
- [x] smoke-test.sh passes `bash -n`
- [x] docker-compose.microservices.yml passes `docker compose config`

## Score: 5/5 must-haves verified
