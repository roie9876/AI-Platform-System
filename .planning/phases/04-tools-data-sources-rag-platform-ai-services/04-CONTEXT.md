# Phase 4: Tools, Data Sources, RAG & Platform AI Services - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the tool registry with Docker sandbox execution, data source management (file upload + URL scraping), the RAG pipeline via Azure AI Search, and platform-managed Azure AI Services exposed as toggleable tools. Agents can invoke registered custom tools in isolated Docker containers, ingest documents and scraped URLs into a RAG index for contextual retrieval, and leverage all 7 Azure AI Services (search, speech, vision, document intelligence, content safety, language, translation) as first-class platform tools.

This phase does NOT include memory management, thread persistence, orchestration/workflows, policy engine, evaluation, cost observability, or marketplace features — those belong in Phases 5-8.

</domain>

<decisions>
## Implementation Decisions

### Tool Execution Model
- **D-01:** Docker container sandbox for tool execution. Each tool invocation spins up a short-lived Docker container with resource limits (CPU, memory, network) and configurable timeout. Tool inputs are validated against JSON Schema before execution. Tool outputs are captured, sanitized, and returned to the agent execution loop. This provides true isolation and security for arbitrary tool code.
- **D-02:** Tool registration via `/api/v1/tools` API. Tools are registered with name, description, JSON Schema for input/output, and a Docker image reference (pre-built or platform-provided base image). Tools are tenant-scoped.
- **D-03:** Tool attachment is a many-to-many relationship between agents and tools. Agents can have multiple tools; tools can be attached to multiple agents within a tenant.

### RAG Pipeline & Data Sources
- **D-04:** Full Azure AI Search integration for RAG. The platform connects to a real Azure AI Search instance for hybrid (vector + keyword) search. Document ingestion pipeline: upload/scrape → chunk → embed (via model endpoint) → index in Azure AI Search → retrieve at agent execution time.
- **D-05:** Data source types: file upload (PDF, TXT, MD, DOCX) + URL scraping. File uploads are stored locally (or Azure Blob in production). URL scraping uses httpx to fetch page content and extract text. Both feed into the same chunking → embedding → indexing pipeline.
- **D-06:** Credential storage continues using Fernet encryption locally (existing `secret_store.py`). The Key Vault interface defined in Phase 3 (D-07) remains the production target — no changes needed for PoC.

### Platform AI Services
- **D-07:** Full 7-service Azure AI Services adapter. Build adapters for: Azure AI Search, Speech, Vision, Document Intelligence, Content Safety, Language, and Translation. Each exposed as a toggleable platform tool per agent.
- **D-08:** Platform Tool Adapter layer provides a unified interface — each Azure AI Service is wrapped as a tool with JSON Schema input/output. Authentication via Managed Identity (production) or API key (local dev). Users never handle credentials for platform tools.
- **D-09:** Platform tools are distinct from custom tools — they are system-registered (not tenant-scoped), always available for toggle, and metered separately. Custom tools are tenant-owned and run in Docker containers.

### Agent Execution Integration
- **D-10:** The existing `AgentExecutionService` will be extended to support the tool-calling loop: model requests tool call → validate inputs → execute tool (Docker for custom, direct call for platform) → return result to model → continue until final response. This follows the sequence diagram in the HLD.
- **D-11:** RAG context injection happens before the model call. When an agent has connected data sources, the platform retrieves relevant chunks from Azure AI Search based on the user message and injects them into the system prompt or as a separate context message.

### Agent's Discretion
- **D-12:** Chunking strategy for RAG documents — agent decides chunk size, overlap, and splitting approach (sentence-based, token-based, or recursive character splitting).
- **D-13:** Docker container lifecycle management — agent decides container pooling/caching vs fresh container per invocation, cleanup strategy, and logging approach.
- **D-14:** UI layout for tools and data source management pages — agent decides the layout, following the established card-based pattern from Phase 3.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture
- `docs/architecture/HLD-ARCHITECTURE.md` — Full HLD with:
  - §"Tool Execution Sandbox" (line ~167) — Isolation, input validation, timeout, output capture
  - §"Tool Management" (line ~291) — Tool Registry API, attachment service, sandbox runtime, marketplace
  - §"Data Sources & RAG" (line ~303) — Data Source Registry, credential store, RAG pipeline, context injection
  - §"AI Services Integration" (line ~397) — Platform tool adapter, managed auth, usage metering
  - §"Azure AI Search" (line ~245) — Hybrid search, document ingestion, memory integration
  - §"Agent Execution Engine" (line ~144) — Core loop with tool call flow (see sequence diagram line ~196)

### Project Context
- `.planning/PROJECT.md` — Key decisions: custom execution loop + SK, Azure AI Search for RAG, platform-managed AI Services (Foundry-style)
- `.planning/REQUIREMENTS.md` — Requirements TOOL-01/02/03, DATA-01/02/03, AISV-01/02
- `.planning/ROADMAP.md` — Phase 4 success criteria (8 items), dependency on Phase 3

### Prior Phase Context
- `.planning/phases/03-agent-core-model-abstraction/03-CONTEXT.md` — Decisions D-06/D-07 (dual auth: Entra ID + API key, Key Vault for secrets), D-08/D-09 (agent discretion patterns)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/models/base.py` — `Base`, `UUIDMixin`, `TimestampMixin` mixins for new models (Tool, DataSource, AgentTool join table)
- `backend/app/models/agent.py` — Agent model with `tenant_id`, `model_endpoint_id`, `status` — needs tool/data-source relationships
- `backend/app/services/agent_execution.py` — `AgentExecutionService` with SSE streaming — needs tool-call loop extension
- `backend/app/services/model_abstraction.py` — `ModelAbstractionService` with LiteLLM — already handles `complete_with_fallback`, needs tool-call message format support
- `backend/app/services/secret_store.py` — Fernet encrypt/decrypt for API keys — reuse for data source credentials
- `backend/app/api/v1/schemas.py` — Pydantic schema patterns with `model_config = {"from_attributes": True}`
- `backend/app/api/v1/router.py` — Router registration pattern for new tool/data-source/ai-service routes
- `backend/app/middleware/tenant.py` — `get_tenant_id()` dependency for tenant-scoped queries
- `frontend/src/lib/api.ts` — `apiFetch<T>()` utility with 204 handling
- `frontend/src/app/dashboard/layout.tsx` — Dashboard layout for new sidebar entries (Tools, Data Sources, AI Services)

### Established Patterns
- **Backend models:** SQLAlchemy declarative with `UUIDMixin` + `TimestampMixin`, `tenant_id` FK, indexed
- **API routes:** FastAPI router at `/api/v1/{domain}`, Pydantic request/response schemas
- **Frontend pages:** Next.js app router under `/dashboard/{feature}`, card-based layouts, `apiFetch()` for data
- **Auth flow:** JWT httpOnly cookies, tenant middleware auto-filters

### Integration Points
- New routes: `/api/v1/tools`, `/api/v1/data-sources`, `/api/v1/ai-services`
- New dashboard pages: `/dashboard/tools`, `/dashboard/data-sources`, `/dashboard/ai-services`
- Agent execution loop extension for tool calls (LiteLLM already supports `tools` parameter in chat completions)
- Docker SDK (`docker` Python package) for container sandbox management
- Azure AI Search SDK (`azure-search-documents`) for RAG indexing and retrieval
- Azure AI Services SDKs for platform tool adapters
- `httpx` for URL scraping in data source ingestion
- Document parsing libraries for file upload handling (e.g., `pypdf`, `python-docx`)

</code_context>

<specifics>
## Specific Ideas

- **LiteLLM tool calling:** LiteLLM already supports the OpenAI tool-calling format (`tools` parameter in chat completions). The model returns `tool_calls` in the response, which the execution loop processes. This means the model abstraction layer requires minimal changes — mostly message format handling.
- **Azure AI Search local dev:** For local development, consider using the Azure AI Search emulator or connecting to a dev-tier search service. The SDK (`azure-search-documents`) works the same regardless.
- **Platform tools as "always available":** Platform AI Services tools should appear in a separate section of the agent config UI — toggleable switches rather than the attach/detach flow used for custom tools. This mirrors Azure AI Foundry's pattern.
- **Docker-in-Docker consideration:** Since the backend runs in Docker (docker-compose), tool sandbox containers require Docker-in-Docker or mounting the host Docker socket. The compose file needs `volumes: ["/var/run/docker.sock:/var/run/docker.sock"]` for the backend service.

</specifics>

<deferred>
## Deferred Ideas

- **TOOL-04 (Tool Marketplace):** Deferred to Phase 8 per ROADMAP.md. Not in scope for Phase 4.
- **AISV-03 (AI Service usage metering):** Deferred to Phase 8 (Cost & Token Observability). Phase 4 builds the adapter framework but metering integration comes later.
- **Azure Blob Storage for file uploads:** Production file storage via Azure Blob. For PoC, local filesystem storage is sufficient.
- **Advanced URL scraping:** JavaScript-rendered page scraping (Playwright/Selenium). Phase 4 uses basic httpx text extraction.

</deferred>
