# Roadmap: AI Agent Platform as a Service

**Created:** 2026-03-23
**Active Milestone:** v4.0 — Architecture Pivot: Platform as Infrastructure Provider

## Milestones

- ✅ **v1.0 AI Agent Platform PoC** — Phases 1-10 (shipped 2026-03-24) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 MCP Tool Integration** — Phases 11-16 (shipped 2026-03-25)
- ✅ **v3.0 Production Multi-Tenant Infrastructure** — Phases 17-27 (shipped 2026-03-26)
- 🔄 **v4.0 Architecture Pivot: Platform as Infrastructure Provider** — Phases 28-32 (active)

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
- [x] **Phase 22: CI/CD Pipelines (GitHub Actions)** — Automated build, push, and deploy to AKS (completed 2026-03-26)
- [x] **Phase 23: Observability & Monitoring** — OpenTelemetry, App Insights, per-tenant metrics, alerting (completed 2026-03-26)
- [x] **Phase 24: Tenant Admin UI** — Tenant selector, admin dashboard, onboarding wizard, scoped views (completed 2026-03-26)
- [x] **Phase 25: Milestone Validation** — Fix DATA-06 gap, automated tests for data layer, tenant lifecycle, and health endpoints (completed 2026-03-26)
- [x] **Phase 26: Tenant Context Wiring** — Wire useTenant() into all dashboard pages so tenant selector filters data (UI-02 critical fix) (completed 2026-03-26)
- [x] **Phase 27: Verification & Traceability Closure** — Create VERIFICATION.md for Phases 19-24, update SUMMARY frontmatter, check off REQUIREMENTS.md (completed 2026-03-26)

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
**Plans**: 2 plans
Plans:
- [x] 22-01-PLAN.md — Build-push workflow (matrix build, OIDC auth, ACR push) and Key Vault CSI SecretProviderClass
- [x] 22-02-PLAN.md — Deploy workflow (Kustomize, rolling updates, smoke tests), frontend deploy, and tenant deploy

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
**Plans**: 2 plans
Plans:
- [x] 23-01-PLAN.md — OpenTelemetry instrumentation, telemetry middleware, structured JSON logging
- [x] 23-02-PLAN.md — Application Insights, Azure Monitor alerts, diagnostic settings, Container Insights

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
**Plans:** 3 plans

Plans:
- [ ] 24-01-PLAN.md — TenantContext, TenantSelector, TenantStatusBadge, sidebar nav, tenants dashboard page
- [ ] 24-02-PLAN.md — Tenant detail page with Settings, Users, and Usage tabs
- [ ] 24-03-PLAN.md — Multi-step onboarding wizard (Organization → Entra ID → Model Endpoint → Agent → Review)

**UI hint**: yes

#### Phase 25: Milestone Validation
**Goal**: All testable v3.0 requirements have automated verification; artifact gap DATA-06 is fixed
**Depends on**: Phase 19 (repos to test), Phase 20 (health endpoints to test), Phase 21 (tenant service to test)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, TENANT-01, TENANT-03, TENANT-04, TENANT-05, TENANT-06, TENANT-07, COMPUTE-07
**Success Criteria** (what must be TRUE):
  1. `pytest tests/` passes with all new validation tests green
  2. Cosmos DB containers have uniqueKeyPolicy defined in Bicep (DATA-06)
  3. Repository CRUD, tenant isolation, and ETag concurrency are tested
  4. Tenant lifecycle state machine transitions are tested
  5. Middleware blocks suspended/deactivated tenants
  6. Health endpoints return 200
**Plans:** 3/3 plans complete

Plans:
- [x] 25-01-PLAN.md — Fix DATA-06 (uniqueKeyPolicy in cosmos.bicep) + test fixtures
- [x] 25-02-PLAN.md — Data layer & repository tests (DATA-01 through DATA-07)
- [x] 25-03-PLAN.md — Tenant lifecycle, middleware, and health endpoint tests

#### Phase 26: Tenant Context Wiring
**Goal**: All dashboard pages filter data by the selected tenant — switching tenants in the selector changes what every page displays
**Depends on**: Phase 24 (TenantContext, TenantSelector exist)
**Requirements**: UI-02
**Gap Closure:** Closes critical gap from v3.0 audit — useTenant() hook exists but is not consumed by any dashboard page
**Success Criteria** (what must be TRUE):
  1. Every dashboard page that fetches data calls `useTenant()` and passes `tenantId` to API requests
  2. Switching tenants in the TenantSelector immediately updates all page data
  3. No cross-tenant data leakage — pages only show data for the selected tenant
**Plans:** 2/2 plans complete
Plans:
- [x] 26-01-PLAN.md — API tenant header injection + core entity pages (agents, tools, data-sources, models, workflows, evaluations)
- [x] 26-02-PLAN.md — Observability + MCP tools pages + human verification

#### Phase 27: Verification & Traceability Closure
**Goal**: All v3.0 requirements have formal verification evidence; REQUIREMENTS.md accurately reflects completion status
**Depends on**: Phase 25, Phase 26 (all implementation gaps must be fixed first)
**Requirements**: DATA-03, DATA-04, DATA-05, COMPUTE-01, COMPUTE-02, COMPUTE-03, COMPUTE-04, COMPUTE-05, COMPUTE-06, COMPUTE-09, UI-01, UI-03, UI-04, UI-05, UI-06, TENANT-08, OBS-05, OBS-06, OBS-07, OBS-08
**Gap Closure:** Closes 20 orphaned requirements from v3.0 audit — code exists but lacks formal verification and traceability
**Success Criteria** (what must be TRUE):
  1. VERIFICATION.md exists for Phases 19, 20, 21, 22, 23, 24 with requirement-level pass/fail evidence
  2. All SUMMARY frontmatter includes correct `requirements_completed` fields
  3. REQUIREMENTS.md checkboxes are checked for all satisfied requirements
  4. Audit re-run shows 0 unsatisfied must-have requirements
**Plans:** 3/3 plans complete

Plans:
- [x] 27-01-PLAN.md — VERIFICATION.md for Phases 19, 20, 21 + fix SUMMARY frontmatter
- [x] 27-02-PLAN.md — VERIFICATION.md for Phases 22, 23, 24 + fix SUMMARY frontmatter
- [x] 27-03-PLAN.md — Update REQUIREMENTS.md checkboxes for all verified requirements

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
    │                             │                   │
    │                             │                   └──► Phase 26 (Tenant Context Wiring)
    │                             │
    │                             ├──► Phase 22 (CI/CD Pipelines)
    │                             │
    │                             └──► Phase 23 (Observability & Monitoring)
    │                                       │
    │                                       └──► Phase 24 (Tenant Admin UI)
    │
    Phase 25 (Milestone Validation) ──► Phase 27 (Verification & Traceability)
    Phase 26 (Tenant Context Wiring) ──► Phase 27
```

### Progress

**Execution Order:** 17 → 18 → 19 → 20 → 21 → 22 → 23 → 24

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 17. Infrastructure Foundation | 3/3 | Complete    | 2026-03-26 |
| 18. Authentication Migration | 3/3 | Complete   | 2026-03-26 |
| 19. Data Layer Migration | 1/3 | Complete    | 2026-03-26 |
| 20. Microservice Extraction & AKS | 2/3 | Complete |  2026-03-26 |
| 21. Tenant Lifecycle & Provisioning | 2/2 | Complete | 2026-03-26 |
| 22. CI/CD Pipelines | 2/2 | Complete | 2026-03-26 |
| 23. Observability & Monitoring | 2/2 | Complete    | 2026-03-26 |
| 24. Tenant Admin UI | 0/? | Not started | - |
| 25. Milestone Validation | 3/3 | Complete    | 2026-03-26 |
| 26. Tenant Context Wiring | 2/2 | Complete   | 2026-03-26 |
| 27. Verification & Traceability | 3/3 | Complete    | 2026-03-26 |

---

## Milestone 4: v4.0 — Architecture Pivot: Platform as Infrastructure Provider

**Goal:** Transform the platform from a "UI wrapper" for OpenClaw into an "infrastructure provider" — exposing OpenClaw's full native UI while keeping platform value-adds (multi-tenancy, Azure infra, per-group rules, monitoring, workflows).

### Overview

v4.0 pivots the platform architecture from wrapping OpenClaw behind a custom UI to providing infrastructure that makes OpenClaw better: multi-tenant isolation, universal token tracking, platform data services as MCP tools, and authenticated access to OpenClaw's native web UI. The critical path is Audit/Foundation → Token Proxy → MCP Servers → Auth Gateway → Dual-Mode, dictated by dependencies: infrastructure must be validated before building services, wildcard DNS/TLS must exist before the auth gateway, and all components must work before dual-mode validation.

### Phases

**Phase Numbering:** Continues from v3.0 (Phases 17-27).

- [x] **Phase 28: Infrastructure Audit & Foundation** — Validate provision-from-zero, resolve drift, establish wildcard DNS/TLS *(completed 2025-07-18)*
- [x] **Phase 29: Token Proxy** — Transparent LLM proxy with universal token tracking and per-tenant budgets *(completed 2025-07-16)*
- [x] **Phase 30: Platform MCP Servers** — Cosmos DB memory, AI Search, and group rules as native agent tools (completed 2026-04-04)
- [ ] **Phase 31: Auth Gateway & Native UI Access** — Authenticated subdomain routing to OpenClaw native UI
- [ ] **Phase 32: Dual-Mode Operation** — Validate platform UI and native UI work simultaneously with full parity

### Phase Details

#### Phase 28: Infrastructure Audit & Foundation
**Goal**: All infrastructure artifacts are validated against production, provision-from-zero works, and wildcard DNS/TLS is established for agent subdomains
**Depends on**: Nothing (first v4.0 phase)
**Requirements**: AUDIT-01, AUDIT-02, AUDIT-03, AUDIT-04, AUDIT-05, AUDIT-06
**Success Criteria** (what must be TRUE):
  1. User can run `az deployment group create` + `kubectl apply` from scratch and get a fully working platform identical to production
  2. Bicep templates match all deployed Azure resources — zero drift between templates and reality
  3. K8s manifests match all running workloads, ConfigMaps, and Secrets — zero drift
  4. Wildcard DNS record (`*.agents.{domain}`) resolves and wildcard TLS certificate is issued via cert-manager DNS-01 challenge
  5. Platform and tenant secrets are in separate Key Vaults — tenant pods can only access the tenant vault
  6. Existing tenant secrets are migrated to the tenant vault with backward-compatible fallback
**Plans**: 3 plans

Plans:
- [ ] 28-01-PLAN.md — Bicep infrastructure extensions (Cosmos DB v4.0 containers, DNS/domain/tenant KV modules)
- [ ] 28-02-PLAN.md — azd framework + K8s manifest drift fixes + cert-manager resources
- [ ] 28-03-PLAN.md — Key Vault separation backend wiring + tenant secret migration

#### Phase 29: Token Proxy
**Goal**: All LLM traffic is transparently proxied through a centralized gateway with universal token tracking and per-tenant budget controls
**Depends on**: Phase 28 (Cosmos DB `token_logs` container, validated infrastructure)
**Requirements**: PROXY-01, PROXY-02, PROXY-03, PROXY-04, PROXY-05
**Success Criteria** (what must be TRUE):
  1. All LLM requests flow through the proxy transparently — agent behavior is unchanged
  2. Token usage is captured from streaming responses via `stream_options.include_usage` without client-side counting
  3. Every LLM request's token usage is logged to Cosmos DB with tenant_id and agent_id attribution
  4. Tenant admins can set token budget limits and receive alerts when thresholds are reached
  5. New OpenClaw agents automatically route LLM traffic through the proxy via CR `baseUrl` configuration
**Plans**: 3 plans

Plans:
- [x] 29-01-PLAN.md — Proxy core service (FastAPI + TokenLogRepository + Dockerfile)
- [x] 29-02-PLAN.md — K8s manifests (Deployment, Service, HPA, PDB)
- [x] 29-03-PLAN.md — Budget API + openclaw_service.py proxy wiring + unit tests

#### Phase 30: Platform MCP Servers
**Goal**: Agents can access platform data services (memory, search, group rules) as native MCP tools without any UI changes
**Depends on**: Phase 28 (Cosmos DB DiskANN vector index, validated infrastructure)
**Requirements**: MCPSRV-01, MCPSRV-02, MCPSRV-03, MCPSRV-04, MCPSRV-05, MCPSRV-06, MCPSRV-07
**Success Criteria** (what must be TRUE):
  1. Agents can search and store memories via MCP tools backed by Cosmos DB with DiskANN vector search
  2. Agents can query Azure AI Search indexes via MCP tools for document retrieval
  3. Agents can retrieve per-group instructions and agent configuration via MCP tools
  4. MCP server URLs are auto-injected into OpenClaw CRs on agent deploy
  5. Cosmos DB `agent_memories` container has DiskANN vector index enabled and operational
**Plans:** 3/3 plans complete
Plans:
- [x] 30-01-PLAN.md — MCP server core + memory tools (store, search, structured, embedding)
- [x] 30-02-PLAN.md — Platform config tools (group instructions, agent config)
- [x] 30-03-PLAN.md — Infrastructure + deployment (Cosmos containers, Dockerfile, K8s, OpenClaw injection)

#### Phase 31: Auth Gateway & Native UI Access
**Goal**: Users can access OpenClaw's full native web UI for any authorized agent via authenticated subdomain routing
**Depends on**: Phase 28 (wildcard DNS/TLS)
**Requirements**: NATIVEUI-01, NATIVEUI-02, NATIVEUI-03, NATIVEUI-04, NATIVEUI-05
**Success Criteria** (what must be TRUE):
  1. User can access any agent's full native UI at `agent-{id}.agents.{domain}` with all features working
  2. User is authenticated via Entra ID OIDC before reaching any OpenClaw UI — unauthenticated requests are rejected
  3. User can only access agents belonging to their tenant — cross-tenant access is blocked
  4. WebSocket-based features (live chat, real-time updates) work through the auth proxy without degradation
  5. User can click "Open Agent Console" in platform frontend to open the native UI in a new tab
**Plans:** 3 plans

Plans:
- [ ] 31-01-PLAN.md — Auth gateway FastAPI service (OIDC, sessions, proxy, WebSocket)
- [ ] 31-02-PLAN.md — K8s infrastructure (Deployment, Ingress, postprovision, NetworkPolicy)
- [ ] 31-03-PLAN.md — OpenClaw gateway config + frontend "Open Agent Console" button

**UI hint**: yes

#### Phase 32: Dual-Mode Operation
**Goal**: Platform UI and OpenClaw native UI work simultaneously with full feature parity — token tracking, group rules, and all platform features function across both paths
**Depends on**: Phase 29 (token tracking), Phase 30 (MCP tools), Phase 31 (native UI access)
**Requirements**: DUAL-01, DUAL-02, DUAL-03, DUAL-04
**Success Criteria** (what must be TRUE):
  1. User can interact with the same agent from both platform UI and OpenClaw native UI concurrently without conflicts
  2. Token tracking works identically regardless of which UI path is used — Cosmos DB logs capture usage from both
  3. Per-group rules function via both platform system message injection (platform path) and MCP tool calls (native path)
  4. All existing platform features (workflows, evaluations, marketplace, observability) continue working with zero regressions
**Plans**: TBD
**UI hint**: yes

### Phase Dependencies

```
Phase 28 (Infrastructure Audit & Foundation)
    │
    ├──► Phase 29 (Token Proxy)
    │
    ├──► Phase 30 (Platform MCP Servers)
    │
    └──► Phase 31 (Auth Gateway & Native UI Access)
              │
              ▼
         Phase 32 (Dual-Mode Operation)
         [depends on 29, 30, 31]
```

**Execution order:** 28 → 29 → 30 → 31 → 32 (sequential despite 29/30 being parallelizable — solo developer workflow)

**Parallelization note:** Phases 29 and 30 have no dependency on each other. Both modify `openclaw_service.py` but in different sections (`baseUrl` vs `mcpServers`). A team could run them in parallel; solo execution proceeds sequentially for simplicity.

### Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|----------|
| 28. Infrastructure Audit & Foundation | 0/? | Not started | - |
| 29. Token Proxy | 0/? | Not started | - |
| 30. Platform MCP Servers | 3/3 | Complete    | 2026-04-04 |
| 31. Auth Gateway & Native UI Access | 0/? | Not started | - |
| 32. Dual-Mode Operation | 0/? | Not started | - |

---
*Roadmap created: 2026-03-23*
*Last updated: 2026-04-04 after v4.0 roadmap creation*
