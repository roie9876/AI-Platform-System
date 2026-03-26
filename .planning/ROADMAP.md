# Roadmap: AI Agent Platform as a Service

**Created:** 2026-03-23
**Active Milestone:** v3.0 — Production Multi-Tenant Infrastructure

## Milestones

- ✅ **v1.0 AI Agent Platform PoC** — Phases 1-10 (shipped 2026-03-24) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 MCP Tool Integration** — Phases 11-16 (shipped 2026-03-25)
- 🔄 **v3.0 Production Multi-Tenant Infrastructure** — Phases 17-24 (active)

<details>
<summary>✅ v1.0 AI Agent Platform PoC (Phases 1-10) — SHIPPED 2026-03-24</summary>

- [x] Phase 1: Foundation & Project Scaffold (3 plans)
- [x] Phase 2: HLD & Microsoft Architecture Documentation (2 plans)
- [x] Phase 3: Agent Core & Model Abstraction (4 plans)
- [x] Phase 4: Tools, Data Sources, RAG & Platform AI Services (5 plans)
- [x] Phase 5: Memory & Thread Management (3 plans)
- [x] Phase 6: Orchestration & Workflow Engine (3 plans)
- [ ] Phase 7: Policy Engine & Governance (skipped — deferred to future milestone)
- [x] Phase 8: Observability, Evaluation, Marketplace & CLI (6 plans)
- [x] Phase 9: Azure Subscription Integration & Foundry-Style AI Services (5 plans)
- [x] Phase 10: Agent-Level Traces & Monitor Tabs (2 plans)

**Known Gaps:**
- Phase 7 (Policy Engine & Governance) was not implemented — PLCY-01 through PLCY-04 deferred

</details>

<details>
<summary>✅ v2.0 MCP Tool Integration (Phases 11-16) — SHIPPED 2026-03-25</summary>

- [x] Phase 11: MCP Client Library (1 plan)
- [x] Phase 12: MCP Server Registry (1 plan)
- [x] Phase 13: MCP Tool Discovery (1 plan)
- [x] Phase 14: Agent Execution Integration (1 plan)
- [x] Phase 15: MCP Tool Catalog UI (1 plan)
- [x] Phase 16: Agent-Level MCP Management (2 plans)

</details>

## Milestone 3: v3.0 — Production Multi-Tenant Infrastructure

**Goal:** Transform the AI Agent Platform from a single-instance PoC into a production-ready, multi-tenant SaaS deployed on Azure with per-tenant compute isolation on AKS and shared Cosmos DB.

### Overview

v3.0 migrates the platform across every layer: infrastructure (Bicep IaC), authentication (Entra ID), data (Cosmos DB), compute (AKS microservices), deployment (GitHub Actions CI/CD), and operations (Azure Monitor). The critical path is IaC → Auth → Data → Microservices → Tenant Provisioning → CI/CD → Observability → UI, dictated by hard dependencies: Azure resources must exist before code targets them, auth must migrate while the codebase is still a monolith, and SQLAlchemy must be replaced before microservice extraction.

### Phases

**Phase Numbering:** Continues from v2.0 (Phases 11-16).

- [x] **Phase 17: Infrastructure Foundation (Bicep IaC)** — Provision all Azure resources via Bicep modules (completed 2026-03-26)
- [x] **Phase 18: Authentication Migration (Entra ID)** — Replace JWT auth with enterprise SSO and Managed Identity (3 plans) (completed 2026-03-26)
- [x] **Phase 19: Data Layer Migration (Cosmos DB)** — Replace SQLAlchemy/PostgreSQL with Cosmos DB NoSQL SDK (completed 2026-03-26)
- [x] **Phase 20: Microservice Extraction & AKS Deployment** — Split monolith into 5 microservices and deploy to AKS (completed 2026-03-26)
- [x] **Phase 21: Tenant Lifecycle & Provisioning** — Tenant creation API with automated namespace provisioning (completed 2026-03-26)
- [ ] **Phase 22: CI/CD Pipelines (GitHub Actions)** — Automated build, push, and deploy to AKS
- [ ] **Phase 23: Observability & Monitoring** — OpenTelemetry, App Insights, per-tenant metrics, alerting
- [ ] **Phase 24: Tenant Admin UI** — Tenant selector, admin dashboard, onboarding wizard, scoped views

### Phase Details

#### Phase 17: Infrastructure Foundation (Bicep IaC)
**Goal**: All Azure resources for the platform are provisioned via Bicep and ready for application deployment
**Depends on**: Nothing (first v3.0 phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, INFRA-07, INFRA-08, INFRA-09
**Success Criteria** (what must be TRUE):
  1. `az deployment group create` deploys all resources (AKS, ACR, Cosmos DB, VNet, Key Vault, Managed Identities, Log Analytics) from a single orchestrator command
  2. AKS cluster is accessible via `kubectl` with system and user node pools running
  3. Cosmos DB account contains the `aiplatform` database with all containers partitioned by `/tenant_id`
  4. Dev, staging, and prod parameter files deploy different SKUs and throughput settings without code changes
  5. Rerunning the deployment is idempotent — no errors, no duplicate resources
**Plans:** 3/3 plans complete
Plans:
- [x] 17-01-PLAN.md — Foundation modules (VNet, Log Analytics, Managed Identities, ACR)
- [x] 17-02-PLAN.md — Cosmos DB module with all containers
- [x] 17-03-PLAN.md — AKS, Key Vault, main.bicep orchestrator + prod.bicepparam

#### Phase 18: Authentication Migration (Entra ID)
**Goal**: Users authenticate via Microsoft Entra ID with enterprise SSO, replacing the existing JWT-based auth
**Depends on**: Phase 17 (Managed Identities, Key Vault)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, AUTH-07
**Success Criteria** (what must be TRUE):
  1. Users log in via Entra ID OIDC flow in the browser and receive a valid access token
  2. Backend rejects requests with expired, invalid, or missing Entra ID tokens
  3. Users are mapped to their tenant based on Entra ID claims and can only access their own tenant's data
  4. Platform Admin, Tenant Admin, Member, and Viewer roles restrict API access at endpoint level
  5. Service-to-service calls authenticate via Managed Identity without any stored credentials
**Plans:** 3/3 plans complete
Plans:
- [x] 18-01-PLAN.md — Backend Entra ID token validation, RBAC dependencies, migrate all API routes
- [x] 18-02-PLAN.md — Frontend MSAL React integration, login page, Bearer token API layer
- [x] 18-03-PLAN.md — Managed Identity (DefaultAzureCredential) for service-to-service auth
**UI hint**: yes

#### Phase 19: Data Layer Migration (Cosmos DB)
**Goal**: All platform data is stored in Cosmos DB with tenant isolation enforced at the partition key level
**Depends on**: Phase 17 (Cosmos DB account), Phase 18 (tenant context from auth)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, DATA-08
**Success Criteria** (what must be TRUE):
  1. All API endpoints read and write data via Cosmos DB repository layer — no SQLAlchemy calls remain
  2. Every data operation includes `tenant_id` in the partition key — no cross-partition queries exist
  3. All 13+ existing data models have been migrated to Cosmos DB document schemas with preserved data
  4. Concurrent document updates are safely handled via ETag-based optimistic concurrency
  5. Cosmos DB throughput is configured with autoscale appropriate to dev/staging workload
**Plans:** 3/3 plans complete
Plans:
- [x] 19-01-PLAN.md — Cosmos DB repository foundation (CosmosClient, base repo, all repository implementations)
- [x] 19-02-PLAN.md — API route migration (all 19 routes from SQLAlchemy to repositories)
- [x] 19-03-PLAN.md — Service migration, CosmosClient lifecycle, data migration script

#### Phase 20: Microservice Extraction & AKS Deployment
**Goal**: The monolith is split into 5 microservices running as isolated workloads on AKS with per-tenant compute boundaries
**Depends on**: Phase 19 (data layer must be migrated before decomposition)
**Requirements**: COMPUTE-01, COMPUTE-02, COMPUTE-03, COMPUTE-04, COMPUTE-05, COMPUTE-06, COMPUTE-07, COMPUTE-08, COMPUTE-09
**Success Criteria** (what must be TRUE):
  1. Five separate container images (api-gateway, agent-executor, workflow-engine, tool-executor, mcp-proxy) build and run independently
  2. Each tenant's workloads run in a dedicated K8s namespace with enforced NetworkPolicy, ResourceQuota, and LimitRange
  3. Pods cannot reach other tenant namespaces — cross-namespace traffic is blocked by NetworkPolicy
  4. Workloads auto-scale via HPA based on CPU/memory utilization
  5. All microservices pass liveness, readiness, and startup health checks
**Plans:** 3/3 plans complete
Plans:
- [x] 20-01-PLAN.md — Microservice scaffolding, health checks, inter-service client
- [x] 20-02-PLAN.md — Inter-service communication refactor (AgentExecutionService, WorkflowEngine)
- [x] 20-03-PLAN.md — Kustomize manifests and tenant namespace isolation

#### Phase 21: Tenant Lifecycle & Provisioning
**Goal**: Platform admins can create, configure, and manage tenants through an API that automatically provisions isolated infrastructure
**Depends on**: Phase 18 (Entra ID for admin user), Phase 19 (Cosmos DB for tenant data), Phase 20 (AKS namespaces)
**Requirements**: TENANT-01, TENANT-02, TENANT-03, TENANT-04, TENANT-05, TENANT-06, TENANT-07
**Success Criteria** (what must be TRUE):
  1. Platform admin creates a tenant via API and a K8s namespace with NetworkPolicy, ResourceQuota, and LimitRange is automatically provisioned
  2. Tenants transition through provisioning → active → suspended → deactivated → deleted lifecycle states
  3. Suspended tenant API requests are blocked at middleware — no data access while suspended
  4. New tenants are seeded with default catalog entries, tools, policies, and an admin user mapped to Entra ID
  5. Platform admin can configure per-tenant settings (display name, allowed providers, quotas, feature flags)
**Plans**: 2 plans
Plans:
- [x] 21-01-PLAN.md — Tenant model, service with lifecycle state machine, and REST API endpoints
- [x] 21-02-PLAN.md — K8s provisioning, data seeding, admin user creation, and middleware suspension blocking

#### Phase 22: CI/CD Pipelines (GitHub Actions)
**Goal**: Code changes are automatically built, tested, and deployed to AKS via GitHub Actions with zero-downtime deployments
**Depends on**: Phase 20 (microservice images + AKS target), Phase 17 (ACR)
**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04, DEPLOY-05, DEPLOY-06, DEPLOY-07, DEPLOY-08
**Success Criteria** (what must be TRUE):
  1. Push to main triggers automated build of all microservice Docker images, tagged with git SHA and pushed to ACR
  2. GitHub Actions deploys to AKS using Helm/Kustomize with rolling updates — no downtime during deployment
  3. Post-deploy smoke tests automatically verify service health before marking deployment complete
  4. Secrets are injected from Key Vault via CSI driver — no hardcoded credentials in manifests or environment variables
  5. A single tenant namespace can be deployed independently without affecting other tenants
**Plans**: TBD

#### Phase 23: Observability & Monitoring
**Goal**: All microservices are instrumented with distributed tracing, per-tenant metrics, and alerting via Azure Monitor
**Depends on**: Phase 20 (microservices deployed), Phase 22 (CI/CD for deployment)
**Requirements**: OBS-01, OBS-02, OBS-03, OBS-04, OBS-05, OBS-06, OBS-07, OBS-08
**Success Criteria** (what must be TRUE):
  1. Requests produce distributed traces spanning all microservices with correlated trace IDs visible in Application Insights
  2. All telemetry and logs include `tenant_id` — per-tenant KQL queries return only that tenant's data
  3. AKS node/pod CPU, memory, and network metrics are visible in Container Insights
  4. Alerts fire when health checks fail, pods restart excessively, 5xx rates exceed threshold, or Cosmos DB RU consumption exceeds 80%
  5. Central Log Analytics workspace receives and correlates logs from App Insights, AKS, Cosmos DB diagnostics, and Key Vault audit
**Plans**: TBD

#### Phase 24: Tenant Admin UI
**Goal**: Platform admins can manage tenants and tenant admins can manage their team through the web UI
**Depends on**: Phase 18 (auth), Phase 19 (data), Phase 21 (tenant API), Phase 23 (observability data for usage)
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, TENANT-08
**Success Criteria** (what must be TRUE):
  1. Platform admin can switch between tenants via a global selector — all pages automatically filter to the selected tenant
  2. Platform admin dashboard shows all tenants with status, resource usage, agent counts, and active users
  3. Platform admin can onboard a new tenant through a multi-step wizard (org name → Entra ID → model endpoint → first agent → review)
  4. Tenant admins can configure settings, view users, assign roles, and invite users via Entra ID groups
  5. Per-tenant usage summary displays API calls, agent executions, token consumption, and cost estimates
**Plans**: TBD
**UI hint**: yes

### Phase Dependencies

```
Phase 17 (Infrastructure Foundation)
    │
    ├──► Phase 18 (Authentication Migration)
    │         │
    │         └──► Phase 19 (Data Layer Migration)
    │                   │
    │                   └──► Phase 20 (Microservice Extraction & AKS)
    │                             │
    │                             ├──► Phase 21 (Tenant Lifecycle & Provisioning)
    │                             │         │
    │                             │         └──► Phase 24 (Tenant Admin UI)
    │                             │
    │                             ├──► Phase 22 (CI/CD Pipelines)
    │                             │
    │                             └──► Phase 23 (Observability & Monitoring)
    │                                       │
    │                                       └──► Phase 24 (Tenant Admin UI)
```

### Progress

**Execution Order:** 17 → 18 → 19 → 20 → 21 → 22 → 23 → 24

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 17. Infrastructure Foundation | 3/3 | Complete    | 2026-03-26 |
| 18. Authentication Migration | 3/3 | Complete   | 2026-03-26 |
| 19. Data Layer Migration | 1/3 | Complete    | 2026-03-26 |
| 20. Microservice Extraction & AKS | 2/3 | In Progress|  |
| 21. Tenant Lifecycle & Provisioning | 0/? | Not started | - |
| 22. CI/CD Pipelines | 0/? | Not started | - |
| 23. Observability & Monitoring | 0/? | Not started | - |
| 24. Tenant Admin UI | 0/? | Not started | - |

---
*Roadmap created: 2026-03-23*
*Last updated: 2026-03-26 after v3.0 roadmap creation*
