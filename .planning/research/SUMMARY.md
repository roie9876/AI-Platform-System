# Project Research Summary

**Project:** AI Platform System
**Domain:** Enterprise AI Platform (multi-provider model orchestration, deployment, and consumption — Azure-native)
**Researched:** 2026-03-23
**Confidence:** HIGH

## Executive Summary

This is an enterprise AI platform that aggregates models from multiple providers (Azure OpenAI, open-source, third-party) behind a unified API, with multi-tenant project isolation, content safety guardrails, and usage-based billing. The expert-validated approach is: Azure-native microservices on AKS with APIM as the AI gateway, Cosmos DB for operational data, and an event-driven architecture for long-running AI operations (deployments, fine-tuning, evaluation). The competitive moat is multi-provider model aggregation — no major platform (Foundry, Vertex AI, Bedrock) offers truly provider-agnostic model consumption through a single API.

The recommended stack is TypeScript full-stack: NestJS 11 for backend microservices (architecture-opinionated with DI, guards, interceptors — essential for 6+ services), Next.js 16 for the web portal (App Router with PPR for dashboard-heavy admin console), and a pnpm/Turborepo monorepo. Azure services are well-matched: APIM Premium v2 has native AI gateway capabilities (token rate limiting, semantic caching, multi-backend routing), Cosmos DB provides hierarchical partition keys for multi-tenant isolation plus integrated vector search for the model catalog, and Service Bus/Event Hubs handle async workflows and telemetry at scale.

The primary risks are: (1) wrong Cosmos DB partition key strategy locking in an unmigrable data model, (2) failing to design streaming (SSE) support into the API gateway from Day 1 — retrofitting is architecturally expensive, (3) Azure OpenAI quota exhaustion from multi-tenant traffic sharing a single subscription/region, and (4) multi-tenant data isolation failures in AI workloads (shared model caches, fine-tuning data contamination, cross-tenant vector search). All four are mitigated by addressing them in the architecture and infrastructure phases before any service writes production data.

## Key Findings

### Recommended Stack

TypeScript 5.7+ unifies the entire platform — NestJS 11 backend services, Next.js 16 frontend, shared types across packages. Azure-native services eliminate operational overhead: AKS for compute, APIM for API gateway, Cosmos DB (NoSQL) + Azure SQL (billing/relational) for data, Service Bus for commands, Event Hubs for telemetry, Entra ID for identity, Bicep for IaC. The monorepo structure (pnpm workspaces + Turborepo) enables independent service deployment while sharing contracts and libraries.

**Core technologies:**
- **NestJS 11 on AKS** — Backend microservices framework with built-in DI, microservices transport (gRPC), and enterprise patterns
- **Next.js 16 (React 19.2)** — Frontend with App Router, PPR, self-hosted on AKS (not locked to Vercel)
- **Azure API Management (Premium v2)** — AI gateway with token rate limiting, multi-backend load balancing, developer portal
- **Azure Cosmos DB (NoSQL)** — Operational database with hierarchical partition keys for multi-tenancy, integrated vector search (DiskANN)
- **Azure OpenAI Service** — Foundation model access (GPT-5.x, embeddings, fine-tuning)
- **Azure Service Bus + Event Hubs** — Async messaging for deployment orchestration (Service Bus) and high-throughput telemetry (Event Hubs)
- **Microsoft Entra ID** — Identity provider with managed identities for inter-service auth (no secrets)
- **Bicep** — IaC with immediate Azure API support, no state files

### Expected Features

**Must have (table stakes — v1 launch):**
- **Auth & RBAC (Entra ID)** — project-level, team-level, resource-level access control
- **Project/Workspace Organization** — multi-tenant isolation with cost attribution
- **Model Catalog & Discovery** — searchable catalog with model cards, metadata, filtering
- **One-Click Model Deployment** — deploy to managed endpoints on AKS / Azure OpenAI
- **Standardized API Gateway** — unified REST API for consuming any model regardless of provider (THE differentiator)
- **Content Safety / Guardrails** — configurable content filters, PII detection, prompt injection protection
- **Prompt Playground** — interactive model testing with parameter tuning
- **Usage Monitoring & Logging** — per-deployment, per-project metrics
- **Cost Tracking** — token-based usage aggregation with project budgets
- **Python SDK** — programmatic access for developers

**Should have (v1.x — after validation):**
- **Model Evaluation & Benchmarking** — automated metrics, custom eval datasets
- **Prompt Management & Versioning** — git-like version history for prompts
- **Model A/B Testing** — traffic splitting at gateway level
- **CLI Tooling** — CI/CD integration for power users
- **LLM-Specific Observability** — token-level tracing, TTFT, cost per request
- **Data Management** — dataset upload/versioning for fine-tuning prep

**Defer (v2+):**
- **Fine-Tuning Workflows** — complex GPU orchestration, defer until data management is solid
- **AI Pipeline / Multi-Model Orchestration** — DAG-based pipeline builder, needs mature gateway
- **Agent Builder Platform** — standards still maturing (MCP, A2A); build after core is stable
- **Marketplace / Model Publishing** — needs user base to be valuable
- **Multi-Cloud Model Aggregation** — cross-cloud is v2+ after Azure-native aggregation proven

### Architecture Approach

Six-layer architecture: Presentation (portal, SDK, CLI) → Gateway & Identity (APIM, Entra ID, Front Door) → Microservices on AKS → Event & Messaging (Service Bus, Event Hubs) → Model Serving (Azure OpenAI, AKS endpoints, third-party APIs) → Data & Storage (Cosmos DB, Blob, AI Search, Azure SQL, Redis, Key Vault). Start with 4–5 coarse-grained services rather than 15+ premature microservices.

**Major components:**
1. **API Gateway (APIM)** — unified API surface, auth termination, rate limiting, model routing, streaming support
2. **Model Catalog & Deployment Service** — model discovery, metadata, deployment lifecycle, version tracking
3. **Inference Service** — model serving proxy, streaming SSE, multi-provider adapter layer
4. **Project Service** — workspace CRUD, team membership, tenant isolation, quota allocation
5. **Billing & Metering Service** — token usage tracking, cost allocation, quota enforcement
6. **Content Safety Service** — Azure AI Content Safety integration, configurable per-tenant policies

**Key patterns:**
- API Gateway with multi-backend routing (APIM routes to Azure OpenAI, AKS model pods, or third-party APIs)
- Event-driven async for long-running ops (deployments, fine-tuning, evaluation via Service Bus)
- Multi-provider model abstraction with per-provider adapters normalizing to a unified API
- Project-scoped resource isolation via Cosmos DB partition keys, APIM subscription keys, and Entra ID RBAC

### Critical Pitfalls

1. **Wrong Cosmos DB partition key** — Cannot be changed in-place; must migrate all data. Use hierarchical partition keys (`tenantId` → `userId` → `sessionId`). Load-test with realistic data distribution before writing any service data. Separate containers for distinct access patterns (metadata read-heavy vs. logs write-heavy).

2. **Not designing for streaming (SSE) from Day 1** — LLM responses stream tokens over 10–60 seconds. Retrofitting streaming into request-response architecture requires rewriting gateway, proxy, and frontend. Build dual-mode (`stream=true/false`) from the first endpoint. Ensure APIM, load balancers, and frontend all handle long-lived SSE connections.

3. **Azure OpenAI quota blindness** — Quotas are per-subscription, per-region, per-model with complex tiering. Multi-tenant traffic saturates single-region quotas fast. Plan multi-region, multi-subscription deployment with gateway-level load balancing across regions from the start.

4. **Multi-tenant data isolation failures** — AI workloads have unique leakage vectors: shared model caches, fine-tuning data contamination, cross-tenant vector search. Enforce partition-level access control in all data stores; never rely on application code filtering alone. Per-tenant isolation for fine-tuning jobs.

5. **Premature microservice decomposition** — Start with 4–5 coarse services, not 15. Extract new services only when teams independently deploy and scale them. More services than team members is a red flag.

6. **GPU/compute cost explosion without attribution** — Instrument every API call with tenant/project context from Day 1. Capture token usage per request from Azure OpenAI response headers. Build cost dashboards before billing — the data pipeline must exist before you need it.

## Implications for Roadmap

Based on combined research, feature dependencies, architecture build order, and pitfall prevention, here is the suggested phase structure:

### Phase 1: Infrastructure & Networking Foundation
**Rationale:** Everything depends on networking, compute, and identity. Pitfalls #9 (network security) and #7 (premature decomposition) both require getting infrastructure right first. Start with private endpoints from Day 1 — retrofitting is architecturally disruptive.
**Delivers:** VNet topology (8+ subnets), AKS cluster, ACR, Key Vault, Azure Monitor/App Insights, Bicep modules for all resources, private DNS zones, Azure Firewall for egress.
**Addresses:** Infrastructure prerequisites for all features.
**Avoids:** Pitfall #9 (network security afterthoughts — start private, never retrofit).

### Phase 2: Identity, Auth & Multi-Tenancy
**Rationale:** Auth & RBAC is the foundation for every feature per the dependency graph. Project-scoped isolation must exist before any service writes tenant data. Pitfall #4 (multi-tenant isolation) requires isolation boundaries defined architecturally before building features.
**Delivers:** Entra ID integration, RBAC framework (project/team/resource roles), Project Service (workspace CRUD, member management), Cosmos DB partition strategy validated with load testing.
**Addresses:** Auth & RBAC, Project/Workspace Organization (table stakes).
**Avoids:** Pitfall #1 (wrong partition key — validated before data is written), Pitfall #4 (tenant isolation defined upfront).

### Phase 3: Model Catalog & Discovery
**Rationale:** Users must discover models before deploying them. The catalog is the platform's front door and enables the deployment and API gateway phases. AI Search integration for semantic model discovery.
**Delivers:** Model metadata schema in Cosmos DB, model cards, provider adapter pattern for Azure OpenAI + at least one additional provider, AI Search index for model discovery, version tracking and lifecycle management.
**Addresses:** Model Catalog & Discovery (table stakes), model versioning (Pitfall #10).
**Avoids:** Pitfall #10 (model versioning mismanagement — registry with lifecycle tracking from start), Pitfall #5 (monolithic API — design polymorphic API types now).

### Phase 4: Model Deployment & Serving
**Rationale:** Deployment is the core workflow — provision endpoints, manage lifecycle. Requires catalog (Phase 3) for model validation. Must handle Azure OpenAI managed models + custom models on AKS.
**Delivers:** Deployment Service, Azure OpenAI managed endpoint provisioning, AKS-based custom model hosting, deployment manifests per tenant, async provisioning via Service Bus, health monitoring.
**Addresses:** One-Click Model Deployment (table stakes).
**Avoids:** Pitfall #3 (Azure OpenAI quota — multi-region deployment strategy designed here).

### Phase 5: API Gateway & Unified Inference API
**Rationale:** The unified API is THE differentiator. Requires deployed model endpoints (Phase 4) to route to. APIM configuration for multi-backend routing, streaming support, rate limiting, and content safety integration. This is where Pitfalls #2 (streaming) and #5 (monolithic API) are directly addressed.
**Delivers:** APIM configuration with model routing policies, dual-mode streaming (SSE + buffered), provider-agnostic request/response transformation, per-tenant rate limiting and quota enforcement, content safety pre/post-filtering integrated into inference pipeline.
**Addresses:** Standardized API Gateway, Content Safety / Guardrails (table stakes).
**Avoids:** Pitfall #2 (streaming from Day 1), Pitfall #5 (polymorphic API — `/chat/completions`, `/embeddings`, `/images/generations`), Pitfall #8 (responsible AI integrated into pipeline, not bolted on).

### Phase 6: Usage Tracking, Billing & Cost Attribution
**Rationale:** Cost tracking must start as soon as inference is live. Pitfall #6 (cost explosion) warns that deferring metering means losing data you can never reconstruct. Event-driven pipeline: inference events → Event Hubs → Billing Service → Azure SQL.
**Delivers:** Token usage capture per request, per-tenant cost aggregation, per-project budget/quota enforcement, cost dashboards, Azure SQL for billing data, usage alerting.
**Addresses:** Usage Monitoring & Logging, Cost Tracking (table stakes).
**Avoids:** Pitfall #6 (GPU cost explosion — attribution from first inference request), Pitfall #11 (AI observability — AI-specific metrics captured here).

### Phase 7: Web Portal
**Rationale:** The portal depends on working APIs (Phases 3-6). Build the frontend after backend APIs are stable. Next.js 16 with App Router, dashboard-heavy admin console using shadcn/ui components.
**Delivers:** Model catalog UI (browse, search, filter), deployment management dashboard, prompt playground (chat/completion modes with parameter tuning), project management interface, usage/cost dashboards with Recharts visualizations.
**Addresses:** Prompt Playground (table stakes), all UI aspects of previous features.

### Phase 8: SDK & CLI
**Rationale:** Programmatic access for developers. Python SDK first (highest demand), CLI for CI/CD. Requires stable API contracts (Phase 5). OpenAPI spec enables SDK generation.
**Delivers:** Python SDK for model inference, deployment, and catalog operations. CLI tool for platform operations. OpenAPI spec published.
**Addresses:** SDK (table stakes), CLI Tooling (v1.x).

### Phase 9: Evaluation, Prompt Management & Observability
**Rationale:** These features strengthen the platform after core workflow is validated. Model evaluation needs data management (datasets in Blob Storage), deployed models, and catalog integration. Prompt versioning and LLM tracing are high-value, lower-complexity additions.
**Delivers:** Evaluation framework with automated metrics, prompt versioning with template library, LLM-specific observability (TTFT, token-level tracing, cost per request), data management for evaluation datasets.
**Addresses:** Model Evaluation, Prompt Management, LLM Observability, Data Management (v1.x features).

### Phase 10: Advanced Features (v2)
**Rationale:** High value but high complexity. Fine-tuning requires GPU orchestration + data management (Phase 9). Pipeline orchestration requires mature gateway. Agent builder should wait for standards to stabilize.
**Delivers:** Fine-tuning workflows (LoRA/PEFT + full SFT), multi-model pipeline orchestration, A/B testing with traffic splitting, additional provider adapters.
**Addresses:** Fine-Tuning, AI Pipelines, Agent Builder, Multi-Provider expansion (v2 features).

### Phase Ordering Rationale

- **Infrastructure → Auth → Catalog → Deployment → API Gateway** follows the strict dependency chain from ARCHITECTURE.md's build order and FEATURES.md's dependency graph. Each phase produces outputs consumed by the next.
- **Content safety is integrated into Phase 5 (API Gateway)**, not deferred, because PITFALLS.md identifies "responsible AI as afterthought" as a critical risk. The inference pipeline must include guardrails from its first version.
- **Billing/metering (Phase 6) immediately follows inference (Phase 5)** because PITFALLS.md warns that cost attribution data cannot be reconstructed retroactively. The pipeline must capture from the first inference request.
- **Portal (Phase 7) after backend APIs (Phases 3-6)** avoids building UI against unstable APIs. Backend-first approach is validated by ARCHITECTURE.md's build order.
- **Start with 4-5 coarse services**, not the 10+ shown in ARCHITECTURE.md's full diagram. PITFALLS.md's "premature decomposition" warning is well-supported. Extract services as scale demands.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Auth & Multi-Tenancy):** Cosmos DB hierarchical partition key design with realistic load testing — complex, multi-tenant-specific, needs careful data modeling research
- **Phase 4 (Model Deployment):** Azure OpenAI multi-region quota management, AKS GPU node pool autoscaling — complex Azure-specific configuration, quota tier system has 7 levels
- **Phase 5 (API Gateway):** APIM streaming/SSE configuration, content safety pipeline integration — need to verify APIM's exact streaming capabilities and latency impact of inline content filtering
- **Phase 10 (Fine-Tuning):** GPU orchestration on AKS, fine-tuning APIs across providers — rapidly evolving space, will need fresh research when this phase is reached

Phases with standard patterns (skip research-phase):
- **Phase 1 (Infrastructure):** Well-documented Azure patterns — Bicep modules, AKS, VNet topology have extensive reference architectures
- **Phase 3 (Model Catalog):** Standard CRUD + search patterns — Cosmos DB + AI Search integration is well-documented
- **Phase 7 (Web Portal):** Standard Next.js patterns — dashboard UI with shadcn/ui, TanStack Query, Recharts
- **Phase 8 (SDK & CLI):** Standard SDK generation from OpenAPI specs — well-established tooling

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies verified against official docs (2025-2026). NestJS 11.1.17, Next.js 16.2, all Azure services confirmed GA with current version numbers. 13 sources cited. |
| Features | HIGH | Competitive analysis across Foundry, Vertex AI, Bedrock, and Hugging Face with 8 official sources. Feature prioritization validated against all three major competitors. MVP definition is well-scoped. |
| Architecture | HIGH | Based on 5 Azure Architecture Center references including baseline Foundry chat architecture and multi-backend gateway patterns. Build order validated against feature dependencies. |
| Pitfalls | HIGH | 12 pitfalls identified with specific Azure documentation backing. Partition key, streaming, quota, and security pitfalls are well-documented failure modes. Phase-specific warnings provide actionable guidance. |

**Overall confidence:** HIGH

### Gaps to Address

- **Third-party model provider APIs:** Research focused on Azure-native services. When adding Anthropic, Cohere, or Hugging Face adapters, need fresh research on their API contracts, rate limits, and authentication patterns.
- **APIM streaming behavior:** PITFALLS.md notes that APIM streaming support requires "specific configuration" and suggests testing explicitly. Need hands-on validation during Phase 5 planning — may need a custom gateway component on AKS as fallback.
- **Azure OpenAI fine-tuning API stability:** Fine-tuning APIs are evolving rapidly (GPT-5 series fine-tuning availability unclear). Defer detailed research until Phase 10 is in scope.
- **Agent framework standards (MCP, A2A):** Deferred to v2+. Standards are maturing rapidly — any research done now will be outdated by execution time.
- **Cost modeling:** No detailed Azure cost estimates were produced. During Phase 1 planning, model infrastructure costs (APIM Premium v2 ~$700/mo, AKS node pools, Cosmos DB RU/s, GPU nodes $3-6+/hr) to establish budget baseline.

## Sources

### Primary (HIGH confidence)
- Azure AKS documentation (2025-06-09) — CNCF-certified, SOC/ISO/PCI compliance
- Azure Cosmos DB documentation (2026-02-02) — Vector search, hierarchical partition keys, NoSQL API
- Azure API Management documentation (2025-10-13) — Premium v2, AI gateway, workspaces
- Azure OpenAI Models documentation (2026-03-14) — GPT-5.4, fine-tuning, embeddings
- Azure AI Content Safety documentation (2026-01-31) — Prompt Shields, groundedness detection
- Azure Service Bus documentation (2026-03-13) — Premium tier, geo-replication
- Azure Event Hubs documentation (2026-01-28) — Kafka compatibility, Schema Registry
- Azure OpenAI quotas and limits (2026-02-28) — 7-tier quota system
- Baseline Microsoft Foundry chat reference architecture (2026) — Enterprise reference architecture
- Multi-backend Azure OpenAI gateway patterns (2026) — APIM load balancing, failover
- Multitenancy and Cosmos DB architecture guide (2024-11-18) — Partition strategies
- MLOps v2 architecture patterns (2026) — Model lifecycle management
- Microsoft Foundry overview (2026-03-23) — Foundry resource hierarchy, rebranding from Azure AI Foundry
- Google Vertex AI documentation (2026-03-23) — Competitive analysis
- AWS Bedrock features and model choice (2026-03-23) — Competitive analysis
- NestJS npm registry (2026-03-23) — v11.1.17, 3.7M weekly downloads
- Next.js blog (2026-03-18) — v16.2, React 19.2, Turbopack stable

### Secondary (MEDIUM confidence)
- Domain expertise in AI/ML platform engineering patterns — verified against official sources
- Performance traps and integration gotchas — based on community patterns, validated against Azure docs

---
*Research completed: 2026-03-23*
*Ready for roadmap: yes*
