# Phase 19 Research: Data Layer Migration (Cosmos DB)

## RESEARCH COMPLETE

**Phase:** 19 — Data Layer Migration (Cosmos DB)
**Date:** 2026-03-26
**Scope:** Replace SQLAlchemy/PostgreSQL with Azure Cosmos DB NoSQL SDK across all 13+ models, 19 API route files, and 4 service files

## 1. Current Architecture Analysis

### SQLAlchemy Models (25 model classes across 22 files)

| Model | Table | Has tenant_id | ForeignKeys | Notes |
|-------|-------|---------------|-------------|-------|
| Tenant | tenants | N/A (IS tenant) | None | Root entity |
| User | users | Yes | tenants | Auth entity |
| RefreshToken | refresh_tokens | Yes | users | Deprecated (Entra ID) |
| Agent | agents | Yes | tenants, model_endpoints | Core entity |
| AgentConfigVersion | agent_config_versions | Yes | agents | Versioning |
| Tool | tools | Yes (nullable) | tenants | Platform tools have null tenant |
| AgentTool | agent_tools | No (via agent) | agents, tools | Junction table |
| DataSource | data_sources | Yes | agents, tenants | RAG data |
| AgentDataSource | agent_data_sources | No (via agent) | agents, data_sources | Junction table |
| Document | documents | Yes | data_sources, tenants | RAG docs |
| DocumentChunk | document_chunks | No | documents | Embed in parent |
| AzureSubscription | azure_subscriptions | Yes | tenants | Azure integration |
| AzureConnection | azure_connections | Yes | agents, azure_subscriptions | Azure resources |
| CatalogEntry | catalog_entries | Yes | tenants | Agent catalog |
| Thread | threads | Yes | agents, users, tenants | Chat threads |
| ThreadMessage | thread_messages | Yes | threads, tenants | Chat messages |
| AgentMemory | agent_memories | Yes | agents, tenants | Long-term memory |
| ExecutionLog | execution_logs | Yes | agents, threads, tenants | Observability |
| Workflow | workflows | Yes | tenants, users | Orchestration |
| WorkflowNode | workflow_nodes | No | workflows, agents | Embed in workflow |
| WorkflowEdge | workflow_edges | No | workflows | Embed in workflow |
| WorkflowExecution | workflow_executions | Yes | workflows, tenants | Execution tracking |
| WorkflowNodeExecution | workflow_node_executions | No | workflow_executions | Embed in parent |
| ModelPricing | model_pricing | Yes | tenants | Cost config |
| CostAlert | cost_alerts | Yes | tenants | Cost alerts |
| TestSuite | test_suites | Yes | agents, tenants | Evaluation |
| TestCase | test_cases | No | test_suites | Embed in suite |
| EvaluationRun | evaluation_runs | Yes | test_suites, agents | Eval runs |
| EvaluationResult | evaluation_results | No | evaluation_runs, test_cases | Embed in run |
| AgentTemplate | agent_templates | Yes (nullable) | tenants | Marketplace |
| ToolTemplate | tool_templates | Yes (nullable) | tenants | Marketplace |
| MCPServer | mcp_servers | Yes | tenants | MCP registry |
| MCPDiscoveredTool | mcp_discovered_tools | No | mcp_servers | MCP tools |
| AgentMCPTool | agent_mcp_tools | No | agents, mcp_discovered_tools | Junction |

### Data Access Patterns

**API Route files (19 files using SQLAlchemy):**
- All use `db: AsyncSession = Depends(get_db)` for session injection
- All filter by `tenant_id` from `get_tenant_id()` middleware
- Common patterns: `select(Model).where(Model.tenant_id == tenant_id)`, `db.add()`, `db.flush()`, `db.refresh()`, `db.execute()`, `db.delete()`

**Service files (3 files using AsyncSession):**
- `agent_execution.py` — Heavy reads (agent, tools, threads, messages), writes (execution logs, messages)
- `evaluation_service.py` — CRUD for test suites, runs, results
- `marketplace_service.py` — Template publishing, instantiation

### Cosmos DB Infrastructure (from Phase 17)

- **Account:** Serverless NoSQL (pay-per-request)
- **Database:** `aiplatform`
- **Containers:** 35 containers mapped 1:1 from SQLAlchemy table names
- **Partition key:** `/tenant_id` on all containers
- **Consistency:** Session level

## 2. Migration Strategy

### Repository Pattern

Create a `backend/app/repositories/` layer that abstracts Cosmos DB operations:

```
backend/app/repositories/
├── __init__.py
├── base.py          # CosmosRepository base class
├── cosmos_client.py # Singleton CosmosClient + container cache
├── agent_repo.py
├── tool_repo.py
├── thread_repo.py
├── workflow_repo.py
├── evaluation_repo.py
├── marketplace_repo.py
├── mcp_repo.py
├── observability_repo.py
└── data_source_repo.py
```

### Base Repository Design

```python
# base.py pattern
class CosmosRepository:
    def __init__(self, container_name: str):
        self.container_name = container_name

    async def get_container(self):
        return get_cosmos_client().get_database_client("aiplatform").get_container_client(self.container_name)

    async def create(self, tenant_id: str, item: dict) -> dict:
        container = await self.get_container()
        item["tenant_id"] = tenant_id
        item["id"] = item.get("id", str(uuid4()))
        return await container.create_item(item)

    async def get(self, tenant_id: str, item_id: str) -> dict | None:
        container = await self.get_container()
        try:
            return await container.read_item(item=item_id, partition_key=tenant_id)
        except CosmosResourceNotFoundError:
            return None

    async def query(self, tenant_id: str, query: str, params: list = None) -> list:
        container = await self.get_container()
        items = container.query_items(
            query=query, parameters=params, partition_key=tenant_id
        )
        return [item async for item in items]

    async def update(self, tenant_id: str, item_id: str, item: dict) -> dict:
        container = await self.get_container()
        return await container.replace_item(item=item_id, body=item)

    async def delete(self, tenant_id: str, item_id: str):
        container = await self.get_container()
        await container.delete_item(item=item_id, partition_key=tenant_id)
```

### SDK Choice: `azure-cosmos` (async)

- Package: `azure-cosmos>=4.7.0`
- Async support via `aio` submodule
- Singleton `CosmosClient` per best practices (`sdk-singleton-client`)
- DefaultAzureCredential from Phase 18 for auth (no connection strings)

### Denormalization Decisions

**Embed (child in parent document):**
- WorkflowNode, WorkflowEdge → embed in Workflow document
- DocumentChunk → embed in Document document (within 2MB limit)
- TestCase → embed in TestSuite document (within 2MB limit)
- WorkflowNodeExecution → embed in WorkflowExecution document
- EvaluationResult → embed in EvaluationRun document (if <2MB)
- MCPDiscoveredTool → keep separate (can be many per server)

**Keep separate containers (reference by ID):**
- Agent, Tool, DataSource, Thread, ThreadMessage — independent access patterns
- AgentTool, AgentDataSource, AgentMCPTool — junction docs in own containers

### ETag-Based Optimistic Concurrency

```python
async def update_with_etag(self, tenant_id: str, item_id: str, item: dict, etag: str):
    container = await self.get_container()
    return await container.replace_item(
        item=item_id,
        body=item,
        etag=etag,
        match_condition=MatchConditions.IfNotModified
    )
```

### Unique Key Constraints

Per-container unique keys (within partition):
- `tenants`: `/slug`
- `agents`: `/name` (within tenant)
- `agent_tools`: `/agent_id` + `/tool_id` composite
- `mcp_servers`: `/name` (within tenant)

Note: Cosmos DB unique keys are set at container creation. The 35 containers from Phase 17 were created without unique keys. Either:
1. Recreate containers with unique keys (breaking change)
2. Enforce uniqueness at application layer via point read before insert

**Recommendation:** Enforce at application layer — simpler, no infra changes needed.

### Migration Tooling

Data migration from PostgreSQL → Cosmos DB:
- Python script using SQLAlchemy to read + Cosmos SDK to write
- Batch inserts using `container.create_item()` in parallel
- Transform UUID columns to string, datetime to ISO 8601 strings
- Add `_type` discriminator field for polymorphic containers

## 3. Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| SDK | `azure-cosmos` async | Official Microsoft SDK, async support |
| Auth | DefaultAzureCredential | Consistent with Phase 18 |
| Repository pattern | Yes | Clean abstraction, testable, swappable |
| Denormalization | Selective embedding | Keep independent entities separate for flexible queries |
| Uniqueness | Application-layer | Avoid container recreation |
| Concurrency | ETag-based | Native Cosmos DB optimistic locking |
| Connection | Singleton CosmosClient | Best practice per SDK guidelines |
| Partition key | `/tenant_id` everywhere | Already configured in Phase 17 |
| ID strategy | UUID v4 as string | Compatible with existing IDs |

## 4. Risk Analysis

| Risk | Impact | Mitigation |
|------|--------|------------|
| 2MB document limit | HIGH for embedded collections | Monitor document sizes, split if needed |
| No JOINs | MEDIUM — cross-container queries | Denormalize or do application-level joins |
| 35 containers | LOW — serverless = no idle cost | Already provisioned in Phase 17 |
| RU cost surprises | LOW — serverless with dev workload | Monitor via Azure Portal |
| Missing unique keys at container level | LOW | Application-layer enforcement |

## 5. Dependencies

- **Phase 17:** Cosmos DB account + containers (COMPLETE)
- **Phase 18:** DefaultAzureCredential + tenant_id from auth (COMPLETE)
- **`azure-cosmos` package:** Must add to requirements.txt
- **`azure-identity` package:** Already added in Phase 18

## 6. Migration Order

1. **Foundation:** CosmosClient singleton, base repository, dependency injection
2. **Core models:** Repository implementations for all 13+ model groups
3. **API migration:** Rewrite all 19 API route files to use repositories instead of SQLAlchemy
4. **Service migration:** Rewrite 3 service files (agent_execution, evaluation, marketplace)
5. **Cleanup:** Remove SQLAlchemy models, database.py, alembic, SQLAlchemy from requirements
6. **Migration script:** Tool to move data from PostgreSQL to Cosmos DB

---
*Phase: 19-data-layer-migration-cosmos-db*
*Research completed: 2026-03-26*
