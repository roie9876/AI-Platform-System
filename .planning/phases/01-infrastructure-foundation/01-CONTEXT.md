# Phase 1: Infrastructure Foundation - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Provision all Azure infrastructure needed for the AI Platform System: VNet with private networking, AKS cluster, ACR, Key Vault, Azure Monitor/App Insights, and CI/CD pipeline. Everything deployed via Bicep IaC templates. This phase produces the foundation that all subsequent services deploy onto.

</domain>

<decisions>
## Implementation Decisions

### Azure Region Strategy
- **D-01:** Primary region is **East US 2** — best GPU availability for future model serving, Azure paired region (Central US) for DR
- **D-02:** Secondary region provisioning deferred to Phase 4 (Model Deployment) when multi-region inference is needed
- **D-03:** All resources deploy to primary region initially; Bicep modules parameterized for multi-region expansion

### AKS Cluster Configuration
- **D-04:** System node pool uses **Standard_D4s_v5** (4 vCPU, 16 GB) with 2-5 node autoscaling
- **D-05:** User node pool uses **Standard_D8s_v5** (8 vCPU, 32 GB) with 1-10 node autoscaling for application workloads
- **D-06:** GPU node pool deferred to Phase 4/5 — not needed until model deployment
- **D-07:** AKS uses **Azure CNI Overlay** networking for better IP management in large clusters
- **D-08:** Kubernetes version: latest stable (1.30.x)
- **D-09:** Workload identity enabled for pod-level managed identity access

### Networking Topology
- **D-10:** **Hub-spoke VNet topology** with Azure Firewall for egress control
- **D-11:** Subnets: AKS system pool, AKS user pool, AKS GPU pool (reserved), APIM, Cosmos DB private endpoints, Azure SQL private endpoints, Service Bus/Event Hubs, management/bastion
- **D-12:** All PaaS services accessed via **private endpoints** — no public internet exposure
- **D-13:** Azure Front Door for global ingress with WAF protection
- **D-14:** NSG rules enforced per subnet with deny-all default

### CI/CD Pipeline
- **D-15:** **GitHub Actions** for CI/CD — build, test, deploy infrastructure and services
- **D-16:** Separate workflows for: infrastructure (Bicep), services (Docker build + AKS deploy), and configuration
- **D-17:** Environment-based deployment: dev → staging → production with approval gates for production
- **D-18:** GitHub OIDC federation with Azure for passwordless deployment (no stored credentials)

### Bicep Module Organization
- **D-19:** **Modular per-resource** structure: `infra/modules/` with one module per Azure resource type
- **D-20:** Main orchestrator: `infra/main.bicep` composes modules with environment-specific parameters
- **D-21:** Parameter files per environment: `infra/parameters/dev.bicepparam`, `staging.bicepparam`, `prod.bicepparam`
- **D-22:** Shared module for tags, naming conventions, and common configurations

### Monitoring & Observability
- **D-23:** **Azure Monitor** with centralized **Log Analytics workspace** for all resource logs
- **D-24:** **Application Insights** (workspace-based) connected to Log Analytics for application telemetry
- **D-25:** Diagnostic settings enabled on all resources (AKS, ACR, Key Vault, Firewall, etc.)
- **D-26:** Azure Monitor alerts for: node health, pod restarts, certificate expiry, firewall blocks
- **D-27:** Azure Managed Grafana for operational dashboards (optional, Bicep module ready)

### Agent's Discretion
- Specific NSG rule definitions — standard enterprise patterns
- Azure Firewall application rule collections for egress filtering
- ACR retention policies and image scanning configuration
- Key Vault access policies vs RBAC model (prefer RBAC)
- Log Analytics workspace retention period (default 90 days)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Azure Architecture
- `.planning/research/ARCHITECTURE.md` — System architecture with component boundaries and build order
- `.planning/research/STACK.md` — Recommended Azure services with versions and rationale
- `.planning/research/PITFALLS.md` — Critical pitfalls including networking security (Pitfall #9) and partition key design (Pitfall #1)

### Requirements
- `.planning/REQUIREMENTS.md` §Infrastructure — INFRA-01 through INFRA-06 requirements

### Project
- `.planning/PROJECT.md` — Constraints section specifies Azure-only, Bicep IaC, microservices on AKS

No external specs — requirements fully captured in decisions above and referenced planning docs.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code

### Established Patterns
- None — patterns will be established by this phase

### Integration Points
- This phase creates the foundation all subsequent phases deploy onto
- AKS cluster will host all microservices (Phases 2-9)
- Key Vault will store secrets for all services
- Azure Monitor/App Insights will collect telemetry from all services
- Private networking topology constrains all subsequent service deployments

</code_context>

<specifics>
## Specific Ideas

- Platform should mirror enterprise-grade Azure patterns similar to Azure AI Foundry's infrastructure
- Security from Day 1: private endpoints, managed identities, no public exposure
- Infrastructure must support the full 11-phase roadmap without major rearchitecting

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-infrastructure-foundation*
*Context gathered: 2026-03-23*
