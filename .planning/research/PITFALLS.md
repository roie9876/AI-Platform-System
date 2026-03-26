# Domain Pitfalls — v3.0 Production Multi-Tenant Infrastructure Migration

**Domain:** Brownfield migration of AI Agent Platform from monolith → microservices, PostgreSQL → Cosmos DB, JWT → Entra ID, Docker Compose → AKS, with Bicep IaC, GitHub Actions CI/CD, and Azure Monitor observability
**Researched:** 2026-03-26
**Scope:** Pitfalls specific to ADDING these features to an existing Python/FastAPI system with SQLAlchemy ORM, 13 Alembic migrations, 20+ relational models, HS256 JWT cookie auth, and tenant middleware

**Sources:**
- Azure Cosmos DB instructions file (`azurecosmosdb.instructions.md`) — HIGH confidence
- Azure Cosmos DB Best Practices skill (45+ rules, 8 categories) — HIGH confidence
- Azure Observability skill (`azure-observability/SKILL.md`) — HIGH confidence
- Azure PostgreSQL / Entra ID skill (`azure-postgres/SKILL.md`) — HIGH confidence
- Existing codebase analysis: `backend/app/models/*.py`, `backend/app/services/*.py`, `backend/app/middleware/tenant.py`, `backend/app/core/security.py` — HIGH confidence
- Microsoft Architecture Center: [Multitenant solutions on Azure](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/overview) — HIGH confidence
- Microsoft: [Use AKS in a multitenant solution](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/service/aks) — HIGH confidence
- Microsoft: [Multitenancy and Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/service/cosmos-db) — HIGH confidence
- Cosmos DB Well-Architected Framework: [Service guide](https://learn.microsoft.com/azure/well-architected/service-guides/cosmos-db) — HIGH confidence

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, cost explosions, or security breaches.

---

### Pitfall 1: Translating Relational JOINs Directly to Cosmos DB Cross-Partition Queries

**What goes wrong:** The existing codebase has 15+ ForeignKey relationships and at least 8 explicit SQL JOINs (`agent_execution.py` joins AgentTool→Tool, AgentMCPTool→MCPDiscoveredTool→MCPServer; `evaluation_service.py` joins EvaluationResult→TestCase; `observability_service.py` joins ExecutionLog→Thread; `rag_service.py` chains AgentDataSource→Document). Developers instinctively replicate these as multiple Cosmos DB cross-partition queries per request — one query per "table," then join in Python.

**Why it happens:** SQL thinking. The team's muscle memory is `SELECT ... JOIN`. Cosmos DB has no server-side JOINs across containers (JOIN only works within a single item's nested arrays). Every "join" becomes N+1 point reads or N cross-partition fan-out queries.

**Consequences:**
- **RU explosion:** A single "get agent with tools" call that was 1 SQL query becomes 3-4 Cosmos DB queries. At 5-10 RU per query, a 10-RU operation becomes 40-50 RU. Multiply by request volume → 4-5x your expected Cosmos DB bill.
- **Latency spike:** Each cross-partition query adds 10-30ms. Chaining 4 of them turns a 15ms SQL call into a 60-120ms Cosmos DB call.
- **Pagination breaks:** Continuation tokens in Cosmos DB are per-query, not per-result-set. Joining paginated results in application code is error-prone.

**Prevention:**
1. **Denormalize for read paths.** Embed tool definitions, data source configs, and MCP tool metadata directly inside the Agent document. The current `AgentTool` junction table becomes an embedded `tools[]` array in the Agent document.
2. **Design containers around access patterns, not entities.** Don't create a container per SQLAlchemy model. Example: `agents` container holds agent + tools + data sources + config versions as one document (or sub-documents). `threads` container holds thread + messages together.
3. **Map every existing JOIN to a denormalization or a deliberate cross-container read.** Before writing any code, build a matrix: existing query → required containers → expected RU cost. If any operation requires >3 container reads, redesign the document model.
4. **Use the Change Feed for cross-container consistency.** When a Tool definition changes, a Change Feed processor updates the embedded copy in all Agent documents that reference it.

**Detection:** Monitor `TotalRequestCharge` per operation via SDK diagnostics. If any single API endpoint consumes >50 RU consistently, investigate denormalization opportunities.

**Phase to address:** Data Migration phase (must complete document model design BEFORE writing any Cosmos DB code)

---

### Pitfall 2: Losing Transactional Guarantees During Migration

**What goes wrong:** The existing PostgreSQL codebase relies on implicit transactions everywhere — `get_db()` wraps each request in `session.commit()` / `session.rollback()`. Operations like "create workflow + create nodes + create edges" happen atomically. Cosmos DB only supports transactions within a single logical partition (via TransactionalBatch), not across partitions or containers.

**Why it happens:** The `get_db()` dependency in FastAPI auto-commits on success or rolls back on any exception. Every service method implicitly assumes atomicity. When migrating to Cosmos DB, developers either: (a) ignore the problem and get partial writes, or (b) try to implement distributed transactions (Saga pattern) for every operation — massive over-engineering.

**Consequences:**
- **Partial writes:** Creating a workflow succeeds but its nodes fail → orphaned workflow document with no nodes. No rollback.
- **Data inconsistency:** Agent update succeeds but embedded tool list update fails → stale tool references.
- **Over-engineering:** Implementing Saga/compensating transactions for 20+ operations adds months of work.

**Prevention:**
1. **Partition key design eliminates most cross-partition writes.** If `tenant_id` is the partition key and you embed related data (agent + tools + config), most writes are single-partition and can use `TransactionalBatch`.
2. **Identify the 3-4 operations that genuinely need cross-container atomicity** (e.g., creating a tenant + seeding default data across containers) and implement compensating transactions ONLY for those.
3. **Accept eventual consistency for non-critical paths.** Tool definition updates propagating to embedded copies via Change Feed is fine with a few seconds' delay.
4. **Map every `await session.commit()` path** in the existing services to determine which ones touch multiple entities. The `agent_execution.py` service creates ExecutionLog + updates Thread + creates ThreadMessage — this needs to be a single document write or use TransactionalBatch within the `threads` partition.

**Detection:** Search for any Cosmos DB write pattern that makes >1 `create_item`/`upsert_item` call without TransactionalBatch wrapping. Each is a partial-write risk.

**Phase to address:** Data Migration phase (document model design) + Repository Pattern phase (service layer rewrite)

---

### Pitfall 3: Breaking Running Services During Monolith Decomposition

**What goes wrong:** Extracting microservices from a running monolith while maintaining the existing Docker Compose dev environment. The temptation is to do a "big bang" split — extract all services at once. This breaks both local development and production simultaneously.

**Why it happens:** The current `backend/app/` is a single FastAPI app with shared models, shared database session, shared middleware. Every service imports from `app.models` and `app.core.database`. Splitting requires untangling these shared imports, but doing it all at once means nothing works during the transition.

**Consequences:**
- **Development paralysis:** 2-4 weeks where neither the monolith nor the microservices work properly.
- **Integration test gaps:** Tests written against the monolith don't validate the microservice boundaries.
- **Import cycles:** Extracting `agent_execution` as a service but it imports `Tool`, `MCPDiscoveredTool`, `MCPServer`, `Thread`, `ThreadMessage`, `ExecutionLog` — half the model layer comes with it.

**Prevention:**
1. **Strangler Fig pattern.** Keep the monolith running. Extract ONE service at a time behind a reverse proxy. Route new traffic to the microservice, old traffic still hits the monolith.
2. **Start with the service that has the fewest cross-cutting dependencies.** Likely candidates: `evaluation_service` (isolated test suite execution), `marketplace_service` (read-heavy, few writes), or `observability_service` (mostly read aggregations).
3. **Shared library for models.** Create a `shared/` package with Pydantic models (NOT SQLAlchemy models) that both the monolith and new microservices import. This decouples data contracts from storage implementation.
4. **API-first boundaries.** Before extracting code, define the inter-service API contracts (OpenAPI specs). The monolith's internal function calls become HTTP/gRPC calls across the boundary.
5. **Keep Docker Compose working throughout.** Each extracted microservice gets its own Dockerfile and entry in `docker-compose.yml`. The monolith shrinks over time; individual services spin up alongside it.

**Detection:** If any PR touches >5 files across multiple service domains simultaneously, it's probably a "big bang" extraction attempt. Flag it.

**Phase to address:** Microservice Extraction phase (must be incremental, not big-bang)

---

### Pitfall 4: Audience/Issuer Confusion During JWT → Entra ID Migration

**What goes wrong:** The current auth is simple: `security.py` creates HS256 tokens with `SECRET_KEY`, `tenant.py` middleware decodes them. Migrating to Entra ID means the backend stops issuing tokens and starts validating externally-issued RS256 tokens. The most dangerous error is misconfiguring the `audience` (aud) claim validation — accepting tokens meant for a different app registration, or accepting both v1.0 and v2.0 tokens without realizing they have different `aud` formats.

**Why it happens:** Entra ID has TWO token versions:
- **v1.0 tokens:** `aud` = `api://<client-id>` (the API's app registration)
- **v2.0 tokens:** `aud` = `<client-id>` (just the GUID)

The frontend's MSAL config (`@azure/msal-browser` is already installed) requests tokens with a `scope`. If the scope uses `api://<client-id>/.default`, you get v1.0 tokens. If it uses `<client-id>/.default`, you might get v2.0. Developers often validate `aud` against the wrong format, causing all tokens to be rejected in production.

**Consequences:**
- **Total auth failure at deployment:** Everything works locally (dev tokens), breaks in production (different Entra ID tenant, different token version).
- **Security hole:** If audience validation is disabled to "fix" the problem, ANY Entra ID token from ANY application in the tenant can access the API.
- **Refresh token confusion:** MSAL handles refresh silently on the frontend. But if the backend has a dual-auth period (supporting both old JWT + new Entra tokens), refresh logic must handle both flows without leaking sessions.

**Prevention:**
1. **Pin the token version in the app registration manifest.** Set `accessTokenAcceptedVersion: 2` in the API's app registration → all tokens use v2.0 format → `aud` = GUID, consistently.
2. **Use `msal` library for token validation, not raw PyJWT.** `msal` handles JWKS key rotation, issuer discovery, audience validation correctly. Raw PyJWT requires manual JWKS fetching and `iss`/`aud` checks that are easy to get wrong.
3. **Implement a dual-auth transition period.** Middleware checks for Entra ID token first → falls back to legacy HS256 token → log a deprecation warning for legacy tokens. Set a hard cutoff date. The current `TenantMiddleware.dispatch()` already catches `jwt.InvalidTokenError` silently — this is where the dual-path logic goes.
4. **Map the `tid` (tenant ID) claim to your `tenants.slug` or `tenants.id`.** Entra ID's `tid` is the Azure AD tenant GUID, NOT your application's `tenant_id`. You need a mapping table: `entra_tenant_id → platform_tenant_id`.
5. **Test with tokens from a DIFFERENT Entra ID tenant** to verify they're rejected.

**Detection:** If token validation uses `algorithms=["RS256"]` without specifying `audience` and `issuer`, it's a security hole. Every token validation MUST check both.

**Phase to address:** Auth Migration phase (before any microservice extraction — auth is cross-cutting)

---

### Pitfall 5: RU Cost Explosion from Unbounded Queries

**What goes wrong:** The existing codebase has several patterns that translate to unbounded Cosmos DB scans: `select(Agent).where(Agent.tenant_id == tid)` returns ALL agents for a tenant with no pagination. `select(ExecutionLog)` in the observability service uses `func.count()` and `func.avg()` across entire result sets. These become full-partition scans in Cosmos DB, each consuming thousands of RUs.

**Why it happens:** In PostgreSQL, these queries are cheap — indexes + query planner handle them efficiently. In Cosmos DB, every query has an RU cost proportional to the data scanned, not just the data returned. A `SELECT COUNT(*)` equivalent scans every item in the partition. Aggregations (`AVG`, `SUM`) similarly scan all matching items.

**Consequences:**
- **A single dashboard load triggers 5,000+ RU** if the observability service runs aggregation queries across all execution logs.
- **429 throttling** when multiple tenants hit aggregate queries simultaneously, consuming all provisioned RU/s.
- **Unpredictable costs** — autoscale RU/s spikes to maximum on every dashboard refresh.

**Prevention:**
1. **Pre-aggregate metrics.** Don't query raw execution logs for dashboards. Maintain a `tenant_metrics` container with hourly/daily rollups: total_requests, avg_latency, total_tokens. Update via Change Feed processor.
2. **Enforce pagination on ALL list queries.** Every Cosmos DB query must use `max_item_count` (page size) and return continuation tokens. Never return all items. The existing `select(Agent).where(...)` pattern needs a mandatory `OFFSET/TOP` equivalent.
3. **Use `VALUE COUNT(1)` cautiously.** Cosmos DB can optimize `SELECT VALUE COUNT(1) FROM c WHERE c.tenant_id = @tid` as a single partition query (low RU), but `SELECT VALUE COUNT(1) FROM c` without partition key filter is a cross-partition scan (high RU).
4. **Profile every endpoint's RU cost during development.** The `azure-cosmos` SDK returns `request_charge` on every response. Build a middleware that logs this for every API call. Set alerts for any endpoint exceeding 100 RU.
5. **Serverless tier for dev/test.** Don't provision 400 RU/s minimum for development. Serverless charges per-request — cheaper for low-volume dev work. Switch to autoscale for production.

**Detection:** Enable Cosmos DB diagnostic settings → Log Analytics. Query: `CDBDataPlaneRequests | where RequestCharge > 50 | summarize count() by OperationName`. Any operation consistently >50 RU needs optimization.

**Phase to address:** Data Migration phase (document model + query design) + Observability phase (pre-aggregation)

---

### Pitfall 6: Namespace-Per-Tenant Sprawl Without Automation

**What goes wrong:** Creating AKS namespaces manually per tenant seems simple at 2-3 tenants. But each namespace needs: NetworkPolicy, ResourceQuota, LimitRange, ServiceAccount, RoleBinding, image pull secrets, and potentially per-tenant ConfigMaps/Secrets. Managing this manually for even 5 tenants means 35+ YAML manifests to keep synchronized.

**Why it happens:** The initial setup for 1-2 namespaces is trivial. But namespace-per-tenant requires identical security policies across all namespaces, and any change must be applied to ALL namespaces simultaneously. Without automation, namespaces drift — one tenant has outdated NetworkPolicy, another is missing ResourceQuota.

**Consequences:**
- **Security drift:** Tenant A's namespace has NetworkPolicy blocking cross-namespace traffic; Tenant B's doesn't (forgot to apply it). Tenant B's pods can reach Tenant A's services.
- **Resource exhaustion:** Without ResourceQuota, one tenant's pods consume all cluster resources, starving other tenants.
- **Toil explosion:** Every cluster configuration change requires `kubectl apply -n tenant-a`, `kubectl apply -n tenant-b`, ... Manual repetition guarantees missed tenants.

**Prevention:**
1. **Tenant provisioning operator or script.** Build a single command/API endpoint that creates a namespace and applies ALL required resources from a template. The FEATURES.md already specifies "Automated namespace provisioning" as table stakes — treat it as a hard prerequisite, not a nice-to-have.
2. **Kustomize overlays per tenant.** Base templates define NetworkPolicy, ResourceQuota, LimitRange. Per-tenant overlays customize only the namespace name, resource limits, and tenant-specific config. `kustomize build overlays/tenant-a/ | kubectl apply -f -`.
3. **NetworkPolicy defaults: deny-all ingress + explicit allowlists.** Every tenant namespace starts with `deny-all` ingress, then explicitly allows only: (a) ingress from the API gateway namespace, (b) egress to Cosmos DB private endpoint and Azure services. This is the single most important security control.
4. **ResourceQuota formula:** For 2-5 tenants, start with: CPU request = (cluster total × 0.8) / tenant_count, Memory request = same formula. Leave 20% for system namespaces. Adjust based on actual usage after 2 weeks.
5. **Label everything.** Every resource in a tenant namespace gets `tenant: <slug>` label. Use label selectors for bulk operations: `kubectl get all -l tenant=acme --all-namespaces`.

**Detection:** `kubectl get ns | wc -l` shows namespace count. `kubectl get networkpolicy -A | grep -c "default-deny"` should equal namespace count minus system namespaces. Any delta = security gap.

**Phase to address:** AKS/Kubernetes phase (namespace provisioning must be automated from the first tenant)

---

### Pitfall 7: Bicep Module Dependency Ordering and RBAC Timing

**What goes wrong:** Bicep modules deploy Azure resources with `dependsOn` controlling order. But RBAC role assignments have a propagation delay of 5-10 minutes after creation. If Module A creates a Managed Identity, Module B assigns it the "Cosmos DB Data Contributor" role, and Module C tries to use that identity to write to Cosmos DB — Module C fails because the role assignment hasn't propagated yet.

**Why it happens:** `dependsOn` in Bicep means "resource creation completed," not "resource is fully operational." ARM returns success for a role assignment as soon as the assignment is recorded, not when it's enforced. The Bicep deployment sees success and proceeds, but the permission isn't active yet.

**Consequences:**
- **Intermittent deployment failures.** The deployment works sometimes (if Azure propagates quickly) and fails other times. Developers add retries, then remove them when it "seems fixed," then it breaks again.
- **Circular dependency pain.** AKS needs Managed Identity → MI needs Cosmos DB role assignment → Cosmos DB needs AKS to exist for private endpoint → circular `dependsOn` that Bicep rejects.

**Prevention:**
1. **Split deployment into stages.** Stage 1: Networking (VNet, subnets, NSGs). Stage 2: Identity (Managed Identities, role assignments). Stage 3: Data (Cosmos DB, Key Vault). Stage 4: Compute (AKS, ACR). Execute as separate `az deployment group create` commands with a wait between Stage 2 and Stage 3.
2. **Use `existing` keyword liberally.** Reference resources created in earlier stages: `resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = { name: cosmosAccountName }`. This avoids circular dependencies.
3. **RBAC assignment MUST happen in its own module** with explicit `dependsOn` on both the identity AND the target resource. Don't inline role assignments in the resource module.
4. **Add a deployment script with retry logic for post-RBAC validation.** After role assignment, run a `Microsoft.Resources/deploymentScripts` that loops until the identity can actually authenticate to the target resource.
5. **Naming collisions: use a consistent naming convention from day one.** `{project}-{service}-{env}-{region}` (e.g., `aiplatform-cosmos-prod-eastus2`). Cosmos DB account names are globally unique — collisions cause cryptic deployment failures.

**Detection:** If `az deployment group create` fails with "AuthorizationFailed" or "ForbiddenByPolicy" intermittently, it's an RBAC propagation timing issue.

**Phase to address:** IaC/Bicep phase (first deployment scripts)

---

### Pitfall 8: Service-to-Service Auth Gaps After Monolith Split

**What goes wrong:** In the current monolith, `agent_execution.py` calls `rag_service.py` as a direct Python import — no auth needed. After splitting into microservices, Agent Service needs to call RAG Service over HTTP. Without service-to-service authentication, any pod in the cluster can call any internal API — a lateral movement risk.

**Why it happens:** Internal service calls feel "safe" because they're inside the cluster. Teams defer service auth as "we'll add it later." Meanwhile, the cluster has tenant namespaces with (hopefully) NetworkPolicy, but services within the shared infrastructure namespace can reach everything.

**Consequences:**
- **Lateral movement:** A compromised pod in one service can call every other service's internal API without authentication.
- **Tenant isolation breach:** Without service-to-service auth carrying tenant context, a confused-deputy attack can make Service A read data belonging to Tenant B.
- **Audit trail gaps:** No way to determine which service initiated a cross-service request.

**Prevention:**
1. **AKS Workload Identity from day one.** Each microservice gets its own Kubernetes ServiceAccount federated with an Azure Managed Identity. Services authenticate to each other using Azure Managed Identity tokens.
2. **Propagate tenant context in service-to-service calls.** Every internal HTTP call includes a `X-Tenant-ID` header (verified from the original JWT `tid` claim, not user-supplied). Receiving services validate this header against their own tenant resolution.
3. **mTLS via service mesh (Istio or Linkerd) as a stretch goal.** For 2-5 tenants, Workload Identity + NetworkPolicy is sufficient. Service mesh adds operational complexity disproportionate to the threat model.
4. **Internal APIs on separate ports.** Public API on port 8000, internal API on port 8001. NetworkPolicy allows port 8001 only from specific service namespaces.

**Detection:** `kubectl exec` into a service pod and `curl` another service's internal endpoint. If it returns data without auth headers, service-to-service auth is missing.

**Phase to address:** Microservice Extraction phase (establish pattern with the first extracted service)

---

### Pitfall 9: Partition Key Mismatch Between Access Patterns and Data Model

**What goes wrong:** Using `tenant_id` as the partition key for EVERY container seems logical for multi-tenancy. But some access patterns don't include `tenant_id` in the query — for example, looking up a thread by `thread_id` across the platform (admin operations), or querying execution logs by `agent_id` for cross-tenant analytics.

**Why it happens:** The existing codebase uses `tenant_id` as an index filter on every table, reinforcing the assumption that `tenant_id` should be the partition key everywhere. But indexes and partition keys serve different purposes — Cosmos DB partition keys determine physical data distribution, not just query filtering.

**Consequences:**
- **Cross-partition fan-out for admin queries.** An admin query like "find thread by ID" without knowing the tenant becomes a cross-partition query hitting every physical partition — O(partition_count) RU cost.
- **Hot partitions.** If one tenant (e.g., a power user team) generates 90% of the execution logs, the `tenant_id` partition for that tenant becomes a hotspot. All writes and reads concentrate on one physical partition.
- **20 GB partition limit.** A tenant with millions of execution logs hits the 20 GB logical partition limit. Cosmos DB rejects writes.

**Prevention:**
1. **Use Hierarchical Partition Keys.** Cosmos DB supports up to 3 levels: `/tenant_id/entity_type/id`. This distributes data within a tenant across sub-partitions while still allowing efficient tenant-scoped queries.
2. **Container-specific partition keys.** Not every container needs the same key:
   - `agents` container: `/tenant_id` (low volume per tenant, always queried by tenant)
   - `threads` container: `/tenant_id` (threads always accessed in tenant context)
   - `execution_logs` container: hierarchical `/tenant_id/agent_id` (high volume, queries filter by agent)
   - `workflows` container: `/tenant_id` (low volume)
3. **Point reads for cross-tenant admin lookups.** Store a global index (separate container with `/id` as partition key) for cross-tenant lookups. This adds a denormalized lookup container but avoids cross-partition scans.
4. **Estimate partition sizes before migration.** Count rows per tenant in the existing PostgreSQL tables. If any tenant × entity exceeds 10 GB worth of documents, hierarchical partition keys are required.

**Detection:** Azure Monitor → Cosmos DB metrics → "Normalized RU Consumption by PartitionKeyRangeId." If one partition range shows >70% utilization while others are <10%, you have a hot partition.

**Phase to address:** Data Migration phase (partition key design is the SINGLE most important Cosmos DB decision — cannot be changed after container creation)

---

### Pitfall 10: GitHub Actions Secrets Sprawl and Image Tag Mutability

**What goes wrong:** Storing Azure credentials, ACR passwords, Cosmos DB keys, and per-environment configs as GitHub Actions secrets. As services multiply (API Gateway, Agent Service, RAG Service, Eval Service, etc.) and environments increase (dev, staging, prod), the secrets count explodes. Developers start hardcoding values or sharing secrets across workflows to reduce friction.

**Why it happens:** GitHub Actions secrets are flat (no hierarchy). There's no `secrets.prod.cosmos.key` — just `COSMOS_KEY_PROD`, `COSMOS_KEY_STAGING`, etc. With 5 microservices × 3 environments × 4-5 secrets each, you hit 60+ secrets. Managing rotations becomes a nightmare.

**Consequences:**
- **Secret rotation failure.** Key rotation requires updating 10+ secrets simultaneously. If you miss one, one environment or service silently breaks.
- **Mutable image tags.** Using `latest` or `main` as Docker image tags means `kubectl rollout undo` doesn't actually roll back — it re-pulls the same tag, which now points to the broken image.
- **No rollback path.** Without immutable, versioned image tags, there's no way to deploy "the exact image that was running yesterday."

**Prevention:**
1. **OIDC federated credentials, not stored secrets.** The STACK.md already specifies `azure/login@v2` with OIDC. This eliminates Azure credential secrets entirely — GitHub Actions authenticates to Azure via federated identity, no secrets to rotate.
2. **Key Vault for application secrets.** Cosmos DB keys, model API keys, and connection strings live in Azure Key Vault, not GitHub secrets. Bicep provisions Key Vault; application reads secrets at runtime via Managed Identity. GitHub Actions needs exactly ONE secret: the OIDC app registration (or zero if using org-level OIDC).
3. **Immutable image tags: `git sha` + `build number`.** Tag format: `acr.azurecr.io/agent-service:sha-a1b2c3d-42`. Never use `latest`. The Helm values file references the exact tag. Rollback = deploy the previous tag.
4. **GitHub Environments for promotion.** Use GitHub Environments (dev, staging, prod) with protection rules. Each environment has its own OIDC trust policy scoped to that environment. Production requires manual approval.
5. **Image scanning before deployment.** Add `trivy` or `microsoft/container-scan` Action between build and deploy. Block deployment if critical CVEs are found.

**Detection:** `grep -r "latest" .github/workflows/` — if any workflow uses `latest` as an image tag, fix immediately. Count secrets in GitHub settings: if >10, evaluate which should be in Key Vault instead.

**Phase to address:** CI/CD phase (establish patterns with the first pipeline, before adding more services)

---

### Pitfall 11: OpenTelemetry Metric Cardinality Explosion

**What goes wrong:** Adding `tenant_id` and `agent_id` as dimensions to every OpenTelemetry metric. With 5 tenants × 100 agents × 20 metric types, you create 10,000 time series. Each additional dimension (model_endpoint, tool_name, status_code) multiplies the cardinality. Azure Monitor charges per time series per month.

**Why it happens:** Developers want per-tenant, per-agent visibility. The natural instinct is to add every identifier as a metric label/attribute. The `azure-monitor-opentelemetry` distro auto-instruments FastAPI, creating `http_server_request_duration` metrics. Adding `tenant_id` to every resource attribute seems harmless — until it's multiplied by routes × status codes × methods.

**Consequences:**
- **Azure Monitor cost spike.** Custom metrics pricing is per-time-series per month. 10,000+ series can cost more than the compute infrastructure.
- **Dashboard slowness.** High-cardinality metrics cause slow queries in Log Analytics and Application Insights.
- **Sampling rate confusion.** Azure Monitor applies adaptive sampling to reduce data volume, but sampling can drop critical error traces. Without understanding sampling, teams miss errors.

**Prevention:**
1. **Traces carry tenant/agent context, not metrics.** Use `tenant_id` and `agent_id` as span attributes (traces), not metric dimensions. Traces are sampled; metrics are aggregated. Query traces for per-tenant debugging; use metrics for aggregate health.
2. **Limit custom metric dimensions to LOW cardinality.** Good dimensions: `service_name` (5 values), `env` (3 values), `status_class` (2xx/4xx/5xx = 3 values). Bad dimensions: `tenant_id` (unbounded), `agent_id` (unbounded), `user_id` (unbounded).
3. **Pre-aggregate in application code.** Instead of emitting per-request metrics with `tenant_id`, maintain in-memory counters per tenant, flush to a `tenant_metrics` Cosmos DB container every 60 seconds. Dashboard queries this container, not Azure Monitor.
4. **Set sampling rate explicitly.** Default `azure-monitor-opentelemetry` may use adaptive sampling. Set `OTEL_TRACES_SAMPLER=parentbased_traceidratio` with `OTEL_TRACES_SAMPLER_ARG=0.1` (10% of traces in production). Keep 100% sampling for errors: configure an `always_on` sampler for error spans.
5. **Configure `configure_azure_monitor()` once at startup with resource attributes.** Don't reconfigure per-request. The `service.name` resource attribute should be the microservice name, not include tenant context.

**Detection:** Azure Monitor → Metrics → "Custom Metric Namespace" → check unique time series count. If >1,000 in dev, you'll hit 100,000+ in production. Also: check monthly Application Insights bill — if data ingestion cost exceeds $50/month in dev, investigate cardinality.

**Phase to address:** Observability phase (instrument AFTER microservices are split, not before — otherwise you're instrumenting code that will be restructured)

---

### Pitfall 12: Cosmos DB Document Schema Evolution Without Versioning

**What goes wrong:** The existing system uses Alembic migrations (13 versions) to evolve the PostgreSQL schema. Cosmos DB is schemaless — there are no migrations. Developers assume this means schema management is unnecessary. Then an Agent document's structure changes (new field, renamed field, removed field), and old documents in the container silently break deserialization.

**Why it happens:** "Schemaless" is misleading. Cosmos DB doesn't enforce a schema, but your application code still expects specific fields. Pydantic models (the replacement for SQLAlchemy models per STACK.md) will throw `ValidationError` when reading old documents that lack new required fields.

**Consequences:**
- **Runtime crashes on read.** Adding a required field to the Pydantic model breaks ALL existing documents that don't have the field.
- **Silent data corruption.** Renaming `model_endpoint_id` to `endpoint_id` means old documents have the old key, new documents have the new key. Queries filter on the new key, silently missing old documents.
- **No rollback path.** Unlike Alembic's `downgrade()`, there's no automated way to revert a Cosmos DB schema change.

**Prevention:**
1. **Add a `_schema_version` field to every document.** Start at `1`. Every structural change increments the version. Read logic checks the version and transforms old documents on read (or lazily migrates them).
2. **New fields MUST have defaults in Pydantic models.** Never add a field as `required` (no default) to a Pydantic model that deserializes existing documents. Always: `new_field: str = "default_value"` or `new_field: Optional[str] = None`.
3. **Never rename fields — add new, mark old as deprecated.** Keep the old field, add the new field with a default that references the old field. A background migration job copies old→new. Delete the old field only after ALL documents are migrated.
4. **Write a document migration utility (equivalent to Alembic but for Cosmos DB).** Script that reads all documents in a container, transforms them to the latest schema, writes them back. Version-controlled alongside code. Run as part of deployment pipeline.

**Detection:** Query for documents missing expected fields: `SELECT VALUE COUNT(1) FROM c WHERE NOT IS_DEFINED(c._schema_version)`. If this returns >0 after a migration script run, the migration is incomplete.

**Phase to address:** Data Migration phase (establish schema versioning pattern with the very first container)

---

## Moderate Pitfalls

Mistakes that cause significant rework or operational pain, but don't cause data loss or security breaches.

---

### Pitfall 13: Docker Compose Local Dev Falls Out of Sync with AKS

**What goes wrong:** Local development uses Docker Compose (current setup), production uses AKS. Developers test against Docker Compose, which doesn't have namespace isolation, NetworkPolicy, ResourceQuota, Managed Identity, or Workload Identity. Features work locally but fail in AKS because they depend on things Docker Compose doesn't simulate.

**Prevention:**
1. **Cosmos DB Emulator in Docker Compose.** Replace the PostgreSQL service with the Cosmos DB Linux emulator container for local dev. This validates Cosmos DB query patterns locally. Note: the emulator supports NoSQL API but has limitations (no Change Feed, no hierarchical partition keys). Document what can't be tested locally.
2. **Use `kind` (Kubernetes in Docker) for integration testing.** A `kind` cluster in CI validates namespace isolation, NetworkPolicy, and RBAC before deploying to AKS. Not for daily dev (too heavy), but for CI pipelines.
3. **Environment-specific configuration.** A single `settings.py` config class with `COSMOS_EMULATOR=true` for local, `COSMOS_ENDPOINT=https://...` for production. Never hardcode endpoints.
4. **Test matrix in CI:** Run unit tests against mocks → integration tests against Cosmos DB emulator → deployment tests against a dev AKS cluster.

**Phase to address:** IaC/Bicep phase (local dev environment setup) + CI/CD phase (test matrix)

---

### Pitfall 14: Tenant Middleware Migration — Dual-State Auth Complexity

**What goes wrong:** The current `TenantMiddleware` extracts `tenant_id` from an HS256 JWT cookie. During migration, it must simultaneously support: (a) legacy HS256 tokens (existing sessions), (b) Entra ID RS256 tokens (new logins), (c) service-to-service Managed Identity tokens (internal calls). Adding three auth paths to a single middleware creates a testing nightmare.

**Prevention:**
1. **Auth strategy chain pattern.** Don't use if/elif/else in the middleware. Create an `AuthStrategy` interface with implementations: `LegacyJWTStrategy`, `EntraIDStrategy`, `ManagedIdentityStrategy`. Middleware iterates strategies in order until one succeeds.
2. **Feature flag for legacy auth.** `LEGACY_AUTH_ENABLED=true` allows HS256 tokens. Set with a target end-of-life date. Monitor usage: log every legacy token auth. When count drops to zero, disable.
3. **Tenant ID mapping is the critical piece.** Entra ID tokens have `tid` (Azure tenant GUID) and `oid` (user object ID). Neither matches the existing `tenants.id` (a UUID you assigned). You need an `entra_tenant_mappings` table: `(entra_tid, platform_tenant_id)`. Populate this during tenant onboarding.
4. **Test matrix:** Test every API endpoint with each auth type. Automated tests must cover: valid legacy token, valid Entra token, valid MI token, expired tokens for each type, tokens from wrong tenant for each type.

**Phase to address:** Auth Migration phase (implement before microservice extraction — auth is shared infrastructure)

---

### Pitfall 15: Forgetting to Migrate Junction Tables to Embedded Arrays

**What goes wrong:** The codebase has N-to-M junction tables: `agent_tools`, `agent_data_sources`, `agent_mcp_tools`. In PostgreSQL, these are separate tables with foreign keys. Developers instinctively create separate Cosmos DB containers for them — recreating relational patterns in a document database.

**Prevention:**
1. **Junction tables → embedded arrays.** `AgentTool` junction → `tools: [{ tool_id, name, config }]` embedded in the Agent document. Eliminates a container and a query.
2. **But check the update pattern.** If tools are updated independently (and frequently), embedding creates a problem: updating a single tool requires reading + replacing the entire Agent document. If tool definitions change <1% of the time agents are read, embedding wins. If tools change hourly, reference by ID and accept the extra read.
3. **Map every junction table:** `agent_tools` → embed in Agent (tools don't change often). `agent_data_sources` → embed in Agent. `agent_mcp_tools` → embed in Agent. `workflow_nodes` → embed in Workflow. `workflow_edges` → embed in Workflow. This eliminates 5 containers and their associated query overhead.

**Phase to address:** Data Migration phase (document model design)

---

### Pitfall 16: AKS DNS and Service Discovery Across Tenant Namespaces

**What goes wrong:** In Kubernetes, a service in namespace `tenant-a` can reach a service in namespace `shared-infra` via `service-name.shared-infra.svc.cluster.local`. But if microservices are deployed per-tenant (each tenant namespace has its own Agent Service pod), tenant-to-shared-service DNS resolution must be explicitly allowed in NetworkPolicy.

**Prevention:**
1. **Shared services in a `shared-infra` namespace.** API Gateway, Auth Service, Cosmos DB proxy (if needed) run in a shared namespace. Tenant namespaces contain only tenant-specific workloads.
2. **NetworkPolicy allows DNS egress.** Every tenant namespace NetworkPolicy must allow egress to `kube-dns` (port 53) in the `kube-system` namespace, plus egress to specific services in `shared-infra`. Forgetting the DNS egress rule means pods can't resolve ANY service names.
3. **Use Kubernetes Service FQDNs in configuration.** Don't rely on short service names. Configure inter-service URLs as `http://api-gateway.shared-infra.svc.cluster.local:8000`, not `http://api-gateway:8000` (which only works in the same namespace).

**Phase to address:** AKS/Kubernetes phase (NetworkPolicy design)

---

### Pitfall 17: Bicep Naming Collisions on Globally Unique Resources

**What goes wrong:** Cosmos DB account names, ACR names, and Key Vault names are globally unique across all of Azure. Using generic names like `aiplatform-cosmos` or `myacr` will collide with other Azure customers. The deployment fails with a cryptic "NameNotAvailable" error.

**Prevention:**
1. **Include a unique suffix in globally scoped names.** Use `uniqueString(resourceGroup().id)` in Bicep to generate a deterministic hash. Example: `var cosmosName = 'aiplatform-cosmos-${uniqueString(resourceGroup().id)}'` → `aiplatform-cosmos-x7k3m2p`.
2. **Validate names before deployment.** `az cosmosdb check-name-exists --name <name>`. Add this as a pre-deployment check in CI/CD.
3. **Document the naming convention in the first Bicep module.** All subsequent modules follow it. The convention goes into a shared `naming.bicep` module that other modules import.

**Phase to address:** IaC/Bicep phase (first module development)

---

## Minor Pitfalls

Issues that cause friction or confusion but are easily corrected.

---

### Pitfall 18: Forgetting Cosmos DB Emulator Limitations

**What goes wrong:** The Cosmos DB Linux emulator doesn't support: hierarchical partition keys, Change Feed processor, continuous backup, or multi-region. Developers rely on the emulator for testing these features, find they work differently in production.

**Prevention:** Maintain a `EMULATOR_LIMITATIONS.md` document. Test Change Feed and hierarchical partition keys against a real (dev/staging) Cosmos DB instance, not the emulator. Budget for a low-cost serverless Cosmos DB dev account.

**Phase to address:** Data Migration phase (local dev setup)

---

### Pitfall 19: MSAL Token Cache in Multi-Instance FastAPI

**What goes wrong:** MSAL's default token cache is in-memory. When FastAPI runs with multiple uvicorn workers (or multiple pods in AKS), each instance has its own token cache. Token refresh on instance A doesn't propagate to instance B, causing intermittent "invalid_grant" errors.

**Prevention:** Configure MSAL with a distributed token cache (Redis-backed). The existing Redis instance in the architecture handles this. Don't use file-based token cache (doesn't work across pods).

**Phase to address:** Auth Migration phase

---

### Pitfall 20: GitHub Actions Workflow Triggering on Every Commit

**What goes wrong:** Without path filters, every push to `main` triggers a build+deploy for ALL microservices. With 5+ services, this wastes CI minutes and risks deploying unchanged services.

**Prevention:** Use `paths` filters in workflow triggers:
```yaml
on:
  push:
    branches: [main]
    paths: ['backend/services/agent-service/**']
```
Or use a monorepo-aware action (`dorny/paths-filter`) to detect which services changed and deploy only those.

**Phase to address:** CI/CD phase (workflow design)

---

### Pitfall 21: Azure Monitor Workspace vs. Application Insights Confusion

**What goes wrong:** Azure Monitor has three overlapping concepts: Log Analytics Workspace (for logs/KQL), Application Insights (for APM/traces), and Azure Monitor Workspace (for Prometheus metrics). Provisioning the wrong one, or provisioning all three without connecting them, results in metrics in one place, logs in another, and traces nowhere.

**Prevention:** Provision ONE Log Analytics Workspace. Connect Application Insights to it (workspace-based mode, not classic). Connect AKS Container Insights to the same workspace. All telemetry flows to one place, queryable via KQL.

**Phase to address:** Observability phase (Bicep provisioning)

---

## Integration Pitfalls (Cross-Cutting)

Pitfalls that span multiple migration areas and manifest at integration boundaries.

---

### Integration Pitfall A: Cosmos DB + AKS + Managed Identity Triangle

**What goes wrong:** The Cosmos DB SDK on a pod needs to authenticate via Workload Identity → Managed Identity → RBAC role on Cosmos DB. Three independent systems (AKS OIDC issuer, Azure Managed Identity federation, Cosmos DB RBAC) must all be configured correctly. A misconfiguration in any one layer causes "401 Unauthorized" with no clear error about which layer failed.

**Prevention:**
1. **Test the auth chain independently.** Verify each layer: (a) `kubectl exec` into a pod and check `AZURE_FEDERATED_TOKEN_FILE` exists, (b) use `azure-identity` to get a token and print `token[:20]...`, (c) use that token against Cosmos DB directly.
2. **Use `DefaultAzureCredential` with `logging.DEBUG` during setup.** It prints which credential method it's trying. In AKS, it should use `WorkloadIdentityCredential` → `ManagedIdentityCredential` chain.
3. **Provision in order:** Managed Identity → RBAC assignment → wait 10 min → AKS pod with Workload Identity → verify.

**Phase to address:** IaC/Bicep phase (identity) + AKS phase (workload identity) — these MUST be tested together before deploying any application code.

---

### Integration Pitfall B: Auth Migration + Microservice Split Ordering

**What goes wrong:** Extracting microservices before auth migration means the extracted services still use HS256 JWT cookies. Then when auth migrates to Entra ID, every extracted service must be updated simultaneously. But migrating auth first (while still a monolith) means only ONE codebase needs to change.

**Prevention:** Migrate auth → Entra ID FIRST (while still a monolith). Then extract microservices. Each extracted service inherits the new auth pattern from day one. The Strangler Fig extraction pattern naturally follows this order.

**Phase to address:** Milestone planning (phase ordering)

---

### Integration Pitfall C: Data Migration + Local Dev + CI/CD Simultaneity

**What goes wrong:** Three teams start in parallel: Team A works on Cosmos DB data layer, Team B on AKS deployment, Team C on CI/CD pipelines. Team A needs a running Cosmos DB to test. Team B needs container images to deploy. Team C needs both to build a pipeline. Without coordination, each team builds their own mock/stub that diverges from what the others expect.

**Prevention:**
1. **IaC (Bicep) deploys a dev environment FIRST.** Before any code migration starts. This gives all teams a real Cosmos DB account, a real AKS cluster, and a real ACR to work against.
2. **Shared docker-compose.yml remains the local dev environment.** Add Cosmos DB emulator container. All teams use the same local environment.
3. **Phase ordering: IaC → Auth → Data Layer → Microservice Extraction → CI/CD → Observability.** Each phase builds on the previous one.

**Phase to address:** Milestone planning (phase ordering and dependencies)

---

## Phase-Specific Warnings (Summary Matrix)

| Phase Topic | Most Likely Pitfall | Severity | Mitigation |
|-------------|--------------------|---------|----|
| IaC / Bicep | RBAC propagation timing (#7), naming collisions (#17) | High | Staged deployments, `uniqueString()` |
| Auth Migration | Audience confusion (#4), dual-auth complexity (#14), MSAL cache (#19) | Critical | Pin token version, strategy chain, Redis cache |
| Cosmos DB Data Migration | JOIN translation (#1), schema evolution (#12), partition key mismatch (#9) | Critical | Denormalize, schema versioning, hierarchical partition keys |
| Microservice Extraction | Big-bang split (#3), service-to-service auth (#8) | High | Strangler Fig, Workload Identity from day one |
| AKS / Kubernetes | Namespace sprawl (#6), DNS/NetworkPolicy (#16) | High | Automated provisioning, deny-all default |
| CI/CD | Secrets sprawl (#10), mutable tags (#10), workflow over-triggering (#20) | Medium | OIDC + Key Vault, SHA-based tags, path filters |
| Observability | Metric cardinality (#11), workspace confusion (#21) | Medium | Traces for context, metrics for aggregates, single workspace |
| Cross-cutting | MI auth triangle (A), phase ordering (B, C) | High | Test auth chain independently, IaC first |

---

## Recommended Phase Ordering Based on Pitfalls

Analysis of pitfall dependencies suggests this order minimizes risk:

1. **IaC / Bicep** — Deploy dev environment first. All other phases need Azure resources to exist.
2. **Auth Migration** — Migrate to Entra ID while still a monolith (Integration Pitfall B). One codebase to change.
3. **Cosmos DB Data Layer** — Design document model, implement repository pattern, migrate data. Must happen in monolith context where you can test against both PostgreSQL and Cosmos DB simultaneously.
4. **Microservice Extraction** — Strangler Fig, one service at a time. Auth and data patterns already established.
5. **AKS / Kubernetes** — Namespace provisioning, NetworkPolicy, deployment manifests. Needs container images from microservice extraction.
6. **CI/CD** — Automate what you've been doing manually. Needs AKS target + container images + tested deployment process.
7. **Observability** — Instrument AFTER services are split and deployed. Instrumenting code that will be restructured wastes effort.

---
*Researched: 2026-03-26*
*Confidence: HIGH (grounded in codebase analysis + official Microsoft documentation + Cosmos DB best practices skill)*
