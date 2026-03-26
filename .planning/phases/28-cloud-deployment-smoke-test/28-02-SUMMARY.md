---
phase: 28-cloud-deployment-smoke-test
plan: 02
subsystem: infra
tags: [bash, azure, kubernetes, smoke-test, bicep, configuration]

requires:
  - phase: 28-cloud-deployment-smoke-test
    provides: deploy.sh, validate-deployment.sh, docker-compose.microservices.yml

provides:
  - Post-deploy configuration bridge (Bicep outputs → K8s manifests)
  - Enhanced smoke test with API, DNS, and resource compliance checks

affects: []

tech-stack:
  added: []
  patterns: [bicep-output-bridge, extended-smoke-testing, idempotent-config-patching]

key-files:
  created:
    - scripts/post-deploy-config.sh
  modified:
    - k8s/scripts/smoke-test.sh

key-decisions:
  - "Used temp file approach instead of sed -i for macOS/Linux portability"
  - "Extended checks use exit code 2 (non-blocking) vs exit code 1 for health failures"
  - "API endpoint checks accept 2xx-4xx as 'reachable' (401 means auth works, route exists)"

patterns-established:
  - "Config bridge pattern: az deployment group show → jq extract → sed replace placeholders"
  - "Smoke test tiers: basic (health only) and --extended (API + DNS + resources)"

requirements-completed: []

duration: 5min
completed: 2026-03-26
---

# Plan 28-02: Enhanced Smoke Tests + Post-Deploy Config Bridge

**Created Bicep-to-K8s configuration bridge and enhanced smoke tests with API reachability, DNS resolution, and resource compliance checks.**

## Performance

- **Duration:** 5 min
- **Tasks:** 3/3 completed (2 auto + 1 checkpoint approved)
- **Files created:** 1
- **Files modified:** 1

## Accomplishments
- Post-deploy config script extracts all Bicep outputs and populates K8s configmap + secret-provider-class placeholders idempotently
- Smoke test enhanced with --extended flag: API endpoint reachability via port-forward or --ingress-url, inter-service DNS resolution, pod resource compliance
- Human checkpoint approved — all deployment artifacts validated

## Task Commits

1. **Task 1: Post-deploy configuration bridge script** — `6c7c277` (feat)
2. **Task 2: Enhanced smoke test with API, DNS, and resource checks** — `12c8b6b` (feat)
3. **Task 3: Deployment readiness verification** — checkpoint:human-verify (approved)

## Files Created/Modified
- `scripts/post-deploy-config.sh` — Extracts Bicep outputs, populates K8s configmap and secret-provider-class placeholders
- `k8s/scripts/smoke-test.sh` — Enhanced with --extended flag for API, DNS, and resource checks; backward compatible

## Self-Check: PASSED
- [x] scripts/post-deploy-config.sh passes bash -n and is executable
- [x] k8s/scripts/smoke-test.sh passes bash -n
- [x] smoke-test.sh contains --extended flag handling
- [x] post-deploy-config.sh extracts Bicep outputs via az deployment group show
- [x] post-deploy-config.sh replaces all K8s manifest placeholders
- [x] Human checkpoint approved
