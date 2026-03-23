# Pitfalls Research

**Domain:** Enterprise AI Platform System (Azure AI Foundry / Vertex AI / Bedrock competitor)
**Researched:** 2026-03-23
**Confidence:** HIGH

---

## Critical Pitfalls

### Pitfall 1: Wrong Cosmos DB Partition Key Locks You In Forever

**What goes wrong:**
Teams pick a partition key for their multi-tenant data (model metadata, usage logs, project data) without understanding Cosmos DB's partitioning model. Common mistakes: using a low-cardinality key (e.g., `modelProvider` with only 3–5 values), using `projectId` when a few large projects dominate traffic, or not planning for the 20 GB logical partition limit. Once chosen, the partition key **cannot be changed in place** — you must migrate all data to a new container. At scale with billions of records, this becomes a multi-day migration with downtime risk.

**Why it happens:**
Cosmos DB partition key choice feels like a simple config decision early on. Teams prototype with small datasets where any key works. The consequences only surface at production scale when hot partitions cause throttling (429 errors) and costs spike from inefficient RU consumption. Per Azure docs, each physical partition has a hard limit of 10,000 RU/s, so a hot partition becomes a throughput ceiling that can't be fixed without data migration.

**How to avoid:**
- Use `tenantId` (or `projectId`) as partition key for tenant-isolated containers — but only if tenants are roughly equal in size. For uneven tenants, use hierarchical partition keys: `tenantId` → `userId` → `sessionId` to break past the 20 GB limit.
- For usage/logging data, use a synthetic key combining `tenantId + date` to spread writes evenly.
- Design partition strategy during architecture phase and load-test with realistic data distribution before building services.
- Set up Azure Monitor alerts for logical partitions approaching 20 GB.
- Plan separate Cosmos DB containers (or accounts) for distinct access patterns: model metadata (read-heavy), usage logs (write-heavy), conversation state (read+write).

**Warning signs:**
- 429 (throttled) responses concentrated on specific logical partitions
- Uneven RU consumption across physical partitions visible in Cosmos DB metrics
- One tenant/project consuming disproportionate throughput
- Logical partition size approaching 20 GB

**Phase to address:**
Database schema and data layer design phase. Must be decided before any service writes data to Cosmos DB. Revisiting this after production launch requires data migration.

**Sources:**
- Microsoft Docs: Partitioning and horizontal scaling in Azure Cosmos DB (updated 2026-02-02)
- Microsoft Docs: Multitenancy and Azure Cosmos DB architecture guide (updated 2024-11-18)

**Confidence:** HIGH

---

### Pitfall 2: Not Designing for Streaming Responses from Day 1

**What goes wrong:**
Teams build the API gateway and frontend assuming traditional request-response semantics. When they integrate LLM inference (which streams tokens via SSE/Server-Sent Events), the entire pipeline needs retrofitting: the API gateway must support long-lived connections, load balancers need WebSocket/SSE awareness, the frontend needs streaming parse logic, and observability must handle partial responses. Retrofitting streaming into a request-response architecture typically requires rewriting the API gateway, proxy layers, and frontend data flow.

**Why it happens:**
Classical API design treats every call as request → response. REST frameworks, API Management policies, and standard middleware (auth, rate limiting, logging) all assume the response arrives as one payload. LLM streaming breaks every assumption: responses arrive token-by-token over 10–60 seconds, connections stay open, and you can't buffer the full response before sending it downstream (users expect real-time token display).

**How to avoid:**
- Design the API gateway to support SSE from the very first endpoint. Use Azure API Management's streaming support or build a custom gateway on AKS that handles chunked transfer encoding.
- Implement a dual-mode response pattern: `stream=true` returns SSE, `stream=false` returns buffered JSON. Both modes should share the same auth, rate limiting, and logging pipeline.
- Frontend architecture must use streaming parsers (e.g., `ReadableStream` / `fetch` streaming API) from the start.
- Observability must capture token-level metrics: time-to-first-token (TTFT), inter-token latency, total tokens, and handle the case where a stream is interrupted mid-response.

**Warning signs:**
- API gateway or proxy layers buffer full responses before forwarding
- Load balancer timeouts on inference requests (defaults are typically 30–60 seconds, model responses can exceed this)
- Frontend shows "loading" for 15+ seconds with no progressive output
- No distinction between streaming and non-streaming endpoints in API contracts

**Phase to address:**
API gateway design and core infrastructure phase. Must be part of the initial API contract and gateway architecture. Cannot be an afterthought.

**Confidence:** HIGH

---

### Pitfall 3: Azure OpenAI Quota and Rate Limit Architecture Blindness

**What goes wrong:**
Teams deploy Azure OpenAI models and hit quota walls in production. Azure OpenAI quotas are scoped per-subscription, per-region, per-model, and per-deployment-type, with complex tiering (Free through Tier 6) that automatically adjusts based on usage patterns. A multi-tenant platform multiplies this complexity: all tenants share the platform's subscription quotas. Teams either run out of quota under load, hit 429 rate limits, or overcommit to expensive Provisioned Throughput Units (PTU) too early.

**Why it happens:**
The Azure OpenAI quota system is complex and layered. Default Tier 1 quotas (e.g., 1,000 RPM for GPT-4.1 GlobalStandard) seem adequate for development but are immediately saturated when multiple tenants hit inference simultaneously. Teams don't realize that quotas are shared across all deployments in a subscription/region, or that exceeding usage tiers causes unpredictable latency increases (2x+ latency variance). Multi-subscriptions/multi-region deployment patterns needed for production are not planned for.

**How to avoid:**
- Plan a multi-region, multi-subscription deployment strategy from the start. Spread model deployments across regions to get independent quota pools per region.
- Implement a smart routing layer (API Management or custom gateway) that routes inference requests across regions based on quota availability and latency. Refer to Azure's "gateway in front of multiple Azure OpenAI deployments" pattern.
- Distinguish between pay-as-you-go (Standard/GlobalStandard) for variable workloads and Provisioned Throughput Units (PTU) for latency-critical SLA-bound tenants. Don't commit to PTU until usage patterns are stable.
- Build tenant-level rate limiting and quota allocation on top of Azure's subscription-level quotas. The platform must enforce per-tenant TPM/RPM limits before Azure's platform-level throttling kicks in.
- Monitor usage against tier thresholds. Request quota increases proactively via Azure's quota request form.
- Use Global Standard or Data Zone Standard deployments for built-in multi-datacenter resilience instead of single-region Standard deployments.

**Warning signs:**
- 429 errors in production even when individual tenant usage seems low
- Latency variance spikes (2x+ normal) indicating usage tier exceeded
- All model deployments in a single region/subscription
- No tenant-level rate limiting — relying solely on Azure's platform-level throttling
- PTU commitments made before understanding actual usage patterns

**Phase to address:**
Model deployment infrastructure and API gateway phases. Must be designed before onboarding enterprise tenants.

**Sources:**
- Microsoft Docs: Azure OpenAI in Microsoft Foundry Models quotas and limits (updated 2026-02-28)
- Tier system: 7 tiers (Free through 6) with automatic upgrades based on consumption

**Confidence:** HIGH

---

### Pitfall 4: Multi-Tenant Data Isolation Failures

**What goes wrong:**
A multi-tenant AI platform leaks data between tenants. This manifests as: Tenant A's fine-tuning data appearing in Tenant B's model responses, shared model caches mixing embeddings across tenants, inference request logs from one project visible to another project's admin, or API keys/tokens granting cross-tenant access. In enterprise AI, this is catastrophic — it violates compliance (SOC 2, GDPR) and destroys customer trust permanently.

**Why it happens:**
AI workloads have unique isolation challenges beyond traditional SaaS:
- **Shared model infrastructure**: Model serving endpoints may cache embeddings, inference context, or KV-cache across requests from different tenants.
- **Fine-tuning data contamination**: If fine-tuning jobs share compute or storage without proper sandboxing, training data can bleed across tenants.
- **Shared vector databases**: RAG (Retrieval-Augmented Generation) pipelines that store all tenant embeddings in one index without partition-level access control.
- **Prompt/response logging**: Centralized logging that doesn't enforce tenant-scoped access creates audit and compliance nightmares.

**How to avoid:**
- Design isolation model per component: Cosmos DB partition-key-per-tenant for metadata, separate Azure OpenAI resources or deployment scopes per premium tenant, per-tenant vector search indexes in AI Search.
- Never share fine-tuning compute or storage across tenants. Use per-tenant storage accounts or containers with strict RBAC.
- Implement row-level/partition-level access control in all data stores. Every query must include a tenant filter — never rely on application code alone.
- For model serving: use separate deployments per tenant for premium isolation, or validate that shared deployments don't leak context (Azure OpenAI's managed endpoints handle this, but custom model hosting may not).
- Ensure logging and observability pipelines are tenant-scoped. Cosmos DB's partition-key-per-tenant model naturally supports this.
- Run penetration tests specifically targeting cross-tenant data access.

**Warning signs:**
- No tenant filter enforcement at the data access layer (relying on application code to filter)
- Shared vector indexes without access control partitions
- Single fine-tuning job queue processing multiple tenants' data
- Admin dashboards that don't scope data by tenant/project
- No automated tests validating tenant isolation

**Phase to address:**
Authentication/authorization and data layer phases. Isolation boundaries must be defined architecturally before building any multi-tenant features.

**Confidence:** HIGH

---

### Pitfall 5: Monolithic Unified API That Can't Handle Model Diversity

**What goes wrong:**
Teams design a single, rigid API schema (`/v1/inference`) that tries to abstract away all model types: LLMs (chat completions), embedding models, image generation, speech-to-text, custom ML classifiers. The result is a lowest-common-denominator API that either forces awkward parameter mappings ("image prompt" crammed into "messages" field) or grows into a bloated schema with dozens of optional fields. Provider-specific features (function calling, structured output, tool use, vision inputs) are either impossible to expose or require constant schema updates.

**Why it happens:**
"Unified API" is a core value proposition (like the project's stated goal). Teams logically conclude this means one endpoint with one schema. But AI model types have fundamentally different I/O patterns: chat models take message arrays and stream tokens, embedding models take text arrays and return float vectors, image models take prompts and return binary blobs, speech models take audio and return text. Forcing these into one schema creates friction for every user segment.

**How to avoid:**
- Design a **unified but polymorphic** API: shared authentication, shared routing, shared observability — but model-type-specific request/response schemas. Example: `/v1/chat/completions`, `/v1/embeddings`, `/v1/images/generations` (following OpenAI's pattern, which is now the de facto industry standard).
- Use a capability registry that advertises what each model supports (streaming, function calling, vision, structured output). Clients query capabilities before making requests.
- Build an adapter layer per model provider (OpenAI, Anthropic, open-source via Azure ML endpoints) that translates the platform's API to the provider's native API. Don't force providers into a common internal schema.
- Plan for model capability evolution: new features like tool use, multimodal inputs, and structured output will emerge. The API must be extensible without breaking changes.

**Warning signs:**
- High rate of API design discussions/arguments about "how to represent X in the unified schema"
- Users requesting raw passthrough to provider APIs (bypassing your abstraction)
- Provider-specific features requiring schema changes for every integration
- Many `null` or `unused` fields in API requests/responses

**Phase to address:**
API design and gateway phase. The API contract shapes every downstream service and SDK. Changing it after SDKs are published is extremely costly.

**Confidence:** HIGH

---

### Pitfall 6: GPU/Compute Cost Explosion Without Tenant-Level Attribution

**What goes wrong:**
AI compute costs (GPU inference, fine-tuning, embedding generation) grow 10–50x faster than traditional SaaS. Teams build the platform without granular cost tracking per tenant/project, then discover they can't attribute costs or implement usage-based billing. GPU nodes on AKS (Standard_NC6s_v3 minimum recommended) cost $3–6+/hour per node. A single fine-tuning job on GPT-4 can cost hundreds of dollars. Without cost attribution, the platform operates at a loss and can't identify abusive usage patterns.

**Why it happens:**
- Traditional SaaS cost attribution (storage used, API calls made) doesn't capture AI costs: token counts, GPU hours, model-specific pricing tiers, and batch vs. real-time pricing differ dramatically.
- Azure pricing is complex: Azure OpenAI charges per-token (varying by model), GPU VMs charge per-hour (varying by SKU and region), Cosmos DB charges per-RU, and AI Search charges per-search-unit. Aggregating these into per-tenant cost requires cross-service correlation.
- Teams defer billing/metering as "Phase N" work, but the data collection must start from Day 1 — you can't retroactively reconstruct costs.

**How to avoid:**
- Instrument every API call with tenant/project/user context in headers. Pass this context through the entire pipeline: API gateway → model serving → logging.
- Capture token usage per request (Azure OpenAI returns token counts in response headers). Store in a cost ledger (Cosmos DB or dedicated analytics store) with tenant attribution.
- For GPU workloads on AKS: use Kubernetes namespaces per tenant with resource quotas. Track GPU-seconds per fine-tuning job.
- Build cost dashboards from Day 1, even if billing isn't implemented yet. The data pipeline must exist before you need it.
- Set per-tenant cost alerts and automatic throttling when budget thresholds approach.
- Distinguish between pass-through costs (model inference) and platform overhead (infrastructure).

**Warning signs:**
- Can't answer "how much does Tenant X cost us per month?"
- No token usage or GPU time metrics in observability dashboards
- Azure Cost Management is the only cost visibility tool (lacks tenant-level granularity)
- Billing/metering discussions deferred past the first production milestone

**Phase to address:**
Must start in the API gateway and observability phases with cost-tracking instrumentation. Full billing pipeline can come later, but data collection must begin immediately.

**Confidence:** HIGH

---

### Pitfall 7: Premature Microservice Decomposition on AKS

**What goes wrong:**
Teams decompose the platform into 15+ microservices before understanding the actual domain boundaries. Each "service" (model-catalog-service, deployment-service, inference-service, fine-tuning-service, playground-service, billing-service, etc.) is deployed as a separate AKS deployment with its own database, leading to: distributed monolith anti-pattern, excessive inter-service communication latency, operational overhead of maintaining 15+ Helm charts and CI/CD pipelines, and difficulty making cross-cutting changes that span multiple services.

**Why it happens:**
The project description lists many capabilities (model catalog, deployment, inference, fine-tuning, playground, monitoring, billing, etc.), and teams map each capability to a microservice 1:1. AKS makes it easy to deploy many services. But premature decomposition creates coupling without the benefits of independence — services that share a database, that must be deployed together, and that can't function without each other aren't real microservices.

**How to avoid:**
- Start with a modular monolith or 3–5 coarse-grained services, not 15. Suggested initial decomposition:
  1. **API Gateway / Platform API** — routing, auth, rate limiting
  2. **Catalog & Deployment Service** — model registry, deployment lifecycle
  3. **Inference Service** — model serving proxy, streaming support
  4. **Async Workflows Service** — fine-tuning, evaluation, data processing (long-running jobs)
  5. **Platform Management** — billing, monitoring, project/workspace CRUD
- Extract new services only when teams independently deploy and scale them. Measure before splitting.
- Use event-driven patterns (Azure Service Bus / Event Grid) for decoupling from the start, but deploy producers and consumers as modules within coarse services initially.
- Domain-Driven Design bounded contexts should emerge from experience, not be guessed upfront.

**Warning signs:**
- More than 8 services before the first production user
- Services that must be deployed together to avoid breaking changes
- Database tables shared across multiple services
- Most inter-service calls are synchronous HTTP (indicating tight coupling)
- Team size smaller than the number of services

**Phase to address:**
Architecture and initial service scaffolding phase.

**Confidence:** MEDIUM — depends heavily on team size and experience

---

### Pitfall 8: Ignoring Responsible AI Guardrails Until Post-Launch

**What goes wrong:**
Content safety, prompt injection protection, PII detection, and bias monitoring are treated as "nice-to-have" features added in a later phase. When enterprise customers evaluate the platform, they require these capabilities for compliance. Retrofitting content safety requires architectural changes: every inference request must pass through a filtering pipeline that sits between the user and the model, and every response must be scanned before delivery. Adding this post-hoc means modifying the streaming pipeline, changing API contracts (to include content filter metadata), and potentially re-architecturing the inference proxy.

**Why it happens:**
Responsible AI is seen as a policy layer, not an architectural concern. Teams focus on "make inference work first, add safety later." But content safety is deeply integrated into the data flow: input filtering happens before the model, output filtering happens during streaming (you can't unsend tokens already streamed to the user), and the metadata (filter reasons, confidence scores, flagged categories) must be part of the API response schema.

**How to avoid:**
- Include Azure AI Content Safety service in the inference pipeline from Day 1. Even if configured permissively, the integration points must exist.
- Design the API response schema to include content filter results (categories, severity, action taken) from the start. Azure OpenAI already returns this metadata — surface it rather than hiding it.
- Implement prompt injection detection as middleware in the API gateway.
- Build configurable safety policies per tenant/project — enterprise tenants will want different thresholds than free-tier users.
- Plan for auditability: every filtered/blocked request must be logged with the reason for compliance review.

**Warning signs:**
- No content safety service in the architecture diagram
- API response schema has no fields for safety metadata
- Streaming pipeline has no interception point for output filtering
- No mention of prompt injection in threat modeling

**Phase to address:**
Must be part of API gateway and inference pipeline architecture phases. Specific policy configuration can come later, but the integration hooks must exist from the start.

**Confidence:** HIGH

---

### Pitfall 9: Network Security Afterthoughts in Enterprise AI

**What goes wrong:**
Teams build the platform with public endpoints for development convenience, planning to "lock it down later." When enterprise security review comes, they discover that adding Private Link, private endpoints, VNet integration, and NSGs requires re-architecting the network topology. Azure services behave differently in private-endpoint mode (DNS resolution changes, some features become unavailable, and connectivity between services must be explicitly configured). The Foundry Agent Service reference architecture requires 8+ subnets with specific NSG rules, UDRs, and Azure Firewall for egress control.

**Why it happens:**
Private networking in Azure is complex and slows development velocity. Developers prefer public endpoints for debugging accessibility. But switching from public to private endpoints isn't a config change — it changes DNS resolution, requires private DNS zones, breaks service-to-service calls that relied on public endpoints, and adds jump box requirements for portal access.

**How to avoid:**
- Start with private endpoints and VNet integration from the development environment. Use Azure Bastion + jump box for portal access.
- Design the VNet topology upfront: separate subnets for private endpoints, AKS nodes, Application Gateway, Azure Firewall, and bastion. The baseline Foundry architecture has 8 subnets — plan for at least this many.
- Deploy all Cosmos DB, Storage, AI Search, and Azure OpenAI resources with public access disabled from Day 1.
- Use Bicep/ARM templates (IaC) that enforce private-endpoint-only deployment. Don't allow human-created resources that skip network security.
- Treat Azure Firewall as a required egress control point. Route all outbound traffic from AKS and agent subnets through it.

**Warning signs:**
- Services deployed with public endpoints "for now"
- No private DNS zones configured
- Developers accessing services directly from local machines instead of through VPN/jump box
- No Azure Firewall or egress control in the architecture
- Bicep templates that don't configure networking

**Phase to address:**
Infrastructure and networking phase. Must be the very first infrastructure provisioning step. Every service deployed afterward inherits the network security posture.

**Sources:**
- Microsoft Architecture Center: Baseline Microsoft Foundry chat reference architecture (2026)

**Confidence:** HIGH

---

### Pitfall 10: Model Versioning and Lifecycle Mismanagement

**What goes wrong:**
Models are deployed ad-hoc without version tracking, lineage, or retirement planning. When a model is updated or retired (Azure OpenAI regularly retires model versions), deployed endpoints break. Teams can't answer: "Which version of GPT-4 is Tenant X using?", "When was this fine-tuned model last updated?", "What happens when Azure retires gpt-4o-2024-08-06?" Without a model registry that tracks versions, deployments, and dependencies, every model retirement becomes a fire drill.

**Why it happens:**
Model versioning seems simple when there's one model. But a multi-provider catalog will have dozens of models across multiple providers, each with their own versioning scheme. Azure OpenAI alone has model versions with specific retirement dates. Fine-tuned models add another dimension: base model version → fine-tuning dataset → fine-tuned model ID → deployment. Without a registry, teams lose track.

**How to avoid:**
- Build a model registry (stored in Cosmos DB) that tracks: model ID, provider, version, capabilities, deployment regions, deployment status, deprecation date, and tenant usage.
- Implement a deployment manifest per tenant: which model versions they're using, when they were deployed, and what the fallback model is.
- Subscribe to Azure OpenAI model retirement notifications. Build automated warnings when a deployed model version approaches end-of-life.
- For fine-tuned models: store the complete lineage (base model → training data hash → training parameters → resulting model) and enable reproducible training.
- Implement a model migration workflow: when a model is deprecated, automatically notify tenants and provide one-click migration to the successor model.

**Warning signs:**
- No central record of which models are deployed and for which tenants
- Model deployments done through portal clicks rather than IaC/API
- Surprise breakage when Azure retires a model version
- Fine-tuned models that can't be reproduced from source data
- No concept of a "model deployment manifest"

**Phase to address:**
Model catalog and deployment service phases.

**Confidence:** HIGH

---

### Pitfall 11: Observability Gaps for AI-Specific Metrics

**What goes wrong:**
Teams instrument the platform with standard web application metrics (HTTP status codes, response time, CPU/memory) but miss AI-specific signals: token usage per request, time-to-first-token (TTFT), inter-token latency, model accuracy/quality drift, prompt injection attempts, content safety filter triggers, embedding similarity scores, and fine-tuning job progress. When production issues arise, they can see that "the API is slow" but can't diagnose whether the bottleneck is model loading, token generation, context window overflow, or rate limiting.

**Why it happens:**
Standard observability tools (Application Insights, Prometheus, Grafana) don't capture AI metrics out of the box. Token-level metrics require parsing Azure OpenAI response headers. Streaming response latency requires custom instrumentation (measuring time between SSE events). Model quality monitoring requires storing predictions alongside ground truth labels — which typical request logging doesn't capture.

**How to avoid:**
- Define an AI-specific metrics taxonomy from Day 1: TTFT, tokens/second, total tokens (input + output), cost per request, content safety filter results, model version, deployment region.
- Capture these metrics as custom dimensions in Application Insights or as Prometheus metrics on AKS.
- Build separate dashboards for: platform health (traditional metrics), model performance (AI metrics), cost tracking (per-tenant usage), and safety monitoring (filter triggers, flagged content).
- Implement distributed tracing that follows a request through: API gateway → auth → rate limit → content safety → model inference → response streaming → logging. Each step should emit spans with AI-relevant attributes.
- For model quality monitoring: log a sample of prompt-response pairs (with tenant consent) for human evaluation pipelines.

**Warning signs:**
- Observability dashboards show only HTTP metrics
- Can't tell how many tokens a specific tenant consumed today
- No alerting on content safety filter trigger rate spikes
- TTFT and streaming latency are unmeasured
- No model-level breakdown of request volume or error rates

**Phase to address:**
Observability and monitoring phase — but instrumentation hooks must be designed into the API gateway and inference pipeline phases.

**Confidence:** HIGH

---

### Pitfall 12: Disaster Recovery for Stateful AI Conversations

**What goes wrong:**
The platform stores conversation history, agent state, uploaded files, and search indexes across multiple services (Cosmos DB, Storage, AI Search). When a failure occurs, teams discover these services can't be restored to a consistent point in time: Cosmos DB supports continuous backup with 7-day PITR, AI Search has no built-in restore capability (requires Microsoft support), and Storage restore depends on redundancy tier. Cross-service consistency is not guaranteed — restoring Cosmos DB but not AI Search leaves orphaned conversation references pointing to missing index entries.

**Why it happens:**
AI platforms are uniquely stateful: conversation history, uploaded documents, embeddings, and agent definitions must be consistent with each other. Traditional DR planning treats each service independently, but in an AI platform, these services have referential integrity dependencies. The baseline Foundry architecture explicitly warns: "Coordinate recovery across all relevant data stores. Restoring only a subset of dependencies can result in orphaned or inconsistent data."

**How to avoid:**
- Enable Cosmos DB continuous backup from Day 1 — it's the most recoverable component.
- For AI Search: maintain a separate source of truth (original documents + chunking pipeline) that can rebuild indexes from scratch. Never treat AI Search as the primary data store.
- For Storage: use geo-zone-redundant storage (GZRS) for uploaded files.
- Define recovery runbooks that restore all dependent services to a consistent point in time.
- Add delete resource locks to critical services (Cosmos DB, Storage, AI Search) to prevent accidental deletion.
- Store agent definitions as code in source control. Never rely on portal-created agents as the sole source of truth.
- Test recovery procedures regularly — especially cross-service consistency.

**Warning signs:**
- No backup configuration on Cosmos DB accounts
- AI Search is the only copy of indexed data (no rebuild pipeline)
- No resource locks on production data stores
- Agent definitions only exist in the Foundry portal (not in source control)
- DR plan doesn't address cross-service consistency

**Phase to address:**
Infrastructure design phase for backup/redundancy config. DR runbooks should be created before entering production.

**Sources:**
- Microsoft Architecture Center: Baseline Foundry chat reference architecture — Disaster Recovery section

**Confidence:** HIGH

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Public endpoints for dev speed | Faster development iteration | Must retrofit private networking; DNS, service-to-service calls all break | Never — start private from Day 1 |
| Single Azure OpenAI deployment | Simpler config, fewer resources | Quota ceiling, no failover, single-region latency | Prototype only, never production |
| Shared Cosmos DB account for all services | Fewer resources to manage | RU contention between services, can't scale independently | Early development with <5 services |
| Hardcoded model versions in code | Works now | Break when Azure retires model version | Never — use model registry with version resolution |
| Sync HTTP between all microservices | Simple to debug | Cascading failures, tight coupling, high latency for chains | Between tightly related services only (2 hops max) |
| Skip tenant cost attribution | Ship faster | Can't bill tenants, can't identify cost outliers | First 2 weeks of prototype only |
| Portal-based resource creation | Quick experimentation | Resources drift from IaC, miss security config, unreproducible | Never in shared/staging/production |
| Buffering full LLM responses before sending | Simpler proxy implementation | 15–60 second delays, terrible UX, timeout failures | Only for non-interactive batch jobs |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Azure OpenAI API | Treating quota as per-resource (it's per-subscription, per-region, per-model) | Plan multi-region deployments; implement gateway-level load balancing across regions |
| Azure Entra ID (Auth) | Using API keys for service-to-service auth | Use managed identities everywhere; API keys only for external SDK consumers with rotation |
| Cosmos DB multi-tenant | Using database-per-tenant from the start (expensive) | Start with partition-key-per-tenant; move premium tenants to dedicated accounts when justified |
| AKS GPU nodes | Deploying GPU node pools without autoscaler or taints | Always use cluster autoscaler (min-count=0 for cost), apply `sku=gpu:NoSchedule` taints to prevent non-GPU workloads from scheduling there |
| AI Search | Treating it as a database (it's a search engine) | Use as a read-optimized index; maintain source of truth elsewhere; plan for index rebuild pipeline |
| Azure API Management | Assuming it handles SSE/streaming natively | Test streaming behavior explicitly; newer API Management versions support it but require specific configuration; consider custom gateway on AKS for complex routing |
| Azure Service Bus / Event Grid | Firing events for every model inference (high volume) | Use events for lifecycle operations (deploy, fine-tune, scale) not per-request operations; use direct logging for per-request data |
| Azure Content Safety | Calling synchronously in the response stream | For streaming: filter input before sending to model; for output, use async scanning to flag (but can't un-stream already-sent tokens) |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Single-region model deployment | Works fine with 10 concurrent users | Multi-region deployment with smart routing | 50+ concurrent users per model in single subscription |
| Unoptimized Cosmos DB queries without partition key in WHERE clause | Cross-partition fan-out queries; 2-3 extra RU per physical partition | Always include partition key in queries; use global secondary indexes for alternative access patterns | >5 physical partitions; visible at >30,000 RU provisioned or >100 GB data |
| Large embedding collections in single AI Search index | Slow vector search, high latency | Shard indexes by tenant or domain; use pre-filtering on partition key before vector similarity | >10M vectors |
| Model cold starts on AKS custom hosting | First request takes 30–120 seconds while model loads into GPU memory | Keep warm pools with pre-loaded models; use readiness probes; implement request queuing during loading | On every scale-up or pod restart |
| No connection pooling for Cosmos DB SDK | Creates new TCP connections per request | Use singleton `CosmosClient` per process; managed by DI container | >100 requests/second |
| Synchronous fine-tuning status polling | UI polling every second generates thousands of wasted API calls | Use webhooks/Event Grid for job completion; long-polling or WebSocket for progress updates | >10 concurrent fine-tuning jobs |
| No API response caching for model catalog/metadata | Same model list fetched on every page load | Cache catalog data with short TTL (5 min); invalidate on catalog changes | >100 concurrent dashboard users |

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Infrastructure / IaC | Public endpoints for convenience → security retrofit | Enforce private endpoints in all Bicep templates from Phase 1 |
| Database design | Wrong partition key → data migration at scale | Load-test partition key design with realistic data before building services |
| API gateway | Request-response only → streaming retrofit | Design SSE support into the gateway architecture from Day 1 |
| Auth / RBAC | Too-coarse roles → privilege escalation | Define granular roles per resource type (model reader, deployer, admin) following Azure Entra ID patterns |
| Model catalog | Static list → can't track versions or retirement | Build a versioned model registry with lifecycle hooks from the start |
| Model deployment | Single-region Azure OpenAI → quota ceiling | Multi-region deployment with gateway load balancing |
| Inference pipeline | No content safety → compliance blocker | Integrate Azure AI Content Safety into the inference pipeline before first production use |
| Fine-tuning | Shared compute → data contamination | Per-tenant isolation for fine-tuning jobs (separate Storage, namespaced AKS jobs) |
| Observability | Web-only metrics → can't diagnose AI-specific issues | Define AI metrics taxonomy and instrument from Day 1 |
| Billing / metering | Deferred cost attribution → can't bill or control costs | Instrument token/compute usage tracking from the first inference request |
| Multi-tenant isolation | Shared everything → data leakage | Define isolation boundaries per component during architecture phase |
| Microservice decomposition | 15+ services before first user → operational overhead | Start with 3–5 coarse services; extract when independently deploying/scaling |
| Disaster recovery | Independent service restore → inconsistent state | Plan cross-service consistent recovery; maintain rebuild pipelines for search indexes |

---

**Sources:**
- Microsoft Docs: Azure OpenAI quotas and limits (2026-02-28) — HIGH confidence
- Microsoft Docs: Partitioning in Azure Cosmos DB (2026-02-02) — HIGH confidence
- Microsoft Architecture Center: Multitenancy and Azure Cosmos DB (2024-11-18) — HIGH confidence
- Microsoft Architecture Center: Baseline Microsoft Foundry chat reference architecture (2026) — HIGH confidence
- Microsoft Docs: AKS GPU cluster management (2026-01-28) — HIGH confidence
- Domain expertise in AI/ML platform engineering patterns — MEDIUM confidence (training data, verified against official sources above)
