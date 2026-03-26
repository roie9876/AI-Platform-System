---
phase: 23-observability-monitoring
plan: 02
subsystem: infra
tags: [bicep, application-insights, azure-monitor, alerts, diagnostics, container-insights]

requires: []
provides:
  - Application Insights Bicep module connected to Log Analytics
  - Azure Monitor alert rules for pod restarts, 5xx rate, Cosmos RU, node CPU
  - Cosmos DB and Key Vault diagnostic settings flowing to Log Analytics
  - APPLICATIONINSIGHTS_CONNECTION_STRING in K8s configmap
affects: [deployment, monitoring, operations]

tech-stack:
  added: [appinsights.bicep, alerts.bicep]
  patterns: [conditional-diagnostic-settings, action-group-email-alerts]

key-files:
  created:
    - infra/modules/appinsights.bicep
    - infra/modules/alerts.bicep
  modified:
    - infra/main.bicep
    - infra/modules/cosmos.bicep
    - infra/modules/keyvault.bicep
    - infra/parameters/prod.bicepparam
    - k8s/base/configmap.yaml

key-decisions:
  - "Diagnostic settings embedded in cosmos.bicep and keyvault.bicep with optional logAnalyticsWorkspaceId param (Bicep scope constraint)"
  - "AKS Container Insights already enabled via omsagent addon in aks.bicep — no changes needed"

patterns-established:
  - "Conditional diagnostic settings using if (!empty(logAnalyticsWorkspaceId)) pattern"
  - "Alert rules with action group email notification"

requirements-completed: [OBS-05, OBS-06, OBS-07, OBS-08]

duration: 10min
completed: 2026-03-26
---

# Plan 23-02: Infrastructure Observability Summary

**Application Insights, 4 Azure Monitor alert rules, and diagnostic settings for Cosmos DB + Key Vault provisioned via Bicep IaC.**

## Performance

- **Tasks:** 2 completed
- **Files modified:** 7

## Accomplishments
- Application Insights resource connected to Log Analytics with 90-day retention
- 4 metric alert rules: pod restarts >5, 5xx rate >10, Cosmos RU >80%, node CPU >80%
- Cosmos DB diagnostic settings sending DataPlaneRequests, QueryRuntimeStatistics, PartitionKeyStatistics
- Key Vault diagnostic settings sending AuditEvent logs
- K8s configmap updated with APPLICATIONINSIGHTS_CONNECTION_STRING placeholder

## Task Commits

1. **Task 1: Application Insights + alerts Bicep modules** - `b9567f0` (feat)
2. **Task 2: Wire into main.bicep, update configmap and parameters** - `0fab967` (feat)

## Files Created/Modified
- `infra/modules/appinsights.bicep` - App Insights resource with Log Analytics workspace connection
- `infra/modules/alerts.bicep` - 4 metric alert rules + action group
- `infra/main.bicep` - Added appInsights/alerts modules, alertEmail param, connection string output
- `infra/modules/cosmos.bicep` - Added conditional diagnostic settings
- `infra/modules/keyvault.bicep` - Added conditional diagnostic settings
- `infra/parameters/prod.bicepparam` - Added alertEmail parameter
- `k8s/base/configmap.yaml` - Added APPLICATIONINSIGHTS_CONNECTION_STRING + OTEL_SERVICE_NAME

## Decisions Made
- Diagnostic settings placed inside resource modules (not main.bicep) due to Bicep scope constraints
- Used conditional deployment pattern for backward compatibility

## Deviations from Plan
Diagnostic settings moved from main.bicep into cosmos.bicep/keyvault.bicep — Bicep requires diagnostic settings to scope to a resource, not a module reference.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full observability stack ready: OTel instrumentation + Azure Monitor infra
- Deploy will wire APPLICATIONINSIGHTS_CONNECTION_STRING from Bicep output into K8s configmap
