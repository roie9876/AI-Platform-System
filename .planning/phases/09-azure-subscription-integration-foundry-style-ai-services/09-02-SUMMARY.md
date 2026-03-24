---
phase: 09-azure-subscription-integration-foundry-style-ai-services
plan: 02
status: complete
started: 2025-03-24
completed: 2025-03-24
commits: [bd4716e, 134ecd8]
---

## Summary

Created connection management, tool catalog, and knowledge integration APIs for the Azure Foundry-style platform.

## Artifacts Created/Modified

### Task 1: Connection Management & Catalog APIs
- **backend/app/api/v1/azure_connections.py** — 5 endpoints: POST/GET/DELETE/PATCH connections, POST health-check. Encrypts credentials via `encrypt_api_key()`.
- **backend/app/api/v1/catalog.py** — 3 endpoints: GET/POST catalog entries, GET by ID. Returns builtin (tenant_id IS NULL) + tenant custom entries.
- **backend/app/api/v1/schemas.py** — Added AzureConnectionCreate/Update/Response, CatalogEntryCreate/Response, SearchIndex, SearchIndexListResponse, SelectIndexesRequest, AgentKnowledgeIndexInfo, AgentKnowledgeResponse schemas.
- **backend/app/api/v1/router.py** — Registered azure_connections_router (/azure) and catalog_router (/catalog).

### Task 2: Knowledge API & RAG Integration
- **backend/app/api/v1/knowledge.py** — 3 endpoints:
  - GET /knowledge/connections/{id}/indexes — lists AI Search indexes via ARM API
  - POST /knowledge/connections/{id}/indexes — selects indexes for RAG (updates connection.config)
  - GET /knowledge/agents/{id}/indexes — lists selected indexes for an agent
- **backend/app/api/v1/router.py** — Added knowledge_router (/knowledge).
- **backend/app/services/rag_service.py** — Added `retrieve_from_azure_search()` method that queries Azure AI Search indexes for connected agents, sorts by score, and returns top_k results.

## Key Decisions
- Used `Optional[str]` instead of `str | None` for Python 3.9 compatibility
- Connection credentials encrypted via Fernet (existing `encrypt_api_key`/`decrypt_api_key`)
- Catalog returns both builtin entries (tenant_id IS NULL) and tenant-specific custom entries
- Azure Search retrieval uses Bearer token auth from subscription, not API keys
- Results from multiple indexes are merged and sorted by `@search.score`

## Patterns Established
- Connection management pattern: agent_id + azure_subscription_id + encrypted credentials
- Knowledge index selection stored in `connection.config["selected_indexes"]`
- Azure Search REST API queries at `{endpoint}/indexes/{name}/docs/search`
