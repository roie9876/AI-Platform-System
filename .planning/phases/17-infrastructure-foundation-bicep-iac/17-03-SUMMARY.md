---
phase: 17-infrastructure-foundation-bicep-iac
plan: 03
subsystem: infra
tags: [bicep, azure, aks, keyvault, orchestrator, bicepparam]

requires:
  - phase: 17-01
    provides: VNet subnets, Log Analytics workspace, Managed Identities, ACR
  - phase: 17-02
    provides: Cosmos DB account and containers
provides:
  - AKS cluster with system + user node pools, Azure CNI Overlay, Workload Identity
  - Key Vault with RBAC authorization and Secrets User role
  - main.bicep orchestrator wiring all 7 modules
  - prod.bicepparam production parameter file
affects: [phase-18, phase-19, phase-20, phase-22, phase-23]

tech-stack:
  added: []
  patterns: [bicep-orchestrator-pattern, module-output-wiring, bicepparam-format]

key-files:
  created:
    - infra/modules/aks.bicep
    - infra/modules/keyvault.bicep
    - infra/main.bicep
    - infra/parameters/prod.bicepparam
  modified: []

key-decisions:
  - "Key Vault name shortened to stumsft-aiplat-${env}-kv to fit 24-char limit"
  - "AKS uses Azure CNI Overlay with pod CIDR 192.168.0.0/16"
  - "Single prod.bicepparam per D-09 (no dev/staging environments)"

patterns-established:
  - "main.bicep as single deployment entry point with wave-based module ordering"
  - "Module output wiring: identity → acr, vnet/identity/loganalytics → aks, identity → keyvault"
  - ".bicepparam format with using directive for type-safe parameters"

requirements-completed: [INFRA-01, INFRA-03, INFRA-06, INFRA-08, INFRA-09]

duration: 5min
completed: 2026-03-26
---

# Plan 17-03: AKS, Key Vault, and Orchestrator Summary

**AKS cluster with dual node pools and workload identity, Key Vault with RBAC, and main.bicep orchestrator wiring all 7 infrastructure modules into a single deployable unit.**

## Performance

- **Duration:** 5 min
- **Tasks:** 2/2 completed
- **Files created:** 4

## Accomplishments
- AKS cluster with system + user node pools, Azure CNI Overlay, Entra ID RBAC, OIDC issuer, workload identity
- Key Vault with RBAC authorization and Secrets User role for workload identity
- main.bicep orchestrator deploys all 7 modules with correct dependency ordering
- prod.bicepparam provides production SKUs and configuration

## Task Commits

1. **Task 1: Create AKS and Key Vault modules** - `75cc953` (feat)
2. **Task 2: Create main.bicep orchestrator and prod.bicepparam** - `4471623` (feat)

## Files Created/Modified
- `infra/modules/aks.bicep` - AKS cluster with CNI Overlay, Workload Identity, Azure Monitor
- `infra/modules/keyvault.bicep` - Key Vault with RBAC and Secrets User role assignment
- `infra/main.bicep` - Orchestrator wiring 7 modules with 10 typed outputs
- `infra/parameters/prod.bicepparam` - Production parameter values

## Decisions Made
- Key Vault name shortened to `stumsft-aiplat-${env}-kv` (22 chars) to fit Azure's 24-char limit

## Deviations from Plan
None - plan executed exactly as written

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
Complete Bicep IaC is deployable via `az deployment group create --template-file infra/main.bicep --parameters infra/parameters/prod.bicepparam`. All outputs needed by Phase 18 (auth), Phase 19 (data), Phase 20 (AKS deployment), and Phase 22 (CI/CD) are exposed.

---
*Phase: 17-infrastructure-foundation-bicep-iac*
*Completed: 2026-03-26*
