# Architecture Patterns — v3.0 Production Multi-Tenant Infrastructure

**Domain:** Multi-tenant SaaS infrastructure migration for AI Agent Platform
**Researched:** 2026-03-26
**Overall confidence:** HIGH
**Scope:** How the target features (Bicep IaC, Cosmos DB, AKS namespace-per-tenant, Entra ID, microservice split, CI/CD, observability) integrate with the existing monolithic FastAPI architecture.

**Sources:**
- Microsoft: [Architect multitenant solutions on Azure](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/overview) — HIGH confidence
- Microsoft: [Use AKS in a multitenant solution](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/service/aks) — HIGH confidence
- Microsoft: [Multitenancy and Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/service/cosmos-db) — HIGH confidence
- Microsoft: [AKS microservices architecture](https://learn.microsoft.com/en-us/azure/architecture/reference-architectures/containers/aks-microservices/aks-microservices) — HIGH confidence
- Microsoft: [Design a Bicep file](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/file) — HIGH confidence
- Existing codebase: `backend/app/` — all models, services, routes, middleware — HIGH confidence

---

## 1. Existing Architecture — What We Have

```
┌──────────────────────────────────────────────────────────────┐
│                     Docker Compose Host                       │
│                                                              │
│  ┌───────────┐  ┌───────────────────────────────────────────┐│
│  │ Next.js   │  │ FastAPI Monolith (:8000)                  ││
│  │ Frontend  │  │                                           ││
│  │ (:3000)   │  │  app/main.py (single process)             ││
│  │           │  │    ├─ TenantMiddleware (JWT HS256)         ││
│  │           │  │    ├─ 22 API routers (all in-process)      ││
│  │           │  │    ├─ 15 service classes (SQLAlchemy)       ││
│  │           │  │    └─ 26 SQLAlchemy models (tenant_id FK)  ││
│  └─────┬─────┘  └─────────┬─────────────────────────────────┘│
│        │                   │                                  │
│  ┌─────▼─────┐  ┌─────────▼──────┐  ┌──────────────────┐   │
│  │           │  │ PostgreSQL 16   │  │ Redis 7          │   │
│  │  (proxy)  │  │ + pgvector      │  │ (cache/queue)    │   │
│  │           │  │ (:5432)         │  │ (:6379)          │   │
│  └───────────┘  └────────────────┘  └──────────────────┘   │
│                                                              │
│  ┌───────────────────────┐  ┌────────────────────────────┐  │
│  │ MCP Server: Atlassian │  │ MCP Server: Web Tools      │  │
│  │ (:8081)               │  │ (:8082)                    │  │
│  └───────────────────────┘  └────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Current Service Inventory (all in-process)

| Service | File | Direct DB Access | Key Dependencies |
|---------|------|-----------------|------------------|
| AgentExecutionService | `agent_execution.py` | Yes (SQLAlchemy) | ModelAbstraction, ToolExecutor, MCPClient, RAG, Memory |
| ModelAbstractionService | `model_abstraction.py` | No | External LLM endpoints |
| ToolExecutor | `tool_executor.py` | No | Subprocess execution |
| WorkflowEngine | `workflow_engine.py` | Yes (SQLAlchemy) | AgentExecutionService |
| MCPClient | `mcp_client.py` | No | External MCP servers (HTTP) |
| MCPDiscovery | `mcp_discovery.py` | Yes (SQLAlchemy) | MCPClient |
| RAGService | `rag_service.py` | Yes (SQLAlchemy) | Azure AI Search |
| MemoryService | `memory_service.py` | Yes (SQLAlchemy) | pgvector |
| ObservabilityService | `observability_service.py` | Yes (SQLAlchemy) | Raw SQL queries |
| EvaluationService | `evaluation_service.py` | Yes (SQLAlchemy) | AgentExecutionService |
| MarketplaceService | `marketplace_service.py` | Yes (SQLAlchemy) | — |
| PlatformTools | `platform_tools.py` | No | Azure AI Services |
| SecretStore | `secret_store.py` | Yes (SQLAlchemy) | Fernet encryption |
| AzureARMService | `azure_arm.py` | Yes (SQLAlchemy) | Azure Management SDK |

### Current Model Inventory (26 SQLAlchemy models)

| Group | Models | Tenant-scoped |
|-------|--------|---------------|
| Identity | Tenant, User, RefreshToken | Tenant: no, User/Token: yes |
| Agent | Agent, AgentConfigVersion | Yes |
| Tools | Tool, AgentTool, MCPServer, MCPDiscoveredTool, AgentMCPTool | Yes |
| Data | DataSource, AgentDataSource, Document, DocumentChunk | Yes |
| Threads | Thread, ThreadMessage, AgentMemory | Yes |
| Execution | ExecutionLog | Yes (via Thread FK) |
| Workflow | Workflow, WorkflowNode, WorkflowEdge, WorkflowExecution, WorkflowNodeExecution | Yes |
| Costs | ModelPricing, CostAlert | Yes |
| Evaluation | TestSuite, TestCase, EvaluationRun, EvaluationResult | Yes |
| Marketplace | AgentTemplate, ToolTemplate | Shared (catalog) |
| Azure | AzureSubscription, AzureConnection, CatalogEntry | Yes |

---

## 2. Target Architecture — What We're Building

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          Azure Kubernetes Service (AKS)                           │
│                                                                                  │
│  ┌──────────────────────────────── platform ─────────────────────────────────┐   │
│  │                        (shared infrastructure namespace)                   │   │
│  │                                                                           │   │
│  │  ┌──────────────┐  ┌────────────────┐  ┌──────────────┐                  │   │
│  │  │ API Gateway  │  │ Tenant Mgmt    │  │ Auth Service │                  │   │
│  │  │ (FastAPI)    │  │ Service        │  │ (Entra ID)   │                  │   │
│  │  │              │◄─┤                │  │              │                  │   │
│  │  │ Ingress:     │  │ Namespace      │  │ Token        │                  │   │
│  │  │ NGINX/AGIC   │  │ provisioning,  │  │ validation,  │                  │   │
│  │  │              │  │ tenant CRUD    │  │ RBAC         │                  │   │
│  │  └──────┬───────┘  └────────────────┘  └──────────────┘                  │   │
│  │         │                                                                 │   │
│  └─────────┼─────────────────────────────────────────────────────────────────┘   │
│            │ (routes by tenant_id from JWT)                                       │
│            │                                                                      │
│  ┌─────────▼──────────────── tenant-alpha ───────────────────────────────────┐   │
│  │                        (tenant namespace)                                  │   │
│  │                                                                           │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │   │
│  │  │ Agent        │  │ Workflow     │  │ Tool         │  │ MCP Server   │  │   │
│  │  │ Executor     │  │ Engine       │  │ Executor     │  │ Proxy        │  │   │
│  │  │              │  │              │  │              │  │              │  │   │
│  │  │ Agent exec,  │  │ DAG engine,  │  │ Sandboxed    │  │ MCP client,  │  │   │
│  │  │ model calls, │  │ parallel/    │  │ tool runs,   │  │ tool         │  │   │
│  │  │ memory, RAG  │  │ sequential   │  │ JSON Schema  │  │ discovery    │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │   │
│  │                                                                           │   │
│  └───────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌──────────────────────────── tenant-bravo ─────────────────────────────────┐   │
│  │  (same 4 pods as above, independently scaled)                              │   │
│  └───────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌──────────────────────────── monitoring ───────────────────────────────────┐   │
│  │  Container Insights agent, OTEL collector (if needed)                      │   │
│  └───────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────┘
         │                    │                    │                │
    ┌────▼────┐    ┌─────────▼──────┐    ┌───────▼──────┐   ┌────▼──────────┐
    │ Cosmos  │    │ Azure Cache    │    │ Key Vault    │   │ App Insights  │
    │ DB      │    │ for Redis      │    │              │   │ + Log         │
    │ NoSQL   │    │                │    │              │   │   Analytics   │
    └─────────┘    └────────────────┘    └──────────────┘   └───────────────┘
```

---

## 3. Microservice Boundaries — How to Split the Monolith

### Decision: 5 Microservices + 1 Frontend

The monolith's 15 service classes split into 5 backend microservices based on **failure domain isolation**, **independent scaling requirements**, and **deployment cadence**. The key principle: services that MUST communicate synchronously for a single request stay together; services with different scaling profiles separate.

### 3.1 API Gateway (`api-gateway`)

**What it contains:**
- FastAPI application with Ingress routing
- Entra ID token validation middleware
- Tenant context resolution (JWT `tid` → platform `tenant_id`)
- RBAC enforcement
- All CRUD API routers (agents, tools, data sources, models, threads, evaluations, marketplace, MCP servers)
- Tenant management API (create, suspend, list tenants)
- Health/readiness probes

**What moves here from monolith:**
- `app/main.py` → refactored as gateway
- `app/middleware/tenant.py` → replaced with Entra ID token validation
- `app/api/v1/*` — all 22 routers remain in the gateway
- `app/services/marketplace_service.py` — stays (CRUD only, no execution logic)
- `app/services/secret_store.py` → replaced with Key Vault SDK calls
- `app/services/azure_arm.py` — stays (management API)

**What it does NOT contain:**
- No agent execution logic
- No model calls
- No tool execution
- No workflow orchestration

**Why this boundary:** The gateway handles all CRUD operations and request routing. CRUD operations are simple DB reads/writes with low CPU. They don't need independent scaling from each other — a single deployment with HPA on request rate suffices.

**Repository services used:** All repositories (agents, tools, threads, etc.) — read/write Cosmos DB.

```
Existing files → API Gateway
─────────────────────────────
app/main.py                    → Modified (Entra ID auth, service routing)
app/middleware/tenant.py       → Replaced (Entra ID token validation)
app/api/v1/*.py (all 22)       → Kept (CRUD routers, same structure)
app/services/marketplace_service.py → Kept
app/services/azure_arm.py     → Kept
app/services/secret_store.py   → Replaced (Key Vault SDK)
app/models/*.py                → Replaced (Pydantic models + Cosmos repos)
app/core/database.py           → Replaced (CosmosClient singleton)
app/core/config.py             → Modified (new env vars)
app/core/security.py           → Replaced (Entra ID validation)
```

### 3.2 Agent Executor (`agent-executor`)

**What it contains:**
- Agent execution loop (receive message → build context → model call → tool call loop → response)
- Model abstraction layer (LiteLLM, provider routing, circuit breaker)
- RAG retrieval (pgvector queries, Azure AI Search calls)
- Memory management (load/save conversation history, long-term memory)
- SSE streaming to API gateway
- Observability telemetry emission
- Internal HTTP server for receiving execution requests

**What moves here from monolith:**
- `app/services/agent_execution.py` → core of this service
- `app/services/model_abstraction.py` → embedded in this service
- `app/services/rag_service.py` → embedded in this service
- `app/services/memory_service.py` → embedded in this service
- `app/services/observability_service.py` → refactored (telemetry emission here, aggregation queries stay in gateway)
- `app/services/platform_tools.py` → embedded (Azure AI Service tool adapters)

**Why this boundary:** Agent execution is the **most CPU/memory-intensive operation** — model calls, context building, streaming responses. It scales independently based on concurrent agent executions (HPA on queue depth / active execution count). Isolating execution in tenant namespaces ensures tenant workloads don't compete for the same pod resources.

**Communication:**
- Receives execution requests from API Gateway via **internal HTTP POST** (or Redis pub-sub for async)
- Calls Tool Executor via **internal HTTP** when model requests tool use
- Calls MCP Server Proxy via **internal HTTP** for MCP tool invocations
- Streams responses back to API Gateway via **SSE over HTTP**
- Reads/writes Cosmos DB directly for thread messages, memory, execution logs

```
Existing files → Agent Executor
────────────────────────────────
app/services/agent_execution.py     → Core (refactored for inter-service calls)
app/services/model_abstraction.py   → Embedded
app/services/rag_service.py         → Embedded
app/services/memory_service.py      → Embedded
app/services/platform_tools.py      → Embedded
app/services/observability_service.py → Split (emit here, aggregate in gateway)
```

### 3.3 Workflow Engine (`workflow-engine`)

**What it contains:**
- Workflow DAG execution (sequential, parallel, autonomous, custom DAG)
- Node scheduling and state management
- Sub-agent delegation (calls Agent Executor for each node)
- Workflow execution records (create, update status, store results)
- Workflow-level timeout and termination logic

**What moves here from monolith:**
- `app/services/workflow_engine.py` → core of this service

**Why this boundary:** Workflows are **long-running, stateful operations** that may span minutes. They orchestrate multiple agent executions and need independent lifecycle management. A workflow failure should not crash the API gateway or block CRUD operations. Workflow pods scale based on active workflow count.

**Communication:**
- Receives workflow execution requests from API Gateway via **internal HTTP POST**
- Calls Agent Executor via **internal HTTP** for each workflow node execution
- Reads Cosmos DB for workflow definitions, writes execution state
- Reports status updates via Redis pub-sub (for real-time UI updates)

```
Existing files → Workflow Engine
─────────────────────────────────
app/services/workflow_engine.py    → Core (refactored: calls Agent Executor via HTTP)
app/models/workflow.py             → Replaced (Pydantic + Cosmos repo)
app/models/workflow_execution.py   → Replaced (Pydantic + Cosmos repo)
```

### 3.4 Tool Executor (`tool-executor`)

**What it contains:**
- Sandboxed tool execution (subprocess with resource limits)
- JSON Schema input validation
- Timeout handling and output capture
- Tool execution audit logging

**What moves here from monolith:**
- `app/services/tool_executor.py` → core of this service

**Why this boundary:** Tool execution runs **untrusted code** (user-defined tools with `execution_command`). Isolating it in a separate pod with restricted NetworkPolicy limits blast radius if a tool escapes the subprocess sandbox. Tools have different resource profiles (some are fast HTTP calls, some run heavy scripts). Separate pod allows tailored resource limits.

**Communication:**
- Receives tool call requests from Agent Executor via **internal HTTP POST**
- Returns tool results synchronously (HTTP response)
- No direct DB access — receives all context in the request payload
- Egress limited by NetworkPolicy: only external tool endpoints, not Cosmos DB

```
Existing files → Tool Executor
────────────────────────────────
app/services/tool_executor.py   → Core (minimal changes, HTTP server wrapper added)
```

### 3.5 MCP Server Proxy (`mcp-proxy`)

**What it contains:**
- MCP client (JSON-RPC 2.0 over HTTP/SSE)
- MCP server discovery and health checking
- MCP tool invocation proxy
- Connection pooling to registered MCP servers

**What moves here from monolith:**
- `app/services/mcp_client.py` → core of this service
- `app/services/mcp_discovery.py` → embedded in this service
- `mcp_server_atlassian_mock.py` → separate MCP server pod (not in proxy)
- `mcp_server_web_tools.py` → separate MCP server pod (not in proxy)

**Why this boundary:** MCP servers are **external HTTP endpoints** with their own lifecycle. The proxy centralizes connection management, auth header injection, and server health monitoring. Tenant-level MCP server registrations mean different tenants connect to different external servers — the proxy enforces tenant isolation on MCP connections.

**Communication:**
- Receives tool invocation requests from Agent Executor via **internal HTTP POST**
- Calls external MCP servers via **HTTP/SSE** (outbound)
- Reads MCP server registrations from Cosmos DB (server URLs, auth config)

```
Existing files → MCP Server Proxy
──────────────────────────────────
app/services/mcp_client.py      → Core
app/services/mcp_discovery.py   → Embedded
app/services/mcp_types.py       → Embedded
```

### 3.6 What Stays Together (NOT split)

| Components That Stay in API Gateway | Reason |
|--------------------------------------|--------|
| Agent CRUD router + service | Simple DB reads/writes, no execution |
| Tool CRUD router + service | Simple DB reads/writes, no execution |
| Thread CRUD router + service | Simple DB reads/writes |
| Evaluation CRUD router | CRUD only; evaluation *execution* calls Agent Executor |
| Marketplace CRUD | Simple DB reads/writes |
| MCP Server registration CRUD | Simple DB reads/writes |
| Observability aggregation queries | Read-only Cosmos queries for dashboard |
| Cost config CRUD | Simple DB reads/writes |

**Rule of thumb:** If it's just **CRUD + tenant-scoped DB queries**, it stays in the API Gateway. If it **executes code, calls external APIs, or runs for more than 1 second**, it becomes its own service.

---

## 4. Cosmos DB Container and Partition Design

### 4.1 Design Decision: Multiple Containers with Type Discriminator Per Group

**Approach:** Group related entities into a small number of containers organized by **access pattern**, NOT one container per entity. Use a `type` field as discriminator within each container. Partition key is `/tenant_id` on all containers.

**Why NOT single-container-per-entity (e.g., 26 containers):**
- Cosmos DB has a maximum of 25 containers in serverless mode before impacting throughput distribution
- Single container per entity wastes RU provisioning (most entities are low-traffic)
- Complicates cross-entity queries within the same domain

**Why NOT one giant container for everything:**
- Different entity groups have different indexing needs
- TTL policies vary (execution logs expire; agents don't)
- Throughput needs vary (execution logs: high write; agent configs: low write)

### 4.2 Container Layout

| Container | Entities (type discriminator) | Partition Key | Why This Grouping |
|-----------|-------------------------------|---------------|-------------------|
| `platform` | Tenant, User | `/id` | Platform-level entities. Tenants are queried by ID, not by tenant_id (they ARE the tenant). |
| `agents` | Agent, AgentConfigVersion, AgentTool, AgentDataSource, AgentMCPTool, ModelEndpoint | `/tenant_id` | Agent and its attached resources are always queried/written together. Embed config versions as sub-array in agent document. |
| `tools` | Tool, MCPServer, MCPDiscoveredTool | `/tenant_id` | Tool registry entities queried together in tool selection UI. |
| `data-sources` | DataSource, Document, DocumentChunk | `/tenant_id` | RAG pipeline entities. Documents and chunks always accessed with their data source. **Note:** DocumentChunk may need a separate container if chunk volume is very high per tenant. |
| `threads` | Thread, ThreadMessage | `/tenant_id` | Conversation data. Thread + messages always accessed together. Messages embedded as sub-documents within Thread (up to size limit), or stored separately with Thread ID as a secondary key. |
| `execution` | ExecutionLog, AgentMemory | `/tenant_id` | High-write telemetry data. Separate container allows aggressive TTL (90 days) without affecting agents/tools. |
| `workflows` | Workflow, WorkflowNode, WorkflowEdge, WorkflowExecution, WorkflowNodeExecution | `/tenant_id` | Workflow definitions and execution state. Nodes and edges embedded in workflow document. |
| `costs` | ModelPricing, CostAlert | `/tenant_id` | Cost configuration. Low volume, separate for independent TTL/indexing. |
| `evaluations` | TestSuite, TestCase, EvaluationRun, EvaluationResult | `/tenant_id` | Evaluation data. Test cases embedded in test suite document. Results linked to runs. |
| `marketplace` | AgentTemplate, ToolTemplate, CatalogEntry | `/category` | Shared catalog not tenant-scoped. Partition by category for browsing queries. |
| `connections` | AzureSubscription, AzureConnection, RefreshToken | `/tenant_id` | Azure integration and auth state. |

### 4.3 Denormalization Strategy

Cosmos DB is not relational. The migration requires **denormalizing** data that PostgreSQL currently joins:

| Current Relational Pattern | Cosmos DB Pattern |
|---------------------------|-------------------|
| `Agent` → FK `AgentConfigVersion` (separate table, JOIN) | Embed `config_versions[]` array inside Agent document |
| `Agent` → FK `AgentTool` (join table) → FK `Tool` | Embed `tool_ids[]` in Agent, store tool details in `tools` container, resolve at read time |
| `Workflow` → FK `WorkflowNode` → FK `WorkflowEdge` | Embed `nodes[]` and `edges[]` arrays inside Workflow document |
| `TestSuite` → FK `TestCase` (1:many) | Embed `test_cases[]` array inside TestSuite document |
| `Thread` → FK `ThreadMessage` (1:many, large) | **Don't fully embed.** Store latest N messages in Thread doc, older messages as separate docs with `thread_id` field. Or use a split: Thread metadata in `threads` container, messages in a separate `messages` container with `/thread_id` partition key if volume is very high. |
| `ExecutionLog` → FK `Thread` (for tenant_id) | Add `tenant_id` directly to ExecutionLog document (denormalize). No FK needed. |

### 4.4 Partition Key Strategy Details

```
Container: agents      Partition key: /tenant_id
├── { id: "agent-1", tenant_id: "t-alpha", type: "Agent", name: "...", config_versions: [...] }
├── { id: "agent-2", tenant_id: "t-alpha", type: "Agent", name: "...", config_versions: [...] }
└── { id: "agent-3", tenant_id: "t-bravo", type: "Agent", name: "...", config_versions: [...] }

Container: threads     Partition key: /tenant_id
├── { id: "thread-1", tenant_id: "t-alpha", type: "Thread", messages: [{...}, {...}] }
└── { id: "thread-2", tenant_id: "t-bravo", type: "Thread", messages: [{...}, {...}] }

Container: execution   Partition key: /tenant_id
├── { id: "log-1", tenant_id: "t-alpha", type: "ExecutionLog", thread_id: "thread-1", ... }
└── { id: "mem-1", tenant_id: "t-alpha", type: "AgentMemory", agent_id: "agent-1", ... }

Container: marketplace Partition key: /category
├── { id: "tmpl-1", category: "customer-support", type: "AgentTemplate", ... }
└── { id: "tmpl-2", category: "data-analysis", type: "ToolTemplate", ... }

Container: platform    Partition key: /id
├── { id: "t-alpha", type: "Tenant", name: "Alpha Team", slug: "alpha", ... }
└── { id: "user-1", type: "User", tenant_id: "t-alpha", ... }
```

**Why `/tenant_id` as partition key (not `/id`):**
- Every query pattern is "get all X for this tenant" — this is always a single-partition query (cheap: 1 RU)
- Cross-partition queries (admin listing all tenants' agents) are rare and acceptable at 2-5 tenant scale
- 20 GB logical partition limit is not a concern for 2-5 tenants
- Aligns with Microsoft's [recommendation for <50 tenants with similar workloads](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/service/cosmos-db#partition-key-per-tenant)

**Exception — `platform` container uses `/id`:**
- Tenants and users are queried by their own ID, not by tenant_id
- Tenant IS the tenant — no parent tenant_id to partition on
- Users are queried by user ID for login lookup

**Exception — `marketplace` container uses `/category`:**
- Shared catalog across all tenants
- Browsing pattern: "show me all templates in category X"
- No tenant scoping needed

### 4.5 Indexing Policy

```json
{
  "indexingPolicy": {
    "automatic": true,
    "indexingMode": "consistent",
    "includedPaths": [
      { "path": "/type/?" },
      { "path": "/tenant_id/?" },
      { "path": "/status/?" },
      { "path": "/created_at/?" },
      { "path": "/name/?" }
    ],
    "excludedPaths": [
      { "path": "/config_versions/*" },
      { "path": "/messages/*" },
      { "path": "/nodes/*" },
      { "path": "/edges/*" },
      { "path": "/state_snapshot/*" },
      { "path": "/\"_etag\"/?" }
    ],
    "compositeIndexes": [
      [
        { "path": "/type", "order": "ascending" },
        { "path": "/created_at", "order": "descending" }
      ]
    ]
  }
}
```

**Rationale:** Index only fields that appear in WHERE clauses and ORDER BY. Exclude large embedded arrays (config versions, messages, nodes) to save RU on writes. Composite index on `type` + `created_at` for listing queries.

---

## 5. Data Access Layer Replacement — Repository Pattern

### 5.1 Architecture: Services → Repository → Cosmos SDK

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│ API Router  │───▶│ Service (existing │───▶│ Repository (NEW)    │
│ (FastAPI)   │    │ logic, unchanged)│    │                     │
│             │    │                  │    │ CosmosRepository    │
│             │    │ AgentExecution   │    │   .create()         │
│             │    │ WorkflowEngine   │    │   .get()            │
│             │    │ etc.             │    │   .query()          │
│             │    │                  │    │   .update()         │
│             │    │                  │    │   .delete()         │
└─────────────┘    └──────────────────┘    └──────────┬──────────┘
                                                       │
                                           ┌──────────▼──────────┐
                                           │ azure-cosmos SDK    │
                                           │ (async CosmosClient)│
                                           │                     │
                                           │ Partition key       │
                                           │ enforcement,        │
                                           │ ETag concurrency    │
                                           └─────────────────────┘
```

### 5.2 Base Repository

```python
# app/repositories/base.py
from typing import TypeVar, Generic, Type, Optional, List
from pydantic import BaseModel
from azure.cosmos.aio import ContainerProxy

T = TypeVar("T", bound=BaseModel)

class CosmosRepository(Generic[T]):
    """Base repository with automatic tenant_id partition key enforcement."""

    def __init__(self, container: ContainerProxy, model_class: Type[T], entity_type: str):
        self._container = container
        self._model_class = model_class
        self._entity_type = entity_type

    async def create(self, tenant_id: str, data: T) -> T:
        doc = data.model_dump(mode="json")
        doc["type"] = self._entity_type
        doc["tenant_id"] = tenant_id
        result = await self._container.create_item(doc, partition_key=tenant_id)
        return self._model_class.model_validate(result)

    async def get(self, tenant_id: str, item_id: str) -> Optional[T]:
        try:
            result = await self._container.read_item(item_id, partition_key=tenant_id)
            if result.get("type") != self._entity_type:
                return None
            return self._model_class.model_validate(result)
        except Exception:
            return None

    async def query(self, tenant_id: str, filters: dict = None) -> List[T]:
        query = f"SELECT * FROM c WHERE c.type = @type"
        params = [{"name": "@type", "value": self._entity_type}]
        if filters:
            for key, value in filters.items():
                query += f" AND c.{key} = @{key}"
                params.append({"name": f"@{key}", "value": value})
        items = self._container.query_items(
            query=query, parameters=params, partition_key=tenant_id
        )
        return [self._model_class.model_validate(item) async for item in items]

    async def update(self, tenant_id: str, item_id: str, data: dict, etag: str = None) -> T:
        existing = await self._container.read_item(item_id, partition_key=tenant_id)
        existing.update(data)
        kwargs = {}
        if etag:
            kwargs["if_match"] = etag
        result = await self._container.replace_item(
            item_id, existing, partition_key=tenant_id, **kwargs
        )
        return self._model_class.model_validate(result)

    async def delete(self, tenant_id: str, item_id: str) -> None:
        await self._container.delete_item(item_id, partition_key=tenant_id)
```

### 5.3 Model Migration Map (SQLAlchemy → Pydantic Documents)

| SQLAlchemy Model | Pydantic Document | Container | Embedding Strategy |
|-----------------|-------------------|-----------|-------------------|
| `Agent` | `AgentDocument` | `agents` | Embed `config_versions[]`, `tool_ids[]`, `data_source_ids[]`, `mcp_tool_ids[]` |
| `AgentConfigVersion` | (embedded in AgentDocument) | `agents` | Embedded array |
| `AgentTool` | (embedded in AgentDocument) | `agents` | `tool_ids[]` array |
| `AgentDataSource` | (embedded in AgentDocument) | `agents` | `data_source_ids[]` array |
| `AgentMCPTool` | (embedded in AgentDocument) | `agents` | `mcp_tool_ids[]` array |
| `Tool` | `ToolDocument` | `tools` | Standalone document |
| `MCPServer` | `MCPServerDocument` | `tools` | Standalone document |
| `MCPDiscoveredTool` | `MCPDiscoveredToolDocument` | `tools` | Standalone, reference `mcp_server_id` |
| `DataSource` | `DataSourceDocument` | `data-sources` | Standalone document |
| `Document` | `DocumentDocument` | `data-sources` | Standalone, reference `data_source_id` |
| `DocumentChunk` | `DocumentChunkDocument` | `data-sources` | Standalone, reference `document_id` |
| `Thread` | `ThreadDocument` | `threads` | Embed recent `messages[]` (cap at 50), metadata |
| `ThreadMessage` | (embedded or overflow) | `threads` | Recent in Thread doc, older as separate docs |
| `AgentMemory` | `AgentMemoryDocument` | `execution` | Standalone document |
| `ExecutionLog` | `ExecutionLogDocument` | `execution` | Standalone, denormalize `tenant_id` |
| `Workflow` | `WorkflowDocument` | `workflows` | Embed `nodes[]`, `edges[]` |
| `WorkflowNode` | (embedded in WorkflowDocument) | `workflows` | Embedded array |
| `WorkflowEdge` | (embedded in WorkflowDocument) | `workflows` | Embedded array |
| `WorkflowExecution` | `WorkflowExecutionDocument` | `workflows` | Standalone, embed `node_executions[]` |
| `WorkflowNodeExecution` | (embedded in WorkflowExecutionDocument) | `workflows` | Embedded array |
| `ModelPricing` | `ModelPricingDocument` | `costs` | Standalone document |
| `CostAlert` | `CostAlertDocument` | `costs` | Standalone document |
| `TestSuite` | `TestSuiteDocument` | `evaluations` | Embed `test_cases[]` |
| `TestCase` | (embedded in TestSuiteDocument) | `evaluations` | Embedded array |
| `EvaluationRun` | `EvaluationRunDocument` | `evaluations` | Embed `results[]` |
| `EvaluationResult` | (embedded in EvaluationRunDocument) | `evaluations` | Embedded array |
| `Tenant` | `TenantDocument` | `platform` | Standalone, partition key is `/id` |
| `User` | `UserDocument` | `platform` | Standalone |
| `RefreshToken` | `RefreshTokenDocument` | `connections` | Standalone, with TTL |
| `AgentTemplate` | `AgentTemplateDocument` | `marketplace` | Standalone |
| `ToolTemplate` | `ToolTemplateDocument` | `marketplace` | Standalone |
| `CatalogEntry` | `CatalogEntryDocument` | `marketplace` | Standalone |
| `AzureSubscription` | `AzureSubscriptionDocument` | `connections` | Standalone |
| `AzureConnection` | `AzureConnectionDocument` | `connections` | Standalone |
| `ModelEndpoint` | `ModelEndpointDocument` | `agents` | Standalone (shared across agents in same tenant) |

### 5.4 Service Layer Changes

Services keep their business logic but replace SQLAlchemy session usage with repository calls:

```python
# BEFORE (SQLAlchemy)
async def get_agents(db: AsyncSession, tenant_id: UUID) -> List[Agent]:
    result = await db.execute(
        select(Agent).where(Agent.tenant_id == tenant_id)
    )
    return list(result.scalars().all())

# AFTER (Repository)
async def get_agents(tenant_id: str) -> List[AgentDocument]:
    return await agent_repo.query(tenant_id=tenant_id)
```

**Key change:** Services no longer receive `db: AsyncSession` as a parameter. Instead, they receive repository instances via dependency injection. The `get_db()` dependency is replaced by `get_agent_repo()`, `get_thread_repo()`, etc.

### 5.5 Cosmos DB Client Singleton

```python
# app/core/cosmos.py
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

_client: CosmosClient | None = None

async def get_cosmos_client() -> CosmosClient:
    global _client
    if _client is None:
        credential = DefaultAzureCredential()
        _client = CosmosClient(
            url=settings.COSMOS_ENDPOINT,
            credential=credential
        )
    return _client

async def get_container(container_name: str):
    client = await get_cosmos_client()
    database = client.get_database_client(settings.COSMOS_DATABASE)
    return database.get_container_client(container_name)
```

---

## 6. AKS Architecture — Namespace Layout and Routing

### 6.1 Namespace Topology

```
AKS Cluster
├── kube-system           (K8s system pods — DNS, kube-proxy, etc.)
├── platform              (shared infrastructure — API gateway, tenant mgmt, NGINX ingress)
│   ├── Deployment: api-gateway (replicas: 2-5)
│   ├── Deployment: tenant-management-service (replicas: 1-2)
│   ├── Service: api-gateway-svc (ClusterIP)
│   ├── Ingress: external-ingress (NGINX or AGIC)
│   └── ConfigMap: platform-config
│
├── tenant-alpha          (tenant workloads)
│   ├── Deployment: agent-executor (replicas: 1-3, HPA)
│   ├── Deployment: workflow-engine (replicas: 1-2, HPA)
│   ├── Deployment: tool-executor (replicas: 1-2)
│   ├── Deployment: mcp-proxy (replicas: 1)
│   ├── Service: agent-executor-svc (ClusterIP)
│   ├── Service: workflow-engine-svc (ClusterIP)
│   ├── Service: tool-executor-svc (ClusterIP)
│   ├── Service: mcp-proxy-svc (ClusterIP)
│   ├── ServiceAccount: tenant-alpha-sa (Workload Identity)
│   ├── NetworkPolicy: default-deny + allow-rules
│   ├── ResourceQuota: cpu=4, memory=8Gi
│   └── LimitRange: default container limits
│
├── tenant-bravo          (same structure as tenant-alpha)
│   └── ...
│
└── monitoring            (observability stack)
    ├── DaemonSet: otel-collector (if not using Azure Monitor addon)
    └── ConfigMap: monitoring-config
```

### 6.2 API Gateway → Tenant Namespace Routing

The API Gateway resolves the target tenant namespace from the JWT token and proxies execution requests to the correct tenant namespace's services.

```
                  External Request
                       │
                       ▼
              ┌────────────────┐
              │ NGINX Ingress  │  TLS termination
              │ Controller     │  (platform namespace)
              └───────┬────────┘
                      │
                      ▼
              ┌────────────────┐
              │ API Gateway    │
              │ (FastAPI)      │
              │                │
              │ 1. Validate    │
              │    Entra ID    │
              │    token       │
              │                │
              │ 2. Extract     │
              │    tenant_id   │  ← from JWT `tid` claim → lookup platform tenant
              │    from JWT    │
              │                │
              │ 3. CRUD ops    │  ← Handle directly (Cosmos DB read/write)
              │    ──── or ──  │
              │ 4. Execution   │  ← Proxy to tenant namespace
              │    requests    │
              └───────┬────────┘
                      │
         ┌────────────┼──────────────┐
         │ (CRUD)     │ (execution)  │
         ▼            ▼              ▼
    ┌─────────┐  ┌──────────────┐  ┌──────────────┐
    │ Cosmos  │  │ agent-exec   │  │ agent-exec   │
    │ DB      │  │ -svc.tenant  │  │ -svc.tenant  │
    │ (direct)│  │ -alpha.svc   │  │ -bravo.svc   │
    └─────────┘  │ .cluster     │  │ .cluster     │
                 │ .local       │  │ .local       │
                 └──────────────┘  └──────────────┘
```

**Routing logic in API Gateway:**

```python
# In API Gateway: route execution requests to tenant namespace
async def proxy_to_tenant_service(
    tenant_slug: str, service: str, path: str, body: dict
):
    """Route request to service in tenant's namespace via K8s DNS."""
    url = (
        f"http://{service}-svc.tenant-{tenant_slug}"
        f".svc.cluster.local:8080{path}"
    )
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=body, timeout=120)
        return response
```

### 6.3 NetworkPolicy Rules

```yaml
# Default deny all ingress/egress in tenant namespaces
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: tenant-alpha
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
---
# Allow ingress FROM api-gateway in platform namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-gateway
  namespace: tenant-alpha
spec:
  podSelector: {}
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: platform
          podSelector:
            matchLabels:
              app: api-gateway
---
# Allow intra-namespace communication (agent-executor <-> tool-executor)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-intra-namespace
  namespace: tenant-alpha
spec:
  podSelector: {}
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector: {}
---
# Allow egress to Azure services (Cosmos DB, Key Vault, model endpoints)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-azure-egress
  namespace: tenant-alpha
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
    - to: []  # Allow all egress (refined with FQDN policies or Calico rules)
      ports:
        - port: 443
          protocol: TCP
    - to: []  # DNS resolution
      ports:
        - port: 53
          protocol: UDP
        - port: 53
          protocol: TCP
```

### 6.4 Inter-Service Communication Within a Tenant Namespace

Services within the same tenant namespace communicate via **K8s ClusterIP Services** (in-cluster HTTP):

```
tenant-alpha namespace:
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  api-gateway (platform namespace)                            │
│       │                                                      │
│       ▼                                                      │
│  agent-executor-svc ──── HTTP ────▶ tool-executor-svc        │
│  :8080                              :8080                    │
│       │                                                      │
│       ├───────── HTTP ────▶ mcp-proxy-svc                    │
│       │                     :8080                            │
│       │                                                      │
│       ├───────── HTTP ────▶ workflow-engine-svc              │
│       │                     :8080                            │
│                                                              │
│  workflow-engine-svc ── HTTP ──▶ agent-executor-svc          │
│  :8080                          :8080                        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Protocol choice: HTTP (not gRPC, not service mesh)**

| Option | Verdict | Rationale |
|--------|---------|-----------|
| HTTP/REST | **Use this** | Same protocol as existing code. FastAPI on both ends. Minimal refactoring. httpx for inter-service calls. |
| gRPC | Defer | Better performance but requires .proto definitions, code generation, new client libraries. Add when inter-service call volume justifies it. |
| Istio service mesh | Defer | mTLS and L7 policies are powerful but adds 0.5-1 CPU per *node* overhead (Envoy sidecars). Overkill for 2-5 trusted internal tenants. |
| NATS/RabbitMQ | Defer | Async messaging adds eventual consistency complexity. HTTP with retries is sufficient for synchronous execution flows. |

**No service mesh for v3.0.** NetworkPolicy provides L3/L4 isolation. HTTP between pods in the same namespace is secure by default (no external network path). If mTLS between services is later required, AKS supports Istio addon without architecture changes.

---

## 7. Auth Flow — Entra ID → API Gateway → Tenant Routing

### 7.1 End-to-End Auth Flow

```
┌──────────┐     ┌───────────────┐     ┌──────────────┐     ┌──────────────┐
│ Browser  │     │ Entra ID      │     │ API Gateway  │     │ Tenant       │
│ (Next.js)│     │ (IdP)         │     │ (FastAPI)    │     │ Services     │
└────┬─────┘     └───────┬───────┘     └──────┬───────┘     └──────┬───────┘
     │                   │                     │                    │
     │ 1. Login redirect │                     │                    │
     │──────────────────▶│                     │                    │
     │                   │                     │                    │
     │ 2. Entra ID login │                     │                    │
     │   + MFA (if CA    │                     │                    │
     │     policy)       │                     │                    │
     │◀──────────────────│                     │                    │
     │                   │                     │                    │
     │ 3. ID token +     │                     │                    │
     │   access token    │                     │                    │
     │◀──────────────────│                     │                    │
     │                   │                     │                    │
     │ 4. API call with  │                     │                    │
     │   Bearer token    │                     │                    │
     │─────────────────────────────────────────▶                    │
     │                   │                     │                    │
     │                   │  5. Validate token  │                    │
     │                   │     - Verify sig    │                    │
     │                   │       (JWKS)        │                    │
     │                   │     - Check iss,    │                    │
     │                   │       aud, exp      │                    │
     │                   │     - Extract oid,  │                    │
     │                   │       tid, roles    │                    │
     │                   │                     │                    │
     │                   │  6. Resolve tenant  │                    │
     │                   │     Entra tid ->    │                    │
     │                   │     platform        │                    │
     │                   │     tenant_id       │                    │
     │                   │                     │                    │
     │                   │  7. Check RBAC      │                    │
     │                   │     App role claim  │                    │
     │                   │     vs endpoint     │                    │
     │                   │     requirement     │                    │
     │                   │                     │                    │
     │                   │  8. Route to tenant │                    │
     │                   │     namespace       │────────────────────▶
     │                   │                     │                    │
     │ 9. Response       │                     │                    │
     │◀─────────────────────────────────────────────────────────────│
```

### 7.2 Token Claims Used

```json
{
  "iss": "https://login.microsoftonline.com/{entra_tenant_id}/v2.0",
  "aud": "api://ai-agent-platform",
  "oid": "user-object-id-in-entra",
  "tid": "entra-tenant-id",
  "preferred_username": "user@org.com",
  "roles": ["TenantAdmin"],
  "exp": 1735084800
}
```

| Claim | Maps To | Purpose |
|-------|---------|---------|
| `oid` | `platform_user_id` (lookup) | Identify user in platform |
| `tid` | `platform_tenant_id` (lookup via `entra_tenant_map` collection) | Resolve tenant namespace |
| `roles` | Platform RBAC role | Enforce permissions |
| `preferred_username` | Display name / audit logging | UI display |

### 7.3 Tenant Mapping Lookup

```python
# Entra ID tid -> platform tenant_id resolution
# Stored in Cosmos DB `platform` container

{
    "id": "entra-map-1",
    "type": "EntraTenantMap",
    "entra_tenant_id": "72f988bf-...",  # Entra ID tenant UUID
    "platform_tenant_id": "t-alpha",    # Platform tenant ID
    "platform_tenant_slug": "alpha",    # For K8s namespace routing
    "created_at": "2026-03-26T..."
}
```

### 7.4 Service-to-Service Auth (Within AKS)

Between microservices **within the cluster**, communication uses Kubernetes ServiceAccount tokens (Workload Identity):

```
API Gateway (platform namespace)
    |
    | HTTP call with X-Tenant-ID header + X-Request-ID header
    | (No Bearer token -- internal trust boundary)
    |
    v
Agent Executor (tenant-alpha namespace)
    |
    | Validates: request came from platform namespace (NetworkPolicy enforces this)
    | Trusts: X-Tenant-ID header (set by gateway, not by user)
    |
    | For Azure SDK calls (Cosmos DB, Key Vault):
    | Uses DefaultAzureCredential -> ServiceAccount -> Workload Identity -> MI token
    |
    v
Cosmos DB / Key Vault / Azure AI Search
```

**Internal trust model:** API Gateway is the **only** ingress point. It validates the Entra ID token and sets trusted internal headers. Tenant services trust these headers because NetworkPolicy ensures only the API Gateway can reach them. No re-validation of Entra ID tokens at each microservice — that would add latency.

---

## 8. Bicep Module Structure

### 8.1 Directory Layout

```
infra/
├── main.bicep                    # Orchestrator — deploys all modules in order
├── main.bicepparam               # Default parameters
├── parameters/
│   ├── dev.bicepparam            # Dev environment overrides
│   ├── staging.bicepparam        # Staging environment overrides
│   └── prod.bicepparam           # Production environment overrides
│
├── modules/
│   ├── network/
│   │   └── vnet.bicep            # VNet + subnets + NSGs
│   │
│   ├── identity/
│   │   └── managed-identities.bicep  # User-assigned MIs for AKS, workloads
│   │
│   ├── security/
│   │   └── keyvault.bicep        # Key Vault + RBAC role assignments
│   │
│   ├── data/
│   │   ├── cosmos.bicep          # Cosmos DB account + database + containers
│   │   └── redis.bicep           # Azure Cache for Redis
│   │
│   ├── compute/
│   │   ├── acr.bicep             # Azure Container Registry + AcrPull role
│   │   └── aks.bicep             # AKS cluster + node pools + addons
│   │
│   ├── observability/
│   │   ├── log-analytics.bicep   # Log Analytics workspace
│   │   └── app-insights.bicep    # Application Insights + connection to LA
│   │
│   └── ai/
│       └── ai-search.bicep       # Azure AI Search (if provisioning new)
│
└── scripts/
    └── tenant-namespace.sh       # kubectl script to provision tenant namespace
```

### 8.2 Module Dependency Graph

```
main.bicep
  │
  ├──▶ network/vnet.bicep
  │       │ outputs: vnetId, aksSubnetId, privateEndpointSubnetId
  │       │
  ├──▶ identity/managed-identities.bicep
  │       │ outputs: aksIdentityId, workloadIdentityClientId
  │       │
  ├──▶ security/keyvault.bicep
  │       │ depends on: vnet (private endpoint), identities (role assignments)
  │       │ outputs: keyVaultUri
  │       │
  ├──▶ data/cosmos.bicep
  │       │ depends on: vnet (private endpoint), identities (RBAC)
  │       │ outputs: cosmosEndpoint, databaseName
  │       │
  ├──▶ data/redis.bicep
  │       │ depends on: vnet (private endpoint)
  │       │ outputs: redisHostname
  │       │
  ├──▶ compute/acr.bicep
  │       │ depends on: identities (AcrPull role)
  │       │ outputs: acrLoginServer
  │       │
  ├──▶ compute/aks.bicep
  │       │ depends on: vnet (subnet), identities (cluster MI), acr (AcrPull)
  │       │ outputs: aksClusterName, aksOidcIssuer
  │       │
  ├──▶ observability/log-analytics.bicep
  │       │ outputs: workspaceId
  │       │
  └──▶ observability/app-insights.bicep
          │ depends on: log-analytics (workspaceId)
          │ outputs: connectionString
```

### 8.3 Cosmos DB Bicep Module Detail

```bicep
// modules/data/cosmos.bicep
param location string
param cosmosAccountName string
param databaseName string = 'aiplatform'
param workloadIdentityPrincipalId string

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: cosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    capabilities: [{ name: 'EnableServerless' }]
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [{ locationName: location, failoverPriority: 0 }]
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: { id: databaseName }
  }
}

var containers = [
  { name: 'platform',     partitionKey: '/id',         ttl: -1 }
  { name: 'agents',       partitionKey: '/tenant_id',  ttl: -1 }
  { name: 'tools',        partitionKey: '/tenant_id',  ttl: -1 }
  { name: 'data-sources', partitionKey: '/tenant_id',  ttl: -1 }
  { name: 'threads',      partitionKey: '/tenant_id',  ttl: -1 }
  { name: 'execution',    partitionKey: '/tenant_id',  ttl: 7776000 }
  { name: 'workflows',    partitionKey: '/tenant_id',  ttl: -1 }
  { name: 'costs',        partitionKey: '/tenant_id',  ttl: -1 }
  { name: 'evaluations',  partitionKey: '/tenant_id',  ttl: -1 }
  { name: 'marketplace',  partitionKey: '/category',   ttl: -1 }
  { name: 'connections',  partitionKey: '/tenant_id',  ttl: -1 }
]

resource cosmosContainers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = [
  for container in containers: {
    parent: database
    name: container.name
    properties: {
      resource: {
        id: container.name
        partitionKey: { paths: [container.partitionKey], kind: 'Hash' }
        defaultTtl: container.ttl
      }
    }
  }
]

// RBAC: Cosmos DB Built-in Data Contributor role for workload identity
resource cosmosRbac 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, workloadIdentityPrincipalId, 'contributor')
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: workloadIdentityPrincipalId
    scope: cosmosAccount.id
  }
}

output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output databaseName string = databaseName
```

### 8.4 AKS Bicep Module (Key Config)

```bicep
// modules/compute/aks.bicep (abbreviated — key configuration)
resource aks 'Microsoft.ContainerService/managedClusters@2024-05-01' = {
  name: aksClusterName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${aksIdentityId}': {} }
  }
  properties: {
    dnsPrefix: aksClusterName
    kubernetesVersion: '1.30'
    networkProfile: {
      networkPlugin: 'azure'
      networkPluginMode: 'overlay'    // Azure CNI Overlay
      networkPolicy: 'calico'        // Calico for NetworkPolicy
      serviceCidr: '10.0.0.0/16'
      dnsServiceIP: '10.0.0.10'
    }
    oidcIssuerProfile: { enabled: true }
    securityProfile: {
      workloadIdentity: { enabled: true }
    }
    addonProfiles: {
      omsagent: {
        enabled: true
        config: {
          logAnalyticsWorkspaceResourceID: logAnalyticsWorkspaceId
        }
      }
    }
    aadProfile: {
      managed: true
      enableAzureRBAC: true
    }
    agentPoolProfiles: [
      {
        name: 'system'
        count: 2
        vmSize: 'Standard_D2s_v5'
        mode: 'System'
        vnetSubnetID: aksSubnetId
      }
      {
        name: 'workload'
        count: 2
        minCount: 1
        maxCount: 10
        vmSize: 'Standard_D4s_v5'
        mode: 'User'
        enableAutoScaling: true
        vnetSubnetID: aksSubnetId
      }
    ]
  }
}
```

---

## 9. Component Change Matrix — New vs Modified vs Replaced

### 9.1 New Components (don't exist today)

| Component | Location | Purpose |
|-----------|----------|---------|
| Bicep modules (all) | `infra/modules/` | Azure resource provisioning |
| CosmosRepository base class | `app/repositories/base.py` | Data access layer |
| Entity-specific repositories | `app/repositories/agents.py`, etc. | Per-entity Cosmos DB access |
| Pydantic document models | `app/documents/` | Cosmos DB document schemas |
| Cosmos DB client singleton | `app/core/cosmos.py` | Connection management |
| Entra ID token validator | `app/core/entra_auth.py` | Token validation via JWKS |
| Tenant mapping service | `app/services/tenant_mapping.py` | Entra tid → platform tenant |
| Inter-service HTTP client | `app/core/service_client.py` | Gateway → tenant service proxy |
| Tenant provisioning service | `app/services/tenant_provisioning.py` | K8s namespace creation |
| Per-microservice Dockerfiles | `docker/api-gateway/Dockerfile`, etc. | Multi-stage production images |
| Helm charts | `deploy/charts/` | K8s deployment templating |
| Kustomize overlays per tenant | `deploy/overlays/tenant-alpha/`, etc. | Tenant-specific K8s config |
| GitHub Actions workflows | `.github/workflows/` | CI/CD pipelines |
| OpenTelemetry configuration | `app/core/telemetry.py` | Azure Monitor integration |
| K8s manifests per service | `deploy/base/` | Deployments, Services, HPA |
| NetworkPolicy manifests | `deploy/base/network-policies/` | Tenant isolation rules |

### 9.2 Modified Components (exist today, need changes)

| Component | Current Location | What Changes |
|-----------|-----------------|--------------|
| `app/main.py` | `backend/app/main.py` | Add OTel middleware, replace auth with Entra ID, add service routing |
| `app/core/config.py` | `backend/app/core/config.py` | Add COSMOS_ENDPOINT, COSMOS_DATABASE, APP_INSIGHTS_CONNECTION_STRING, remove DATABASE_URL |
| `app/api/v1/*.py` (all routers) | `backend/app/api/v1/` | Replace `db: AsyncSession` dependency with repository dependencies |
| All service classes | `backend/app/services/` | Replace SQLAlchemy queries with repository calls |
| `docker-compose.yml` | root | Add dev Cosmos DB emulator, update service definitions |
| Frontend auth | `frontend/src/` | Add MSAL provider, Entra ID login flow |
| Backend `Dockerfile` | `backend/Dockerfile` | Multi-stage build, non-root user |
| Frontend `Dockerfile` | `frontend/Dockerfile` | Multi-stage build (standalone output), non-root user |

### 9.3 Replaced Components (exist today, removed and replaced)

| Component | Replaced By | Reason |
|-----------|-------------|--------|
| `app/models/*.py` (26 SQLAlchemy models) | Pydantic document models in `app/documents/` | Cosmos DB is schemaless; Pydantic defines document shape |
| `app/models/base.py` (Base, UUIDMixin, TimestampMixin) | Pydantic `BaseDocument` with `id`, `created_at`, `updated_at` fields | No SQLAlchemy DeclarativeBase needed |
| `app/core/database.py` (async_session, get_db) | `app/core/cosmos.py` (CosmosClient, get_container) | No SQLAlchemy engine/session management |
| `app/core/security.py` (JWT HS256 creation) | Entra ID token validation (verify, not issue) | Platform no longer issues tokens |
| `app/middleware/tenant.py` (JWT decode + tenant extract) | Entra ID middleware (JWKS validation + tid → tenant lookup) | Token format and validation flow completely different |
| `alembic/` (all migration scripts) | Cosmos DB container provisioning in Bicep | No schema migrations for schemaless DB |
| `alembic.ini` | (removed) | No more Alembic |
| `.env` secrets (DATABASE_URL, SECRET_KEY) | Key Vault references + Managed Identity | Secrets not in env vars in production |

### 9.4 Unchanged Components

| Component | Why Unchanged |
|-----------|---------------|
| `app/services/model_abstraction.py` | No DB access; calls external model endpoints. Logic is the same. |
| `app/services/tool_executor.py` | No DB access; subprocess execution. Logic is the same. |
| `app/services/mcp_client.py` | No DB access; HTTP/JSON-RPC to external MCP servers. Logic is the same. |
| `app/services/mcp_types.py` | Pydantic types for MCP protocol. No changes. |
| `app/services/platform_tools.py` | Azure AI Service adapters. No DB access. |
| Frontend UI components | Same React components, same API calls. Auth wrapper changes. |
| MCP server processes | `mcp_server_atlassian_mock.py`, `mcp_server_web_tools.py` — become separate pods, no code changes. |

---

## 10. Data Flow Changes — Before and After

### 10.1 Agent Chat Execution (Before → After)

**BEFORE (Monolith):**
```
Browser → FastAPI (:8000) → TenantMiddleware (HS256 JWT)
  → AgentExecutionService (in-process)
    → SQLAlchemy: SELECT agent, thread, messages
    → ModelAbstractionService (in-process) → LLM endpoint
    → ToolExecutor (in-process, subprocess)
    → SQLAlchemy: INSERT thread_message, execution_log
  ← SSE response
```

**AFTER (Microservices):**
```
Browser → NGINX Ingress → API Gateway (platform namespace)
  → Entra ID token validation (JWKS)
  → Resolve tenant: Entra tid → platform tenant "alpha"
  → HTTP POST to agent-executor-svc.tenant-alpha.svc.cluster.local:8080
    → Agent Executor (tenant-alpha namespace):
      → Cosmos DB: read agent, thread, messages (partition_key=tenant-alpha)
      → ModelAbstractionService (in-process) → LLM endpoint
      → HTTP POST to tool-executor-svc.tenant-alpha.svc.cluster.local:8080
        → Tool Executor: execute subprocess, return result
      → Cosmos DB: write thread_message, execution_log
      → OpenTelemetry: emit spans + metrics to App Insights
    ← SSE response proxied back through API Gateway
  ← SSE response to browser
```

### 10.2 Workflow Execution (Before → After)

**BEFORE:**
```
API → WorkflowEngine (in-process)
  → For each node: AgentExecutionService (in-process)
    → All DB access via SQLAlchemy
```

**AFTER:**
```
API Gateway → HTTP POST to workflow-engine-svc.tenant-alpha:8080
  → Workflow Engine (tenant-alpha namespace)
    → For each node: HTTP POST to agent-executor-svc.tenant-alpha:8080
      → Agent Executor handles each agent run
    → Cosmos DB: update workflow execution status
  ← Result to API Gateway
```

---

## 11. Suggested Build Order

Dependencies drive the build order. Each phase builds on the previous.

```
Phase 1: Bicep IaC Foundation
  │ Deploys: VNet, AKS, ACR, Cosmos DB, Redis, Key Vault, Log Analytics, App Insights
  │ Depends on: Nothing (greenfield Azure resources)
  │ Enables: Everything else
  │
Phase 2: Cosmos DB Repository Layer + Document Models
  │ Creates: Pydantic documents, CosmosRepository base, entity repositories
  │ Modifies: All service classes (replace SQLAlchemy with repos)
  │ Removes: SQLAlchemy models, Alembic
  │ Depends on: Cosmos DB provisioned (Phase 1)
  │ Critical path: Largest code change (26 models, 15 services, 22 routers)
  │
Phase 3: Entra ID Authentication
  │ Creates: Entra ID token validator, tenant mapping, RBAC enforcement
  │ Modifies: Tenant middleware, auth endpoints, frontend auth
  │ Removes: Custom JWT issuance, HS256 token generation
  │ Depends on: Entra ID app registration (manual Azure portal step)
  │
Phase 4: Microservice Container Images
  │ Creates: Multi-stage Dockerfiles per service, shared base image
  │ Modifies: app/main.py (gateway mode vs executor mode)
  │ Splits: Monolith entrypoint into 5 service entrypoints
  │ Depends on: Phases 2-3 (code must be refactored before packaging)
  │
Phase 5: AKS Deployment + Tenant Namespaces
  │ Creates: Helm charts, Kustomize overlays, NetworkPolicies, tenant provisioning
  │ Deploys: All 5 services to AKS with namespace-per-tenant
  │ Depends on: Phase 1 (AKS), Phase 4 (container images)
  │
Phase 6: CI/CD Pipeline
  │ Creates: GitHub Actions workflows (build → push → deploy)
  │ Depends on: Phase 4 (images to build), Phase 5 (AKS to deploy to)
  │
Phase 7: Observability + Per-Tenant Metrics
  │ Creates: OpenTelemetry instrumentation, App Insights integration
  │ Modifies: All services (add tracing, structured logging)
  │ Depends on: Phase 1 (App Insights), Phase 5 (services deployed)
  │
Phase 8: Tenant Admin UI
  │ Creates: Tenant selector, onboarding wizard, admin dashboard
  │ Modifies: Frontend auth, all pages (tenant context)
  │ Depends on: Phase 3 (Entra ID), Phase 5 (namespaces to provision)
```

### Build Order Rationale

1. **Bicep first** because every other phase needs Azure resources to exist.
2. **Cosmos DB migration second** because it's the highest-risk, highest-effort change. All services depend on the data layer. Doing this early surfaces design issues before adding more complexity.
3. **Entra ID third** because microservices need real auth before deployment. Can't deploy to AKS with HS256 dev tokens.
4. **Container images fourth** because you need the refactored codebase (Cosmos repos + Entra ID auth) before packaging into Docker images.
5. **AKS deployment fifth** because images must exist before deploying. Namespace provisioning depends on AKS cluster.
6. **CI/CD sixth** because it automates what phases 4-5 do manually. Needs both images and deployment targets.
7. **Observability seventh** because it's an enhancement layer — everything works without it, but production needs it.
8. **Tenant admin UI last** because it's a frontend feature that depends on all backend APIs being operational.

---

## 12. Anti-Patterns to Avoid

### Anti-Pattern 1: Big Bang Migration
**What:** Trying to replace SQLAlchemy AND split into microservices AND deploy to AKS simultaneously.
**Why bad:** Too many variables changing at once. Impossible to debug failures.
**Instead:** Phase 2 (Cosmos migration) should work in the monolith first. Verify all tests pass with Cosmos DB before splitting into microservices.

### Anti-Pattern 2: Over-splitting Microservices
**What:** Creating 15 microservices (one per service class).
**Why bad:** Operational overhead of 15 Helm charts, 15 Dockerfiles, 15 health endpoints, 15 HPA configs for 2-5 tenants.
**Instead:** 5 microservices with clear boundaries (gateway, executor, workflow, tool, mcp). Merge, don't proliferate.

### Anti-Pattern 3: Synchronous Cross-Namespace Calls
**What:** Workflow Engine in `tenant-alpha` calling Agent Executor in `tenant-bravo`.
**Why bad:** Cross-tenant communication violates isolation guarantees. NetworkPolicy should prevent this.
**Instead:** All services for a tenant are in the SAME namespace. Cross-tenant operations always go through the API Gateway.

### Anti-Pattern 4: Embedding Unbounded Arrays in Cosmos DB
**What:** Embedding ALL thread messages inside the Thread document.
**Why bad:** Cosmos DB documents have a 2 MB size limit. Active threads with 1000+ messages will hit this.
**Instead:** Embed recent messages (cap at 50), store overflow as separate documents. Or use a dedicated `messages` container.

### Anti-Pattern 5: Re-validating Entra ID Tokens at Every Microservice
**What:** Each microservice independently validates the Entra ID JWT (calling JWKS endpoint).
**Why bad:** Adds ~50-100ms latency per hop. Multiplied across gateway → executor → tool executor = 150-300ms wasted.
**Instead:** Gateway validates once, sets trusted internal headers. NetworkPolicy ensures only gateway can reach tenant services.

---

## 13. Scalability Considerations

| Concern | At 2-5 Tenants (Launch) | At 10-20 Tenants | At 50+ Tenants |
|---------|------------------------|-------------------|----------------|
| AKS cluster | 1 cluster, 2 system + 2-4 workload nodes | 1 cluster, scale workload node pool | Consider multi-cluster or dedicated node pools per tenant |
| Cosmos DB | Serverless (pay-per-RU) | Autoscale (400-4000 RU/s) | Autoscale with higher max; consider multi-region |
| Tenant namespaces | 2-5 namespaces, manual provisioning OK | Automate namespace provisioning | Namespace-per-tenant may need rethinking (cluster limits ~10K namespaces) |
| API Gateway | 2 replicas | 3-5 replicas, HPA | API Management in front of gateway for rate limiting |
| Agent Executor | 1-2 replicas per tenant | HPA per tenant, 2-5 replicas | Dedicated node pools per high-volume tenant |
| Cosmos DB partitions | All data in few logical partitions | Well-distributed; monitor partition sizes | May need hierarchical partition keys |
| Observability | Single Log Analytics workspace | Same workspace, per-tenant KQL filtering | Consider per-tenant workspace if log volume is massive |

---

*Researched: 2026-03-26*
*Sources: Microsoft Azure Architecture Center (multi-tenant guide), AKS microservices reference architecture, Cosmos DB partitioning best practices, existing codebase analysis (all 26 models, 15 services, 22 API routers)*
*Confidence: HIGH — all patterns sourced from Microsoft official documentation and verified against existing codebase structure*
