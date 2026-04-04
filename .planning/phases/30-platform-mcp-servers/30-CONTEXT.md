# Phase 30: Platform MCP Servers - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Give agents access to platform data services as native MCP tools. Three tool domains: (1) persistent memory with vector search backed by Cosmos DB DiskANN, (2) document retrieval via Azure AI Search (deferred — infra added when needed), and (3) group rules and agent configuration from Cosmos DB. Deployed as a single modular MCP server using the Python MCP SDK, auto-injected into OpenClaw CRs on agent deploy. Agents call tools like `memory_store`, `memory_search`, `get_group_instructions` without any UI changes.

</domain>

<decisions>
## Implementation Decisions

### Memory Architecture Depth
- **D-01:** Implement Tier 1 (core) + Tier 2 (high value) capabilities. Tier 1: persistent memory store/retrieve, vector similarity search (semantic recall), conversation context carryover across sessions. Tier 2: entity extraction (people, places, preferences), structured memory (key-value facts), semantic query cache, time-decay relevance scoring.
- **D-02:** Defer Tier 3 (advanced) to a future phase: knowledge graph traversal, episode materialization, procedural memory, cross-encoder reranking, mutation audit trail (event sourcing), tiered retrieval with LLM-driven planner (8 retrieval paths).
- **D-03:** Architecture inspired by ClawMongo's concepts (26 MongoDB capabilities) but implemented natively on Azure Cosmos DB + Azure OpenAI. No ClawMongo code is used — only their architecture, feature design, and lessons learned are ported.

### Memory Data Model
- **D-04:** Hybrid container strategy. `agent_memories` (existing, DiskANN 1536-dim) as the primary store for all vector-searchable content — memories, extracted entities, conversation chunks. Distinguished by a `type` field.
- **D-05:** Add `memory_query_cache` container — TTL-based, no vector index. Caches embedding results for repeated queries to avoid re-embedding identical search terms.
- **D-06:** Add `structured_memories` container — key-value facts (e.g., "user prefers Hebrew", "budget is 10k"). No vector index, queried by exact key lookup within tenant+agent scope.
- **D-07:** All new containers use `/tenant_id` partition key — consistent with entire platform.

### Embedding & Search Strategy
- **D-08:** Cosmos DB DiskANN for all memory search. Embedding model: Azure OpenAI `text-embedding-3-small` (1536 dimensions) — already configured in `agent_memories` container. Pure semantic search for memory recall.
- **D-09:** Azure AI Search for document retrieval (MCPSRV-03) only — provides hybrid search (vector + BM25 keyword) where it matters. AI Search Bicep module and `search_documents()` tool deferred until document indexes are actually needed. MCPSRV-03 is explicitly deferred from this phase.
- **D-10:** No Azure AI Search resource provisioned in this phase. Cosmos DiskANN is sufficient for memory. AI Search added to Bicep when document search is needed.

### MCP Server Architecture
- **D-11:** Single MCP server deployed as one FastAPI service (`mcp-platform-tools`), one Docker image, one K8s Deployment+Service. Agents get one MCP server URL.
- **D-12:** Modular internal organization — separate Python modules per domain: memory module (store, search, entity extraction), platform config module (group rules, agent config). Code organized so splitting into separate services later is straightforward.
- **D-13:** Use the Python MCP SDK (`mcp` package) for proper MCP protocol handling and tool schema generation. Existing MCP servers (`mcp_server_atlassian.py`, etc.) use raw HTTP — this new server adopts the proper SDK as a platform service.
- **D-14:** Deployed in `aiplatform` namespace as a shared service (same pattern as token-proxy, api-gateway). HPA with 2-5 replicas.

### Group Rules & Agent Config Data Source
- **D-15:** Read from Cosmos DB — Cosmos is the source of truth for group rules and agent config. The MCP server reads the same data that `openclaw_service.py` uses to generate OpenClaw CRs.
- **D-16:** No K8s API dependency from the MCP server. No data duplication — platform API writes to Cosmos, `openclaw_service.py` generates CRs from Cosmos data, MCP server reads from Cosmos.
- **D-17:** Existing Cosmos containers are used: `agents` for agent config, agent deploy config for group rules (same data `openclaw_service.py` reads when building CRs).

### MCP Server Auto-Injection
- **D-18:** `openclaw_service.py` already handles `mcp_server_urls` → `mcpServers` in CR config. The platform MCP server URL is auto-added to every agent's MCP server list on deploy/update. Pattern: `http://mcp-platform-tools.aiplatform.svc:8085/mcp`.

### Agent's Discretion
- Memory document schema within `agent_memories` (fields, metadata structure)
- Entity extraction approach (regex-based vs LLM-based for Tier 2)
- Query cache TTL duration and eviction strategy
- Time-decay relevance scoring formula
- Structured memory key naming conventions
- K8s Deployment resource limits, HPA thresholds
- Health check endpoint design
- MCP tool parameter schemas and descriptions
- How tenant_id and agent_id are passed to MCP tools (header, URL path, tool parameter)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Platform MCP Servers — MCPSRV-01 through MCPSRV-07 (note: MCPSRV-03 deferred)

### Architecture
- `docs/v2-architecture-pivot.md` — Architecture pivot overview; MCP servers are Phase 3 in the original pivot doc

### Phase 28 Dependencies
- `.planning/phases/28-infrastructure-audit-foundation/28-CONTEXT.md` — D-08: `token_logs` container; D-09: DiskANN on `agent_memories`

### Phase 29 Reference (similar deployment pattern)
- `.planning/phases/29-token-proxy/29-CONTEXT.md` — Token proxy architecture decisions; similar FastAPI microservice deployment pattern

### Existing MCP Servers (protocol reference)
- `backend/mcp_server_atlassian.py` — Existing raw HTTP MCP server pattern (13 Jira+Confluence tools)
- `backend/mcp_server_github.py` — Existing raw HTTP MCP server pattern (10 GitHub tools)
- `backend/mcp_server_sharepoint.py` — Existing raw HTTP MCP server pattern

### Existing Code (integration points)
- `backend/app/services/openclaw_service.py` — Builds OpenClaw CR, handles `mcp_server_urls` → `mcpServers` injection (line ~1230)
- `backend/app/repositories/base.py` — `CosmosRepository` base class with CRUD + ETag concurrency
- `backend/app/repositories/thread_repo.py` — `AgentMemoryRepository` (line ~46, currently only has `list_by_agent`)
- `infra/modules/cosmos.bicep` — `agent_memories` container with DiskANN vector index definition

### ClawMongo Reference (architecture inspiration)
- `https://github.com/romiluz13/ClawMongo` — README documents 26 MongoDB capabilities, 23 collections, 8 retrieval paths. Used as architecture reference only — no code adopted.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CosmosRepository` base class: CRUD, ETag concurrency, tenant-scoped queries — all new repos extend this
- `AgentMemoryRepository`: exists at `backend/app/repositories/thread_repo.py`, needs extension for vector search
- `openclaw_service.py` MCP injection: reads `mcp_server_urls` config, maps to `mcpServers` in CR — add platform MCP URL here
- K8s manifests pattern: `k8s/base/` has Deployment+Service+HPA templates from token-proxy (Phase 29)

### Established Patterns
- MCP servers: raw HTTP `BaseHTTPRequestHandler` with JSON-RPC (existing), but new server will use Python MCP SDK
- Cosmos repositories: all extend `CosmosRepository`, all use `/tenant_id` partition key
- Microservices: FastAPI apps in `backend/microservices/`, Dockerfiles in `backend/`
- K8s: shared services in `aiplatform` namespace, per-tenant services in `tenant-{slug}` namespace

### Integration Points
- `openclaw_service.py` → add platform MCP server URL to default `mcp_server_urls`
- `cosmos.bicep` → add `memory_query_cache` and `structured_memories` containers
- `k8s/base/kustomization.yaml` → add mcp-platform-tools Deployment, Service, HPA
- `backend/Dockerfile.mcp-platform-tools` → new Dockerfile for the server
- `hooks/postprovision.sh` → add mcp-platform-tools to Docker build list

</code_context>

<specifics>
## Specific Ideas

- ClawMongo's semantic query cache is simple but effective — hash the query text, store the embedding vector, return cached embedding on repeat queries. Saves Azure OpenAI embedding API calls and latency.
- ClawMongo's time-decay: `relevance_score = similarity * decay_factor(age)` — recent memories rank higher. Simple exponential decay with configurable half-life.
- Entity extraction in Tier 2 should start with regex patterns (names, emails, phone numbers, dates) — LLM-based extraction is Tier 3 complexity.
- Structured memories are write-heavy, read-light: agent stores "user preference: X" facts, reads them on context assembly. Simple key-value with upsert semantics.

</specifics>

<deferred>
## Deferred Ideas

### Tier 3 Memory Capabilities (future phase)
- Knowledge graph traversal (entity relationships with graph queries)
- Episode materialization (grouping related memories into narrative summaries)
- Procedural memory (how-to sequences learned from agent interactions)
- Cross-encoder reranking (second-pass relevance scoring on search results)
- Mutation audit trail / event sourcing (immutable log of all memory changes)
- Tiered retrieval with LLM-driven planner (8 retrieval paths, planner selects best)

### Azure AI Search (MCPSRV-03)
- `search_documents(query, index)` deferred — requires AI Search resource provisioning
- AI Search Bicep module (`infra/modules/aisearch.bicep`) — add when document search is needed
- Hybrid search (vector + BM25) for document retrieval

### MCP Server Splitting
- If single server becomes too large, split into `mcp-memory` and `mcp-platform` services — modular code design supports this

</deferred>

---

*Phase: 30-platform-mcp-servers*
*Context gathered: 2026-04-04*
