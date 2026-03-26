---
phase: 19-data-layer-migration-cosmos-db
plan: 01
subsystem: database
tags: [cosmos-db, azure, repository-pattern, async]

requires:
  - phase: 17-infrastructure-foundation-bicep-iac
    provides: Cosmos DB infrastructure via Bicep
  - phase: 18-authentication-migration-entra-id
    provides: DefaultAzureCredential and azure-identity

provides:
  - CosmosClient singleton with DefaultAzureCredential
  - Base CosmosRepository with CRUD + ETag optimistic concurrency
  - 13+ repository implementations for all model groups
  - Tenant-isolated data access via partition key

affects: [api-routes, services, data-migration]

tech-stack:
  added: [azure-cosmos>=4.7.0]
  patterns: [repository-pattern, partition-key-isolation, etag-concurrency, async-cosmos-sdk]

key-files:
  created:
    - backend/app/repositories/__init__.py
    - backend/app/repositories/cosmos_client.py
    - backend/app/repositories/base.py
    - backend/app/repositories/agent_repo.py
    - backend/app/repositories/tool_repo.py
    - backend/app/repositories/thread_repo.py
    - backend/app/repositories/workflow_repo.py
    - backend/app/repositories/evaluation_repo.py
    - backend/app/repositories/marketplace_repo.py
    - backend/app/repositories/mcp_repo.py
    - backend/app/repositories/observability_repo.py
    - backend/app/repositories/data_source_repo.py
    - backend/app/repositories/tenant_repo.py
    - backend/app/repositories/user_repo.py
    - backend/app/repositories/config_repo.py
  modified:
    - backend/requirements.txt
    - backend/app/core/config.py

key-decisions:
  - "Singleton CosmosClient with lazy initialization — avoids connection overhead on import"
  - "ETag-based optimistic concurrency via MatchConditions.IfNotModified on all updates"
  - "tenant_id as first parameter on every repository method for partition key isolation"
  - "Cross-partition query for TenantRepository.get_by_slug since slug is not partition key"

patterns-established:
  - "Repository pattern: each model group gets a CosmosRepository subclass with container_name"
  - "Partition key convention: all containers use /tenant_id, tenants use self-referential tenant_id"
  - "Query pattern: parameterized queries with @-prefixed names and partition_key kwarg"

requirements-completed: [DATA-01, DATA-02, DATA-06, DATA-07, DATA-08]

duration: 8min
completed: 2026-03-26
---

# Plan 19-01: Cosmos DB Repository Foundation Summary

**Created complete data access layer with 15 repository files, CosmosClient singleton, and ETag-based optimistic concurrency — replacing SQLAlchemy ORM pattern.**

## Performance

- **Tasks:** 2/2 completed
- **Files created:** 15
- **Files modified:** 2

## Accomplishments

1. **CosmosClient singleton** — Lazy-initialized async client using `DefaultAzureCredential` with proper shutdown cleanup
2. **Base CosmosRepository** — CRUD operations (create, get, query, list_all, update, delete, upsert, count) with `tenant_id` partition key isolation and ETag optimistic concurrency
3. **13+ repository implementations** — AgentRepository, ToolRepository, ThreadRepository, WorkflowRepository, EvaluationRepository, MarketplaceRepository, MCPRepository, ObservabilityRepository, ConfigRepository, DataSourceRepository, TenantRepository, UserRepository with domain-specific query methods
4. **Config settings** — Added `COSMOS_ENDPOINT` and `COSMOS_DATABASE` to Settings class

## Self-Check: PASSED

- All repository classes extend CosmosRepository
- Every data access method has tenant_id as first parameter  
- ETag concurrency via MatchConditions.IfNotModified in base update
- All imports resolve without errors
- azure-cosmos>=4.7.0 added to requirements.txt
