---
phase: 30-platform-mcp-servers
plan: 01
subsystem: mcp
tags: [fastmcp, cosmos-db, vector-search, embeddings, azure-openai]

requires:
  - phase: existing
    provides: Cosmos DB client singleton, repository patterns, health endpoints
provides:
  - FastMCP server with 4 memory tools (store, search, store_structured, get_structured)
  - EmbeddingService with in-memory LRU cache (1000 entries)
  - VectorDistance-based semantic search against agent_memories
  - Starlette app combining MCP + health routes
affects: [30-02-platform-config, 30-03-infra]

tech-stack:
  added: [mcp-sdk, fastmcp]
  patterns: [FastMCP tool registration, stateless HTTP transport, embedding cache]

key-files:
  created:
    - backend/microservices/mcp_platform_tools/__init__.py
    - backend/microservices/mcp_platform_tools/main.py
    - backend/microservices/mcp_platform_tools/memory.py
    - backend/microservices/mcp_platform_tools/embedding.py
    - backend/tests/test_mcp_platform_tools.py
  modified: []

key-decisions:
  - "In-memory LRU cache for embeddings (not Cosmos memory_query_cache — deferred to later enhancement)"
  - "Starlette app wraps FastMCP + health routes (MCP at /mcp, health at root)"
  - "Tools receive tenant_id and agent_id as explicit parameters (no session state)"
  - "structured_memories use SHA256(tenant:agent:key) as deterministic document ID for upsert"

patterns-established:
  - "FastMCP tool pattern: @mcp.tool() decorated async functions delegating to module functions"
  - "Memory module uses set_embedding_service() for late binding (set in lifespan)"
  - "Health endpoints as plain Starlette routes alongside MCP mount"

requirements-completed: [MCPSRV-01, MCPSRV-02, MCPSRV-07]

duration: 15min
completed: 2026-04-04
---

# Phase 30, Plan 01: MCP Server Core + Memory Tools Summary

**FastMCP server with 4 memory tools — vector search via Cosmos DB VectorDistance, embedding cache, and health probes**

## What Was Built

- `embedding.py`: Azure OpenAI embedding client with OrderedDict-based LRU cache (max 1000 entries, SHA256 keyed)
- `memory.py`: Four memory tools — `memory_store` (with embedding), `memory_search` (VectorDistance query), `memory_store_structured` (key-value upsert), `memory_get_structured` (filtered retrieval)
- `main.py`: FastMCP server (`stateless_http=True, json_response=True`) mounted at `/mcp` with health endpoints at `/healthz`, `/readyz`, `/startupz`
- 6 unit tests covering store, search, structured memory, embedding cache, and error handling — all passing

## Self-Check: PASSED

- [x] FastMCP server with 4 `@mcp.tool()` registrations
- [x] VectorDistance-based semantic search implemented
- [x] Embedding service with in-memory LRU cache
- [x] Health endpoints for K8s probes
- [x] All 6 unit tests passing
