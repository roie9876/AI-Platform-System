# Phase 3: Agent Core & Model Abstraction - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the agent CRUD UI, model endpoint registry, model abstraction layer, and basic agent conversations with streaming. Users can create agents through a card-based dashboard, register model endpoints (Azure OpenAI via Entra ID, others via API key), configure agents (system prompt, model, temperature, max tokens), version agent configurations, and have real-time streaming conversations with agents through an AI Foundry-style playground interface.

This phase does NOT include tools, data sources, RAG, memory management, orchestration, or policy engine — those belong in Phases 4-7.

</domain>

<decisions>
## Implementation Decisions

### Agent Management UI
- **D-01:** Card-based dashboard layout for the agent list page. Each agent displayed as a card with key info (name, status, model, last active). Cards are clickable to enter the agent detail/chat view.
- **D-02:** Agent creation via a clean form (single-page, not a multi-step wizard). Fields: name, system prompt, model endpoint selection, temperature, max tokens, timeout.

### Chat / Conversation Interface
- **D-03:** AI Foundry playground-style layout — sidebar with conversation history on the left, main chat area in the center, and a configuration/parameters panel on the right side.
- **D-04:** Config panel visible alongside chat (Foundry-style). Users can tweak temperature, max tokens, and system prompt while chatting — changes apply to the next message, not retroactively.
- **D-05:** Model endpoint selector at the top of the chat area (like Foundry's deployment picker). Users can switch which model endpoint the agent uses mid-conversation.

### Model Endpoint Authentication
- **D-06:** Dual auth strategy per provider type:
  - **Azure OpenAI endpoints** → Entra ID / Managed Identity authentication (no API keys stored). Platform authenticates to Azure OpenAI using the app's Managed Identity.
  - **Non-Azure providers** (OpenAI direct, Anthropic, local models, etc.) → API keys required, stored securely in Azure Key Vault.
- **D-07:** Azure Key Vault for all secret storage (non-Azure provider API keys). Backend retrieves keys at request time via Managed Identity — keys never exposed to the frontend or stored in the database.

### Agent's Discretion
- **D-08:** Agent config versioning strategy — agent decides implementation approach (separate version snapshots table vs JSON diff tracking, rollback mechanism).
- **D-09:** Streaming UX details — agent decides token rendering approach (typing cursor, word chunks, loading states, error recovery mid-stream). Should feel responsive and polished.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture
- `docs/architecture/HLD-ARCHITECTURE.md` — Full HLD with control plane / runtime plane separation, agent management subsystem (§a), model abstraction subsystem (§d), agent execution sequence diagram, data flow diagrams
- `docs/architecture/HLD-ARCHITECTURE.md` §"Agent Management" (line ~119) — CRUD, versioning, status tracking architecture
- `docs/architecture/HLD-ARCHITECTURE.md` §"Model Abstraction Layer" (line ~155) — OpenAI-compatible interface, LiteLLM, multi-model routing, fallback chains, circuit breaker
- `docs/architecture/HLD-ARCHITECTURE.md` §"Agent Execution Engine" (line ~144) — Core execution loop: message → config → prompt → model → tool → response → SSE

### Project Context
- `.planning/PROJECT.md` — Core value, constraints, key decisions (custom execution loop + SK, Azure AI Search for RAG, platform-managed AI Services)
- `.planning/REQUIREMENTS.md` — Requirements AGNT-01 through AGNT-04, MODL-01 through MODL-04
- `.planning/ROADMAP.md` — Phase 3 success criteria, dependency graph

### Prior Decisions
- `.planning/phases/01-foundation-project-scaffold/01-CONTEXT.md` — Foundation patterns (SQLAlchemy 2.0 async, Alembic, UUID PKs, JWT httpOnly cookies, tenant middleware, cursor pagination, structured errors, CORS)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/models/base.py` — `Base`, `UUIDMixin`, `TimestampMixin` mixins for all new models (Agent, AgentConfig, ModelEndpoint)
- `backend/app/core/security.py` — JWT token creation/decode, password hashing (pattern for auth utilities)
- `backend/app/middleware/tenant.py` — `TenantMiddleware` + `get_tenant_id()` dependency for tenant-scoped queries
- `backend/app/api/v1/schemas.py` — Pydantic schema pattern (`model_config = {"from_attributes": True}`)
- `backend/app/api/v1/router.py` — Router registration pattern (`api_router.include_router()`)
- `frontend/src/lib/api.ts` — `apiFetch<T>()` utility with credentials + error handling
- `frontend/src/contexts/auth-context.tsx` — Context provider pattern for global state
- `frontend/src/components/protected-route.tsx` — Route protection pattern

### Established Patterns
- **Backend models:** SQLAlchemy declarative with `UUIDMixin` + `TimestampMixin`, `tenant_id` FK on tenant-scoped tables
- **API routes:** FastAPI router at `/api/v1/{domain}`, Pydantic request/response schemas, structured error `{"detail": "...", "code": "..."}`
- **Frontend data fetching:** `apiFetch()` with `credentials: "include"` for httpOnly cookie auth
- **Frontend state:** React Context + `useState` + `useEffect` pattern
- **Auth flow:** JWT in httpOnly cookies, tenant context from middleware

### Integration Points
- New agent routes mount at `/api/v1/agents` and `/api/v1/models` via `api_router.include_router()`
- Agent pages at `/dashboard/agents` and `/dashboard/agents/[id]/chat` in Next.js app router
- SSE streaming endpoint requires FastAPI `StreamingResponse` with `text/event-stream` content type
- Model abstraction layer via LiteLLM connects to external model providers
- Azure Key Vault integration for secret retrieval (new dependency: `azure-keyvault-secrets` + `azure-identity`)

</code_context>

<specifics>
## Specific Ideas

- **AI Foundry reference:** The chat interface should feel like Azure AI Foundry's playground — professional, clean, with the three-panel layout (conversations sidebar, chat center, config right). This is the benchmark for presentation quality.
- **Microsoft-first auth:** Entra ID / Managed Identity is the preferred auth pattern for Azure services. The platform demonstrates Microsoft best practices for the manager presentation.
- **Model-agnostic from day one:** While Azure OpenAI is the default, the abstraction layer must handle any OpenAI-compatible endpoint. LiteLLM provides this out of the box.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-agent-core-model-abstraction*
*Context gathered: 2026-03-23*
