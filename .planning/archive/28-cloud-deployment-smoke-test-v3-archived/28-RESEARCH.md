# Phase 28: Cloud Deployment & Smoke Test — Research

**Researched:** 2026-03-26
**Phase:** 28-cloud-deployment-smoke-test
**Discovery Level:** 1 (Quick Verification — all artifacts exist, validating deployment readiness)

## Phase Scope

Deploy the AI Agent Platform to Azure and verify end-to-end functionality. All infrastructure code (Bicep), Docker images, K8s manifests, CI/CD pipelines, and smoke tests were built in phases 17-27. This phase validates they work together as a cohesive deployment.

## What Already Exists

### Infrastructure (Phase 17)
- `infra/main.bicep` — Orchestrator deploying VNet, Log Analytics, Identity, Cosmos DB, ACR, AKS, Key Vault, App Insights, Alerts
- `infra/parameters/prod.bicepparam` — Production parameters (swedencentral, Standard_D4s_v5, K8s 1.33)
- 10 Bicep modules in `infra/modules/`

### Docker Images (Phase 20)
- 5 microservice Dockerfiles: `backend/microservices/{api-gateway,agent-executor,workflow-engine,tool-executor,mcp-proxy}/Dockerfile`
- 1 frontend Dockerfile: `frontend/Dockerfile`
- All use `python:3.12-slim`, have HEALTHCHECK directives

### K8s Manifests (Phase 20)
- `k8s/base/` — Kustomize base with deployments, services, ingress, configmap, secret-provider-class
- `k8s/overlays/tenant-template/` — Per-tenant overlay with namespace, NetworkPolicy, ResourceQuota, LimitRange, HPA
- `k8s/scripts/setup-tenant.sh` — Tenant provisioning script

### CI/CD (Phase 22)
- `.github/workflows/build-push.yml` — Matrix build for 5 microservices + frontend, pushes to ACR
- `.github/workflows/deploy.yml` — Deploys to AKS via Kustomize, runs smoke tests
- OIDC auth (no stored secrets for Azure login)

### Smoke Tests (Phase 22)
- `k8s/scripts/smoke-test.sh` — Checks healthz + readyz for all 5 microservices

### Health Endpoints (Phase 20)
- `backend/app/health.py` — `/healthz`, `/readyz` (checks Cosmos), `/startupz`
- All microservice `main.py` files include `health_router`

## Gaps Identified

### 1. Placeholder Values in K8s Manifests
- `k8s/base/secrets/secret-provider-class.yaml` has `${WORKLOAD_IDENTITY_CLIENT_ID}`, `${KEY_VAULT_NAME}`, `${AZURE_TENANT_ID}` placeholders
- `k8s/base/configmap.yaml` has `APPLICATIONINSIGHTS_CONNECTION_STRING: "REPLACE_WITH_APP_INSIGHTS_CONNECTION_STRING"`

### 2. No Deployment Orchestration Script
- No single script to run the full deployment end-to-end (infra → build → push → deploy → smoke test)
- Individual pieces exist but not wired together

### 3. No Local Integration Test
- `docker-compose.yml` runs the monolith, not the 5 microservices
- Cannot validate microservice architecture locally before cloud deploy

### 4. Smoke Test Scope
- Current smoke test only checks health endpoints
- No API-level validation (e.g., can create a tenant, can list agents)

### 5. No Post-Deploy Configuration Script
- After Bicep deploys, outputs (Cosmos endpoint, ACR server, App Insights connection string, Key Vault name) need to be fed into K8s manifests
- No automation for this bridge step

## Technical Approach

### Pre-Deployment Validation
- `az bicep build` to lint/validate Bicep
- `docker build` (dry run) to validate Dockerfiles
- `kubectl kustomize k8s/base` to validate K8s manifests render without errors

### Deployment Orchestration
Create `scripts/deploy.sh` that:
1. Deploys infrastructure via `az deployment group create`
2. Captures Bicep outputs (ACR server, Cosmos endpoint, Key Vault URI, App Insights connection string)
3. Populates K8s secrets/configmap with actual values
4. Builds + pushes images to ACR
5. Deploys to AKS via Kustomize
6. Provisions default tenant namespace
7. Runs smoke tests

### Local Microservice Validation
Create `docker-compose.microservices.yml` that runs all 5 backend services + frontend with mock/local dependencies to validate the containerized microservice architecture.

### Enhanced Smoke Tests
Extend `k8s/scripts/smoke-test.sh` to test:
- Health endpoints (existing)
- API endpoint reachability through ingress
- Tenant creation flow
- Frontend accessibility

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Azure subscription not provisioned | Deployment script validates prerequisites before starting |
| Bicep deployment failures | Pre-validate with `az deployment group what-if` |
| Docker build failures at scale | Local build validation before push |
| K8s manifest issues | `kubectl apply --dry-run=client` before real apply |
| Cosmos DB connectivity from AKS | Readiness probe already checks Cosmos; smoke test will surface |

## Recommendations

1. **Create deployment orchestration script** — Single `scripts/deploy.sh` that does everything
2. **Create pre-deployment validation** — `scripts/validate-deployment.sh` to catch issues early
3. **Create docker-compose.microservices.yml** — Local integration testing
4. **Enhance smoke tests** — API-level validation beyond health checks
5. **Post-deploy configuration bridge** — Script to extract Bicep outputs and populate K8s manifests

---
*Phase: 28-cloud-deployment-smoke-test*
*Research completed: 2026-03-26*
