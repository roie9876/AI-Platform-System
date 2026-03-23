---
phase: 04-tools-data-sources-rag-platform-ai-services
plan: 01
subsystem: database, api
tags: [sqlalchemy, fastapi, alembic, postgresql, jsonb]

requires:
  - phase: 01-foundation
    provides: Base models, tenant middleware, auth, secret_store encryption

provides:
  - Tool, AgentTool, DataSource, AgentDataSource, Document, DocumentChunk SQLAlchemy models
  - Alembic migration 003 creating 6 new tables
  - CRUD API endpoints for tools and data sources
  - Agent-tool and agent-data-source attachment endpoints
  - Pydantic schemas for tool and data source requests/responses

affects: [04-02-tool-execution, 04-03-rag-pipeline, 04-04-platform-tools, 04-05-frontend]

tech-stack:
  added: []
  patterns: [JSONB columns for flexible schemas, credential encryption via secret_store]

key-files:
  created:
    - backend/app/models/tool.py
    - backend/app/models/data_source.py
    - backend/app/models/document.py
    - backend/alembic/versions/003_tools_data_sources_schema.py
    - backend/app/api/v1/tools.py
    - backend/app/api/v1/data_sources.py
  modified:
    - backend/app/models/__init__.py
    - backend/app/api/v1/schemas.py
    - backend/app/api/v1/router.py

key-decisions:
  - "Used JSONB for embedding storage (pgvector can be added later without schema change)"
  - "Renamed DocumentChunk.metadata to chunk_metadata (Python attr) mapped to 'metadata' column to avoid SQLAlchemy reserved name conflict"
  - "Platform tools have nullable tenant_id (system-scoped), tenant tools are tenant-scoped"
  - "Credentials encrypted at rest using existing Fernet encryption from secret_store"

patterns-established:
  - "Agent attachment pattern: separate router (agent_tools_router) for /{agent_id}/tools endpoints"
  - "Platform vs tenant tool visibility: list shows both tenant-owned and platform tools"

requirements-completed: [TOOL-01, TOOL-02, DATA-01, DATA-03]

duration: 8min
completed: 2026-03-23
---

# Plan 04-01: Models, Migration & CRUD APIs Summary

**Created 6 database models for tools/data sources/documents with full CRUD API endpoints and tenant-scoped access control.**

## Performance

- **Tasks:** 2 completed
- **Files created:** 6
- **Files modified:** 3

## Accomplishments
- Created Tool, AgentTool, DataSource, AgentDataSource, Document, DocumentChunk models with proper constraints
- Built Alembic migration 003 creating all 6 tables with indexes and foreign keys
- Implemented full CRUD + attachment APIs for tools and data sources with tenant isolation
- Added credential encryption for data source secrets using existing Fernet encryption

## Task Commits

1. **Task 1: Create database models and Alembic migration** - `6dfaaaa` (feat)
2. **Task 2: Create Tool and DataSource CRUD API endpoints with Pydantic schemas** - `cf57fd0` (feat)

## Files Created/Modified
- `backend/app/models/tool.py` - Tool and AgentTool SQLAlchemy models
- `backend/app/models/data_source.py` - DataSource and AgentDataSource models
- `backend/app/models/document.py` - Document and DocumentChunk models (for RAG)
- `backend/alembic/versions/003_tools_data_sources_schema.py` - Migration for 6 tables
- `backend/app/api/v1/tools.py` - Tool CRUD + agent attachment endpoints
- `backend/app/api/v1/data_sources.py` - DataSource CRUD + agent attachment endpoints
- `backend/app/api/v1/schemas.py` - Added 12 Pydantic schemas for tools and data sources
- `backend/app/api/v1/router.py` - Registered tools and data sources routers
- `backend/app/models/__init__.py` - Added imports for all 6 new models

## Deviations from Plan

### Auto-fixed Issues

**1. SQLAlchemy reserved attribute name**
- **Found during:** Task 1 (models)
- **Issue:** `metadata` is reserved in SQLAlchemy's DeclarativeBase
- **Fix:** Renamed Python attribute to `chunk_metadata` with `Column("metadata", ...)` to preserve DB column name
- **Verification:** All models import successfully

## Issues Encountered
None beyond the metadata naming fix above.
