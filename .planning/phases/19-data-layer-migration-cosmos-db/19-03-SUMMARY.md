---
phase: 19-data-layer-migration-cosmos-db
plan: 03
status: complete
commits:
  - hash: 50c1d66
    message: "feat(19-03): migrate all service files to Cosmos DB repositories"
  - hash: dff5e97
    message: "feat(19-03): add migration script and deprecate SQLAlchemy models"
---

## What Was Done

Migrated all 12 service files from SQLAlchemy/AsyncSession to Cosmos DB repositories. Wired CosmosClient lifecycle into app startup/shutdown. Deprecated SQLAlchemy models. Created PostgreSQL → Cosmos DB data migration script.

### Task 1: Service Layer Migration

**Files Modified:**

- `backend/app/main.py` — Added `lifespan` context manager that calls `close_cosmos_client()` on shutdown
- `backend/app/core/database.py` — Added DEPRECATED comment; SQLAlchemy code retained for migration script use only
- `backend/app/services/platform_tools.py` → ToolRepository
- `backend/app/services/mcp_discovery.py` → MCPServerRepository, MCPDiscoveredToolRepository
- `backend/app/services/memory_service.py` → AgentMemoryRepository, ThreadMessageRepository
- `backend/app/services/marketplace_service.py` → AgentTemplateRepository, ToolTemplateRepository, AgentRepository, ToolRepository, AgentToolRepository
- `backend/app/services/evaluation_service.py` → TestSuiteRepository, TestCaseRepository, EvaluationRunRepository, EvaluationResultRepository, AgentRepository
- `backend/app/services/rag_service.py` → DocumentRepository, DocumentChunkRepository, AgentDataSourceRepository, AzureConnectionRepository, AzureSubscriptionRepository
- `backend/app/services/observability_service.py` → ExecutionLogRepository, ModelPricingRepository, CostAlertRepository, AgentRepository (complete rewrite: PostgreSQL PERCENTILE_CONT, date_trunc, JOINs replaced with client-side aggregation)
- `backend/app/services/workflow_engine.py` → WorkflowRepository, WorkflowNodeRepository, WorkflowEdgeRepository, WorkflowExecutionRepository, WorkflowNodeExecutionRepository, AgentRepository, ThreadRepository
- `backend/app/services/agent_execution.py` → AgentRepository, ToolRepository, AgentToolRepository, MCPServerRepository, MCPDiscoveredToolRepository, AgentMCPToolRepository, ExecutionLogRepository, ModelEndpointRepository, ThreadRepository, ThreadMessageRepository (11 repositories)
- `backend/app/services/model_abstraction.py` → Changed ModelEndpoint type hints to `dict`, all dot notation to `.get()` access

### Task 2: Deprecation & Migration Tooling

**Files Modified/Created:**

- `backend/app/models/__init__.py` — Added DEPRECATED comment (models preserved for migration script only)
- `backend/scripts/__init__.py` — Created package
- `backend/scripts/migrate_to_cosmos.py` — Full migration script with:
  - `serialize_row()` — UUID→str, datetime→ISO, JSONB preserved
  - `migrate_table()` — Reads all rows via SQLAlchemy, upserts to Cosmos
  - 35 model→container mappings (all models)
  - `--database-url` and `--dry-run` CLI arguments
  - Progress logging and error summary

### Key Technical Decisions

1. **Observability client-side aggregation**: Cosmos DB lacks PERCENTILE_CONT, date_trunc, and cross-container JOINs. All aggregation (percentiles, time bucketing, cost computation) now happens in Python after fetching raw data.
2. **Denormalized execution logs**: ExecutionLog documents store `tenant_id` and `agent_id` directly (not via thread JOIN) for efficient partition-key queries.
3. **Stateless repos for parallelism**: `workflow_engine.py` parallel node execution works because repos are singleton instances — no session sharing issues.
4. **model_abstraction.py dict access**: Since ModelEndpoint objects are now dicts from Cosmos, all attribute access changed to `.get()` pattern.

### Verification

- `grep -rn "from sqlalchemy\|from app.core.database\|AsyncSession" backend/app/services/ backend/app/api/` returns zero matches
- `grep -n "close_cosmos_client\|lifespan" backend/app/main.py` confirms lifecycle wiring
- All services use module-level repository instances, no `db: AsyncSession` parameters remain
