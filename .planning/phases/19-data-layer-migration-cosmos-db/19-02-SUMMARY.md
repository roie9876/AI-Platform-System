---
phase: 19-data-layer-migration-cosmos-db
plan: 02
status: complete
commits:
  - hash: 360dd37
    message: "feat(19-02): migrate core API routes to Cosmos DB repositories"
  - hash: 3f6a49b
    message: "feat(19-02): migrate remaining API routes to Cosmos DB repositories"
  - hash: c68f036
    message: "feat(19-02): migrate all API routes to Cosmos DB repositories"
requirements_completed: [DATA-03, DATA-04]
---

## What Was Done

Migrated all 19 API route files from SQLAlchemy/AsyncSession to Cosmos DB repository pattern. Every `db: AsyncSession = Depends(get_db)` was removed and replaced with module-level repository instances.

### Files Modified

**Core API Routes (Task 1):**
- `backend/app/api/v1/agents.py` → AgentRepository, AgentConfigVersionRepository
- `backend/app/api/v1/tools.py` → ToolRepository, AgentToolRepository
- `backend/app/api/v1/threads.py` → ThreadRepository, ThreadMessageRepository
- `backend/app/api/v1/chat.py` → AgentRepository, ThreadRepository, ThreadMessageRepository
- `backend/app/api/v1/model_endpoints.py` → ModelEndpointRepository

**Remaining API Routes (Task 2):**
- `backend/app/api/v1/workflows.py` → WorkflowRepository, WorkflowNodeRepository, WorkflowEdgeRepository, WorkflowExecutionRepository, WorkflowNodeExecutionRepository, AgentRepository
- `backend/app/api/v1/evaluations.py` → TestSuiteRepository, TestCaseRepository, EvaluationRunRepository, EvaluationResultRepository
- `backend/app/api/v1/mcp_servers.py` → MCPServerRepository
- `backend/app/api/v1/mcp_discovery.py` → MCPServerRepository, MCPDiscoveredToolRepository
- `backend/app/api/v1/agent_mcp_tools.py` → AgentRepository, MCPDiscoveredToolRepository, AgentMCPToolRepository, MCPServerRepository
- `backend/app/api/v1/marketplace.py` → removed SQLAlchemy, service calls pass tenant_id instead of db
- `backend/app/api/v1/data_sources.py` → DataSourceRepository, AgentDataSourceRepository, DocumentRepository, AgentRepository
- `backend/app/api/v1/memories.py` → AgentRepository, AgentMemoryRepository
- `backend/app/api/v1/catalog.py` → CatalogEntryRepository
- `backend/app/api/v1/azure_connections.py` → AzureConnectionRepository, AgentRepository
- `backend/app/api/v1/azure_subscriptions.py` → AzureSubscriptionRepository
- `backend/app/api/v1/knowledge.py` → AzureConnectionRepository, AzureSubscriptionRepository
- `backend/app/api/v1/observability.py` → ModelPricingRepository, CostAlertRepository
- `backend/app/api/v1/ai_services.py` → AgentRepository, ToolRepository, AgentToolRepository

**Not Modified (already clean):**
- `backend/app/api/v1/auth.py` — no SQLAlchemy imports, no migration needed

### Migration Pattern Applied

1. Removed: `from sqlalchemy`, `from app.core.database import get_db`, `AsyncSession`, SQLAlchemy model imports
2. Added: Repository imports from `app.repositories.*`
3. Instantiated repos at module level (e.g., `agent_repo = AgentRepository()`)
4. Removed `db: AsyncSession = Depends(get_db)` from all endpoint signatures
5. Changed UUID path params to `str`
6. Replaced ORM queries with repo methods (`repo.get()`, `repo.query()`, `repo.create()`, `repo.update()`, `repo.delete()`)
7. Used dict access (`item["field"]`) instead of ORM attribute access (`item.field`)

### Service Call Signature Changes

Services still use old signatures — they will be migrated in Plan 19-03. API routes now pass `tenant_id` instead of `db`:
- `execution_service.execute()` → `tenant_id=tenant_id` (no db)
- `EvaluationService.run_evaluation()` → `(suite_id, tenant_id)`
- `MarketplaceService.*()` → tenant_id as str, no db
- `ObservabilityService.*()` → `(tenant_id, ...)` instead of `(db, UUID(tenant_id), ...)`
- `register_platform_tools()` → `(tenant_id)` instead of `(db)`

### Verification

`grep -rn --include="*.py" "from sqlalchemy|from app.core.database import|AsyncSession|Depends(get_db)" backend/app/api/v1/` returns zero matches.

## Decisions Made

- Module-level repo instantiation (repos are stateless, safe to share)
- UUID params changed to str (Cosmos uses string IDs)
- Service methods get tenant_id instead of db — services to be migrated in Plan 19-03
