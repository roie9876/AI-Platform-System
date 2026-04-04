---
phase: 28-cloud-deployment-smoke-test
plan: 01
subsystem: infra
tags: [bash, docker-compose, azure, bicep, kubernetes, deployment]

requires:
  - phase: 17-infrastructure-foundation
    provides: Bicep IaC templates
  - phase: 20-microservice-extraction
    provides: 5 microservice Dockerfiles
  - phase: 22-ci-cd-pipelines
    provides: GitHub Actions workflows

provides:
  - Pre-deployment validation script (Bicep, Docker, K8s checks)
  - End-to-end deployment orchestration script
  - Local microservice docker-compose for integration testing

affects: [28-cloud-deployment-smoke-test]

tech-stack:
  added: []
  patterns: [deployment-orchestration, pre-flight-validation, local-integration-testing]

key-files:
  created:
    - scripts/validate-deployment.sh
    - scripts/deploy.sh
    - docker-compose.microservices.yml
  modified: []

key-decisions:
  - "deploy.sh captures all Bicep outputs via az deployment group show JSON rather than hardcoding names"
  - "docker-compose uses placeholder Cosmos values since v3.0 uses Cosmos DB not local PostgreSQL"
  - "Validation script builds Docker images to validate Dockerfiles parse correctly"

patterns-established:
  - "Deployment orchestration: validate → infra → build → push → configure → deploy → smoke test → tenant"
  - "Pre-flight checks as separate script so CI/CD can run independently of deploy"

requirements-completed: []

duration: 8min
completed: 2026-03-26
---

# Plan 28-01: Deployment Orchestration & Local Microservice Validation

**Created single-command deployment workflow and local 6-service docker-compose for validating the containerized architecture before cloud deployment.**

## Performance

- **Duration:** 8 min
- **Tasks:** 2/2 completed
- **Files created:** 3

## Accomplishments
- Pre-deployment validation checks prerequisites, Azure login, Bicep compilation, K8s manifests, and Docker builds
- Deployment script orchestrates full end-to-end: Bicep infra → capture outputs → AKS credentials → ACR build/push → K8s configmap/secrets → deploy → smoke test → tenant provisioning
- Docker-compose runs all 5 microservices + frontend on a shared network with health checks and inter-service URLs

## Task Commits

1. **Task 1: Pre-deployment validation + deployment orchestration** — `7fa75e0` (feat)
2. **Task 2: Local microservice docker-compose** — `dda5f24` (feat)

## Files Created/Modified
- `scripts/validate-deployment.sh` — Pre-flight checks: prerequisites, Azure login, Bicep lint, K8s manifests, Docker builds
- `scripts/deploy.sh` — End-to-end deployment: infra → build → push → deploy → smoke test with --dry-run support
- `docker-compose.microservices.yml` — 5 backend microservices + frontend with healthchecks and shared aiplatform network

## Self-Check: PASSED
- [x] scripts/validate-deployment.sh passes bash -n and is executable
- [x] scripts/deploy.sh passes bash -n and is executable
- [x] docker-compose.microservices.yml validates with docker compose config
- [x] deploy.sh has --resource-group, --dry-run, --skip-infra, --skip-build arguments
- [x] validate-deployment.sh checks az, kubectl, docker, kustomize, jq prerequisites
