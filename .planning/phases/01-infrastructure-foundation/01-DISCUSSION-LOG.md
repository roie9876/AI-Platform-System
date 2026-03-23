# Phase 1: Infrastructure Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-23
**Phase:** 01-infrastructure-foundation
**Areas discussed:** Azure Region Strategy, AKS Cluster Configuration, Networking Topology, CI/CD Pipeline, Bicep Module Organization, Monitoring Setup
**Mode:** Auto (all recommended defaults selected)

---

## Azure Region Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| East US 2 | Best GPU availability, paired region support (Central US) | ✓ |
| West US 3 | Good availability, newer region | |
| North Europe | EU data residency option | |

**User's choice:** [auto] East US 2 (recommended default)
**Notes:** GPU availability was the deciding factor for future model serving phases.

---

## AKS Cluster Configuration

| Option | Description | Selected |
|--------|-------------|----------|
| Start with system + user pools, GPU later | Cost-efficient, add GPU when Phase 4/5 needs it | ✓ |
| Full cluster with GPU from start | All node pools ready, higher initial cost | |
| Minimal single pool | Simplest, but limits workload isolation | |

**User's choice:** [auto] System + user pools, defer GPU (recommended default)
**Notes:** Standard_D4s_v5 for system, Standard_D8s_v5 for user workloads. Azure CNI Overlay for IP management.

---

## Networking Topology

| Option | Description | Selected |
|--------|-------------|----------|
| Hub-spoke with Azure Firewall | Enterprise security, egress control, full isolation | ✓ |
| Flat VNet with NSGs only | Simpler, less cost, adequate for dev | |
| Azure Virtual WAN | Multi-region ready, higher complexity | |

**User's choice:** [auto] Hub-spoke with Azure Firewall (recommended default)
**Notes:** Private endpoints for all PaaS services, no public internet exposure. Front Door for ingress with WAF.

---

## CI/CD Pipeline

| Option | Description | Selected |
|--------|-------------|----------|
| GitHub Actions | Widest adoption, good Azure integration, OIDC federation | ✓ |
| Azure DevOps Pipelines | Deep Azure integration, enterprise features | |
| GitLab CI | Alternative if GitLab is preferred | |

**User's choice:** [auto] GitHub Actions (recommended default)
**Notes:** OIDC federation for passwordless deployment. Separate workflows for infra, services, and config.

---

## Bicep Module Organization

| Option | Description | Selected |
|--------|-------------|----------|
| Modular per-resource with orchestrator | One module per resource type, main.bicep composes | ✓ |
| Monolithic single file | Simpler for small infra, harder to maintain | |
| Bicep registry modules | Shared across projects, more setup | |

**User's choice:** [auto] Modular per-resource (recommended default)
**Notes:** Parameter files per environment (dev, staging, prod). Shared module for naming and tags.

---

## Monitoring Setup

| Option | Description | Selected |
|--------|-------------|----------|
| Azure Monitor + App Insights + Log Analytics | Azure-native, unified, workspace-based | ✓ |
| Third-party (Datadog, New Relic) | More features, additional cost and vendor | |
| Prometheus + Grafana on AKS | Open-source, self-managed, more control | |

**User's choice:** [auto] Azure Monitor + App Insights + Log Analytics (recommended default)
**Notes:** Diagnostic settings on all resources. Azure Managed Grafana for dashboards. Alerts for node health, pod restarts, cert expiry.

---

## Agent's Discretion

- NSG rule definitions (standard enterprise patterns)
- Azure Firewall application rules
- ACR retention policies and image scanning
- Key Vault RBAC model
- Log Analytics retention (90 days default)

## Deferred Ideas

None — discussion stayed within phase scope
