---
phase: 23
slug: observability-monitoring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend), az bicep build (infra) |
| **Config file** | backend/pyproject.toml |
| **Quick run command** | `az bicep build --file infra/modules/appinsights.bicep --stdout > /dev/null` |
| **Full suite command** | `az bicep build --file infra/main.bicep --stdout > /dev/null` |
| **Estimated runtime** | ~5 seconds |

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 23-01-01 | 01 | 1 | OBS-01 | artifact | `ls backend/app/core/telemetry.py` | ✅ | ✅ green |
| 23-01-01 | 01 | 1 | OBS-02 | artifact | `grep -c 'HTTPXClientInstrumentor' backend/app/core/telemetry.py` | ✅ | ✅ green |
| 23-01-01 | 01 | 1 | OBS-03 | artifact | `grep -c 'tenant_id' backend/app/middleware/telemetry.py` | ✅ | ✅ green |
| 23-01-01 | 01 | 1 | OBS-04 | artifact | `grep -c 'trace_id' backend/app/core/logging_config.py` | ✅ | ✅ green |
| 23-02-01 | 02 | 2 | OBS-05 | artifact | `grep -c 'omsagent' infra/modules/aks.bicep` | ✅ | ✅ green |
| 23-02-01 | 02 | 2 | OBS-06 | artifact | `grep -c 'restart' infra/modules/alerts.bicep` | ✅ | ✅ green |
| 23-02-01 | 02 | 2 | OBS-07 | artifact | `grep -c '5xx' infra/modules/alerts.bicep` | ✅ | ✅ green |
| 23-02-01 | 02 | 2 | OBS-08 | artifact | `ls infra/modules/loganalytics.bicep infra/modules/appinsights.bicep` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Traces appear in App Insights | OBS-01 | Requires deployed services + App Insights resource | Deploy, send requests, check App Insights > Transaction search |
| Distributed traces span services | OBS-02 | Requires multiple deployed microservices | Send request through api-gateway, verify trace spans in App Insights |
| Tenant-filtered KQL queries | OBS-03 | Requires App Insights with data | Run `customDimensions.tenant_id == 'X'` in KQL |
| Container Insights dashboards | OBS-05 | Requires AKS cluster with omsagent | Check Azure Monitor > Containers |
| Alert fires on pod restart | OBS-06 | Requires AKS cluster | Kill pod, verify alert fires |
| Alert fires on 5xx spike | OBS-07 | Requires deployed services | Generate 5xx errors, verify alert fires |

*Note: OBS-01 through OBS-04 are instrumentation code (artifact-verified). OBS-05 through OBS-08 are infra (Bicep-verified). Runtime verification requires deployed infrastructure.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Wave 0 covers all MISSING references
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending — artifact-verified only, runtime testing blocked by deployment
