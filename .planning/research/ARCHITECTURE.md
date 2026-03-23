# Architecture Research

**Domain:** Enterprise AI Platform System (Azure-native)
**Researched:** 2026-03-23
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐   │
│  │  Web Portal  │  │  SDK (C#/Py) │  │     CLI      │  │ Developer     │   │
│  │  (React SPA) │  │              │  │              │  │ Portal (APIM) │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘   │
├─────────┴──────────────────┴──────────────────┴─────────────────┴───────────┤
│                         GATEWAY & IDENTITY LAYER                            │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐  │
│  │  Azure API Mgmt      │  │  Azure Entra ID      │  │  Azure Front    │  │
│  │  (API Gateway)       │  │  (AuthN + RBAC)      │  │  Door / App GW  │  │
│  └──────────┬───────────┘  └──────────┬───────────┘  └────────┬─────────┘  │
├─────────────┴──────────────────────────┴──────────────────────┴─────────────┤
│                         MICROSERVICES LAYER  (AKS)                          │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐              │
│  │  Model     │ │ Deployment │ │ Orchestr-  │ │  Project   │              │
│  │  Catalog   │ │  Service   │ │  ation     │ │  Service   │              │
│  │  Service   │ │            │ │  Service   │ │            │              │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘              │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐              │
│  │ Fine-Tune  │ │ Evaluation │ │  Content   │ │  Billing   │              │
│  │  Service   │ │  Service   │ │  Safety    │ │  & Quota   │              │
│  │            │ │            │ │  Service   │ │  Service   │              │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘              │
│  ┌────────────┐ ┌────────────┐                                             │
│  │  Data      │ │ Playground │                                             │
│  │  Mgmt      │ │  Service   │                                             │
│  │  Service   │ │            │                                             │
│  └─────┬──────┘ └─────┬──────┘                                             │
├────────┴───────────────┴───────────────────────────────────────────────────┤
│                         EVENT & MESSAGING LAYER                             │
│  ┌──────────────────────┐  ┌──────────────────────┐                        │
│  │  Azure Service Bus   │  │  Azure Event Grid    │                        │
│  │  (Async Commands)    │  │  (Domain Events)     │                        │
│  └──────────┬───────────┘  └──────────┬───────────┘                        │
├─────────────┴──────────────────────────┴───────────────────────────────────┤
│                         MODEL SERVING LAYER                                 │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐  │
│  │  Azure OpenAI        │  │  AKS Model Endpoints │  │  Third-Party     │ │
│  │  (Managed Models)    │  │  (Custom/OSS Models) │  │  Model APIs      │ │
│  └──────────┬───────────┘  └──────────┬───────────┘  └────────┬─────────┘  │
├─────────────┴──────────────────────────┴──────────────────────┴─────────────┤
│                         DATA & STORAGE LAYER                                │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐              │
│  │ Cosmos DB  │ │ Azure Blob │ │ AI Search  │ │ Azure SQL  │              │
│  │ (Metadata, │ │ (Models,   │ │ (Model     │ │ (Billing,  │              │
│  │  Projects, │ │  Datasets, │ │  Discovery,│ │  Quotas,   │              │
│  │  Configs)  │ │  Artifacts)│ │  RAG Index)│ │  Audit)    │              │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘              │
│  ┌────────────┐ ┌────────────┐                                             │
│  │ Redis      │ │ Key Vault  │                                             │
│  │ (Cache,    │ │ (Secrets,  │                                             │
│  │  Sessions) │ │  Keys)     │                                             │
│  └────────────┘ └────────────┘                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                         OBSERVABILITY LAYER                                 │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐  │
│  │  Azure Monitor       │  │  Application         │  │  Log Analytics   │  │
│  │  (Metrics & Alerts)  │  │  Insights (APM)      │  │  (KQL Queries)   │  │
│  └──────────────────────┘  └──────────────────────┘  └──────────────────┘  │
├─────────────────────────────────────────────────────────────────────────────┤
│                         INFRASTRUCTURE LAYER                                │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐  │
│  │  Azure VNet          │  │  Azure Firewall      │  │  Azure DDoS      │  │
│  │  (Network Isolation) │  │  (Egress Control)    │  │  Protection      │  │
│  └──────────────────────┘  └──────────────────────┘  └──────────────────┘  │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐  │
│  │  Bicep/ARM           │  │  Azure DevOps /      │  │  Container       │  │
│  │  (IaC)               │  │  GitHub Actions      │  │  Registry (ACR)  │  │
│  └──────────────────────┘  └──────────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Azure Implementation |
|-----------|----------------|----------------------|
| **Web Portal** | User-facing UI for model catalog, playground, dashboards, project management | React SPA on Azure App Service or AKS, behind App Gateway |
| **API Gateway** | Unified API surface, rate limiting, auth termination, request routing, model endpoint abstraction | Azure API Management (Premium v2) |
| **Identity & Access** | Authentication, RBAC, managed identities, tenant isolation | Azure Entra ID + custom RBAC service |
| **Model Catalog Service** | Model discovery, search, metadata, provider aggregation, versioning | AKS microservice → Cosmos DB + AI Search |
| **Deployment Service** | Model lifecycle — provision, deploy, scale, retire endpoints | AKS microservice → orchestrates Azure OpenAI deployments + custom AKS endpoints |
| **Orchestration Service** | Multi-model pipelines, chaining, agent workflows | AKS microservice using Semantic Kernel or custom orchestrator |
| **Project Service** | Workspace/project CRUD, team membership, resource isolation | AKS microservice → Cosmos DB |
| **Fine-Tuning Service** | Training job management, dataset preparation, checkpointing | AKS microservice → Azure ML backend or Azure OpenAI fine-tuning API |
| **Evaluation Service** | Model benchmarking, A/B testing, responsible AI assessments | AKS microservice → custom eval runners on AKS |
| **Content Safety Service** | Prompt/response filtering, PII detection, guardrails | Azure AI Content Safety + custom policy engine |
| **Billing & Quota Service** | Usage metering, cost allocation, quota enforcement per project/team | AKS microservice → Azure SQL + Event-driven metering |
| **Data Management Service** | Dataset upload, versioning, preprocessing pipelines | AKS microservice → Blob Storage + data pipeline |
| **Playground Service** | Interactive prompt experimentation, parameter tuning, response comparison | AKS microservice → proxies to model endpoints via APIM |
| **Monitoring Service** | Usage dashboards, model performance tracking, alerting | Azure Monitor + Application Insights + custom dashboards |

## Recommended Project Structure

```
ai-platform/
├── infra/                          # Infrastructure as Code
│   ├── modules/                    # Reusable Bicep modules
│   │   ├── aks.bicep               # AKS cluster
│   │   ├── apim.bicep              # API Management
│   │   ├── cosmosdb.bicep          # Cosmos DB account
│   │   ├── keyvault.bicep          # Key Vault
│   │   ├── networking.bicep        # VNet, subnets, NSGs
│   │   ├── monitoring.bicep        # Monitor, App Insights
│   │   └── storage.bicep           # Blob Storage
│   ├── environments/               # Per-environment configs
│   │   ├── dev.bicepparam
│   │   ├── staging.bicepparam
│   │   └── prod.bicepparam
│   └── main.bicep                  # Root deployment
├── src/
│   ├── services/                   # Microservices (each independently deployable)
│   │   ├── catalog-service/        # Model catalog & discovery
│   │   │   ├── src/
│   │   │   ├── Dockerfile
│   │   │   └── helm/               # Helm chart
│   │   ├── deployment-service/     # Model deployment lifecycle
│   │   ├── project-service/        # Project/workspace management
│   │   ├── orchestration-service/  # Pipeline & agent orchestration
│   │   ├── finetune-service/       # Fine-tuning workflows
│   │   ├── eval-service/           # Model evaluation
│   │   ├── billing-service/        # Usage & cost tracking
│   │   ├── data-service/           # Dataset management
│   │   ├── playground-service/     # Interactive experimentation
│   │   ├── safety-service/         # Content safety & guardrails
│   │   └── gateway-config/         # APIM policies & API definitions
│   ├── portal/                     # Web frontend (React/Next.js)
│   │   ├── src/
│   │   ├── Dockerfile
│   │   └── helm/
│   ├── sdk/                        # Client SDK
│   │   ├── python/
│   │   └── dotnet/
│   └── cli/                        # CLI tooling
│       └── src/
├── shared/
│   ├── contracts/                  # Shared API contracts (OpenAPI specs)
│   ├── libraries/                  # Shared code libraries
│   │   ├── auth/                   # Auth helpers
│   │   ├── messaging/              # Service Bus/Event Grid helpers
│   │   └── telemetry/              # Observability helpers
│   └── proto/                      # gRPC protobuf definitions
├── tests/
│   ├── integration/                # Cross-service integration tests
│   ├── e2e/                        # End-to-end tests
│   └── load/                       # Load/performance tests
├── deploy/
│   ├── k8s/                        # Kubernetes manifests
│   ├── helm/                       # Umbrella Helm chart
│   └── pipelines/                  # CI/CD pipeline definitions
└── docs/
    ├── architecture/               # ADRs and design docs
    ├── api/                        # API documentation
    └── runbooks/                   # Operational runbooks
```

### Structure Rationale

- **infra/:** Bicep modules separated from application code; environment-specific parameters enable consistent multi-stage deployments
- **src/services/:** Each microservice is independently deployable with its own Dockerfile and Helm chart, enabling independent scaling and deployment cadence
- **shared/contracts/:** OpenAPI specs serve as contracts between services — enables code generation and contract testing
- **shared/libraries/:** Common concerns (auth, messaging, telemetry) extracted once to prevent duplication across services
- **deploy/:** Separation of deployment manifests from application code enables GitOps workflows

## Multi-Tenant Isolation Architecture

**Full details:** `.planning/adrs/adr-001-multi-tenant-isolation.md`

The platform uses **shared infrastructure with logical isolation** — all tenants share the same physical resources (AKS cluster, Cosmos DB, APIM, VNet) with isolation enforced at each layer through Azure-native mechanisms:

| Layer | Isolation Mechanism |
|-------|---------------------|
| Network | Shared subnets, NSG per-service boundaries, private endpoints |
| Compute (AKS) | Per-service namespaces (not per-tenant), tenant context in request headers |
| API Gateway (APIM) | Per-project subscription keys, rate limiting policies |
| Database (Cosmos DB) | Hierarchical partition keys: `/tenantId/projectId/entityType` |
| Database (Azure SQL) | Row-level security filtered by `project_id` |
| Identity (Entra ID) | Application-level RBAC scoped per project |
| Secrets (Key Vault) | RBAC + managed identities, per-service access scoping |
| Monitoring | `projectId` custom dimension, application-enforced dashboard filtering |

This model was chosen over namespace-per-tenant, database-per-tenant, and VNet-per-tenant alternatives for cost efficiency, operational simplicity, and proven scalability at enterprise SaaS scale.

## Architectural Patterns

### Pattern 1: API Gateway with Multi-Backend Routing

**What:** Azure API Management acts as the single entry point for all API consumers (portal, SDK, CLI, third-party integrations). It terminates authentication, applies rate limiting, routes to backend microservices, and provides a unified model consumption API that abstracts away individual model provider differences.

**When to use:** Always — this is a foundational pattern for any multi-model AI platform. Azure's official architecture guidance recommends APIM as the gateway for model endpoint access.

**Trade-offs:**
- Pro: Unified API surface, centralized auth/throttling, model provider abstraction, developer portal
- Pro: Circuit breaking and failover across model endpoints (built-in backend pool support)
- Con: Additional latency hop (typically <5ms within same region)
- Con: APIM Premium v2 cost (~$700/mo per unit), but justified for enterprise requirements

**Azure Reference:** Microsoft's "Use a gateway in front of multiple Azure OpenAI deployments" recommends APIM for load balancing, failover, usage tracking, and security segmentation across model backends.

### Pattern 2: Event-Driven Microservices on AKS

**What:** Microservices communicate asynchronously via Azure Service Bus (commands/tasks) and Azure Event Grid (domain events/notifications). Synchronous REST/gRPC calls used only for real-time request-response paths (e.g., model inference, catalog queries).

**When to use:** For all cross-service workflows that don't require immediate response — model deployments, fine-tuning jobs, evaluation runs, billing meter events, usage reporting.

**Trade-offs:**
- Pro: Services scale independently, loose coupling, resilient to downstream failures
- Pro: Natural fit for long-running AI operations (training, evaluation, deployment)
- Con: Eventual consistency — billing/quota views may lag by seconds
- Con: Debugging distributed event flows requires good observability (correlation IDs, distributed tracing)

**Example event flow:**
```
User deploys model via API
  → Deployment Service receives REST request
  → Publishes "DeploymentRequested" event to Service Bus
  → Deployment Service provisions endpoint (async)
  → Publishes "DeploymentCompleted" event to Event Grid
  → Billing Service meters the deployment
  → Monitoring Service starts health tracking
  → Portal receives notification via SignalR
```

### Pattern 3: Multi-Provider Model Abstraction

**What:** The platform abstracts model consumption behind a unified API, regardless of whether the model is hosted on Azure OpenAI, deployed as a custom container on AKS, or accessed via a third-party API (Anthropic, Cohere, etc.). The Model Catalog Service maintains provider-agnostic metadata, and the API Gateway routes inference requests to the appropriate backend.

**When to use:** This is the platform's key differentiator — enabling multi-provider model aggregation with standardized consumption.

**Trade-offs:**
- Pro: Users get one API to consume any model; provider switching doesn't break clients
- Pro: Platform can optimize routing (cost, latency, availability) across providers
- Con: Must maintain provider adapters for each model backend
- Con: Feature parity across providers is challenging (not all models support streaming, function calling, etc.)

### Pattern 4: Project-Scoped Resource Isolation (Multi-Tenancy)

**What:** Each project/workspace gets logically isolated resources — its own Cosmos DB partition, its own APIM subscription key, its own RBAC scope, its own quota allocation. The platform enforces tenant boundaries at the data layer (partition keys) and API layer (APIM policies).

**When to use:** Always for multi-tenant enterprise platforms. Azure Foundry uses a similar pattern: top-level resource for governance, with project-scoped boundaries for development teams.

**Trade-offs:**
- Pro: Cost attribution per project, blast radius containment, compliance isolation
- Pro: Aligns with Azure Entra ID group-based access patterns
- Con: Cross-project resource sharing (e.g., shared models) requires explicit connection management
- Con: More complex onboarding flows

## Data Flow

### Model Inference Request Flow

```
Client (Portal/SDK/CLI)
    │
    ▼
Azure Front Door / App Gateway (WAF, DDoS, TLS termination)
    │
    ▼
Azure API Management
    ├── Authenticate (Entra ID token validation)
    ├── Check quota (rate limit by project/subscription)
    ├── Apply content safety pre-filter
    ├── Route to model backend based on deployment config
    │
    ▼
Model Backend (one of:)
    ├── Azure OpenAI endpoint (managed models)
    ├── AKS model serving pod (custom/OSS models on Triton, vLLM, etc.)
    └── Third-party API (Anthropic, Cohere, etc.)
    │
    ▼
Response flows back through APIM
    ├── Apply content safety post-filter
    ├── Meter usage (emit event to billing pipeline)
    ├── Log to Application Insights (latency, tokens, model used)
    │
    ▼
Client receives response
```

### Model Deployment Flow

```
User requests deployment (via Portal or API)
    │
    ▼
Deployment Service
    ├── Validates model exists in catalog
    ├── Checks project quota/permissions
    ├── Determines deployment target:
    │   ├── Azure OpenAI → calls Azure OpenAI management API
    │   ├── Custom model → creates AKS Deployment + Service
    │   └── Third-party → configures API connection
    ├── Stores deployment record in Cosmos DB
    ├── Publishes "DeploymentRequested" → Service Bus
    │
    ▼
Async provisioning (may take seconds to minutes)
    ├── Health check loop
    ├── Configure APIM backend + routing policy
    │
    ▼
Publishes "DeploymentReady" → Event Grid
    ├── Billing Service: starts metering
    ├── Monitoring Service: begins health monitoring
    ├── Portal: notifies user (via SignalR websocket)
```

### Key Data Flows

1. **Model Discovery:** User → Portal → APIM → Catalog Service → AI Search (vector + keyword search) + Cosmos DB (metadata) → aggregated results
2. **Fine-Tuning:** User uploads dataset → Data Service → Blob Storage → Fine-Tune Service → Azure OpenAI fine-tuning API or AKS training job → Model registered in catalog
3. **Evaluation:** User configures eval → Eval Service → pulls test dataset from Blob → runs inference against model endpoint → stores results in Cosmos DB → generates report
4. **Cost Tracking:** Every model call → APIM emits usage event → Event Hub → Billing Service → aggregates in Azure SQL → dashboard query via API

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **0–1K users** | Single AKS cluster (3-node pool), single APIM unit, Cosmos DB serverless, shared model endpoints. Keep services count minimal — catalog, deployment, project, and billing as initial set. |
| **1K–50K users** | Multi-node AKS with dedicated node pools (system vs. user workloads vs. GPU inference), APIM Premium v2 with 2+ units, Cosmos DB provisioned throughput, Azure Cache for Redis for catalog queries, separate AKS namespace per environment. |
| **50K+ users** | Multi-region AKS with Azure Front Door for global routing, Cosmos DB multi-region write, APIM multi-region gateways, dedicated AKS clusters for model serving (GPU pools), Event Hub with partitioned consumers, Azure SQL Hyperscale for billing data. |

### Scaling Priorities

1. **First bottleneck: Model inference endpoints.** AI model serving is the most resource-intensive component. Azure OpenAI has TPM (tokens-per-minute) quotas; custom models on AKS need GPU node autoscaling. Mitigation: implement APIM backend pools with circuit breaking, deploy spillover from provisioned to standard deployments, cache common inference results.

2. **Second bottleneck: API Gateway throughput.** APIM processes every request. At high volume, a single unit saturates. Mitigation: scale APIM units (up to 12 per region), use APIM self-hosted gateway on AKS for internal service-to-service calls.

3. **Third bottleneck: Cosmos DB hot partitions.** If project IDs aren't well-distributed or a single project generates disproportionate load. Mitigation: design partition keys around project ID + date sharding for usage data, use hierarchical partition keys for large tenants.

## Anti-Patterns

### Anti-Pattern 1: Shared Databases Across Services

**What people do:** Multiple microservices read/write to the same Cosmos DB container or SQL database for "simplicity."
**Why it's wrong:** Creates tight coupling, makes independent deployment impossible, causes contention, and violates service boundaries. A schema change in one service breaks others.
**Do this instead:** Each service owns its data. Catalog Service owns model metadata. Billing Service owns usage records. Communicate changes via events, not shared database queries. Use the Cosmos DB change feed for event-driven cross-service data propagation where needed.

### Anti-Pattern 2: Synchronous Orchestration of Long-Running AI Operations

**What people do:** Client sends a request to deploy a model, and the API blocks until deployment is complete (which can take minutes).
**Why it's wrong:** Holds connections open, creates cascading timeouts, wastes resources, and provides a terrible user experience.
**Do this instead:** Accept the request, return a 202 Accepted with a status polling URL or operation ID. Use Service Bus for async processing. Notify the client via webhooks or SignalR when the operation completes. This pattern applies to: deployments, fine-tuning jobs, evaluations, batch inference.

### Anti-Pattern 3: Direct Client-to-Model-Endpoint Access

**What people do:** Clients call model inference endpoints directly (e.g., Azure OpenAI API keys embedded in client code), bypassing the platform's API gateway.
**Why it's wrong:** No centralized auth, no usage tracking, no content safety filtering, no quota enforcement, no model abstraction. Clients become coupled to specific model providers.
**Do this instead:** All model access flows through APIM. Clients authenticate to the platform, and the platform authenticates to model backends using managed identities. Azure's reference architecture explicitly recommends credential termination at the gateway.

### Anti-Pattern 4: Monolithic Model Catalog with All Providers

**What people do:** Build one giant service that scrapes/integrates every model provider in real-time, trying to maintain live parity with upstream catalogs.
**Why it's wrong:** Each provider has different APIs, rate limits, and data formats. A single failure point that affects the entire catalog experience.
**Do this instead:** Use a provider adapter pattern. Each model provider has its own lightweight adapter that normalizes metadata into the platform's schema. Adapters sync on a schedule (or webhook) and write to the catalog's data store. The catalog service reads from its own normalized store, never calling providers in real-time for search/browse.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **Azure OpenAI** | REST API via managed identity + APIM proxy | Primary managed model provider. Use data zone deployments for compliance. Deploy provisioned + standard for spillover. |
| **Azure AI Content Safety** | REST API per-request inline filter | Called pre- and post-inference. Latency-sensitive — deploy in same region. |
| **Azure AI Search** | SDK (push model) for indexing, REST for queries | Indexes model metadata, documentation, and knowledge bases. Use semantic ranker for natural language model discovery. |
| **Azure ML** | REST API for training job orchestration | Backend for fine-tuning and custom model training workflows. Platform submits jobs, monitors status, registers outputs. |
| **Third-party model APIs** | REST via APIM outbound policy, through Azure Firewall | Anthropic, Cohere, Hugging Face Inference API. Each provider needs its own adapter. Egress controlled via Azure Firewall FQDN rules. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| **Portal ↔ API Gateway** | HTTPS/REST via APIM | Portal never calls microservices directly. All requests go through APIM for auth + routing. |
| **API Gateway ↔ Microservices** | HTTPS/REST or gRPC via private endpoints | APIM routes to AKS internal ingress controller. mTLS between APIM and AKS. |
| **Microservice ↔ Microservice (sync)** | gRPC via Kubernetes service DNS | For low-latency service-to-service calls within AKS (e.g., Catalog → Deployment for validation). |
| **Microservice ↔ Microservice (async)** | Azure Service Bus (commands) / Event Grid (events) | Long-running operations, cross-cutting concerns (billing, monitoring, notifications). |
| **Microservices ↔ Data Stores** | Azure SDK via managed identity + private endpoints | No connection strings or keys. All data stores accessed via managed identity and private endpoints within VNet. |
| **Microservices ↔ Model Endpoints** | HTTPS via APIM (outbound) or direct private endpoint | Platform services that call model inference route through internal APIM policy or direct private endpoint to Azure OpenAI. |

## Build Order (Dependencies Between Components)

The following build order reflects component dependencies — each phase can start only after its prerequisites are complete:

```
Phase 1: Foundation (no dependencies)
├── Infrastructure (VNet, AKS, ACR, Key Vault, Monitoring)
├── Identity & Auth (Entra ID app registrations, RBAC framework)
└── API Gateway skeleton (APIM instance, basic policies)

Phase 2: Core Platform (depends on Phase 1)
├── Project Service (workspaces, team management, isolation)
├── Model Catalog Service (metadata store, search index)
└── Data Storage Layer (Cosmos DB containers, Blob accounts)

Phase 3: Model Operations (depends on Phase 2)
├── Deployment Service (model lifecycle management)
├── Model Serving Layer (Azure OpenAI integration, AKS endpoints)
└── Unified Model Consumption API (APIM routing policies)

Phase 4: User Experience (depends on Phase 3)
├── Web Portal (catalog browsing, deployment management)
├── Playground Service (interactive model experimentation)
└── SDK & CLI (programmatic access)

Phase 5: Advanced Features (depends on Phase 3 & 4)
├── Fine-Tuning Service (training workflows)
├── Evaluation Service (benchmarking framework)
├── Orchestration Service (multi-model pipelines)
└── Content Safety Service (guardrails integration)

Phase 6: Operations & Business (depends on Phase 3)
├── Billing & Quota Service (usage metering, cost allocation)
├── Monitoring Dashboards (usage, performance, cost views)
└── Multi-Provider Model Adapters (third-party integrations)
```

**Build order rationale:**
- **Infrastructure first:** Everything depends on networking, compute, and identity being in place
- **Project Service early:** Multi-tenancy boundaries must exist before any other service stores data
- **Catalog before Deployment:** Users must discover models before deploying them
- **Deployment before Portal:** The Portal needs working APIs to render
- **Fine-tuning & Evaluation after deployment:** These advanced features require model serving to be operational
- **Billing after deployment:** Can't meter what isn't deployed; billing is valuable but not blocking for MVP

## Sources

- [Microsoft Foundry Architecture](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/architecture) — Official architecture documentation for Foundry resource hierarchy, security separation, computing, and data storage (HIGH confidence, official docs, reviewed 2026-03-23)
- [Baseline Microsoft Foundry Chat Reference Architecture](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/architecture/baseline-microsoft-foundry-chat) — Enterprise-grade reference architecture for AI chat applications on Azure, covering components, networking, reliability, security, and operational excellence (HIGH confidence, Azure Architecture Center, reviewed 2026-03-23)
- [Machine Learning Operations (MLOps v2)](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/mlops-technical-paper) — Architecture patterns for ML model lifecycle including inner/outer loop, RBAC, monitoring, and package management (HIGH confidence, Azure Architecture Center, reviewed 2026-03-23)
- [Use a Gateway in Front of Multiple Azure OpenAI Deployments](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/azure-openai-gateway-multi-backend) — Multi-backend gateway patterns using Azure API Management for load balancing, failover, and security across model deployments (HIGH confidence, Azure Architecture Center, reviewed 2026-03-23)
- [Azure API Management Key Concepts](https://learn.microsoft.com/en-us/azure/api-management/api-management-key-concepts) — API gateway, management plane, developer portal, policies, and workspaces (HIGH confidence, official docs, reviewed 2026-03-23)

---
*Architecture research for: AI Platform System (Azure-native enterprise AI platform)*
*Researched: 2026-03-23*
