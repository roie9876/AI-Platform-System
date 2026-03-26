# Project Research Summary

**Project:** AI Agent Platform as a Service — v3.0 Production Multi-Tenant Infrastructure
**Domain:** Brownfield migration of AI Agent Platform from monolith → microservices, PostgreSQL → Cosmos DB, JWT → Entra ID, Docker Compose → AKS
**Researched:** 2026-03-26
**Confidence:** HIGH

## Executive Summary

This project is a **brownfield infrastructure migration** of an existing AI Agent Platform (Python/FastAPI monolith, SQLAlchemy/PostgreSQL, HS256 JWT auth, Docker Compose) to a production multi-tenant Azure architecture. The target state is a microservice-based platform running on AKS with namespace-per-tenant isolation, Cosmos DB NoSQL for data, Microsoft Entra ID for enterprise SSO, Bicep IaC, GitHub Actions CI/CD, and Azure Monitor observability. The platform serves 2-5 internal enterprise tenants — not a public SaaS, so billing, multi-region, and tiered service levels are out of scope.

The recommended approach, validated by all four research streams, follows a strict sequential order: **IaC first → Auth migration → Cosmos DB data layer → Microservice extraction → AKS deployment → CI/CD automation → Observability instrumentation**. This order is dictated by three hard dependencies: (1) Azure resources must exist before any code can target them, (2) auth must migrate while the codebase is still a single monolith (changing auth in 5 microservices simultaneously is exponentially harder), and (3) the data layer must be replaced before service extraction because SQLAlchemy's shared session model creates import dependencies that block decomposition.

The **highest-risk item** is the Cosmos DB migration — replacing SQLAlchemy across 26 models, 15 services, and all tests with a repository pattern over the Cosmos DB SDK. The critical danger is translating relational JOINs into cross-partition queries (4-5x RU cost), losing transactional atomicity (Cosmos DB only supports transactions within a single logical partition), and schema evolution without Alembic (schemaless doesn't mean schema-free). These risks are manageable with upfront document model design, denormalization mapping, and schema versioning — but they must be addressed in the design phase, not discovered during implementation.

## Key Findings

### Recommended Stack

The existing Python/FastAPI, Next.js, Docker stack is validated and retained. All additions target Azure-native services and tooling.

**Core additions:**
- **Bicep CLI** (bundled with Azure CLI ≥2.84.0): Infrastructure-as-Code for all Azure resources. Chosen over Terraform for Azure-native type safety and no state file management.
- **azure-cosmos 4.15.0**: Cosmos DB NoSQL data operations with async support. Replaces SQLAlchemy ORM — the SDK is used directly with a Repository pattern, no ORM abstraction.
- **azure-identity 1.25.3**: `DefaultAzureCredential` for unified auth chain (local dev via Azure CLI, AKS via Workload Identity). Single credential type for all Azure SDK calls.
- **msal 1.35.1**: Entra ID token validation on the backend. Validates RS256 tokens with JWKS key rotation and authority discovery.
- **azure-monitor-opentelemetry 1.8.7**: All-in-one OpenTelemetry distro for Azure Monitor. Auto-instruments FastAPI, exports to Application Insights. Replaces deprecated opencensus.
- **Helm v4.0.x + Kustomize v5.0.x**: Helm for microservice packaging, Kustomize for tenant-specific namespace overlays. Used together, not either/or.
- **azure-keyvault-secrets 4.10.0**: Runtime secret retrieval via Managed Identity. Replaces env vars and DB-stored encrypted secrets.

**Frontend:** No new packages needed. `@azure/msal-browser` 5.6.1 and `@azure/msal-react` 5.1.0 are already installed.

**Key version constraints:** Python 3.12, Node.js 22, Kubernetes 1.30.x.

**SQLAlchemy replacement strategy:** Drop SQLAlchemy ORM for Cosmos DB-backed entities. Introduce Repository pattern abstracting data access. Pydantic `BaseModel` classes become canonical schema (schema-on-write). No Alembic migrations — Cosmos DB is schemaless; container provisioning handled in Bicep.

### Expected Features

94 total features identified across 8 categories. 63 table stakes, 31 differentiators.

**Must have (table stakes):**
- Tenant registration API with lifecycle states (provisioning → active → suspended → deleted)
- Automated AKS namespace provisioning with NetworkPolicy, ResourceQuota, LimitRange per tenant
- Core Bicep modules for VNet, AKS, ACR, Cosmos DB, Key Vault, Managed Identities, Log Analytics
- Cosmos DB repository layer replacing SQLAlchemy with partition key enforcement and cross-tenant query prevention
- Entra ID OIDC integration replacing homegrown JWT, with tenant mapping (Entra `tid` → platform `tenant_id`) and 4-role RBAC
- 5 microservice container images (api-gateway, agent-executor, workflow-engine, tool-executor, mcp-proxy) with multi-stage Dockerfiles
- GitHub Actions build + deploy pipelines with OIDC auth, immutable SHA-based image tags, staging auto-deploy + production manual approval
- Application Insights + per-tenant metrics via OpenTelemetry, structured logging with tenant/trace correlation
- Tenant selector UI, tenant-scoped views, platform admin dashboard, tenant onboarding wizard

**Should have (differentiators):**
- Cosmos DB Change Feed for event streaming and cache invalidation
- Canary deployments (deploy to single tenant namespace first)
- Per-tenant usage dashboards and cost attribution
- Group-based access control via Entra ID security groups
- Infrastructure drift detection via `az deployment what-if`

**Defer to post-v3.0:**
- Istio service mesh (NetworkPolicy sufficient for 2-5 trusted tenants)
- GitOps with Flux (GitHub Actions is simpler to start)
- SLO tracking and anomaly detection
- Multi-region tenant placement
- Per-tenant branded portals
- Billing/payment integration (internal platform)

### Architecture Approach

The monolith's 15 service classes split into **5 backend microservices** based on failure domain isolation, scaling requirements, and deployment cadence. The API Gateway handles all CRUD plus routing; execution-intensive services (agent execution, workflow orchestration, tool execution, MCP proxy) deploy per-tenant in isolated namespaces.

**Major components:**
1. **API Gateway** (`platform` namespace) — Entra ID token validation, RBAC, all 22 CRUD routers, tenant management, Cosmos DB reads/writes. Single deployment, HPA on request rate.
2. **Agent Executor** (per-tenant namespace) — Agent execution loop, model calls, RAG retrieval, memory management, SSE streaming. Most CPU/memory-intensive; scales on concurrent executions.
3. **Workflow Engine** (per-tenant namespace) — Long-running DAG orchestration, sub-agent delegation. Scales on active workflow count.
4. **Tool Executor** (per-tenant namespace) — Sandboxed untrusted code execution with restricted NetworkPolicy. Isolated for blast radius containment.
5. **MCP Server Proxy** (per-tenant namespace) — MCP client, server discovery, connection pooling. Enforces tenant-level MCP server registration isolation.

**Cosmos DB design:** 11 containers organized by access pattern (not entity), all partitioned on `/tenant_id` except `platform` (`/id`) and `marketplace` (`/category`). Denormalization strategy: embed config versions, tool IDs, workflow nodes/edges, test cases within parent documents. Custom indexing policy excludes large embedded arrays to save write RUs.

**AKS layout:** Single shared cluster. `platform` namespace for shared infrastructure (API gateway, tenant management). Per-tenant namespaces (`tenant-{slug}`) with 4 workload pods each, default-deny NetworkPolicy, ResourceQuota, LimitRange, dedicated ServiceAccount with Workload Identity.

**Inter-service communication:** HTTP/REST via httpx. No service mesh, no gRPC, no async messaging for v3.0. Internal trust model: API Gateway is sole ingress point, validates Entra ID token, sets trusted `X-Tenant-ID` header. Tenant services trust this header because NetworkPolicy enforces only the gateway can reach them.

### Critical Pitfalls

12 critical/high pitfalls identified, plus 9 moderate/minor and 3 cross-cutting integration pitfalls.

1. **Relational JOIN → cross-partition query translation** — Developers instinctively replicate SQL JOINs as multiple Cosmos DB queries, causing 4-5x RU cost and 60-120ms latency vs. 15ms SQL. **Prevention:** Denormalize read paths upfront. Map every existing JOIN to an embedding strategy before writing code.

2. **Lost transactional atomicity** — PostgreSQL's implicit `session.commit()` atomicity doesn't exist in Cosmos DB across partitions/containers. **Prevention:** Partition key design + embedded documents make most writes single-partition (use `TransactionalBatch`). Identify the 3-4 genuinely cross-container operations and implement compensating transactions only for those.

3. **Big-bang monolith decomposition** — Extracting all microservices simultaneously causes 2-4 weeks of development paralysis. **Prevention:** Strangler Fig pattern. Extract one service at a time behind a reverse proxy.

4. **Entra ID audience/issuer confusion** — Misconfiguring `aud` claim validation (v1.0 vs v2.0 token format) causes total auth failure in production. **Prevention:** Pin `accessTokenAcceptedVersion: 2` in app registration. Use `msal` library (not raw PyJWT) for validation.

5. **RU cost explosion from unbounded queries** — Existing `SELECT *` patterns translate to full-partition scans consuming thousands of RUs. **Prevention:** Enforce pagination on all list queries. Pre-aggregate metrics via Change Feed. Profile every endpoint's RU cost during development.

6. **RBAC propagation timing in Bicep** — Role assignments have 5-10 minute propagation delay. **Prevention:** Split deployment into stages with waits between identity and data stages.

7. **Auth migration + microservice split ordering** — Migrating auth after microservice extraction means updating 5+ codebases simultaneously. **Prevention:** Auth migration MUST happen while still a monolith.

## Implications for Roadmap

Based on combined research, the migration requires **8 phases** in strict dependency order.

### Phase 1: Infrastructure Foundation (Bicep IaC)
**Rationale:** Everything depends on Azure resources existing. Cannot write code targeting Cosmos DB or AKS without provisioned resources.
**Delivers:** Dev/staging Azure environment — VNet, AKS cluster, ACR, Cosmos DB account + 11 containers, Key Vault, Managed Identities, Log Analytics, App Insights.
**Addresses:** All 9 IaC table-stakes features.
**Avoids:** Pitfall #7 (RBAC timing — staged deployments), Pitfall #17 (naming collisions — `uniqueString()`).

### Phase 2: Authentication Migration (Entra ID)
**Rationale:** Auth MUST migrate while still a monolith (Integration Pitfall B). One codebase to change vs. five. Cross-cutting concern that every subsequent phase depends on.
**Delivers:** Entra ID OIDC login, RS256 token validation, tenant mapping, 4-role RBAC, dual-auth transition period, Managed Identity auth for Azure SDK calls.
**Addresses:** All 7 auth table-stakes features.
**Avoids:** Pitfall #4 (audience confusion), Pitfall #14 (dual-auth complexity), Pitfall #19 (MSAL token cache).

### Phase 3: Data Layer Migration (Cosmos DB)
**Rationale:** Highest-risk, highest-complexity item. Must complete before microservice extraction because SQLAlchemy imports block decomposition.
**Delivers:** Document model design, Repository pattern, 11 concrete repositories, Pydantic document models, `CosmosClient` singleton, data migration scripts, schema versioning.
**Addresses:** All 8 Cosmos DB table-stakes features.
**Avoids:** Pitfall #1 (JOIN translation), Pitfall #2 (lost transactions), Pitfall #5 (RU explosion), Pitfall #9 (partition key mismatch), Pitfall #12 (schema evolution), Pitfall #15 (junction tables).

### Phase 4: Microservice Extraction
**Rationale:** With auth and data layer migrated, the monolith can decompose. Strangler Fig: one service at a time.
**Delivers:** 5 microservice codebases with Dockerfiles, inter-service HTTP contracts, shared Pydantic model library.
**Addresses:** Microservice container images, service boundaries from ARCHITECTURE.md.
**Avoids:** Pitfall #3 (big-bang split), Pitfall #8 (service-to-service auth gaps).

### Phase 5: AKS Deployment & Tenant Provisioning
**Rationale:** Container images from Phase 4 need a deployment target. Namespace-per-tenant is the core isolation mechanism.
**Delivers:** Helm charts, Kustomize overlays, automated namespace provisioning, tenant lifecycle API, deployment manifests with HPA.
**Addresses:** All 9 AKS compute isolation table stakes, tenant registration API.
**Avoids:** Pitfall #6 (namespace sprawl), Pitfall #16 (DNS/NetworkPolicy), Integration Pitfall A (MI auth triangle).

### Phase 6: CI/CD Pipelines (GitHub Actions)
**Rationale:** Automate build/test/deploy. Needs AKS target + container images from previous phases.
**Delivers:** Build pipeline, deploy pipeline, OIDC auth, staging auto-deploy + production manual approval, container vulnerability scanning.
**Addresses:** All 8 CI/CD table-stakes features.
**Avoids:** Pitfall #10 (secrets sprawl — OIDC + Key Vault), Pitfall #20 (over-triggering — path filters).

### Phase 7: Observability & Monitoring
**Rationale:** Instrument AFTER services are split (PITFALLS.md: instrumenting code that will be restructured wastes effort).
**Delivers:** Application Insights, distributed tracing, per-tenant metrics, structured logging, Container Insights, alerting.
**Addresses:** All 8 observability table-stakes features.
**Avoids:** Pitfall #11 (metric cardinality explosion), Pitfall #21 (workspace confusion).

### Phase 8: Tenant Admin UI
**Rationale:** Requires all APIs, auth, and data layer to be complete. Least risky layer.
**Delivers:** Tenant selector, tenant-scoped views, platform admin dashboard, onboarding wizard, settings, user management.
**Addresses:** All 7 tenant admin UI table-stakes features.

### Phase Ordering Rationale

- **IaC → Auth → Data → Services → Infra → CI/CD → Observability → UI** follows strict dependency chains validated across all four research files.
- Auth before Data because auth is cross-cutting and simpler to migrate in a monolith.
- Data before Services because SQLAlchemy import dependencies block decomposition.
- Services before AKS because container images are needed for K8s deployment.
- CI/CD after AKS because a deployment target must exist before automating deployment.
- Observability after service split because instrumenting code that will be restructured wastes effort.
- UI last because it depends on all APIs being production-ready.

### Research Flags

**Needs `/gsd-research-phase` during planning:**
- **Phase 2 (Auth Migration):** Entra ID app registration, token validation flow, dual-auth transition, `tid` → `tenant_id` mapping.
- **Phase 3 (Data Layer):** Cosmos DB denormalization strategy, RU cost modeling, TransactionalBatch boundaries, Change Feed architecture.
- **Phase 5 (AKS Deployment):** NetworkPolicy rules, Workload Identity federation, tenant provisioning automation.

**Standard patterns (skip research):**
- **Phase 1 (IaC):** Well-documented Bicep patterns from Azure Architecture Center.
- **Phase 4 (Microservice Extraction):** Strangler Fig is established; ARCHITECTURE.md provides exact file-to-service mapping.
- **Phase 6 (CI/CD):** Standard GitHub Actions; STACK.md provides action versions and pipeline structure.
- **Phase 7 (Observability):** `azure-monitor-opentelemetry` distro handles most instrumentation automatically.
- **Phase 8 (Tenant Admin UI):** Standard React/Next.js patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All from official Microsoft SDKs with pinned versions. No speculative choices. |
| Features | HIGH | 94 features from Azure Architecture Center multi-tenant guides + codebase analysis. |
| Architecture | HIGH | 5-service decomposition mapped to existing files. Cosmos DB design with Bicep code. |
| Pitfalls | HIGH | 21 pitfalls grounded in Cosmos DB best practices skill (45+ rules) + codebase analysis. |

**Overall confidence:** HIGH

### Gaps to Address

- **Data volume estimation:** Need actual row counts per tenant from PostgreSQL to validate partition key choices and estimate Cosmos DB costs. If any tenant × entity > 10 GB, hierarchical partition keys are mandatory.
- **Cosmos DB emulator limitations:** Linux emulator doesn't support hierarchical partition keys or Change Feed processor. Need a real serverless Cosmos DB dev account for integration testing.
- **Thread message storage:** Embed recent messages in Thread doc (cap at 50) vs. separate container — depends on average message count, requires production data analysis.
- **Tool Executor security model:** Subprocess sandboxing specifics (gVisor? seccomp? Kata?) deferred. NetworkPolicy helps but isn't a complete sandbox.
- **Dual-auth transition timeline:** How long to support both HS256 and Entra ID tokens? Need cutoff strategy and monitoring.
- **Cost modeling:** No estimated Azure costs for target architecture. Need to model AKS nodes, Cosmos DB RUs, ACR storage, Key Vault ops, App Insights ingestion for budget approval.

## Sources

### Primary (HIGH confidence)
- Microsoft Azure Architecture Center: [Architect multitenant solutions on Azure](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/overview)
- Microsoft: [Tenancy models for a multitenant solution](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/considerations/tenancy-models)
- Microsoft: [Use AKS in a multitenant solution](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/service/aks)
- Microsoft: [Multitenancy and Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/service/cosmos-db)
- Microsoft: [AKS microservices architecture](https://learn.microsoft.com/en-us/azure/architecture/reference-architectures/containers/aks-microservices/aks-microservices)
- Cosmos DB Well-Architected Framework service guide
- Azure Cosmos DB best practices skill (45+ rules, 8 categories)
- Azure Observability skill, Azure PostgreSQL / Entra ID skill

### Secondary (MEDIUM confidence)
- Existing codebase analysis: `backend/app/` — 26 SQLAlchemy models, 15 services, 22 routers verified

---
*Research completed: 2026-03-26*
*Ready for roadmap: yes*
