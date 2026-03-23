# Architecture Research: AI Agent Platform as a Service

## System Overview

The platform follows a **Control Plane / Runtime Plane** separation — a well-established pattern from Kubernetes, service meshes, and cloud-native platforms.

```
┌─────────────────────────────────────────────────────────┐
│                    CONTROL PLANE                         │
│  (Configuration, Management, Monitoring, Governance)     │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Agent    │  │ Policy   │  │ Eval     │  │ Cost    │  │
│  │ Manager  │  │ Engine   │  │ Engine   │  │ Monitor │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Tool     │  │ Model    │  │ Memory   │  │ Workflow│  │
│  │ Registry │  │ Registry │  │ Manager  │  │ Engine  │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
└─────────────────────┬───────────────────────────────────┘
                      │ API Boundary
┌─────────────────────▼───────────────────────────────────┐
│                    RUNTIME PLANE                         │
│  (Execution, Isolation, Data Flow, Model Interaction)    │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Agent    │  │ Thread   │  │ Tool     │  │ Model   │  │
│  │ Runtime  │  │ Manager  │  │ Executor │  │ Router  │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Memory   │  │ RAG      │  │ State    │              │
│  │ Store    │  │ Pipeline │  │ Store    │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
```

## Component Deep Dive

### Control Plane Components

**1. Agent Manager**
- CRUD operations for agent configurations
- Version management (each config change creates new version)
- Agent lifecycle: draft → active → paused → archived
- Multi-tenant isolation: tenant_id on every record

**2. Policy Engine**
- Policy evaluation pipeline: pre-execution → during-execution → post-execution
- Policy types: content filter, rate limit, token quota, RBAC
- Policy attachment: agent-level, tenant-level, global-level
- Policy evaluation order: global → tenant → agent (most specific wins)

**3. Evaluation Engine**
- Test suite management: define input/expected-output pairs
- Evaluation metrics: automated (semantic similarity, latency, token efficiency) + human rating
- Evaluation runs: batch execution against agent versions
- Results storage and comparison dashboards

**4. Cost Monitor**
- Token counting middleware intercepts all model calls
- Cost calculation: tokens × model pricing table
- Aggregation: per-request → per-agent → per-tenant → global
- Alerting: threshold-based notifications
- Budget enforcement: hard caps that reject requests when exceeded

**5. Tool Registry**
- Tool definitions: name, description, JSON Schema for input/output
- Tool categories: built-in, custom, marketplace
- Tool versioning: semantic versioning with compatibility checks
- Tool discovery: search, filter, tag-based browsing

**6. Model Registry**
- Model endpoint definitions: provider, URL, API key (encrypted), capabilities
- Model capabilities: chat, completion, embedding, vision, function calling
- Model pricing: per-token input/output costs for cost calculation
- Health monitoring: periodic health checks, latency tracking

**7. Memory Manager (Control Plane)**
- Memory space definitions: scope (agent, user, tenant), TTL, max size
- Memory policies: retention, summarization triggers, cleanup schedules
- Memory type configuration: conversation, semantic, episodic

**8. Workflow Engine (Control Plane)**
- Workflow definitions: DAG of agent nodes, edges, conditions
- Workflow templates: pre-built patterns
- Workflow versioning and lifecycle management

### Runtime Plane Components

**1. Agent Runtime**
- Request lifecycle: receive → validate → load config → execute → respond
- Isolation: each agent execution runs in isolated context
- Execution modes: synchronous (API call), asynchronous (background job), streaming (SSE/WebSocket)
- Resource limits: memory, CPU, execution time per agent run

**2. Thread Manager**
- Thread creation and persistence
- Message append with role tracking (user, assistant, system, tool)
- Thread windowing: sliding window for long conversations
- Thread metadata: created_at, last_active, message_count, token_count

**3. Tool Executor**
- Sandboxed tool execution
- Input validation against JSON Schema
- Output capture and formatting
- Timeout and error handling
- Parallel tool execution when agent requests multiple tools

**4. Model Router**
- Route selection: agent config → model registry → endpoint
- Request formatting: translate to model-specific API format
- Response normalization: standardize to OpenAI-compatible format
- Streaming: proxy SSE/WebSocket from model endpoint
- Fallback: circuit breaker pattern, retry with alternative model
- Token counting: intercept and count before/after model call

**5. Memory Store (Runtime)**
- Short-term: in-memory + Redis for active conversations
- Long-term: PostgreSQL + pgvector for persistent semantic memory
- Read/write operations: scoped by agent_id, user_id, tenant_id
- Retrieval: vector similarity search for relevant memories

**6. RAG Pipeline**
- Ingest: accept documents from data sources
- Chunk: split documents into appropriate segments
- Embed: generate vector embeddings via configured model
- Index: store in vector database (pgvector)
- Retrieve: query by similarity, return ranked results with source attribution

**7. State Store**
- Agent execution state: current step, intermediate results, tool call history
- Workflow state: which nodes completed, pending, failed
- Checkpoint support: save/restore execution state for debugging

## Data Flow — Agent Execution Lifecycle

```
User Request
    │
    ▼
┌─────────────┐
│ API Gateway │ ← Authentication, rate limiting
└──────┬──────┘
       │
       ▼
┌──────────────┐
│ Policy Check │ ← Pre-execution policies (content filter, quota check)
│ (Pre)        │
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────────┐
│ Agent Runtime│────▶│ Memory Load  │ ← Load conversation history + relevant memories
│              │     └──────────────┘
│              │     ┌──────────────┐
│              │────▶│ RAG Retrieve │ ← Fetch relevant documents if data sources attached
│              │     └──────────────┘
│              │
│   Build      │ ← System prompt + memory + RAG context + user message
│   Context    │
│              │
│              │     ┌──────────────┐
│              │────▶│ Model Router │ ← Route to configured model endpoint
│              │     └──────┬───────┘
│              │            │
│              │     ┌──────▼───────┐
│              │     │ Model Call   │ ← Send request, stream response
│              │     └──────┬───────┘
│              │            │
│              │     ┌──────▼───────┐
│              │◀────│ Tool Calls?  │ ← If model requests tool calls
│              │     └──────┬───────┘
│              │            │ yes
│              │     ┌──────▼───────┐
│              │     │ Tool Execute │ ← Run tools, return results to model
│              │     └──────┬───────┘
│              │            │
│              │     ┌──────▼───────┐
│              │◀────│ Continue     │ ← Model processes tool results
│              │     └──────────────┘
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Policy Check │ ← Post-execution policies (output filter)
│ (Post)       │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Telemetry    │ ← Token count, latency, cost, trace
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Memory Save  │ ← Persist conversation, update long-term memory
└──────┬───────┘
       │
       ▼
Response to User
```

## Multi-Tenant Isolation Model

```
Tenant A                          Tenant B
┌─────────────────────┐          ┌─────────────────────┐
│ Agents [A1, A2, A3] │          │ Agents [B1, B2]     │
│ Tools  [T1, T2]     │          │ Tools  [T3, T4]     │
│ Models [M1]         │          │ Models [M2, M3]     │
│ Data   [D1, D2]     │          │ Data   [D3]         │
│ Memory [mem-A]      │          │ Memory [mem-B]      │
└─────────────────────┘          └─────────────────────┘
         │                                │
         └────────────┬───────────────────┘
                      │
              ┌───────▼────────┐
              │ Shared Infra   │
              │ (API, DB, K8s) │
              │ tenant_id      │
              │ isolation       │
              └────────────────┘
```

**Isolation boundaries:**
- **Data**: Row-level security (tenant_id on every table), separate schemas optional for strict isolation
- **Execution**: Kubernetes namespaces or pod labels per tenant
- **Network**: Network policies preventing cross-tenant traffic
- **Secrets**: Tenant-scoped key vault entries
- **Resources**: Resource quotas per tenant namespace

## Scalability Considerations

| Component | Scaling Strategy |
|-----------|-----------------|
| API Layer | Horizontal (stateless), behind load balancer |
| Agent Runtime | Horizontal, auto-scale based on queue depth |
| Database (PostgreSQL) | Vertical scaling + read replicas for queries |
| Redis | Cluster mode for cache and pub-sub |
| Model Router | Horizontal, connection pooling per model endpoint |
| RAG Pipeline | Async ingestion with worker scaling |
| WebSocket | Sticky sessions or Redis pub-sub for multi-instance |

## Suggested Build Order

1. **Foundation**: Database schema, API skeleton, auth
2. **Agent Core**: Agent CRUD, model abstraction, basic execution
3. **Tools & Data**: Tool registry, tool execution, data source connection
4. **Memory & Threads**: Thread management, short-term memory, long-term memory
5. **Orchestration**: Workflow engine, parallel execution, sub-agents
6. **Governance**: Policy engine, RBAC, content filtering
7. **Observability**: Token counting, cost dashboard, evaluation engine
8. **Marketplace & CLI**: Agent marketplace, tool marketplace, CLI

---
*Researched: 2026-03-23*
