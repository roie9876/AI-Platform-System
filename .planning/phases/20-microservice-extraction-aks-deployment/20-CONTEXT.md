# Phase 20: Microservice Extraction & AKS Deployment - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Split the monolith FastAPI backend into 5 microservices (api-gateway, agent-executor, workflow-engine, tool-executor, mcp-proxy) and deploy them to AKS with per-tenant namespace isolation, NetworkPolicy, ResourceQuota, LimitRange, HPA, and health checks.

</domain>

<decisions>
## Implementation Decisions

### Agent's Discretion
All implementation details are at the agent's discretion. The user deferred all gray areas. The following are the key decision areas and the agent should make reasonable choices:

- **D-01:** Service boundary mapping — how to partition the current 24 API routes and 18 services across the 5 microservices (api-gateway, agent-executor, workflow-engine, tool-executor, mcp-proxy). The 5 service names are locked per ROADMAP.md (COMPUTE-08).
- **D-02:** Inter-service communication pattern — sync HTTP, gRPC, or async messaging between extracted microservices. Currently agent-executor imports workflow-engine and tool-executor directly.
- **D-03:** Shared code & repo structure — how to handle models, repositories, core config, and middleware that are currently shared across all services. Monorepo with shared package, duplicated code, or other approach.
- **D-04:** K8s manifest approach — Helm charts vs Kustomize overlays vs raw YAML for per-tenant namespace deployments and how tenant-specific values (quotas, replicas) are parameterized.
- **D-05:** Ingress & tenant routing — ingress controller choice (NGINX, Traefik, Azure AGIC) and how tenant context is propagated across service boundaries.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture
- `docs/architecture/HLD-ARCHITECTURE.md` — Control Plane vs Runtime Plane architecture, service responsibilities
- `.planning/REQUIREMENTS.md` §Compute Isolation (AKS) — COMPUTE-01 through COMPUTE-09 requirements

### Infrastructure (from Phase 17)
- `infra/main.bicep` — AKS, ACR, VNet orchestrator already provisioned
- `infra/modules/aks.bicep` — AKS cluster config (system + user node pools, Azure CNI Overlay)
- `infra/modules/acr.bicep` — ACR with Managed Identity pull
- `infra/parameters/prod.bicepparam` — Production sizing parameters

### Current Monolith (extraction source)
- `backend/app/main.py` — Single FastAPI app with all routes and middleware
- `backend/app/api/v1/router.py` — All 24 API route registrations
- `backend/app/services/` — 18 service modules to be distributed across microservices
- `backend/app/repositories/` — Cosmos DB repository layer (shared by all services)
- `backend/app/middleware/tenant.py` — Tenant middleware with Entra ID token validation
- `backend/app/core/` — Config, database, security modules
- `backend/Dockerfile` — Current single-image Dockerfile

### Auth (from Phase 18)
- `backend/app/core/security.py` — Entra ID token validation, user context extraction
- `backend/app/middleware/tenant.py` — TenantMiddleware with Bearer token handling

### Data Layer (from Phase 19)
- `backend/app/repositories/cosmos_client.py` — Cosmos DB async client
- `backend/app/repositories/base.py` — Base repository with tenant_id partition key

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TenantMiddleware` — Already validates Entra ID tokens and extracts tenant_id; can be reused in each microservice
- `cosmos_client.py` — Shared Cosmos DB client; each microservice will need its own instance pointing to relevant containers
- `base.py` repository — Base CRUD operations with tenant_id scoping; portable to any microservice
- `Dockerfile` — Simple Python 3.12-slim base; can be templated for each microservice

### Established Patterns
- **Tenant isolation via middleware** — All requests filtered by tenant_id from Entra ID JWT claims
- **Repository pattern** — All data access goes through repository classes, not direct DB calls
- **Service layer** — Business logic in service classes, API routes are thin wrappers
- **Cosmos DB async SDK** — All repos use async operations with partition key = tenant_id

### Integration Points
- `router.py` registers all 24 API routes — this is the primary decomposition point
- `AgentExecutionService` imports `WorkflowEngine`, `ToolExecutor`, `MCPClient` directly — these become inter-service calls after extraction
- `WorkflowEngine` imports `AgentExecutionService` — circular dependency that must be resolved via inter-service communication
- AKS cluster already provisioned with system + user node pools (Phase 17)
- ACR ready for image pushes with AcrPull role for AKS (Phase 17)

### Natural Service Boundaries (from code analysis)
- **api-gateway**: auth, agents CRUD, model-endpoints, catalog, marketplace, observability, evaluations, azure-* routes
- **agent-executor**: chat (agent execution), threads, memories — the runtime execution loop
- **workflow-engine**: workflows routes + WorkflowEngine service
- **tool-executor**: tools routes + ToolExecutor service + data-sources + ai-services + knowledge
- **mcp-proxy**: mcp-servers, mcp-discovery, agent-mcp-tools routes + MCPClient service

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 20-microservice-extraction-aks-deployment*
*Context gathered: 2026-03-26*
