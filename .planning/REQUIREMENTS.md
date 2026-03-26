# Requirements: v3.0 Production Multi-Tenant Infrastructure

**Defined:** 2026-03-26
**Core Value:** Product teams can go from zero to a working AI agent with tools, data sources, and orchestration — without writing infrastructure code or managing model deployments.

## v3.0 Requirements

Requirements for production multi-tenant infrastructure. Each maps to roadmap phases.

### Tenant Lifecycle

- [ ] **TENANT-01**: Platform admin can create a tenant with name, slug, and admin contact via API
- [ ] **TENANT-02**: Platform automatically provisions K8s namespace with NetworkPolicy, ResourceQuota, and LimitRange on tenant creation
- [ ] **TENANT-03**: Tenant lifecycle states transition through provisioning → active → suspended → deactivated → deleted
- [ ] **TENANT-04**: Suspended tenant API requests are blocked at middleware layer while data and namespace are retained
- [ ] **TENANT-05**: Platform admin can configure per-tenant settings (display name, allowed model providers, token quotas, feature flags)
- [ ] **TENANT-06**: New tenant is seeded with default catalog entries, built-in tools, and default policies on creation
- [ ] **TENANT-07**: Admin user is auto-created for new tenant with Entra ID mapping
- [ ] **TENANT-08**: Platform admin can onboard a new tenant through a multi-step UI wizard (org name → Entra ID connection → model endpoint → first agent → review & create)

### Infrastructure Provisioning

- [ ] **INFRA-01**: Bicep modules provision AKS cluster, ACR, Cosmos DB, VNet + subnets, Managed Identities, Key Vault, and Log Analytics workspace
- [ ] **INFRA-02**: VNet deploys with subnets for AKS nodes, AKS pods, and private endpoints with NSGs per subnet
- [ ] **INFRA-03**: AKS cluster provisions with system + user node pools, Azure CNI Overlay, K8s RBAC, Entra ID integration, and Azure Monitor addon
- [ ] **INFRA-04**: ACR provisions with admin disabled and Managed Identity pull from AKS via AcrPull role assignment
- [ ] **INFRA-05**: Cosmos DB NoSQL account provisions with aiplatform database and containers using /tenant_id partition key
- [ ] **INFRA-06**: Key Vault provisions with RBAC-based access for secrets (model API keys, connection strings)
- [ ] **INFRA-07**: Managed Identities are configured for AKS (system-assigned) and workloads (user-assigned) with Workload Identity federation
- [ ] **INFRA-08**: Environment parameter files exist for dev, staging, and prod with appropriate SKUs and throughput settings
- [ ] **INFRA-09**: Orchestrator main.bicep deploys all resources in correct dependency order and is idempotent

### Data Isolation (Cosmos DB)

- [ ] **DATA-01**: Repository layer replaces SQLAlchemy ORM for all data access with Cosmos DB async SDK
- [ ] **DATA-02**: All containers use /tenant_id as partition key and every query includes tenant_id in the partition key filter
- [ ] **DATA-03**: Cross-partition queries are prevented by design — no operation can read data across tenants
- [ ] **DATA-04**: All 13+ existing data models are migrated to Cosmos DB document schemas
- [ ] **DATA-05**: Data migration tooling converts existing PostgreSQL data to Cosmos DB documents
- [ ] **DATA-06**: Unique key constraints enforce business uniqueness rules within tenant partitions
- [ ] **DATA-07**: Optimistic concurrency is implemented using Cosmos DB ETags on document updates
- [ ] **DATA-08**: Cosmos DB throughput is configured with autoscale or serverless appropriate to 2-5 tenant workload

### Authentication (Entra ID)

- [ ] **AUTH-01**: Entra ID app registration is configured with OIDC authorization code flow for frontend login
- [ ] **AUTH-02**: Backend validates Entra ID JWT tokens (issuer, audience, signature, expiry) on every API request
- [ ] **AUTH-03**: Token claims map to tenant_id via Entra ID group or custom claim, replacing current cookie-based JWT
- [ ] **AUTH-04**: RBAC roles (Platform Admin, Tenant Admin, Member, Viewer) are enforced at API endpoint level
- [ ] **AUTH-05**: Frontend uses MSAL React for login, token acquisition, and silent refresh
- [ ] **AUTH-06**: Service-to-service authentication uses Managed Identity with DefaultAzureCredential
- [ ] **AUTH-07**: Existing API endpoints are migrated from cookie JWT auth to Entra ID token validation

### Compute Isolation (AKS)

- [ ] **COMPUTE-01**: Each tenant runs workloads in a dedicated K8s namespace (tenant-{slug})
- [ ] **COMPUTE-02**: NetworkPolicy restricts cross-namespace traffic — tenant pods cannot reach other tenant namespaces
- [ ] **COMPUTE-03**: ResourceQuota limits per-tenant CPU, memory, and pod count
- [ ] **COMPUTE-04**: LimitRange enforces default and max resource requests/limits per container
- [ ] **COMPUTE-05**: Helm charts or Kustomize overlays generate per-tenant deployment manifests
- [ ] **COMPUTE-06**: HPA scales tenant workloads based on CPU/memory utilization
- [ ] **COMPUTE-07**: Health check endpoints (liveness, readiness, startup) are implemented for all microservices
- [ ] **COMPUTE-08**: Backend is split into microservice container images (api-gateway, agent-executor, workflow-engine, tool-executor, mcp-proxy)
- [ ] **COMPUTE-09**: Ingress controller routes requests to correct tenant namespace based on tenant context

### Deployment & CI/CD

- [ ] **DEPLOY-01**: GitHub Actions workflow builds Docker images for all microservices on push to main
- [ ] **DEPLOY-02**: Docker images are tagged with git SHA and pushed to ACR
- [ ] **DEPLOY-03**: GitHub Actions workflow deploys to AKS using Helm/Kustomize with environment-specific values
- [ ] **DEPLOY-04**: Rolling update strategy ensures zero-downtime deployments
- [ ] **DEPLOY-05**: Deployment pipeline runs smoke tests after deploy to verify service health
- [ ] **DEPLOY-06**: Secrets and configuration are injected via Key Vault CSI driver, not hardcoded
- [ ] **DEPLOY-07**: Frontend builds as static export or container image and deploys to AKS or Azure Static Web Apps
- [ ] **DEPLOY-08**: Pipeline supports deploying to a single tenant namespace without affecting others

### Observability

- [ ] **OBS-01**: FastAPI backend is instrumented with OpenTelemetry exporting to Application Insights
- [ ] **OBS-02**: Distributed traces span across microservices with correlated trace IDs
- [ ] **OBS-03**: All telemetry is tagged with tenant_id custom dimension for per-tenant KQL queries
- [ ] **OBS-04**: Structured JSON logs include tenant_id, agent_id, trace_id, and span_id in every entry
- [ ] **OBS-05**: AKS Container Insights monitors node and pod CPU, memory, and network metrics
- [ ] **OBS-06**: Azure Monitor alerts trigger on health check failures and pod restart loops
- [ ] **OBS-07**: Alert rules fire when 5xx error rate exceeds threshold per tenant or Cosmos DB RU consumption exceeds 80%
- [ ] **OBS-08**: Central Log Analytics workspace receives App Insights telemetry, AKS container logs, Cosmos DB diagnostics, and Key Vault audit logs

### Tenant Admin UI

- [ ] **UI-01**: Global tenant selector in navigation allows platform admins to switch tenant context
- [ ] **UI-02**: All existing UI pages automatically filter by selected tenant with no cross-tenant data leakage
- [ ] **UI-03**: Platform admin dashboard lists all tenants with status, resource usage, agent counts, and active user counts
- [ ] **UI-04**: Tenant settings page allows tenant admins to configure display name, allowed features, and token quotas
- [ ] **UI-05**: Tenant admins can view users, assign roles, and invite new users via Entra ID group membership
- [ ] **UI-06**: Per-tenant usage summary shows API call volume, agent execution count, token consumption, and cost estimate

## Future Requirements

Deferred to post-v3.0. Tracked but not in current roadmap.

### Tenant Lifecycle

- **TENANT-F01**: Tenant configuration can be cloned as a template for new tenants
- **TENANT-F02**: Tenants auto-suspend after N days of inactivity
- **TENANT-F03**: All tenant data can be exported as portable JSON archive before offboarding

### Infrastructure Provisioning

- **INFRA-F01**: Bicep module provisions K8s namespace + RBAC + NetworkPolicy + ResourceQuota for a new tenant via AKS command invoke
- **INFRA-F02**: Minimal-cost staging environment parameter file uses single-node AKS and serverless Cosmos DB
- **INFRA-F03**: GitHub Actions workflow runs az deployment what-if for infrastructure drift detection

### Data Isolation

- **DATA-F01**: Cosmos DB change feed enables event streaming for cross-service reactivity
- **DATA-F02**: Auto-archive cold tenant data to lower-cost storage tier
- **DATA-F03**: Per-tenant RU consumption tracking with budget alerts
- **DATA-F04**: Tenant data can be hard-deleted with cryptographic verification

### Authentication

- **AUTH-F01**: Conditional access policies enforce MFA and compliant-device requirements per tenant
- **AUTH-F02**: API keys with scoped permissions for headless automation and CI/CD integration
- **AUTH-F03**: Comprehensive audit log of all auth events (login, logout, token refresh, role changes)
- **AUTH-F04**: B2B guest user support for cross-organization collaboration within a tenant

### Compute Isolation

- **COMPUTE-F01**: Pod Security Standards enforce restricted security context for tenant workloads
- **COMPUTE-F02**: Dedicated node pools for high-priority tenants via node affinity and taints
- **COMPUTE-F03**: KEDA event-driven autoscaling based on queue depth or agent execution backlog
- **COMPUTE-F04**: Pod disruption budgets ensure availability during node upgrades

### Deployment & CI/CD

- **DEPLOY-F01**: Canary deployment strategy routes percentage of traffic to new version before full rollout
- **DEPLOY-F02**: GitOps with Flux for declarative AKS state management
- **DEPLOY-F03**: Preview environments spin up from PR branches automatically
- **DEPLOY-F04**: Deployment approval gates require manual sign-off for production

### Observability

- **OBS-F01**: Per-tenant usage dashboards via Azure Workbooks or Managed Grafana
- **OBS-F02**: Azure Monitor smart alerts for anomaly detection in tenant request patterns
- **OBS-F03**: Cost attribution correlates Cosmos DB RU + model tokens + compute time per tenant
- **OBS-F04**: SLO tracking with SLI/SLO dashboards (availability, latency, error rate)

### Tenant Admin UI

- **UI-F01**: Tenant health status indicators (green/yellow/red) based on real-time error rates
- **UI-F02**: Multi-tenant comparison view for platform admins
- **UI-F03**: Searchable audit log of all admin actions per tenant
- **UI-F04**: Visual editor for per-tenant resource quotas

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Billing/payment integration | Internal enterprise platform — no customer billing needed for 2-5 internal teams |
| Multi-region tenant placement | 2-5 tenants in single Azure region; multi-region adds disproportionate cost and complexity |
| Tenant-level SLA tiers | All internal enterprise tenants get uniform namespace-per-tenant isolation |
| Terraform dual-stack | Decided on Bicep in PROJECT.md; maintaining both doubles IaC complexity |
| Per-tenant AKS clusters | Overkill for 2-5 tenants; namespace isolation is sufficient |
| Istio service mesh | Heavy resource overhead; NetworkPolicy provides sufficient isolation for trusted internal tenants |
| Datadog/Splunk/New Relic | Microsoft-first architecture; Azure Monitor stack provides full observability natively |
| Per-tenant Log Analytics workspaces | Single workspace with tenant_id dimension provides sufficient query isolation |
| Per-tenant branded portal | Custom domains/CSS themes per tenant is B2C SaaS complexity; internal platform uses single UI |
| Tenant self-provisioning infrastructure | IaC is platform team responsibility; tenants configure agents/tools, not Azure resources |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TENANT-01 | Phase 21 | Pending |
| TENANT-02 | Phase 21 | Pending |
| TENANT-03 | Phase 21 | Pending |
| TENANT-04 | Phase 21 | Pending |
| TENANT-05 | Phase 21 | Pending |
| TENANT-06 | Phase 21 | Pending |
| TENANT-07 | Phase 21 | Pending |
| TENANT-08 | Phase 24 | Pending |
| INFRA-01 | Phase 17 | Pending |
| INFRA-02 | Phase 17 | Pending |
| INFRA-03 | Phase 17 | Pending |
| INFRA-04 | Phase 17 | Pending |
| INFRA-05 | Phase 17 | Pending |
| INFRA-06 | Phase 17 | Pending |
| INFRA-07 | Phase 17 | Pending |
| INFRA-08 | Phase 17 | Pending |
| INFRA-09 | Phase 17 | Pending |
| DATA-01 | Phase 19 | Pending |
| DATA-02 | Phase 19 | Pending |
| DATA-03 | Phase 19 | Pending |
| DATA-04 | Phase 19 | Pending |
| DATA-05 | Phase 19 | Pending |
| DATA-06 | Phase 19 | Pending |
| DATA-07 | Phase 19 | Pending |
| DATA-08 | Phase 19 | Pending |
| AUTH-01 | Phase 18 | Pending |
| AUTH-02 | Phase 18 | Pending |
| AUTH-03 | Phase 18 | Pending |
| AUTH-04 | Phase 18 | Pending |
| AUTH-05 | Phase 18 | Pending |
| AUTH-06 | Phase 18 | Pending |
| AUTH-07 | Phase 18 | Pending |
| COMPUTE-01 | Phase 20 | Pending |
| COMPUTE-02 | Phase 20 | Pending |
| COMPUTE-03 | Phase 20 | Pending |
| COMPUTE-04 | Phase 20 | Pending |
| COMPUTE-05 | Phase 20 | Pending |
| COMPUTE-06 | Phase 20 | Pending |
| COMPUTE-07 | Phase 20 | Pending |
| COMPUTE-08 | Phase 20 | Pending |
| COMPUTE-09 | Phase 20 | Pending |
| DEPLOY-01 | Phase 22 | Pending |
| DEPLOY-02 | Phase 22 | Pending |
| DEPLOY-03 | Phase 22 | Pending |
| DEPLOY-04 | Phase 22 | Pending |
| DEPLOY-05 | Phase 22 | Pending |
| DEPLOY-06 | Phase 22 | Pending |
| DEPLOY-07 | Phase 22 | Pending |
| DEPLOY-08 | Phase 22 | Pending |
| OBS-01 | Phase 23 | Pending |
| OBS-02 | Phase 23 | Pending |
| OBS-03 | Phase 23 | Pending |
| OBS-04 | Phase 23 | Pending |
| OBS-05 | Phase 23 | Pending |
| OBS-06 | Phase 23 | Pending |
| OBS-07 | Phase 23 | Pending |
| OBS-08 | Phase 23 | Pending |
| UI-01 | Phase 24 | Pending |
| UI-02 | Phase 24 | Pending |
| UI-03 | Phase 24 | Pending |
| UI-04 | Phase 24 | Pending |
| UI-05 | Phase 24 | Pending |
| UI-06 | Phase 24 | Pending |

**Coverage:**
- v3.0 requirements: 63 total
- Mapped to phases: 63
- Unmapped: 0

---
*Requirements defined: 2026-03-26*
*Last updated: 2026-03-26 after milestone v3.0 scoping*
