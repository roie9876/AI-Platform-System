# Feature Landscape — v3.0 Production Multi-Tenant Infrastructure

**Domain:** Multi-tenant SaaS infrastructure for AI Agent Platform
**Researched:** 2026-03-26
**Scope:** NEW infrastructure features only — existing agent CRUD, tool marketplace, RAG, orchestration, observability, evaluation, CLI, MCP features are NOT repeated.

**Sources:**
- Microsoft Azure Architecture Center: [Architect multitenant solutions on Azure](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/overview) — HIGH confidence
- Microsoft: [Tenancy models for a multitenant solution](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/considerations/tenancy-models) — HIGH confidence
- Microsoft: [Tenant lifecycle considerations](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/considerations/tenant-lifecycle) — HIGH confidence
- Microsoft: [Use AKS in a multitenant solution](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/service/aks) — HIGH confidence
- Microsoft: [AKS cluster isolation best practices](https://learn.microsoft.com/en-us/azure/aks/operator-best-practices-cluster-isolation) — HIGH confidence
- Microsoft: [Multitenancy and Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/service/cosmos-db) — HIGH confidence
- Existing codebase: `backend/app/models/tenant.py`, `backend/app/middleware/tenant.py`, `backend/app/models/azure_*.py` — HIGH confidence

**Platform context:** Internal enterprise platform (STU-MSFT), 2-5 tenants, no billing system needed. Namespace-per-tenant AKS isolation and Cosmos DB partition-by-tenant_id are decided architecture choices.

---

## 1. Tenant Lifecycle

Features for onboarding, provisioning, managing, suspending, and offboarding tenants.

**Depends on existing:** Tenant model (`tenants` table with name, slug, is_active), tenant middleware (JWT with tenant_id claim).

### Table Stakes

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Tenant registration API | Medium | POST /api/v1/tenants — create tenant record with name, slug, admin contact. Validates uniqueness, assigns UUID. | Existing tenant model |
| Automated namespace provisioning | High | On tenant creation, automatically create K8s namespace, apply NetworkPolicy, ResourceQuota, LimitRange. | AKS cluster, Bicep IaC |
| Tenant status management | Low | Lifecycle states: `provisioning` → `active` → `suspended` → `deactivated` → `deleted`. API to transition between states. | Existing tenant model (extend is_active to status enum) |
| Tenant suspension | Medium | Soft-disable: block API requests for suspended tenants at middleware layer, retain data, keep namespace but scale pods to 0. | Tenant middleware, K8s API |
| Tenant configuration | Low | Per-tenant settings: display name, logo URL, allowed model providers, token quotas, feature flags. | Existing tenant model (add JSONB config column) |
| Tenant data seeding | Medium | On creation, seed default catalog entries, built-in tools, default policies so tenant starts with usable platform. | Existing catalog_entries, tools, policies |
| Tenant admin user creation | Medium | Auto-create admin user for new tenant with Entra ID mapping. First user bootstraps the tenant workspace. | Entra ID integration |

### Differentiators

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Self-service tenant onboarding wizard | High | Multi-step UI flow: organization name → Entra ID connection → model endpoint setup → first agent creation. Guided experience. | Tenant registration API, Entra ID, frontend |
| Tenant cloning | Medium | Clone a tenant's configuration (not data) as a template for new tenants. Useful for dev/staging environments. | Tenant configuration |
| Scheduled deactivation | Low | Auto-suspend tenants after N days of inactivity or trial expiration. | Tenant status management |
| Tenant data export | High | Export all tenant data (agents, configs, threads, evaluations) as portable JSON archive before offboarding. | All data models |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Billing/payment integration | Internal enterprise platform — no customer billing. Adds massive scope with zero value for 2-5 internal teams. | Track usage for showback dashboards only. |
| Multi-region tenant placement | 2-5 tenants in single Azure region. Multi-region adds Cosmos DB geo-replication cost and AKS fleet complexity disproportionate to scale. | Single-region deployment; add multi-region only if a tenant requires data residency. |
| Tenant-level SLA tiers (Basic/Standard/Premium) | Only 2-5 tenants, all internal enterprise. Tiered isolation adds engineering complexity for no business differentiation. | Uniform namespace-per-tenant isolation for all tenants. |

---

## 2. Infrastructure Provisioning (IaC)

Automated Azure resource provisioning via Bicep modules.

**Depends on existing:** Azure subscription integration (AzureSubscription model, ARM service).

### Table Stakes

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Core Bicep modules | High | Modular Bicep for: AKS cluster, ACR, Cosmos DB account + database, VNet + subnets, Managed Identities, Key Vault, Log Analytics workspace. | Azure CLI, Azure subscription |
| VNet with subnet topology | Medium | Hub VNet with subnets for AKS nodes, AKS pods (if Azure CNI), private endpoints (Cosmos DB, ACR, Key Vault). NSGs per subnet. | Bicep modules |
| AKS cluster provisioning | High | AKS with: system node pool + user node pool, Azure CNI Overlay (for pod IP efficiency), Kubernetes RBAC enabled, Entra ID integration, Azure Monitor addon. | VNet, Bicep modules |
| ACR provisioning | Low | Azure Container Registry with admin disabled, Managed Identity pull from AKS (AcrPull role assignment). | Bicep modules |
| Cosmos DB account + database | Medium | Cosmos DB NoSQL account with: serverless or autoscale provisioning, `aiplatform` database, containers with `/tenant_id` partition key. | Bicep modules |
| Key Vault provisioning | Low | Azure Key Vault for secrets (model API keys, connection strings). RBAC-based access, no access policies. | Bicep modules, Managed Identities |
| Managed Identity setup | Medium | System-assigned MI for AKS, user-assigned MIs for workloads (Cosmos DB access, Key Vault access, ACR pull). AKS Workload Identity federation. | Bicep modules |
| Environment parameter files | Low | Bicep parameter files for dev, staging, prod environments. Different SKUs, node counts, Cosmos DB throughput settings per environment. | Bicep modules |
| Deployment script (main.bicep) | Medium | Orchestrator module that deploys all resources in correct dependency order. Idempotent, re-runnable. | All Bicep modules |

### Differentiators

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Tenant namespace Bicep module | High | Bicep module that provisions K8s namespace + RBAC + NetworkPolicy + ResourceQuota for a new tenant via AKS command invoke or deployment script. | AKS cluster, tenant provisioning API |
| Preview/staging environment stack | Medium | Bicep parameter file for a minimal-cost staging stack (single-node AKS, serverless Cosmos DB, B-series VMs) for pre-production validation. | Bicep modules |
| Infrastructure drift detection | Medium | GitHub Actions workflow that runs `az deployment what-if` against the live environment to detect manual changes. | Bicep modules, CI/CD pipeline |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Terraform dual-stack | Decided on Bicep in PROJECT.md. Maintaining both Bicep and Terraform doubles IaC complexity for no benefit on Azure-only deployment. | Bicep only. |
| Per-tenant AKS clusters | Overkill for 2-5 tenants. Each AKS cluster costs $73/month (uptime SLA) + node costs. Namespace isolation is sufficient. | Single shared AKS cluster with namespace-per-tenant. |
| Dynamic infrastructure creation from API | Tenant provisioning should create K8s namespaces (control plane), NOT Azure resources. Bicep manages infrastructure; API manages K8s resources on existing infra. | Static infrastructure via Bicep + dynamic namespaces via K8s API. |

---

## 3. Data Isolation (Cosmos DB)

Replace PostgreSQL/SQLAlchemy with Cosmos DB NoSQL, partitioned by tenant_id.

**Depends on existing:** All 13 SQLAlchemy models, 13 Alembic migrations, entire service layer, all API endpoints.

### Table Stakes

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Cosmos DB repository layer | Very High | New data access layer replacing SQLAlchemy. `CosmosRepository` base class with async CRUD operations, automatic tenant_id injection, partition key enforcement. | azure-cosmos SDK 4.15+ |
| Container design | High | Map existing 15+ entity types into Cosmos DB containers. Recommended: single-container-per-entity-group with type discriminator, `/tenant_id` as partition key on all containers. | Cosmos DB account |
| Partition key enforcement | High | Middleware/repository that ALWAYS includes `tenant_id` as partition key in queries. No cross-partition queries allowed without explicit admin override. Prevents data leakage. | Cosmos repository layer |
| Data model migration | Very High | Convert SQLAlchemy models to Cosmos DB document schemas. Denormalize where appropriate (embed agent config versions in agent documents). Handle UUID→string ID conversion. | All existing models |
| Hierarchical partition keys | Medium | Use hierarchical partition keys (`/tenant_id` → `/entity_type`) on containers that store multiple entity types. Enables efficient single-tenant queries without fan-out. | Cosmos DB container design |
| Cross-tenant query prevention | High | Application-layer enforcement: reject any query that doesn't specify `tenant_id`. Repository layer validates partition key is always present. Admin queries require explicit elevated scope. | Cosmos repository layer |
| Optimistic concurrency | Medium | Use Cosmos DB ETags (`_etag`) for optimistic concurrency control on writes. Replaces SQLAlchemy's versioning. | Cosmos repository layer |
| Managed Identity auth for Cosmos | Medium | Authenticate to Cosmos DB using Workload Identity (Managed Identity), not connection strings. Use `DefaultAzureCredential` in SDK. | Managed Identity setup, AKS Workload Identity |

### Differentiators

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Change feed for event streaming | High | Cosmos DB change feed to trigger downstream events: index updates to Azure AI Search, cache invalidation, audit log emission. | Cosmos DB container, event processing |
| Tenant data size monitoring | Medium | Track per-tenant storage consumption and document count. Alert when a tenant approaches partition size limits (20 GB logical partition). | Cosmos repository layer, observability |
| Soft-delete with TTL | Medium | Deleted documents marked with `_deleted: true` and TTL set for 30-day retention, enabling recovery. Cosmos DB auto-purges after TTL expiry. | Cosmos repository layer |
| Bulk import/export per tenant | High | Admin API to export all documents for a tenant as JSON Lines, or bulk-import documents for tenant data migration. | Cosmos repository layer |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Database-per-tenant | Massive operational overhead for 2-5 tenants. Partition-key-per-tenant is Microsoft's recommendation for ≤50 tenants with similar workloads. | Single database, shared containers, partition by tenant_id. |
| Account-per-tenant | Costs $$$. Each account has minimum throughput. Only justified for tenants requiring customer-managed encryption keys or geo-replication. | Single account for all tenants. |
| ORM abstraction over Cosmos | Cosmos DB is document-native. Trying to bolt an ORM on top fights the data model. Direct SDK with repository pattern is cleaner. | Repository pattern with Cosmos SDK directly. |
| Relational joins via stored procedures | Cosmos DB is not PostgreSQL. Cross-document joins should be avoided. Denormalize data at write time or use materialized views via change feed. | Denormalization + change feed for cross-entity queries. |

---

## 4. Authentication & Authorization (Entra ID)

Replace JWT-only auth with Microsoft Entra ID enterprise SSO and RBAC.

**Depends on existing:** User model, JWT middleware (`tenant.py`), auth endpoints (`/api/v1/auth/login`, `/api/v1/auth/register`).

### Table Stakes

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Entra ID OIDC integration | High | Replace homegrown JWT login with Entra ID OIDC flow. Backend validates Entra ID tokens (via `msal` or `azure-identity`). Frontend redirects to Entra ID for login. | Entra ID app registration, Managed Identity |
| Token validation middleware | Medium | Replace current `jwt.decode` with Entra ID token validation: verify issuer, audience, signature against Entra ID JWKS endpoint. Extract `oid`, `tid`, `roles` claims. | Entra ID OIDC |
| Tenant mapping from Entra ID | Medium | Map Entra ID `tid` (Azure AD tenant ID) to platform tenant_id. Lookup table: `entra_tenant_id` → `platform_tenant_id`. Auto-resolve on token validation. | Tenant model extension |
| Role-Based Access Control (RBAC) | High | Define platform roles: `platform_admin`, `tenant_admin`, `tenant_member`, `tenant_viewer`. Map Entra ID app roles to platform roles. Enforce on every API endpoint. | Entra ID app registration, role model |
| Managed Identity for backend services | Medium | Backend authenticates to Cosmos DB, Key Vault, ACR, and Azure AI Search using Workload Identity (Managed Identity) instead of API keys/connection strings. | AKS Workload Identity, Bicep Managed Identity setup |
| Secure secret storage | Medium | Move encrypted API keys, model endpoint credentials from database columns to Azure Key Vault. Backend retrieves at runtime via Managed Identity. | Key Vault provisioning |
| Session management | Medium | Replace httpOnly cookie JWT with Entra ID session tokens. Support token refresh via MSAL. Handle token expiration gracefully in frontend. | Entra ID OIDC, frontend auth |

### Differentiators

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Group-based access control | Medium | Map Entra ID security groups to platform RBAC roles. Admin adds users to groups in Entra ID portal; platform auto-discovers role assignments. | Entra ID groups, Microsoft Graph API |
| Conditional access policy support | Low | Respect Entra ID conditional access policies (MFA, device compliance, location-based). Platform doesn't need to implement — Entra ID enforces at login. | Entra ID premium features |
| Service principal for CLI | Medium | CLI authenticates via device code flow or service principal with certificate. Maps to a machine tenant_id for automation/CI scenarios. | CLI auth module, Entra ID app registration |
| API key fallback for external integrations | Low | Optional API key auth for MCP server connections and webhook endpoints where Entra ID flow isn't practical. Keys scoped to tenant, stored in Key Vault. | Key Vault, API key model |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Custom identity provider | Entra ID is the decided identity provider. Building a custom auth system or supporting Okta/Auth0 adds scope with no internal enterprise value. | Entra ID only for v3.0. |
| Fine-grained resource-level permissions | ABAC or per-resource ACLs (e.g., "user X can access agent Y but not agent Z") is enterprise complexity beyond current need. 4 role levels are sufficient for 2-5 tenants. | Role-based access at tenant level, not resource level. |
| Multi-factor authentication (custom) | MFA belongs in Entra ID, not in the platform. Entra ID conditional access handles this natively. | Rely on Entra ID conditional access for MFA enforcement. |

---

## 5. Compute Isolation (AKS)

Namespace-per-tenant with network policies, resource quotas, and pod security.

**Depends on existing:** Docker Compose setup, Dockerfile, monolithic FastAPI backend.

### Table Stakes

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Namespace-per-tenant creation | Medium | K8s namespace for each tenant (`tenant-{slug}`). Created by provisioning API. Contains all K8s resources for that tenant's workloads. | AKS cluster, tenant provisioning API |
| NetworkPolicy per namespace | Medium | Default-deny ingress/egress between tenant namespaces. Allow: ingress from API gateway namespace, egress to Cosmos DB / Key Vault private endpoints, egress to model endpoints. | AKS network policy engine (Azure or Calico) |
| ResourceQuota per namespace | Low | CPU/memory limits per tenant namespace. Prevents noisy neighbor: e.g., 4 CPU / 8Gi memory per tenant. Configurable per tenant tier. | Namespace creation |
| LimitRange per namespace | Low | Default container resource requests/limits within tenant namespace. Ensures every pod has resource bounds even if not explicitly set. | Namespace creation |
| Pod security standards | Low | Apply Kubernetes Pod Security Standards (restricted or baseline profile) to tenant namespaces. Prevent privilege escalation, host networking, hostPath mounts. | AKS cluster, namespace creation |
| Microservice container images | High | Split monolith into container images: `api-gateway`, `agent-executor`, `workflow-engine`, `tool-executor`, `mcp-server-proxy`. Each with Dockerfile, health check, graceful shutdown. | Existing monolith code, ACR |
| Deployment manifests | High | K8s Deployment + Service + HPA manifests for each microservice. Parameterized by tenant (namespace), replicas, resource limits. Kustomize or Helm for templating. | Container images, AKS cluster |
| Horizontal Pod Autoscaler (HPA) | Medium | HPA on agent-executor and workflow-engine: scale pods based on CPU/memory or custom metrics (queue depth, concurrent executions). | Deployment manifests, metrics server |
| Service account per tenant | Medium | Dedicated K8s ServiceAccount per tenant namespace, annotated with Workload Identity client ID. Pods authenticate to Azure via this identity. | AKS Workload Identity, Managed Identity |

### Differentiators

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Pod disruption budgets | Low | PDB per microservice ensuring minimum available replicas during node drains and upgrades. Prevents tenant downtime during maintenance. | Deployment manifests |
| Istio service mesh (optional) | Very High | mTLS between services, fine-grained authorization policies, traffic management. Strong tenant isolation at L7. Heavy resource overhead. | AKS Istio addon |
| Node pool per tenant tier | Medium | Dedicated node pools with taints/tolerations for premium tenants needing guaranteed compute. System node pool for shared infra. | AKS cluster, node pool Bicep |
| Priority classes | Low | K8s PriorityClass resources to ensure critical services (API gateway, workflow engine) survive resource pressure before agent executors. | Deployment manifests |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Cluster-per-tenant | Massive cost ($73/mo per cluster uptime SLA + node costs) and operational overhead for 2-5 tenants. Microsoft recommends logical isolation for trusted tenants. | Single cluster, namespace-per-tenant. |
| Pod sandboxing (Kata containers) | Adds latency, limits to Linux Azure Linux 3.0, no Defender support. Overkill for internal trusted tenants. | Standard security contexts + NetworkPolicy. |
| Custom CNI plugins | Azure CNI Overlay handles pod IP efficiency. Custom CNI (Cilium standalone, Calico CNI) adds operational complexity. | Azure CNI Overlay with Azure network policies or Calico for NetworkPolicy only. |

---

## 6. Deployment & CI/CD

GitHub Actions pipelines for building, testing, and deploying to AKS.

**Depends on existing:** GitHub repository, Docker Compose, existing test suite.

### Table Stakes

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Dockerfile per microservice | Medium | Multi-stage Dockerfiles: build stage (install deps, run tests) → production stage (minimal image, non-root user, health check). One per microservice. | Microservice split |
| GitHub Actions build pipeline | Medium | On push to main: lint → test → build Docker images → push to ACR with SHA + `latest` tags. Parallel builds per microservice. | ACR, GitHub Actions |
| GitHub Actions deploy pipeline | High | On merge to main (or manual trigger): pull images from ACR → apply K8s manifests to AKS → rolling update with health check verification. | AKS cluster, build pipeline, K8s manifests |
| Rolling update strategy | Low | K8s Deployment with `RollingUpdate` strategy: maxSurge=1, maxUnavailable=0. Zero-downtime deployments for each microservice. | Deployment manifests |
| Environment-specific configs | Medium | K8s ConfigMaps and Secrets (from Key Vault via CSI driver) per environment. Separate GitHub Actions environments for staging/prod with approval gates. | Key Vault, K8s manifests |
| Health check endpoints | Low | `/health` (liveness) and `/ready` (readiness) endpoints per microservice. K8s probes configured in Deployment manifests. | Microservice code |
| Smoke tests post-deploy | Medium | Post-deployment step: hit health endpoints, run critical API path tests, auto-rollback if smoke tests fail. | Deploy pipeline, health endpoints |
| Container vulnerability scanning | Low | GitHub Actions step with Trivy or Microsoft Defender for Containers to scan images before push to ACR. Fail pipeline on critical CVEs. | Build pipeline |

### Differentiators

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Canary deployments | High | Deploy new version to single tenant namespace first, monitor error rates, promote or rollback. Requires traffic splitting or namespace-scoped deployments. | Deploy pipeline, observability |
| Infrastructure CI (Bicep validation) | Medium | Validate Bicep on PR: `az bicep build` + `az deployment what-if` in GitHub Actions. Catch IaC errors before merge. | Bicep modules, GitHub Actions |
| GitOps with Flux | High | AKS Flux addon for declarative K8s state management. Git repo is source of truth for K8s manifests. Auto-reconciles drift. | AKS Flux addon, K8s manifests |
| Database migration automation | Medium | CI step to apply Cosmos DB container/index changes via deployment script. Version-controlled schema evolution (index policies, stored procedures). | Cosmos DB, deploy pipeline |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Azure DevOps pipelines | GitHub Actions decided. Running both GitHub Actions and Azure DevOps adds context switching and configuration duplication. | GitHub Actions only. |
| Blue/green AKS clusters | Requires 2x cluster cost. For 2-5 tenants, rolling updates with health checks provide sufficient zero-downtime guarantees. | Rolling updates per deployment with PDB + health checks. |
| Auto-deploy on push to all environments | Unsafe for production. Staging should auto-deploy; production requires manual approval gate. | Staging auto-deploy, production manual trigger with approval. |

---

## 7. Observability

Per-tenant monitoring, distributed tracing, and alerting via Azure Monitor stack.

**Depends on existing:** Execution logs, cost tracking, agent traces, observability dashboards (frontend).

### Table Stakes

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Application Insights integration | Medium | Instrument FastAPI backend with OpenTelemetry → Application Insights. Auto-collect: HTTP requests, dependencies, exceptions, custom metrics. | App Insights resource (Bicep), OpenTelemetry SDK |
| Distributed tracing | High | End-to-end trace IDs across microservices: API gateway → agent executor → tool executor → model endpoint. Correlate spans across services. | OpenTelemetry, App Insights |
| Per-tenant metrics | Medium | Tag all telemetry with `tenant_id` custom dimension. Enables KQL queries scoped to single tenant: request rates, error rates, latency percentiles, token usage. | OpenTelemetry, App Insights |
| Structured logging | Medium | JSON-structured logs with `tenant_id`, `agent_id`, `trace_id`, `span_id` in every log entry. Ship to Log Analytics workspace via Azure Monitor agent. | Log Analytics workspace (Bicep) |
| Container/pod monitoring | Low | AKS monitoring addon: Container Insights for node/pod CPU, memory, network metrics. Per-namespace dashboards for tenant isolation visibility. | AKS monitoring addon (Bicep) |
| Health check monitoring | Low | Azure Monitor alerts on health check endpoint failures. Alert on pod restart loops (CrashLoopBackOff). | Health endpoints, Azure Monitor alerts |
| Error rate alerting | Medium | Azure Monitor alert rules: trigger when 5xx error rate > threshold per tenant, when Cosmos DB RU consumption > 80%, when pod CPU > 90%. | App Insights, Azure Monitor alerts |
| Log Analytics workspace | Low | Central Log Analytics workspace receiving: App Insights telemetry, AKS container logs, Cosmos DB diagnostics, Key Vault audit logs. | Bicep module |

### Differentiators

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Per-tenant usage dashboards | High | Azure Workbooks or Managed Grafana dashboards showing per-tenant: API call volume, agent execution count, token consumption, error rates, cost estimates. | App Insights, per-tenant metrics |
| Anomaly detection | Medium | Azure Monitor smart alerts: auto-detect anomalous patterns in tenant request rates, error rates, latency. No manual threshold configuration needed. | App Insights, Azure Monitor |
| Cost attribution per tenant | Medium | Correlate Cosmos DB RU consumption + model API token usage + compute time to generate per-tenant cost breakdown. Feed into existing cost dashboards. | Per-tenant metrics, existing cost tracking |
| SLO tracking | Medium | Define and track Service Level Objectives per tenant: availability (99.9%), latency (p95 < 2s), error rate (< 1%). SLI/SLO dashboards. | Per-tenant metrics, Azure Workbooks |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Datadog/Splunk/New Relic | Microsoft-first architecture. Azure Monitor + App Insights + Log Analytics provide full observability stack natively. Third-party adds cost and integration overhead. | Azure Monitor stack (App Insights + Log Analytics + Azure Workbooks). |
| Per-tenant Log Analytics workspaces | 2-5 tenants don't justify separate workspaces. Single workspace with tenant_id dimension provides sufficient isolation for queries. | Single workspace, filter by tenant_id in KQL queries. |
| Custom metrics aggregation service | Azure Monitor handles metric aggregation natively. Building a custom aggregator duplicates functionality. | Use Azure Monitor metrics + KQL in Log Analytics. |

---

## 8. Tenant Admin UI

UI for platform admins to manage tenants, and per-tenant scoped views for tenant users.

**Depends on existing:** Next.js frontend, React dashboard components, agent management UI, observability dashboards.

### Table Stakes

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Tenant selector | Medium | Global tenant context switcher in the top navigation bar. Platform admins see all tenants; tenant users see only their tenant(s). Persisted in session/URL. | Entra ID RBAC, frontend auth |
| Tenant-scoped views | Medium | All existing UI pages (agents, tools, data sources, workflows, evaluations, marketplace) automatically filter by selected tenant. No cross-tenant data leakage in UI. | Tenant selector, API tenant scoping |
| Platform admin dashboard | High | Admin-only page: list all tenants, their status, resource usage, agent counts, active user counts. CRUD operations on tenants (create, suspend, reactivate). | Tenant registration API, RBAC |
| Tenant onboarding flow | High | Step-by-step wizard for creating a new tenant: org name → slug → Entra ID connection → initial admin user → model endpoint → review & create. Progress indicators. | Tenant registration API, Entra ID |
| Tenant settings page | Medium | Per-tenant configuration: display name, logo, allowed features, token quotas, model endpoint whitelist. Accessible to tenant admins only. | Tenant configuration API, RBAC |
| User management within tenant | Medium | Tenant admins can view users, assign roles (admin/member/viewer), invite new users. User list from Entra ID group membership. | Entra ID, Microsoft Graph API |
| Tenant usage summary | Medium | Per-tenant page showing: API call volume (7d/30d), agent execution count, token consumption, cost estimate, top agents by usage. | Per-tenant metrics, observability APIs |

### Differentiators

| Feature | Complexity | Description | Dependencies |
|---------|-----------|-------------|--------------|
| Tenant health status indicators | Medium | Traffic light indicators on tenant cards: green (healthy), yellow (warnings), red (errors). Based on real-time error rates and resource usage. | Observability integration |
| Multi-tenant comparison view | Medium | Platform admin view comparing all tenants side-by-side: resource usage, agent counts, error rates. Identify underperforming or overloaded tenants. | Platform admin dashboard, observability |
| Tenant activity audit log | Medium | Searchable log of all admin actions per tenant: user additions, config changes, agent deployments, suspension events. | Audit logging, structured logs |
| Tenant quota management UI | Low | Visual editor for per-tenant resource quotas: max agents, max model endpoints, max concurrent executions, token budget. | Tenant configuration API |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Per-tenant branded portal | Custom domains, logos, CSS themes per tenant is B2C SaaS complexity. Internal platform doesn't need tenant-branded UIs. | Single platform UI with tenant selector. |
| Tenant self-provisioning infrastructure | Tenants should not provision Azure resources. IaC is platform team responsibility. Tenants configure agents and tools, not infrastructure. | Platform admin provisions tenants; tenants configure platform features only. |
| In-app chat/ticketing for tenants | Support ticketing is orthogonal to the platform. Internal teams use existing enterprise tools (Teams, ServiceNow). | Link to existing support channels. |

---

## Feature Dependencies

```
Bicep IaC Foundation
 ├── AKS Cluster ─────────────┐
 │    ├── Namespace-per-tenant │
 │    ├── NetworkPolicy        │
 │    ├── ResourceQuota        │
 │    ├── Deployment Manifests │
 │    └── HPA                  │
 ├── ACR ──────────────────────┤
 ├── Cosmos DB Account ────────┤── Cosmos Repository Layer
 │    └── Containers           │    ├── Partition Key Enforcement
 │                             │    ├── Data Model Migration
 │                             │    └── Cross-tenant Prevention
 ├── Key Vault ────────────────┤
 ├── Managed Identities ───────┤── Workload Identity
 └── Log Analytics ────────────┤
      └── App Insights ────────┘── Per-tenant Metrics

Entra ID App Registration
 ├── OIDC Integration
 ├── Token Validation Middleware
 ├── RBAC (Roles)
 └── Tenant Mapping

Microservice Split (depends on all above)
 ├── api-gateway
 ├── agent-executor
 ├── workflow-engine
 ├── tool-executor
 └── mcp-server-proxy

GitHub Actions CI/CD (depends on ACR + AKS)
 ├── Build Pipeline
 ├── Deploy Pipeline
 └── Smoke Tests

Tenant Admin UI (depends on all APIs)
 ├── Tenant Selector
 ├── Onboarding Wizard
 └── Usage Dashboards
```

---

## MVP Recommendation

**Prioritize (must ship for v3.0):**

1. **Bicep IaC Foundation** — Everything depends on deployed Azure resources. Must be first.
2. **Cosmos DB Repository Layer** — Most complex migration. Must replace SQLAlchemy before any other feature depends on it.
3. **Entra ID Authentication** — Security foundation. All API access must use Entra ID tokens.
4. **Tenant Registration API + Namespace Provisioning** — Core lifecycle management.
5. **Microservice Container Images + Deployment Manifests** — Required for AKS deployment.
6. **GitHub Actions CI/CD** — Build + deploy pipeline for automated deployments.
7. **Application Insights + Per-tenant Metrics** — Basic observability for production readiness.
8. **Tenant Selector + Scoped Views** — Minimum UI for multi-tenant operation.
9. **Tenant Onboarding Flow** — Platform admin can create new tenants through UI.

**Defer to post-v3.0:**

- **Change feed event streaming** — Nice-to-have, not needed for initial multi-tenant operation.
- **Canary deployments** — Rolling updates suffice for 2-5 tenants.
- **GitOps / Flux** — GitHub Actions deploy is simpler to start; Flux adds operational learning curve.
- **Istio service mesh** — Heavy resource overhead. NetworkPolicy provides sufficient isolation for trusted internal tenants.
- **SLO tracking / anomaly detection** — Observability polish, not blocking for launch.
- **Multi-tenant comparison views** — Admin convenience, not launch blocker.

---

## Complexity Summary

| Category | Table Stakes | Differentiators | Total Features | Highest Complexity |
|----------|-------------|----------------|----------------|-------------------|
| Tenant Lifecycle | 7 | 4 | 11 | Medium |
| Infrastructure Provisioning | 9 | 3 | 12 | High |
| Data Isolation (Cosmos DB) | 8 | 4 | 12 | Very High |
| Authentication (Entra ID) | 7 | 4 | 11 | High |
| Compute Isolation (AKS) | 9 | 4 | 13 | High |
| Deployment & CI/CD | 8 | 4 | 12 | High |
| Observability | 8 | 4 | 12 | High |
| Tenant Admin UI | 7 | 4 | 11 | High |
| **Total** | **63** | **31** | **94** | **Very High** |

**Critical path:** Bicep IaC → Cosmos DB migration → Entra ID → Microservice split → CI/CD. The Cosmos DB migration (replacing SQLAlchemy across 15+ models, all services, all tests) is the single highest-risk, highest-complexity item.

---

*Researched: 2026-03-26*
*Sources: Microsoft Azure Architecture Center (multi-tenant guide), AKS multi-tenant best practices, Cosmos DB multi-tenancy patterns, existing codebase analysis*
*Confidence: HIGH — all recommendations sourced from Microsoft official documentation and verified against existing codebase*
