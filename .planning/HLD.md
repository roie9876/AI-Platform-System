# High-Level Design: AI Agent Platform

**Version:** 1.0
**Date:** 2026-03-23
**Status:** Approved for implementation
**Scope:** Full platform architecture — Control Plane, Runtime Plane, and cross-cutting concerns

---

## 1. Executive Summary

This document describes the high-level architecture of a multi-tenant AI Agent Platform as a Service (PaaS). The platform enables product teams to discover AI models, deploy them to managed endpoints, create and configure AI agents, orchestrate multi-agent workflows, and consume everything through standardized APIs — with built-in evaluation, cost observability, policy enforcement, and responsible AI controls.

The architecture separates concerns into two fundamental planes:

- **Control Plane**: Management-oriented operations — CRUD, configuration, versioning, policy, identity, and governance
- **Runtime Plane**: Execution-oriented operations — model inference, agent execution, memory, tool invocation, streaming, and RAG

This separation ensures that management operations never compete with execution-critical paths for resources, and that each plane can scale, deploy, and fail independently.

---

## 2. Architectural Principles

| Principle | Rationale |
|-----------|-----------|
| **Plane separation** | Control and runtime operations have fundamentally different latency, throughput, and availability requirements |
| **Shared infrastructure, logical isolation** | Cost-efficient multi-tenancy with isolation enforced at data, API, identity, and network layers |
| **Event-driven communication** | Asynchronous messaging between services for long-running operations; synchronous only for real-time request-response paths |
| **API-first contracts** | All capabilities exposed through versioned APIs; the portal, SDK, and CLI are consumers, not special cases |
| **Defense in depth** | Security enforcement at every layer boundary — network, gateway, service, data, and runtime |
| **Observability as infrastructure** | Distributed tracing, structured logging, and metrics collection are non-negotiable from Day 1 |
| **Capability-based extensibility** | New model providers, tools, and agent types plug in through adapters and registries, not code changes |

---

## 3. System Context

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL ACTORS                              │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────┐   │
│  │  Portal  │  │   SDK    │  │   CLI    │  │  External Systems │   │
│  │  (Web)   │  │ (Client) │  │          │  │  (Webhooks, CI/CD)│   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬──────────┘   │
│       │              │             │                  │              │
├───────┴──────────────┴─────────────┴──────────────────┴──────────────┤
│                                                                      │
│                    ┌──────────────────────┐                           │
│                    │    EDGE / INGRESS    │                           │
│                    │  (Global LB + WAF)   │                           │
│                    └──────────┬───────────┘                           │
│                               │                                      │
│              ┌────────────────┴────────────────┐                     │
│              │         API  GATEWAY            │                     │
│              │  (AuthN, Rate Limiting, Routing)│                     │
│              └───────┬────────────────┬────────┘                     │
│                      │                │                               │
│         ┌────────────┴──┐     ┌───────┴────────────┐                 │
│         │ CONTROL PLANE │     │   RUNTIME PLANE    │                 │
│         │ (Management)  │     │   (Execution)      │                 │
│         └───────────────┘     └────────────────────┘                 │
│                                                                      │
│              ┌──────────────────────────────────┐                    │
│              │      CROSS-CUTTING CONCERNS      │                    │
│              │  Identity · Observability · Cost  │                    │
│              │  Security · Governance · Isolation│                    │
│              └──────────────────────────────────┘                    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Actor Descriptions

| Actor | Interaction Pattern |
|-------|---------------------|
| **Web Portal** | Browser-based UI for all management and experimentation. Communicates exclusively through the API Gateway — never calls internal services directly. |
| **SDK / Client Libraries** | Language-specific libraries (Python, .NET) wrapping the platform API. Handles auth, retries, streaming, and type-safe model consumption. |
| **CLI** | Terminal-based tool for platform operations — deploy, list, delete, query. Uses the same API endpoints as the SDK. |
| **External Systems** | CI/CD pipelines, monitoring integrations, and webhook consumers that react to platform events (deployment completed, budget exceeded, evaluation finished). |

---

## 4. Control Plane Architecture

The Control Plane handles all management operations. These are lower-throughput, higher-latency-tolerant operations that configure, version, and govern platform resources.

### 4.1 Control Plane Component Diagram

```
┌────────────────────────────────────── CONTROL PLANE ──────────────────────────────────────┐
│                                                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │   Project    │  │    Model     │  │    Agent     │  │ Deployment   │                   │
│  │  Management  │  │   Catalog    │  │  Management  │  │  Lifecycle   │                   │
│  │   Service    │  │   Service    │  │   Service    │  │   Service    │                   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                   │
│         │                 │                 │                 │                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │    Tool      │  │   Policy     │  │   Quota &    │  │  Evaluation  │                   │
│  │   Registry   │  │   Engine     │  │   Budget     │  │   Engine     │                   │
│  │   Service    │  │   Service    │  │   Service    │  │   Service    │                   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                   │
│         │                 │                 │                 │                             │
│  ┌──────────────┐  ┌──────────────┐                                                       │
│  │  Data Source │  │  Marketplace │                                                       │
│  │  Connection  │  │   Service    │                                                       │
│  │   Service    │  │              │                                                       │
│  └──────┬───────┘  └──────┬───────┘                                                       │
│         │                 │                                                                │
│  ┌──────┴─────────────────┴──────────────────────────────────────────────────────────┐     │
│  │                          CONTROL PLANE EVENT BUS                                   │     │
│  │                   (Commands → Message Queue, Events → Event Router)                │     │
│  └───────────────────────────────────────────────────────────────────────────────────┘     │
│                                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐      │
│  │                       CONTROL PLANE DATA STORES                                  │      │
│  │                                                                                  │      │
│  │  ┌─────────────┐  ┌───────────────┐  ┌──────────────┐  ┌─────────────────┐      │      │
│  │  │  Document   │  │ Search Index  │  │  Relational  │  │  Secret Store   │      │      │
│  │  │  Database   │  │ (Catalog,     │  │  Database    │  │  (Credentials,  │      │      │
│  │  │  (Metadata, │  │  Discovery)   │  │  (Billing,   │  │   API Keys,     │      │      │
│  │  │   Config)   │  │               │  │   Audit)     │  │   Certificates) │      │      │
│  │  └─────────────┘  └───────────────┘  └──────────────┘  └─────────────────┘      │      │
│  └──────────────────────────────────────────────────────────────────────────────────┘      │
│                                                                                            │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Control Plane Services

#### 4.2.1 Project Management Service

**Responsibility:** Tenant and project lifecycle — creation, membership, isolation boundaries, and resource governance.

| Operation | Description |
|-----------|-------------|
| Create project | Provisions logical isolation scope: document database partition, API subscription, RBAC scope, monitoring dimension |
| Manage members | Invite/remove users, assign roles (Owner, Contributor, Reader) per project |
| Set quotas | Configure per-project limits for compute, storage, token consumption, model deployments |
| Project metadata | Name, description, tags, environment classification, compliance tier |

**Data model:**
```
Project {
  id: UUID
  tenantId: UUID
  name: string
  description: string
  members: [{ userId, role, joinedAt }]
  quotas: { maxDeployments, maxTokensPerDay, maxStorageGB, maxBudgetUSD }
  settings: { defaultRegion, complianceTier, retentionDays }
  status: active | suspended | archived
  createdAt: timestamp
  updatedAt: timestamp
}
```

**Isolation effect:** Every resource created within the platform is scoped to a `projectId`. The Project Management Service is the authority for project existence and membership. All downstream services validate project context before processing requests.

#### 4.2.2 Model Catalog Service

**Responsibility:** Aggregated, provider-agnostic model discovery with searchable metadata.

| Operation | Description |
|-----------|-------------|
| Model registration | Register models from multiple upstream providers via provider adapters |
| Model search | Full-text and semantic (vector) search across model metadata |
| Model comparison | Side-by-side comparison on capabilities, pricing, benchmarks, license terms |
| Version tracking | Model lifecycle status: preview → generally available → deprecated → retired |
| Provider sync | Periodic synchronization with upstream provider catalogs (schedule-based, not real-time) |

**Provider Adapter Pattern:**
```
┌──────────────────────────────────────────────────────────────┐
│                     MODEL CATALOG SERVICE                     │
│                                                               │
│  ┌──────────────────────────────────┐                         │
│  │      Normalized Model Store     │ ◄── Single schema for   │
│  │      (Document Database)         │     all providers        │
│  └───────────┬──────────────────────┘                         │
│              │                                                │
│  ┌───────────┴───────────────────────────────────────────┐    │
│  │              ADAPTER REGISTRY                          │    │
│  │                                                       │    │
│  │  ┌─────────────┐ ┌──────────────┐ ┌─────────────┐    │    │
│  │  │ Provider A  │ │ Provider B   │ │ Provider C  │    │    │
│  │  │ Adapter     │ │ Adapter      │ │ Adapter     │    │    │
│  │  │             │ │              │ │ (Open-     │    │    │
│  │  │ (Managed    │ │ (Third-party │ │  source     │    │    │
│  │  │  Models)    │ │  API)        │ │  Models)    │    │    │
│  │  └──────┬──────┘ └──────┬───────┘ └──────┬──────┘    │    │
│  └─────────┴───────────────┴────────────────┴────────────┘    │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

Each adapter normalizes provider-specific metadata (model name, capabilities, pricing, license, benchmarks, supported modalities) into the platform's canonical schema. Adapters run on a configurable sync schedule and push updates to the normalized store. The catalog never queries upstream providers in real-time for browse/search operations.

**Search architecture:** The catalog indexes model metadata into a search index supporting:
- Full-text keyword search (model name, description, tags)
- Semantic vector search (natural language queries: "find a model good at code generation")
- Faceted filtering (provider, modality, task type, license, pricing tier)
- Relevance ranking combining text scores, popularity signals, and recency

#### 4.2.3 Agent Management Service

**Responsibility:** Agent CRUD, configuration, versioning, and lifecycle management.

| Operation | Description |
|-----------|-------------|
| Create agent | Define agent with name, system prompt, model assignment, tool bindings, memory config |
| Version agent | Immutable agent versions with diff tracking; rollback to any prior version |
| Configure tools | Attach/detach tools per agent; configure tool parameters and permissions |
| Configure data sources | Connect knowledge bases, databases, APIs to an agent's context |
| Configure memory | Set memory strategy (conversation-scoped, project-scoped, persistent), retention policy |
| Agent templates | Create and publish reusable agent templates to the marketplace |

**Agent Configuration Model:**
```
AgentDefinition {
  id: UUID
  projectId: UUID
  name: string
  version: integer (immutable per version)
  systemPrompt: string
  modelId: UUID (reference to catalog model)
  toolBindings: [{
    toolId: UUID
    permissions: [read | write | execute]
    parameters: Map<string, any>
  }]
  dataSources: [{
    sourceId: UUID
    accessMode: read | readWrite
    indexConfig: { chunkSize, overlapTokens, embeddingModel }
  }]
  memoryConfig: {
    strategy: conversation | project | persistent
    maxTokens: integer
    retentionDays: integer
    indexingEnabled: boolean
  }
  executionPolicy: {
    maxSteps: integer
    timeoutSeconds: integer
    maxTokensPerTurn: integer
    allowedSubAgents: [UUID]
    humanApprovalRequired: boolean
  }
  status: draft | published | deprecated
  createdAt: timestamp
  publishedAt: timestamp
}
```

#### 4.2.4 Deployment Lifecycle Service

**Responsibility:** Model and agent endpoint provisioning, scaling, health monitoring, and teardown.

**Deployment flow (asynchronous):**
```
Request received (API)
    │
    ├── Validate: model/agent exists, project has quota headroom
    ├── Reserve: decrement project quota allocation
    ├── Persist: deployment record with status = "provisioning"
    ├── Emit: DeploymentRequested → message queue
    │
    ▼ (async worker)
    ├── Provision: create compute endpoint (managed or self-hosted)
    ├── Configure: routing rules in API gateway
    ├── Health check: poll endpoint until healthy
    ├── Update: deployment status = "running"
    ├── Emit: DeploymentReady → event router
    │
    ▼ (event consumers)
    ├── Cost tracking service: begin metering
    ├── Monitoring service: begin health polling
    └── Notification service: alert user (websocket push)
```

**Deployment targets:**
| Target Type | Description | Scale Model |
|-------------|-------------|-------------|
| **Managed endpoints** | Platform-hosted model inference; provider manages compute | Auto-scaled by provider; platform configures quotas |
| **Self-hosted endpoints** | Models deployed on platform-managed container infrastructure | Horizontal pod autoscaler based on request queue depth + GPU utilization |
| **External endpoints** | Third-party model APIs configured as pass-through backends | No scaling — platform manages routing and failover |

#### 4.2.5 Tool Registry Service

**Responsibility:** Registration, versioning, and discovery of tools that agents can invoke.

**Tool types:**
| Type | Execution Model | Examples |
|------|-----------------|---------|
| **API Tool** | HTTP/gRPC call to external service | Web search, calendar access, CRM queries |
| **Function Tool** | Sandboxed function execution within the platform | Data transformation, calculation, format conversion |
| **Data Tool** | Query against a connected data source | Database query, document retrieval, knowledge base search |
| **System Tool** | Platform-native operation | Create deployment, query metrics, manage files |

**Tool definition schema:**
```
ToolDefinition {
  id: UUID
  name: string
  version: semver
  description: string (used by LLMs for tool selection)
  type: api | function | data | system
  inputSchema: JSONSchema (parameter specification)
  outputSchema: JSONSchema (return value specification)
  authentication: { type: none | apiKey | oauth | managedIdentity, config: {...} }
  rateLimit: { requestsPerMinute, maxConcurrent }
  timeout: integer (seconds)
  sandboxRequirements: { networkAccess: boolean, maxMemoryMB: integer, maxCpuMillis: integer }
  visibility: private | project | public
  publishedBy: { projectId, userId }
}
```

#### 4.2.6 Policy Engine Service

**Responsibility:** Define and enforce governance rules across all platform operations.

**Policy types:**
| Policy Type | Scope | Enforcement Point |
|-------------|-------|-------------------|
| **Content safety** | Per-project or global | Runtime Plane — inference pipeline pre/post filters |
| **Budget limits** | Per-project | Control Plane — deployment and inference request validation |
| **Model access** | Per-project | Control Plane — catalog and deployment authorization |
| **Tool permissions** | Per-agent | Runtime Plane — tool invocation authorization |
| **Data residency** | Per-tenant | Control Plane — deployment region restrictions |
| **Retention** | Per-project | Control Plane — data lifecycle enforcement |
| **Rate limiting** | Per-project, per-user | API Gateway — request throttling |

**Policy evaluation flow:**
```
Request arrives at enforcement point
    │
    ├── Load applicable policies (cached, per-project + global)
    ├── Evaluate policies in priority order
    │   ├── DENY overrides all → request rejected with policy violation detail
    │   ├── All ALLOW → request proceeds
    │   └── AUDIT → request proceeds, violation logged for review
    │
    ├── Log evaluation result (policy ID, decision, latency)
    └── Return decision to enforcement point
```

#### 4.2.7 Quota & Budget Service

**Responsibility:** Track resource consumption, enforce limits, and enable cost attribution.

**Quota dimensions:**
| Dimension | Unit | Enforcement |
|-----------|------|-------------|
| Model deployments | Count per project | Checked at deployment creation |
| Token consumption | Tokens per day/month per project | Checked at inference time (pre-request) |
| Storage | GB per project | Checked at data upload |
| Compute hours | GPU-hours per project | Tracked per training/fine-tuning job |
| API requests | Requests per minute per project | Enforced at API gateway |
| Budget | USD per month per project | Soft limit (alert) + hard limit (block) |

**Budget enforcement flow:**
```
Inference request arrives
    │
    ├── Read project budget state (from cache, refreshed every N seconds)
    │   ├── Current spend < 80% of budget → proceed
    │   ├── 80% ≤ spend < 100% → proceed + emit budget warning event
    │   └── spend ≥ 100% (hard limit) → reject with 429 + budget exceeded
    │
    ├── After request completes:
    │   ├── Calculate cost: tokens × model pricing rate
    │   ├── Increment project spend counter (atomic operation)
    │   └── Emit cost event → cost ledger
```

#### 4.2.8 Evaluation Engine Service

**Responsibility:** Automated quality assessment, benchmarking, and A/B testing for models and agents.

**Evaluation types:**
| Type | Description | Output |
|------|-------------|--------|
| **Benchmark evaluation** | Run standard benchmarks (accuracy, latency, safety) against a model/agent | Score card with pass/fail thresholds |
| **Custom evaluation** | User-defined test datasets with expected outputs | Precision, recall, similarity scores |
| **A/B evaluation** | Compare two model/agent versions on the same test set | Statistical significance report |
| **Continuous evaluation** | Scheduled re-evaluation of production agents against regression datasets | Trend dashboards + regression alerts |

#### 4.2.9 Data Source Connection Service

**Responsibility:** Manage connections to external and internal data sources that agents use for knowledge retrieval (RAG).

**Connection types:**
| Source Type | Connection Method | Use Case |
|-------------|-------------------|----------|
| **Object storage** | Authenticated blob access | Document corpora, PDFs, images |
| **Relational database** | Connection pool with credential rotation | Structured data queries |
| **Document database** | Authenticated read access | Semi-structured data retrieval |
| **API endpoint** | HTTP with OAuth/API key | Real-time data from external services |
| **Search index** | Query interface | Pre-indexed knowledge bases |

**Indexing pipeline (for RAG-connected sources):**
```
Data source configured
    │
    ├── Initial sync: crawl source, extract content
    │   ├── Document chunking (configurable: size, overlap, strategy)
    │   ├── Embedding generation (using configured embedding model)
    │   └── Index storage (vector database with metadata)
    │
    ├── Incremental sync: detect changes, re-index affected chunks
    │   ├── Change detection: timestamps, checksums, webhooks
    │   └── Selective re-embedding + index update
    │
    └── Status tracking: last sync time, document count, error log
```

#### 4.2.10 Marketplace Service

**Responsibility:** Discover, publish, install, and rate pre-built agents, tools, and templates.

**Marketplace entities:**
| Entity | Description |
|--------|-------------|
| **Agent templates** | Pre-configured agent definitions with system prompts, tool bindings, and recommended models |
| **Tool packages** | Reusable tool definitions with authentication configuration |
| **Workflow templates** | Pre-built multi-agent orchestration patterns |
| **Prompt libraries** | Curated system prompts and prompt templates for common use cases |

### 4.3 Control Plane Data Architecture

**Data store selection rationale:**

| Store Type | Used For | Why |
|------------|----------|-----|
| **Distributed document database** | Project metadata, agent definitions, model metadata, tool definitions, deployment records, agent configurations | Schema flexibility for evolving configurations; hierarchical partition keys for tenant isolation; change feed for event-driven propagation |
| **Search index** | Model catalog discovery, tool discovery, agent template search | Full-text + semantic (vector) search with faceted filtering; sub-second query latency for browsable UIs |
| **Relational database** | Billing records, audit logs, quota tracking, cost aggregation | ACID transactions for financial data; complex JOIN queries for cost roll-ups; row-level security for tenant isolation |
| **Secret store** | API keys, service credentials, connection strings, certificates | Hardware-backed encryption; managed credential rotation; RBAC access control per service identity |
| **Cache layer** | Session state, rate limit counters, quota state, frequently read configurations | Sub-millisecond reads for hot-path decisions (rate limits, budget checks) |

**Partition key strategy (document database):**
```
Hierarchical partition key: /tenantId/projectId/entityType

Examples:
  tenant-001/project-abc/agent       → All agents in project-abc
  tenant-001/project-abc/deployment   → All deployments in project-abc
  tenant-001/project-abc/model-entry  → All catalog entries for project-abc

Benefits:
  - Queries never cross tenant boundaries (partition-level enforcement)
  - Per-partition throughput isolation (noisy neighbor protection)
  - Efficient range queries within a project scope
  - Physical data locality for tenant data
```

---

## 5. Runtime Plane Architecture

The Runtime Plane handles all execution-critical operations. These are high-throughput, low-latency operations that require real-time responsiveness and strict resource isolation.

### 5.1 Runtime Plane Component Diagram

```
┌────────────────────────────────────── RUNTIME PLANE ──────────────────────────────────────┐
│                                                                                            │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐    │
│  │                           INFERENCE GATEWAY                                        │    │
│  │                                                                                    │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │    │
│  │  │  Auth    │  │  Rate    │  │ Content  │  │  Model   │  │   Streaming      │    │    │
│  │  │ Validate │→ │  Limit   │→ │ Safety   │→ │ Routing  │→ │   Protocol       │    │    │
│  │  │          │  │  Check   │  │ Pre-     │  │  Engine  │  │   Engine (SSE)   │    │    │
│  │  │          │  │          │  │ Filter   │  │          │  │                  │    │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘    │    │
│  └────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                            │
│  ┌──────────────────────────────────── EXECUTION TIER ────────────────────────────────┐    │
│  │                                                                                    │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │    │
│  │  │    Agent     │  │  Workflow    │  │  Sub-Agent   │  │    Tool      │           │    │
│  │  │  Execution   │  │  Execution   │  │ Orchestrator │  │  Execution   │           │    │
│  │  │   Runtime    │  │   Engine     │  │              │  │   Sandbox    │           │    │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘           │    │
│  │         │                 │                 │                 │                     │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                              │    │
│  │  │   Memory     │  │   Thread &   │  │    RAG       │                              │    │
│  │  │  Management  │  │    State     │  │  Pipeline    │                              │    │
│  │  │   Engine     │  │   Manager    │  │              │                              │    │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                              │    │
│  └─────────┴─────────────────┴─────────────────┴──────────────────────────────────────┘    │
│                                                                                            │
│  ┌──────────────────────────────────── INFERENCE TIER ────────────────────────────────┐    │
│  │                                                                                    │    │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                    │    │
│  │  │  Managed Model  │  │  Self-Hosted    │  │  External       │                    │    │
│  │  │  Endpoints      │  │  Model Servers  │  │  Provider       │                    │    │
│  │  │  (Provider A,B) │  │  (Open-source)  │  │  Adapters       │                    │    │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘                    │    │
│  └────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                            │
│  ┌──────────────────────────────────── DATA TIER ─────────────────────────────────────┐    │
│  │                                                                                    │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │    │
│  │  │   Vector     │  │    Object    │  │   Document   │  │    Cache     │           │    │
│  │  │   Database   │  │   Storage    │  │   Database   │  │   (Hot       │           │    │
│  │  │  (Embeddings,│  │  (Artifacts, │  │  (State,     │  │    State)    │           │    │
│  │  │   RAG Index) │  │   Files)     │  │   Memory)    │  │              │           │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘           │    │
│  └────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                            │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Inference Gateway

The Inference Gateway is the hot path for all model and agent invocations. Every millisecond of latency here directly impacts user experience.

#### 5.2.1 Request Processing Pipeline

```
Incoming request (HTTPS)
    │
    ▼
┌─── Stage 1: Authentication ──────────────────────────────────────┐
│  • Validate bearer token (identity provider token validation)    │
│  • Extract tenant/project context from token claims              │
│  • Reject if unauthorized → 401                                  │
│  • Latency budget: < 2ms (cached token validation)               │
└──────────────────────────────────────────────┬───────────────────┘
                                               │
    ▼
┌─── Stage 2: Rate Limiting & Quota ───────────────────────────────┐
│  • Check per-project rate limit counter (cache lookup)           │
│  • Check per-project budget state (cache lookup)                 │
│  • Reject if over limit → 429 with retry-after header           │
│  • Latency budget: < 1ms (in-memory counter)                    │
└──────────────────────────────────────────────┬───────────────────┘
                                               │
    ▼
┌─── Stage 3: Content Safety Pre-Filter ───────────────────────────┐
│  • Load project's content safety policy (cached)                 │
│  • Run input through safety classifier                           │
│  • Categories: hate, sexual, violence, self-harm, PII            │
│  • If violates → 400 with violation category + severity          │
│  • If PII detected + redaction enabled → redact before forwarding│
│  • Latency budget: < 50ms (optimized classifier)                 │
└──────────────────────────────────────────────┬───────────────────┘
                                               │
    ▼
┌─── Stage 4: Model/Agent Routing ─────────────────────────────────┐
│  • Resolve deployment ID → backend endpoint configuration        │
│  • Select backend from pool (weighted round-robin + health)      │
│  • Apply circuit breaker state (if backend degraded → failover)  │
│  • Transform request to provider-specific format                 │
│  • Latency budget: < 1ms (cached routing table)                  │
└──────────────────────────────────────────────┬───────────────────┘
                                               │
    ▼
┌─── Stage 5: Backend Invocation ──────────────────────────────────┐
│  • Forward request to model endpoint                             │
│  • If stream=true: establish SSE connection, proxy tokens         │
│  • If stream=false: buffer complete response                     │
│  • Capture: time-to-first-token, inter-token latency,            │
│    total tokens, completion reason                               │
└──────────────────────────────────────────────┬───────────────────┘
                                               │
    ▼
┌─── Stage 6: Content Safety Post-Filter ──────────────────────────┐
│  • Run output through safety classifier                          │
│  • For streaming: evaluate incrementally on sentence boundaries   │
│  • If violates → truncate stream + safety warning                │
│  • Latency budget: < 50ms (for buffered), incremental for stream │
└──────────────────────────────────────────────┬───────────────────┘
                                               │
    ▼
┌─── Stage 7: Metering & Telemetry ────────────────────────────────┐
│  • Emit usage event (async, non-blocking):                       │
│    { projectId, modelId, inputTokens, outputTokens,              │
│      latencyMs, ttftMs, statusCode, requestId }                  │
│  • Log to distributed tracing (correlated by requestId)          │
│  • Update rate limit counter (async, non-blocking)               │
│  • Latency budget: 0ms (fire-and-forget to event bus)            │
└──────────────────────────────────────────────┬───────────────────┘
                                               │
    ▼
Response returned to client
```

#### 5.2.2 Streaming Protocol Engine

Streaming is a first-class citizen, not an afterthought. The platform supports Server-Sent Events (SSE) for real-time token delivery.

**Streaming architecture:**
```
Client ◄──── SSE Connection ────► Inference Gateway ◄─── SSE/gRPC stream ───► Model Backend

Token flow:
  Backend generates token
    → Gateway receives token
    → Gateway evaluates content safety (incremental, buffered by sentence)
    → Gateway emits token to client SSE stream
    → Gateway records token in telemetry buffer
    → On stream completion: flush telemetry, emit usage event
```

**Streaming design decisions:**
| Concern | Design |
|---------|--------|
| Connection timeout | Configurable per deployment, default 120s, max 600s |
| Backpressure | If client cannot consume fast enough, gateway buffers up to 64KB, then signals backend to slow |
| Interrupted streams | Stream ID tracked; client can detect incomplete stream by checking `finish_reason` field |
| Partial safety filtering | Safety evaluated on sentence boundaries during streaming; full-stream evaluation on completion |
| Token counting (streaming) | Accumulated during stream; final token count emitted on stream completion |
| Load balancer compatibility | Long-lived connections require sticky sessions or connection-aware load balancing |

#### 5.2.3 Model Routing Engine

**Multi-backend routing with intelligent failover:**

```
┌──────────────────────────────────────────────────────────────────┐
│                      MODEL ROUTING ENGINE                        │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐      │
│  │              ROUTING TABLE (cached, per-deployment)     │      │
│  │                                                        │      │
│  │  deployment-001:                                       │      │
│  │    primary:   region-a/managed-endpoint-gpt4           │      │
│  │    fallback1: region-b/managed-endpoint-gpt4           │      │
│  │    fallback2: region-c/self-hosted-vllm-llama          │      │
│  │    weights:   [70%, 20%, 10%]                          │      │
│  │    strategy:  weighted-round-robin                     │      │
│  └────────────────────────┬───────────────────────────────┘      │
│                           │                                      │
│  ┌────────────────────────┴───────────────────────────────┐      │
│  │              CIRCUIT BREAKER (per-backend)              │      │
│  │                                                        │      │
│  │  States: closed (healthy) → open (failing) → half-open │      │
│  │  Threshold: 5 failures in 60s → open for 30s           │      │
│  │  Half-open: allow 1 probe request, reset if success    │      │
│  │                                                        │      │
│  │  On open: redirect traffic to next backend in priority  │      │
│  └────────────────────────┬───────────────────────────────┘      │
│                           │                                      │
│  ┌────────────────────────┴───────────────────────────────┐      │
│  │              HEALTH CHECKER (continuous)                │      │
│  │                                                        │      │
│  │  Interval: 10s per backend                             │      │
│  │  Signals: latency, error rate, queue depth, GPU util   │      │
│  │  Action: update routing weights, trigger circuit breaker│      │
│  └────────────────────────────────────────────────────────┘      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Routing strategies:**
| Strategy | Description | Use Case |
|----------|-------------|----------|
| **Weighted round-robin** | Distribute requests across backends by weight | Default — spread load across regions/providers |
| **Latency-optimized** | Route to lowest-latency healthy backend | Real-time applications requiring minimum TTFT |
| **Cost-optimized** | Route to cheapest available backend | Batch workloads where latency is less critical |
| **Priority failover** | Primary → fallback chain, only failover on failure | SLA-bound tenants with preferred provider |

### 5.3 Execution Tier

#### 5.3.1 Agent Execution Runtime

The Agent Execution Runtime manages the lifecycle of a single agent invocation — from receiving a user message to producing a final response, including any intermediate tool calls, sub-agent invocations, and memory operations.

**Agent execution loop:**
```
User message received
    │
    ▼
┌─── Step 1: Context Assembly ─────────────────────────────────────┐
│  • Load agent definition (system prompt, model, tool bindings)   │
│  • Load conversation thread (prior messages, if continuation)    │
│  • Load relevant memory (long-term + short-term, see §5.3.5)    │
│  • Execute RAG retrieval if data sources configured (see §5.4)   │
│  • Assemble prompt: system + memory + RAG context + thread + user│
│  • Token budget: calculate remaining tokens after context         │
└──────────────────────────────────────────────┬───────────────────┘
                                               │
    ▼
┌─── Step 2: Model Inference ──────────────────────────────────────┐
│  • Send assembled prompt to model endpoint via Inference Gateway │
│  • Stream tokens back to client (if streaming enabled)           │
│  • Parse response for tool call indicators                       │
└──────────────────────────────────────────────┬───────────────────┘
                                               │
    ▼
┌─── Step 3: Tool Call Resolution (if needed) ─────────────────────┐
│  • For each tool call in model response:                         │
│    ├── Validate tool is bound to this agent                      │
│    ├── Validate tool permissions (policy engine check)           │
│    ├── Execute tool in sandbox (see §5.3.4)                      │
│    ├── Capture tool result                                       │
│    └── If tool returns error → include error in next prompt      │
│  • Append tool results to conversation context                   │
│  • Return to Step 2 (model processes tool results)               │
│  • Max iterations: agent.executionPolicy.maxSteps (default: 10)  │
└──────────────────────────────────────────────┬───────────────────┘
                                               │
    ▼
┌─── Step 4: Response Finalization ────────────────────────────────┐
│  • Final model response (no more tool calls)                     │
│  • Update conversation thread (persist messages)                 │
│  • Update memory (extract key facts, update short-term buffer)   │
│  • Emit execution telemetry:                                     │
│    { agentId, threadId, steps, totalTokens, toolCalls,           │
│      latencyMs, modelId, cost }                                  │
│  • Apply content safety post-filter on final response            │
│  • Return response to client                                    │
└──────────────────────────────────────────────────────────────────┘
```

**Execution isolation:**
| Concern | Mechanism |
|---------|-----------|
| Compute isolation | Each agent execution runs in a resource-bounded container/process with CPU and memory limits |
| Timeout enforcement | Hard timeout per execution (configurable, default 120s); kills execution if exceeded |
| Token budget | Max tokens per turn enforced; prevents runaway generation costs |
| Step limit | Max tool call iterations enforced; prevents infinite loops |
| Concurrent executions | Per-project concurrency limit; queued beyond limit with backpressure |

#### 5.3.2 Workflow Execution Engine

**Responsibility:** Orchestrate multi-agent and multi-step workflows — sequential chains, parallel fan-out, conditional branching, and human-in-the-loop gates.

**Workflow execution model:**

```
┌──────────────────────────── WORKFLOW ENGINE ─────────────────────────────┐
│                                                                          │
│  Workflow Definition (DAG of steps):                                     │
│                                                                          │
│    ┌─────────┐     ┌─────────┐                                           │
│    │ Step 1: │────►│ Step 2: │──┐                                        │
│    │ Agent A │     │ Agent B │  │   ┌─────────┐     ┌──────────┐         │
│    └─────────┘     └─────────┘  ├──►│ Step 4: │────►│ Step 5:  │         │
│                    ┌─────────┐  │   │ Merge   │     │ Agent E  │         │
│                    │ Step 3: │──┘   └─────────┘     └──────────┘         │
│                    │ Agent C │                                            │
│                    │ (fanout)│                                            │
│                    └─────────┘                                            │
│                                                                          │
│  Step Types:                                                             │
│  ┌──────────────┬────────────────────────────────────────────────────┐   │
│  │ agent_call   │ Invoke an agent with input, capture output         │   │
│  │ parallel     │ Fan-out to N agents, wait for all (or first)       │   │
│  │ conditional  │ Branch based on prior step output (if/else)        │   │
│  │ transform    │ Data transformation between steps (jq/jsonpath)    │   │
│  │ human_gate   │ Pause workflow, notify human, wait for approval    │   │
│  │ delay        │ Wait for a specified duration                      │   │
│  │ webhook      │ Call external HTTP endpoint, capture response      │   │
│  └──────────────┴────────────────────────────────────────────────────┘   │
│                                                                          │
│  State Machine:                                                          │
│    pending → running → [step_executing → step_complete]* →               │
│    completed | failed | cancelled | waiting_human                        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

**Workflow durability:**
- Workflow state persisted after each step completion (crash recovery)
- Each step execution is idempotent (safe to retry on failure)
- Failed steps retry with exponential backoff (configurable max retries)
- Dead letter queue for workflows that exceed max retries
- Workflow execution timeout (sum of all step timeouts + buffer)

#### 5.3.3 Sub-Agent Orchestrator

**Responsibility:** Enable agents to spawn and manage other agents as part of their execution.

**Orchestration patterns:**
| Pattern | Description | Example |
|---------|-------------|---------|
| **Delegation** | Agent A invokes Agent B for a specific subtask, waits for result | Research agent delegates fact-checking to a verification agent |
| **Parallel fan-out** | Agent A spawns N agents simultaneously, aggregates results | Analysis agent fans out to 3 domain-specific agents, synthesizes findings |
| **Pipeline** | Output of Agent A feeds as input to Agent B sequentially | Drafting agent → Review agent → Formatting agent |
| **Supervisor** | Meta-agent monitors sub-agent outputs, provides corrections, re-invokes | Quality assurance agent reviewing and iterating on sub-agent work |

**Sub-agent constraints:**
```
Sub-agent invocation rules:
  • Max depth: 3 levels (agent → sub-agent → sub-sub-agent)
  • Max fanout: 10 concurrent sub-agents per parent
  • Token budget: inherited from parent, shared across all sub-agents
  • Timeout: sub-agent timeout ≤ remaining parent timeout
  • Permissions: sub-agent can only access tools/data sources
    explicitly allowed in parent's executionPolicy.allowedSubAgents
  • Cost attribution: all sub-agent costs roll up to parent project
```

#### 5.3.4 Tool Execution Sandbox

**Responsibility:** Execute tool invocations in isolated, resource-constrained environments.

**Sandbox architecture:**
```
Agent requests tool execution
    │
    ▼
┌─── Authorization ──────────────────────────────────────────────┐
│  • Verify tool is bound to this agent                          │
│  • Verify tool permissions in policy engine                    │
│  • Verify input parameters match tool's input schema           │
│  • Rate limit check (per-tool, per-agent)                      │
└──────────────────────────────────────────────┬─────────────────┘
                                               │
    ▼
┌─── Sandbox Setup ──────────────────────────────────────────────┐
│  • Allocate container/process with resource limits:             │
│    - CPU: tool.sandboxRequirements.maxCpuMillis                │
│    - Memory: tool.sandboxRequirements.maxMemoryMB              │
│    - Network: tool.sandboxRequirements.networkAccess            │
│    - Timeout: tool.timeout (hard kill)                         │
│  • Inject credentials (from secret store, scoped to tool)      │
│  • Mount input data (read-only)                                │
└──────────────────────────────────────────────┬─────────────────┘
                                               │
    ▼
┌─── Execution ──────────────────────────────────────────────────┐
│  • API Tool: execute HTTP call with configured auth             │
│  • Function Tool: run in sandboxed runtime (e.g., Deno/Wasm)   │
│  • Data Tool: execute query against connected data source       │
│  • System Tool: invoke platform API with service identity       │
│                                                                 │
│  • Capture: stdout, stderr, return value, execution time        │
│  • On timeout: kill process, return timeout error               │
│  • On crash: return execution error with sanitized stack trace  │
└──────────────────────────────────────────────┬─────────────────┘
                                               │
    ▼
┌─── Result Processing ─────────────────────────────────────────┐
│  • Validate output against tool's output schema                │
│  • Sanitize output (remove credentials, internal details)      │
│  • Truncate if output exceeds max size (configurable)          │
│  • Emit tool execution telemetry                               │
│  • Return result to agent execution runtime                    │
└────────────────────────────────────────────────────────────────┘
```

#### 5.3.5 Memory Management Engine

**Responsibility:** Manage agent memory across conversation turns, sessions, and agent lifetimes.

**Memory architecture:**

```
┌──────────────────── MEMORY MANAGEMENT ENGINE ──────────────────────────┐
│                                                                        │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                   MEMORY TIERS                                 │    │
│  │                                                                │    │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐│    │
│  │  │  WORKING MEMORY │  │  SHORT-TERM     │  │  LONG-TERM     ││    │
│  │  │  (Turn Context) │  │  MEMORY         │  │  MEMORY        ││    │
│  │  │                 │  │  (Session)       │  │  (Persistent)  ││    │
│  │  │  • Current msg  │  │  • Conversation  │  │  • Key facts   ││    │
│  │  │  • Tool results │  │    thread        │  │  • User prefs  ││    │
│  │  │  • RAG context  │  │  • Session vars  │  │  • Learned     ││    │
│  │  │                 │  │  • Recent facts   │  │    patterns    ││    │
│  │  │  Stored: None   │  │                  │  │  • Entity      ││    │
│  │  │  (ephemeral)    │  │  Stored: Cache   │  │    knowledge   ││    │
│  │  │                 │  │  TTL: session     │  │                ││    │
│  │  │                 │  │  duration         │  │  Stored:       ││    │
│  │  │                 │  │                  │  │  Document DB + ││    │
│  │  │                 │  │                  │  │  Vector Index  ││    │
│  │  │                 │  │                  │  │  TTL: retention ││    │
│  │  │                 │  │                  │  │  policy         ││    │
│  │  └─────────────────┘  └─────────────────┘  └────────────────┘│    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                   MEMORY OPERATIONS                            │    │
│  │                                                                │    │
│  │  RECALL: Retrieve relevant memory for current context          │    │
│  │    1. Embed current query/context                              │    │
│  │    2. Vector search long-term memory (semantic similarity)     │    │
│  │    3. Retrieve recent short-term entries (recency)             │    │
│  │    4. Rank and select within token budget                      │    │
│  │    5. Inject into prompt as memory context section             │    │
│  │                                                                │    │
│  │  STORE: Persist important information from current turn        │    │
│  │    1. Extract key facts from conversation (LLM-based)          │    │
│  │    2. Classify: short-term (session) vs long-term (persistent) │    │
│  │    3. Embed facts for future vector retrieval                  │    │
│  │    4. Write to appropriate store                               │    │
│  │    5. Apply retention policy (TTL, max entries)                 │    │
│  │                                                                │    │
│  │  FORGET: Remove outdated or contradicted information           │    │
│  │    1. Detect contradictions with new information               │    │
│  │    2. Mark superseded memories as inactive                     │    │
│  │    3. Periodic garbage collection of expired entries           │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                        │
│  Memory isolation: Each agent's memory is scoped by                    │
│  (projectId, agentId, [threadId]). No cross-agent memory access        │
│  unless explicitly shared via data source connection.                   │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

**Token budget management for memory:**
```
Total model context window: N tokens

Allocation:
  System prompt:       fixed    (from agent definition)
  Memory context:      dynamic  (up to 30% of remaining budget)
  RAG context:         dynamic  (up to 30% of remaining budget)
  Conversation thread: dynamic  (up to 40% of remaining budget, LIFO truncation)
  User message:        fixed    (current turn)
  Reserved for output: fixed    (max_tokens parameter)

When context approaches limit:
  1. First: summarize older conversation turns (compress thread)
  2. Then: reduce RAG context (top-K retrieval with lower K)
  3. Then: reduce memory context (highest-relevance entries only)
  4. Never: truncate system prompt or current user message
```

#### 5.3.6 Thread & State Manager

**Responsibility:** Manage persistent conversation threads and execution state across sessions.

**Thread model:**
```
Thread {
  id: UUID
  projectId: UUID
  agentId: UUID
  userId: UUID
  messages: [{
    role: system | user | assistant | tool
    content: string
    toolCalls: [{ toolId, input, output }]
    tokenCount: integer
    timestamp: timestamp
  }]
  metadata: {
    title: string (auto-generated from first message)
    tags: [string]
    status: active | archived | deleted
    totalTokens: integer
    totalCost: decimal
    messageCount: integer
  }
  createdAt: timestamp
  lastMessageAt: timestamp
}
```

**Thread operations:**
| Operation | Description |
|-----------|-------------|
| Create thread | New conversation with an agent; generates thread ID |
| Continue thread | Resume existing conversation; loads full message history |
| Fork thread | Create a branch from a specific message (for experimentation) |
| Summarize thread | Compress older messages into a summary to save context window |
| Archive thread | Mark as read-only; retain for audit but exclude from active queries |
| Export thread | Download conversation as JSON/Markdown for external use |

### 5.4 RAG Pipeline

**Responsibility:** Retrieval-Augmented Generation — connect agent responses to grounded, up-to-date knowledge from configured data sources.

#### 5.4.1 RAG Architecture Overview

```
┌──────────────────────────── RAG PIPELINE ────────────────────────────┐
│                                                                      │
│  ┌────────────────────── INDEXING PIPELINE (offline) ──────────────┐ │
│  │                                                                  │ │
│  │  Data Source → Document Loader → Chunker → Embedder → Index     │ │
│  │                                                                  │ │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────┐  ┌────────────┐  │ │
│  │  │  Document  │  │  Chunking  │  │ Embedding│  │  Vector    │  │ │
│  │  │  Loader    │  │  Engine    │  │ Service  │  │  Index     │  │ │
│  │  │            │  │            │  │          │  │  Writer    │  │ │
│  │  │ • PDF      │  │ • Fixed    │  │ • Model  │  │            │  │ │
│  │  │ • HTML     │  │   size     │  │   based  │  │ • Upsert   │  │ │
│  │  │ • Markdown │  │ • Semantic │  │ • Batch  │  │ • Metadata │  │ │
│  │  │ • Office   │  │ • Sliding  │  │   proc.  │  │ • Tenant   │  │ │
│  │  │ • JSON     │  │   window   │  │          │  │   scoped   │  │ │
│  │  │ • Database │  │ • Parent-  │  │          │  │            │  │ │
│  │  │   rows     │  │   child    │  │          │  │            │  │ │
│  │  └─────┬──────┘  └─────┬──────┘  └────┬─────┘  └─────┬──────┘  │ │
│  │        │               │              │               │          │ │
│  └────────┴───────────────┴──────────────┴───────────────┴──────────┘ │
│                                                                      │
│  ┌────────────────────── RETRIEVAL PIPELINE (online) ──────────────┐ │
│  │                                                                  │ │
│  │  Query → Rewrite → Embed → Search → Rerank → Format → Inject   │ │
│  │                                                                  │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │ │
│  │  │  Query   │ │  Vector  │ │  Re-     │ │  Context │            │ │
│  │  │ Rewriter │ │  Search  │ │  Ranker  │ │ Formatter│            │ │
│  │  │          │ │  + BM25  │ │          │ │          │            │ │
│  │  │ • HyDE   │ │          │ │ • Cross- │ │ • Source │            │ │
│  │  │ • Multi- │ │ • Hybrid │ │   encoder│ │   attrib │            │ │
│  │  │   query  │ │ • Filter │ │ • Score  │ │ • Token  │            │ │
│  │  │ • Step-  │ │ • Top-K  │ │   cutoff │ │   budget │            │ │
│  │  │   back   │ │          │ │          │ │          │            │ │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘            │ │
│  │       │            │            │            │                    │ │
│  └───────┴────────────┴────────────┴────────────┴────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

#### 5.4.2 Indexing Pipeline (Offline)

The indexing pipeline processes data sources into searchable vector indexes.

**Document processing stages:**

| Stage | Operation | Configuration |
|-------|-----------|---------------|
| **Load** | Extract text content from source documents | Format-specific loaders (PDF, HTML, Office, Markdown, JSON, database rows) |
| **Clean** | Remove boilerplate, normalize whitespace, extract metadata | Configurable per source type; preserve structural information (headers, tables) |
| **Chunk** | Split documents into retrieval-sized segments | Strategy: fixed-size (default 512 tokens), semantic (split on topic boundaries), sliding window (with 20% overlap), parent-child (hierarchical) |
| **Embed** | Generate vector representations using embedding model | Configurable embedding model per data source; batch processing for efficiency |
| **Index** | Store vectors + metadata in vector database | Tenant-scoped index; metadata includes: sourceId, chunkIndex, documentPath, timestamp |

**Chunking strategies:**
```
┌── Fixed-Size Chunking ──────────────────────────────────────────┐
│  Document → [chunk₁(512 tokens)] [chunk₂(512 tokens)] ...      │
│  Overlap: configurable (default 64 tokens)                      │
│  Pro: Predictable, simple                                       │
│  Con: May split semantic units                                  │
└─────────────────────────────────────────────────────────────────┘

┌── Semantic Chunking ────────────────────────────────────────────┐
│  Document → split on paragraph/section boundaries               │
│  Merge small chunks, split large ones                           │
│  Pro: Preserves meaning                                         │
│  Con: Variable chunk sizes, more complex                        │
└─────────────────────────────────────────────────────────────────┘

┌── Parent-Child Chunking ────────────────────────────────────────┐
│  Document → parent chunks (2048 tokens)                         │
│              └── child chunks (256 tokens each)                 │
│  Search on child chunks, return parent chunk as context          │
│  Pro: Precise retrieval with broad context                      │
│  Con: Higher storage, more complex retrieval logic              │
└─────────────────────────────────────────────────────────────────┘
```

**Incremental indexing:**
- Change detection via document checksums and timestamps
- Only re-embed modified/new chunks (not entire corpus)
- Tombstone deleted documents (mark inactive, garbage collect periodically)
- Index versioning for safe rollback if embedding model changes

#### 5.4.3 Retrieval Pipeline (Online)

The retrieval pipeline runs during agent execution to fetch relevant context for the current query.

**Retrieval stages:**

| Stage | Operation | Latency Budget |
|-------|-----------|----------------|
| **Query rewrite** | Transform user query for better retrieval: HyDE (hypothetical document embedding), multi-query expansion, step-back abstraction | < 500ms (if LLM-based) or < 5ms (template-based) |
| **Hybrid search** | Combine vector similarity (semantic) with keyword matching (BM25) for comprehensive recall | < 100ms |
| **Metadata filter** | Apply pre-search filters: data source scope, date range, document type, tenant isolation | < 1ms (filter integrated into search query) |
| **Re-ranking** | Cross-encoder re-ranking of top-K candidates for precision | < 200ms (for K ≤ 50) |
| **Score threshold** | Remove results below minimum relevance score (configurable per agent) | < 1ms |
| **Context formatting** | Format retrieved chunks with source attribution, truncate to token budget | < 5ms |

**Hybrid search scoring:**
```
final_score = α × vector_similarity_score + (1 - α) × bm25_score

Where:
  α = 0.7 (default, configurable per data source)
  vector_similarity_score: cosine similarity between query embedding and chunk embedding
  bm25_score: normalized BM25 relevance score

Ranking: sort by final_score descending, take top-K (default K=10)
```

**RAG quality signals (tracked per retrieval):**
| Signal | Measurement | Purpose |
|--------|-------------|---------|
| Retrieval latency | End-to-end retrieval time | Performance monitoring |
| Result count | Number of chunks returned vs requested | Coverage monitoring |
| Score distribution | Mean/min/max relevance scores | Quality monitoring |
| Source diversity | Number of unique source documents in results | Breadth monitoring |
| Context utilization | Tokens used for RAG vs total context budget | Efficiency monitoring |

**Tenant isolation in RAG:**
- Each project's data source produces its own isolated partition in the vector index
- Search queries are always scoped by `(projectId, dataSourceId)` — enforced at the index layer, not application layer
- No cross-project retrieval is possible without explicit data source sharing configuration in the Control Plane

---

## 6. Cross-Cutting Concerns

### 6.1 Security Architecture

#### 6.1.1 Security Boundaries

```
┌──────────────────────────── SECURITY BOUNDARY MAP ──────────────────────────┐
│                                                                              │
│  BOUNDARY 1: PERIMETER                                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  • Global load balancer with DDoS protection                        │    │
│  │  • Web Application Firewall (WAF) — OWASP top-10 rules             │    │
│  │  • TLS 1.3 termination at edge                                      │    │
│  │  • Geographic access restrictions (if compliance requires)          │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  BOUNDARY 2: API GATEWAY                                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  • Authentication: bearer token validation (identity provider)      │    │
│  │  • Authorization: project membership + role check                   │    │
│  │  • Rate limiting: per-project, per-user, per-IP                     │    │
│  │  • Request validation: size limits, content type, schema validation │    │
│  │  • No credentials forwarded — gateway authenticates to backends     │    │
│  │    using service identities                                         │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  BOUNDARY 3: SERVICE MESH                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  • Mutual TLS (mTLS) between all services                          │    │
│  │  • Service-to-service authentication via workload identities        │    │
│  │  • Network policies: services can only reach their dependencies     │    │
│  │  • No service can access another service's data store directly      │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  BOUNDARY 4: DATA LAYER                                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  • All data stores accessible only via private network endpoints    │    │
│  │  • No public internet access to any data store                      │    │
│  │  • Encryption at rest (platform-managed keys, per-tenant BYOK opt.) │    │
│  │  • Encryption in transit (TLS for all connections)                  │    │
│  │  • Partition-level tenant isolation (document DB partition keys)    │    │
│  │  • Row-level security (relational database)                        │    │
│  │  • Tenant-scoped partitions (vector index)                         │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  BOUNDARY 5: RUNTIME ISOLATION                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  • Tool execution in sandboxed containers with resource limits      │    │
│  │  • Agent execution with CPU/memory/timeout constraints              │    │
│  │  • Sub-agent permissions gated by parent policy                     │    │
│  │  • No direct network access from sandbox unless explicitly allowed  │    │
│  │  • Credentials injected per-invocation, never persisted in sandbox  │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### 6.1.2 Identity & Access Control

**Authentication flow:**
```
User → Identity Provider (SSO) → Token with claims:
  {
    sub: "user-uuid",
    email: "user@org.com",
    projectMemberships: [
      { projectId: "proj-001", role: "owner" },
      { projectId: "proj-002", role: "reader" }
    ],
    tenantId: "tenant-001"
  }
```

**RBAC model:**
| Role | Project | Deployment | Agent | Data |
|------|---------|------------|-------|------|
| **Owner** | Full CRUD + member management | Create/delete/modify | Create/delete/modify | Upload/delete |
| **Contributor** | Read + modify settings | Create/modify | Create/modify | Upload |
| **Reader** | Read only | View, invoke | Invoke only | Read only |

**Service-to-service authentication:**
- Each microservice has a workload identity (managed, no stored credentials)
- Service identities are granted only the data store access they need
- No service has admin access to another service's resources
- Credential rotation is automatic and transparent

#### 6.1.3 Data Protection

| Protection Layer | Mechanism |
|------------------|-----------|
| Encryption at rest | Platform-managed keys for all data stores; option for customer-managed keys for premium tenants |
| Encryption in transit | TLS 1.3 for all connections (external and internal); mTLS between services |
| Secret management | All credentials stored in secret store; accessed via workload identity; auto-rotation |
| PII handling | Content safety pipeline detects PII; configurable per-project redaction |
| Data residency | Deployment region restrictions enforced by policy engine; data does not leave configured regions |
| Audit trail | All data access logged (who, what, when, from where); immutable audit log |

### 6.2 Multi-Tenant Isolation Model

**Isolation is enforced at every layer, not trusted to application code alone:**

```
┌──────────────────────── ISOLATION ENFORCEMENT LAYERS ──────────────────────┐
│                                                                             │
│  Layer 1: NETWORK                                                           │
│  ├── All data stores on private network only (no public endpoints)         │
│  ├── Network policies restrict service-to-service communication            │
│  └── Egress controlled through firewall (deny by default)                  │
│                                                                             │
│  Layer 2: API GATEWAY                                                       │
│  ├── Per-project API subscriptions with independent rate limits            │
│  ├── Project context extracted and validated on every request               │
│  └── Cross-project access impossible without valid project membership      │
│                                                                             │
│  Layer 3: APPLICATION                                                       │
│  ├── All queries include project scope (enforced by base repository class) │
│  ├── Service-level authorization checks before data access                 │
│  └── Middleware injects tenant context from authenticated token            │
│                                                                             │
│  Layer 4: DATA                                                              │
│  ├── Document DB: hierarchical partition keys (/tenantId/projectId/...)    │
│  │   → Queries physically cannot cross partition boundaries                │
│  ├── Relational DB: row-level security policies                            │
│  │   → Database engine filters rows; application cannot bypass             │
│  ├── Vector DB: tenant-scoped index partitions                             │
│  │   → Search results limited to tenant's partition                        │
│  ├── Object storage: project-scoped paths with scoped access tokens        │
│  └── Cache: key prefix by project ID; TTL-based eviction                   │
│                                                                             │
│  Layer 5: RUNTIME                                                           │
│  ├── Agent memory scoped by (projectId, agentId)                           │
│  ├── Tool credentials scoped to project                                    │
│  └── Execution containers have no access to other tenants' resources       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Noisy neighbor mitigation:**
| Resource | Mitigation |
|----------|------------|
| Model inference | Per-project rate limiting at gateway; per-project token quotas |
| Database throughput | Per-partition throughput limits; hierarchical partition keys distribute load |
| Compute | Per-project concurrency limits; priority queuing for premium tenants |
| Storage | Per-project storage quotas with hard limits |

### 6.3 Observability Architecture

#### 6.3.1 Three Pillars

```
┌─────────────────────── OBSERVABILITY ARCHITECTURE ───────────────────────┐
│                                                                           │
│  ┌─────────────┐         ┌──────────────┐         ┌──────────────────┐   │
│  │   METRICS   │         │    LOGS      │         │    TRACES        │   │
│  │             │         │              │         │                  │   │
│  │ • Counters  │         │ • Structured │         │ • Distributed    │   │
│  │ • Gauges    │         │   JSON       │         │   request tracing│   │
│  │ • Histograms│         │ • Severity   │         │ • Span-based     │   │
│  │             │         │   levels     │         │   propagation    │   │
│  │ Sources:    │         │              │         │                  │   │
│  │ • Request   │         │ Sources:     │         │ Context:         │   │
│  │   rates     │         │ • Application│         │ • requestId      │   │
│  │ • Token     │         │ • Gateway    │         │ • projectId      │   │
│  │   counts    │         │ • Data store │         │ • agentId        │   │
│  │ • Latency   │         │ • Runtime    │         │ • userId         │   │
│  │   (p50/99)  │         │ • Security   │         │ • modelId        │   │
│  │ • Error     │         │   events     │         │ • deploymentId   │   │
│  │   rates     │         │              │         │                  │   │
│  │ • TTFT      │         │ Retention:   │         │ Sampling:        │   │
│  │ • GPU util  │         │ 90 days      │         │ 100% for errors  │   │
│  │ • Cache hit │         │ (configurable│         │ 10% for success  │   │
│  │   ratio     │         │  per tier)   │         │ 100% for debug   │   │
│  └──────┬──────┘         └──────┬───────┘         └──────┬───────────┘   │
│         │                       │                        │                │
│         └───────────────────────┴────────────────────────┘                │
│                                 │                                         │
│                    ┌────────────┴────────────┐                            │
│                    │   UNIFIED TELEMETRY     │                            │
│                    │      COLLECTOR          │                            │
│                    │                         │                            │
│                    │  • OpenTelemetry SDK    │                            │
│                    │  • Correlation by       │                            │
│                    │    requestId across     │                            │
│                    │    all pillars          │                            │
│                    │  • Project-scoped       │                            │
│                    │    custom dimensions    │                            │
│                    └────────────┬────────────┘                            │
│                                │                                         │
│              ┌─────────────────┼─────────────────┐                       │
│              │                 │                  │                       │
│         ┌────┴─────┐    ┌──────┴──────┐    ┌─────┴──────┐                │
│         │Dashboards│    │  Alerting   │    │  Query     │                │
│         │          │    │  Engine     │    │  Engine    │                │
│         │• Platform│    │             │    │            │                │
│         │  health  │    │ • Error rate│    │ • Ad-hoc   │                │
│         │• Per-    │    │   spikes    │    │   queries  │                │
│         │  project │    │ • Latency   │    │ • Forensic │                │
│         │  usage   │    │   anomalies │    │   analysis │                │
│         │• Model   │    │ • Budget    │    │ • Cost     │                │
│         │  perf    │    │   thresholds│    │   reports  │                │
│         │• Cost    │    │ • Health    │    │            │                │
│         │  trends  │    │   degraded  │    │            │                │
│         └──────────┘    └─────────────┘    └────────────┘                │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

#### 6.3.2 AI-Specific Telemetry

Standard observability is necessary but not sufficient for an AI platform. Additional AI-specific signals:

| Signal | Description | Collection Point |
|--------|-------------|------------------|
| **Time-to-first-token (TTFT)** | Latency from request to first streamed token | Inference gateway |
| **Inter-token latency** | Time between consecutive tokens during streaming | Inference gateway |
| **Token throughput** | Tokens per second per model endpoint | Inference gateway |
| **Model error rate** | Non-HTTP errors (hallucination detection, safety violations) per model | Content safety pipeline |
| **RAG retrieval quality** | Relevance scores of retrieved chunks; empty result rate | RAG pipeline |
| **Agent step count** | Number of LLM calls + tool calls per agent execution | Agent execution runtime |
| **Memory hit rate** | Percentage of agent turns that successfully retrieved relevant memory | Memory management engine |
| **Cost per request** | Token cost + compute cost per inference request | Metering pipeline |
| **Context window utilization** | Percentage of model context window used per request | Agent execution runtime |
| **Tool execution latency** | Per-tool execution time; timeout rate | Tool execution sandbox |

#### 6.3.3 Alerting Rules

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| Model endpoint unhealthy | Health check fails 3 consecutive times | Critical | Circuit breaker opens; failover to backup |
| Error rate spike | 5xx rate > 5% over 5-minute window | High | Page on-call; investigate model backend |
| TTFT degradation | P95 TTFT > 2x baseline for 10 minutes | High | Investigate model capacity/routing |
| Budget threshold | Project spend > 80% of monthly budget | Medium | Notify project owner |
| Budget exceeded | Project spend > 100% of budget (hard limit) | High | Block new requests for project |
| Quota exhaustion | Model deployment quota > 90% for project | Medium | Notify project owner |
| Data store latency | P99 latency > 500ms for 5 minutes | High | Investigate partition hot spots |
| Security event | Unauthorized access attempt from new IP | High | Log + alert security team |
| RAG index stale | Data source sync last succeeded > 24h ago | Medium | Retry sync; notify data owner |

### 6.4 Fault Tolerance & Resilience

#### 6.4.1 Failure Modes and Recovery

```
┌──────────────────── FAULT TOLERANCE PATTERNS ──────────────────────────┐
│                                                                        │
│  ┌─── CIRCUIT BREAKER ────────────────────────────────────────────┐   │
│  │                                                                │   │
│  │  Applied to: model endpoints, external APIs, data stores       │   │
│  │                                                                │   │
│  │  CLOSED ──(failures > threshold)──► OPEN                       │   │
│  │    │                                  │                        │   │
│  │    │                            (timeout expires)              │   │
│  │    │                                  │                        │   │
│  │    │                                  ▼                        │   │
│  │    ◄────(probe succeeds)──── HALF-OPEN                         │   │
│  │                                  │                              │   │
│  │                           (probe fails)                        │   │
│  │                                  │                              │   │
│  │                                  ▼                              │   │
│  │                                OPEN                             │   │
│  │                                                                │   │
│  │  Config: 5 failures / 60s → open 30s → half-open (1 probe)    │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌─── RETRY WITH BACKOFF ─────────────────────────────────────────┐   │
│  │                                                                │   │
│  │  Applied to: transient failures (429, 503, timeouts)           │   │
│  │  Strategy: exponential backoff with jitter                     │   │
│  │  Max retries: 3 (configurable)                                 │   │
│  │  Base delay: 1s, Max delay: 30s                                │   │
│  │  Jitter: ±25% (prevents thundering herd)                      │   │
│  │                                                                │   │
│  │  NOT retried: 400 (bad request), 401 (auth), 403 (forbidden)  │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌─── BULKHEAD (RESOURCE ISOLATION) ─────────────────────────────┐   │
│  │                                                                │   │
│  │  Applied to: per-project execution pools                       │   │
│  │  Each project gets isolated:                                   │   │
│  │    • Connection pools to data stores                           │   │
│  │    • Thread pools for request processing                      │   │
│  │    • Queue capacity for async operations                      │   │
│  │  Effect: one project's overload cannot exhaust shared pools    │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌─── DEAD LETTER QUEUE ─────────────────────────────────────────┐   │
│  │                                                                │   │
│  │  Applied to: async message processing failures                 │   │
│  │  After max retries exhausted:                                  │   │
│  │    • Message moved to dead letter queue                        │   │
│  │    • Alert emitted with failure context                        │   │
│  │    • Dashboard shows DLQ depth for investigation               │   │
│  │    • Manual or automated replay after root cause resolved      │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌─── GRACEFUL DEGRADATION ──────────────────────────────────────┐   │
│  │                                                                │   │
│  │  When a non-critical system fails:                             │   │
│  │    • Content safety down → log warning, allow pass-through    │   │
│  │      with enhanced monitoring (never silently skip safety)     │   │
│  │    • Cost tracking down → continue serving, emit to DLQ       │   │
│  │    • Memory service down → agent works without memory context  │   │
│  │    • RAG index unavailable → respond without retrieval context │   │
│  │    • Marketplace down → catalog browse returns cached results  │   │
│  │                                                                │   │
│  │  When a critical system fails:                                 │   │
│  │    • Model endpoint down → circuit breaker → failover backend  │   │
│  │    • If all backends down → 503 with estimated recovery time   │   │
│  │    • Auth system down → reject all requests (fail closed)      │   │
│  │    • Data store down → reject writes, serve reads from cache   │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

#### 6.4.2 Data Durability

| Data Type | Durability Strategy |
|-----------|---------------------|
| Agent definitions | Document DB with point-in-time recovery; version history immutable |
| Conversation threads | Document DB; optionally replicated to secondary region |
| Billing records | Relational DB with automated backups; transaction log for replay |
| Vector indexes | Rebuildable from source documents; checkpoint-based backup |
| Object storage artifacts | Geo-redundant storage; soft delete with 30-day recovery |
| Audit logs | Append-only store; immutable retention per compliance policy |

### 6.5 Scalability Architecture

#### 6.5.1 Scaling Dimensions

```
┌──────────────────── SCALING MODEL ────────────────────────────────────┐
│                                                                       │
│  TIER 1: 0 – 1,000 users                                             │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │  • Container orchestration: minimal node count (3 system, 2  │    │
│  │    user nodes)                                                │    │
│  │  • API gateway: single unit                                   │    │
│  │  • Document DB: serverless (auto-scale RU/s)                  │    │
│  │  • Model endpoints: shared managed endpoints                  │    │
│  │  • Cache: single instance                                     │    │
│  │  • Async processing: single consumer per queue                │    │
│  │  • Services: minimal replicas (2 per service for HA)          │    │
│  └───────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  TIER 2: 1,000 – 50,000 users                                        │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │  • Container orchestration: dedicated node pools (system,     │    │
│  │    user, GPU); horizontal pod autoscaler on all services      │    │
│  │  • API gateway: 2-4 units, rate limiting enforced             │    │
│  │  • Document DB: provisioned throughput, partition-aware        │    │
│  │    query optimization                                         │    │
│  │  • Model endpoints: per-region dedicated endpoints +          │    │
│  │    spillover to shared                                        │    │
│  │  • Cache: clustered with replication                          │    │
│  │  • Async processing: partitioned consumers, competing workers │    │
│  │  • Services: 3-10 replicas with pod disruption budgets        │    │
│  └───────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  TIER 3: 50,000+ users                                                │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │  • Multi-region active-active deployment                      │    │
│  │  • Global load balancer routing to nearest region             │    │
│  │  • Document DB: multi-region write with conflict resolution   │    │
│  │  • API gateway: per-region instances (12+ units total)        │    │
│  │  • Model endpoints: multi-region with intelligent routing     │    │
│  │    (latency, cost, capacity)                                  │    │
│  │  • Dedicated container clusters for GPU-intensive workloads   │    │
│  │  • Event streaming with partitioned consumers per region      │    │
│  │  • Relational DB: hyperscale tier with read replicas          │    │
│  │  • Independent vector indexes per region                      │    │
│  └───────────────────────────────────────────────────────────────┘    │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

#### 6.5.2 Autoscaling Signals

| Component | Scale Signal | Response |
|-----------|-------------|----------|
| Application services | CPU > 70% or request queue depth > 100 | Add pod replicas (HPA) |
| Model serving pods | GPU utilization > 80% or inference queue > 50 | Add GPU nodes (cluster autoscaler) |
| API gateway | Request rate approaching unit capacity | Add gateway units |
| Document DB | RU consumption > 80% of provisioned | Increase provisioned throughput (auto-scale) |
| Message consumers | Queue depth growing for > 5 minutes | Add consumer instances |
| Cache | Memory > 85% or eviction rate > 10% | Scale to larger tier or add shards |

### 6.6 Governance & Compliance

#### 6.6.1 Responsible AI Controls

```
┌──────────────────── RESPONSIBLE AI PIPELINE ──────────────────────────┐
│                                                                       │
│  Every inference request flows through safety controls:               │
│                                                                       │
│  INPUT STAGE:                                                         │
│  ├── Content classifier: hate, sexual, violence, self-harm            │
│  ├── PII detector: email, phone, SSN, credit card, custom patterns    │
│  ├── Prompt injection detector: system prompt extraction attempts     │
│  └── Policy check: project-specific blocked topics/keywords           │
│                                                                       │
│  OUTPUT STAGE:                                                        │
│  ├── Content classifier: same categories as input                     │
│  ├── PII detector: prevent model from generating PII                  │
│  ├── Grounding check: verify claims against RAG sources (optional)    │
│  └── Compliance filter: industry-specific output restrictions          │
│                                                                       │
│  Each stage produces:                                                  │
│  ├── Decision: allow | block | redact | warn                          │
│  ├── Category and severity score                                      │
│  └── Audit log entry (immutable)                                      │
│                                                                       │
│  Configuration:                                                        │
│  ├── Global defaults (platform-wide minimums, cannot be disabled)     │
│  ├── Per-project overrides (can be stricter, not looser)              │
│  └── Per-agent overrides (within project bounds)                      │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

#### 6.6.2 Audit & Compliance

| Requirement | Implementation |
|-------------|----------------|
| Audit trail | All data access, configuration changes, and inference requests logged with actor, timestamp, and affected resource |
| Immutable logs | Audit records written to append-only storage; no modification or deletion |
| Data retention | Configurable per-project and per-data-type; automatic purge after retention period |
| Access reviews | API to export who has access to what; supports periodic access review workflows |
| Data sovereignty | Deployment region restrictions enforced by policy engine; data does not leave configured region |
| Model governance | Model usage tracked — which models are deployed, who uses them, for what purpose |
| Cost governance | Budget controls with soft and hard limits; spending visibility at project, team, and org level |

#### 6.6.3 Compliance Controls Matrix

| Control Area | Mechanism | Evidence |
|-------------|-----------|----------|
| **Access control** | RBAC per project, MFA via identity provider, API key rotation | Access logs, role assignments |
| **Encryption** | TLS 1.3 in transit, platform-managed keys at rest | Certificate inventory, encryption config |
| **Logging** | Structured logs for all operations, 90-day retention minimum | Log analytics dashboards |
| **Incident response** | Automated alerting, documented runbooks, on-call rotation | Alert history, runbook repository |
| **Change management** | IaC for all infrastructure, CI/CD with approval gates | Git history, deployment logs |
| **Vulnerability management** | Container image scanning, dependency scanning in CI | Scan reports, remediation timelines |

---

## 7. Data Flow Diagrams

### 7.1 End-to-End Agent Execution Flow

```
User sends message to agent
    │
    ▼
[1] API Gateway
    ├── Authenticate user (token validation) ────────────── ► Identity Provider
    ├── Extract projectId, validate membership
    ├── Rate limit check ────────────────────────────────── ► Cache (rate counter)
    ├── Route to Agent Execution Runtime
    │
    ▼
[2] Agent Execution Runtime
    ├── Load agent definition ──────────────────────────── ► Document DB
    ├── Load conversation thread ──────────────────────── ► Document DB
    ├── Retrieve relevant memory ──────────────────────── ► Vector DB + Document DB
    ├── Execute RAG retrieval (if data sources configured):
    │   ├── [3] RAG Pipeline
    │   │   ├── Rewrite query ─────────────────────────── ► (local)
    │   │   ├── Hybrid search ─────────────────────────── ► Vector DB (embeddings)
    │   │   │                                                + Search Index (BM25)
    │   │   ├── Re-rank results ───────────────────────── ► Re-ranker Model
    │   │   └── Format context (source attribution)
    │   │
    ├── Assemble prompt (system + memory + RAG + thread + user message)
    │
    ▼
[4] Inference Gateway
    ├── Content safety pre-filter ─────────────────────── ► Safety Classifier
    ├── Model routing (circuit breaker, health check)
    ├── Forward to model backend ──────────────────────── ► Model Endpoint
    ├── Stream tokens back (SSE)
    ├── Content safety post-filter (incremental)
    ├── Emit usage event (async) ──────────────────────── ► Event Bus ► Cost Service
    │
    ▼
[5] Agent Execution Runtime (continued)
    ├── Parse model response
    ├── IF tool calls detected:
    │   ├── [6] Tool Execution Sandbox
    │   │   ├── Validate tool binding + permissions ──── ► Policy Engine
    │   │   ├── Execute tool in sandbox ───────────────── ► External API / Function / DB
    │   │   └── Return result to agent
    │   └── Return to [4] with tool results (loop)
    │
    ├── ELSE (final response):
    │   ├── Update conversation thread ────────────────── ► Document DB
    │   ├── Update agent memory ───────────────────────── ► Vector DB + Document DB
    │   ├── Emit execution telemetry ──────────────────── ► Telemetry Collector
    │   └── Return response to client via SSE stream
    │
    ▼
[7] Async Event Consumers (non-blocking)
    ├── Cost Service: calculate cost, update project budget ► Relational DB
    ├── Monitoring Service: update dashboards, check alerts ► Metrics Store
    └── Notification Service: push updates via websocket ──► Client
```

### 7.2 Model Deployment Flow

```
User requests model deployment
    │
    ▼
[1] API Gateway → Deployment Lifecycle Service
    ├── Validate model exists ─────────────────────── ► Model Catalog Service
    ├── Check project quota ───────────────────────── ► Quota & Budget Service
    ├── Check deployment policy ───────────────────── ► Policy Engine
    ├── Reserve quota (decrement available slots)
    ├── Create deployment record (status: provisioning) ► Document DB
    ├── Emit DeploymentRequested ──────────────────── ► Message Queue
    ├── Return 202 Accepted + operation ID to client
    │
    ▼
[2] Deployment Worker (async consumer)
    ├── Determine target:
    │   ├── Managed endpoint → call provider management API
    │   ├── Self-hosted → create container deployment + service
    │   └── External → configure API connection
    │
    ├── Wait for endpoint healthy (poll with backoff)
    ├── Configure routing in API Gateway
    ├── Update deployment record (status: running) ── ► Document DB
    ├── Emit DeploymentReady ─────────────────────── ► Event Router
    │
    ▼
[3] Event Consumers
    ├── Cost Service: begin metering deployed endpoint
    ├── Monitoring Service: start health polling
    ├── Notification Service: push "deployment ready" to user
    └── Dashboard: update deployment status indicator
```

---

## 8. Technology-Neutral Component Mapping

This section maps the architecture to technology categories without naming specific products, allowing implementation teams to select appropriate solutions.

| Architectural Component | Technology Category | Selection Criteria |
|------------------------|--------------------|--------------------|
| Container orchestration | Managed Kubernetes | Auto-scaling, GPU node support, workload identity |
| API gateway | Managed API gateway | Rate limiting, policy engine, developer portal, streaming support |
| Identity provider | Enterprise SSO / OIDC provider | RBAC, group management, managed identities, MFA |
| Document database | Distributed NoSQL with partition keys | Hierarchical partition keys, change feed, global distribution |
| Relational database | Managed RDBMS with row-level security | Hyperscale support, automated backups, RLS |
| Vector database | Vector search index with hybrid (semantic + keyword) support | Tenant-scoped partitions, re-ranking, faceted filtering |
| Object storage | Blob/object storage with access scoping | Geo-redundancy, SAS/presigned URL support, lifecycle policies |
| Cache | Distributed in-memory cache | Clustering, persistence, pub/sub, TTL eviction |
| Message queue | Managed message broker | Dead letter queues, ordered delivery, at-least-once semantics |
| Event router | Event routing/pub-sub service | Topic-based subscription, filtering, webhook delivery |
| Secret management | Managed secret/key store | RBAC, auto-rotation, HSM-backed encryption |
| Observability | APM + metrics + log analytics platform | Distributed tracing, custom dimensions, alerting, KQL/query |
| IaC | Declarative infrastructure templating | Modular, environment-parameterized, idempotent deployment |
| CI/CD | Pipeline automation | OIDC federation, environment gates, parallel stages |
| Global load balancer | CDN/edge with WAF and DDoS protection | Geographic routing, TLS termination, OWASP ruleset |
| Network firewall | Managed firewall for egress control | FQDN-based rules, threat intelligence, logging |
| Container registry | Managed container image registry | Image scanning, geo-replication, retention policies |

---

## 9. Deployment Topology

```
┌──────────────────────── DEPLOYMENT TOPOLOGY ─────────────────────────────┐
│                                                                           │
│  ┌─── REGION A (Primary) ──────────────────────────────────────────────┐ │
│  │                                                                      │ │
│  │  ┌── Ingress ──────────────────────────────────────┐                 │ │
│  │  │  Global LB endpoint → WAF → API Gateway (2 units)│                │ │
│  │  └──────────┬──────────────────────────────────────┘                 │ │
│  │             │                                                        │ │
│  │  ┌──────────┴──── Container Cluster ──────────────────────────────┐  │ │
│  │  │                                                                │  │ │
│  │  │  ┌── System Pool ──┐  ┌── User Pool ───┐  ┌── GPU Pool ────┐  │  │ │
│  │  │  │  (3 nodes)      │  │  (2-10 nodes)  │  │  (0-N nodes)   │  │  │ │
│  │  │  │  CoreDNS,       │  │  All app       │  │  Model serving │  │  │ │
│  │  │  │  ingress ctrl,  │  │  services,     │  │  (on-demand)   │  │  │ │
│  │  │  │  monitoring     │  │  agent runtime │  │                │  │  │ │
│  │  │  └─────────────────┘  └────────────────┘  └────────────────┘  │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  │  ┌── Data Services (Private Endpoints) ──────────────────────────┐  │ │
│  │  │  Document DB │ Relational DB │ Vector Index │ Cache │ Secrets  │  │ │
│  │  └─────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  │  ┌── Messaging ──────────────────────────────────────────────────┐  │ │
│  │  │  Message Queue │ Event Router │ Stream Processor               │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  │  ┌── Managed Model Endpoints ────────────────────────────────────┐  │ │
│  │  │  Provider A deployments │ Provider B deployments               │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌─── REGION B (DR / Scale-Out) ───────────────────────────────────────┐ │
│  │  (Same topology as Region A, activated for Tier 3 scale)            │ │
│  │  • Document DB: multi-region write replica                          │ │
│  │  • Read replicas for relational DB                                  │ │
│  │  • Independent model endpoints (regional quotas)                    │ │
│  │  • Independent vector indexes (rebuilt from source)                 │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌─── SHARED (Cross-Region) ───────────────────────────────────────────┐ │
│  │  • Global LB (routes to nearest healthy region)                     │ │
│  │  • Container registry (geo-replicated)                              │ │
│  │  • Identity provider (global)                                       │ │
│  │  • Observability (centralized telemetry collector + dashboards)     │ │
│  │  • IaC repository + CI/CD pipelines                                 │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Network Architecture

```
┌──────────────────── NETWORK TOPOLOGY ──────────────────────────────────────┐
│                                                                             │
│  ┌── HUB VNET ──────────────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  ┌── Firewall Subnet ──────────┐  ┌── Bastion Subnet ─────────────┐ │  │
│  │  │  Network Firewall            │  │  Management jump-box          │ │  │
│  │  │  (egress filtering)          │  │  (admin access only)          │ │  │
│  │  └──────────────────────────────┘  └───────────────────────────────┘ │  │
│  │                                                                       │  │
│  │  ┌── Gateway Subnet ──────────────────────────────────────────────┐  │  │
│  │  │  VPN / Express Route (hybrid connectivity, if needed)          │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  └───────────┬───────────────────────────────────────────────────────────┘  │
│              │ (VNet peering)                                               │
│  ┌───────────┴── SPOKE VNET ─────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  ┌── AKS System Subnet (/24) ──┐  ┌── AKS User Subnet (/22) ──────┐ │  │
│  │  │  System node pool             │  │  Application workloads         │ │  │
│  │  │  NSG: allow internal only     │  │  NSG: allow from gateway only  │ │  │
│  │  └───────────────────────────────┘  └────────────────────────────────┘ │  │
│  │                                                                        │  │
│  │  ┌── AKS GPU Subnet (/24) ─────┐  ┌── API Gateway Subnet (/27) ───┐ │  │
│  │  │  GPU node pool (reserved)     │  │  API Gateway instances         │ │  │
│  │  │  NSG: allow from user subnet  │  │  NSG: allow from global LB    │ │  │
│  │  └───────────────────────────────┘  └────────────────────────────────┘ │  │
│  │                                                                        │  │
│  │  ┌── Private Endpoints Subnet (/24) ─────────────────────────────────┐│  │
│  │  │  Document DB PE │ Relational DB PE │ Cache PE │ Secret Store PE    ││  │
│  │  │  Search Index PE │ Object Storage PE │ Message Queue PE            ││  │
│  │  │  NSG: allow from AKS subnets only                                  ││  │
│  │  └────────────────────────────────────────────────────────────────────┘│  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Traffic flows:                                                              │
│  1. Internet → Global LB (WAF) → API Gateway Subnet → AKS User Subnet      │
│  2. AKS Subnet → Private Endpoints Subnet → Data Stores                     │
│  3. AKS Subnet → Hub Firewall → External APIs (model providers, etc.)       │
│  4. Admin → Bastion Subnet → AKS/Data Stores (management only)             │
│                                                                              │
│  Default: deny all. Explicit allow rules per flow above.                     │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Summary of Key Architecture Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Separate Control Plane and Runtime Plane | Different latency/throughput/availability requirements; independent scaling and deployment |
| 2 | Shared infrastructure with logical isolation | Cost-efficient multi-tenancy; isolation enforced at data (partition keys), API (subscriptions), and identity (RBAC) layers |
| 3 | Asynchronous by default, synchronous only for real-time paths | Model deployments, evaluations, and training are long-running; async prevents blocking and cascading failures |
| 4 | Streaming (SSE) as first-class citizen | LLM inference produces tokens over seconds/minutes; non-streaming UX is fundamentally broken for AI workloads |
| 5 | Provider adapter pattern for model catalog | New providers added without core changes; provider failures isolated; platform never queries providers in real-time for browse |
| 6 | Hierarchical partition keys for document database | Physical data isolation between tenants; 20GB+ data per tenant supported; impossible to accidentally query cross-tenant |
| 7 | Circuit breaker + multi-backend routing for inference | Model endpoints are the most failure-prone component; automatic failover prevents user-facing outages |
| 8 | Three-tier memory (working / short-term / long-term) | Different retention and retrieval needs; working memory is ephemeral, long-term memory uses vector search for relevance |
| 9 | Hybrid RAG search (vector + BM25 + re-ranking) | Vector search alone misses keyword matches; BM25 alone misses semantic similarity; re-ranking improves precision |
| 10 | Tool execution in sandboxed environments | Untrusted tool code cannot access agent memory, other tenants' data, or platform internals |
| 11 | Content safety on both input and output | Input filtering prevents prompt injection; output filtering prevents harmful generation; both are auditable |
| 12 | Cost attribution from Day 1 | Cannot be retrofitted; token counting and project tagging must be in the inference pipeline from first request |

---

*High-Level Design Document — AI Agent Platform*
*Version 1.0 — 2026-03-23*
*References: ADR-001 (Multi-Tenant Isolation), ARCHITECTURE.md, REQUIREMENTS.md*
