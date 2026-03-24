# Phase 9: Azure Subscription Integration & Foundry-Style AI Services - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase connects the platform to Azure subscriptions so tenants can discover their Azure AI resources, manage per-agent connections to those resources, browse a Foundry-style tool catalog (Configured/Catalog/Custom tabs), and use Azure AI Search indexes for Knowledge/RAG retrieval. The admin authenticates via the web portal using Entra ID (same credentials as Azure Portal), selects subscriptions to connect, and the backend uses ARM APIs to discover resources by type. The UI mirrors Azure AI Foundry's design language — purple accent, clean white layout, card grids, region badges, collapsible config sections.

This phase does NOT include Data management, Evaluations, Guardrails, Memory, Workflows, or Fine-tune features — those are covered in Phases 5-8.

</domain>

<decisions>
## Implementation Decisions

### Subscription Authentication
- **D-01:** Admin authenticates via the web portal using the same Entra ID / OAuth credentials they use for Azure Portal. The platform does NOT ask for service principal credentials or client secrets — it uses the admin's own identity token.
- **D-02:** Backend uses the admin's OAuth access token (with ARM scope) to call Azure Resource Manager APIs for subscription listing and resource discovery. Token is obtained via standard OAuth 2.0 authorization code flow with PKCE.
- **D-03:** Admin can select one or more subscriptions from the discovered subscription list. Multi-subscription support is required — resources are discovered across all connected subscriptions.

### Resource Discovery
- **D-04:** Resource discovery is type-filtered. The user selects the type of resource they want to connect (e.g., AI Search, Cognitive Services, Cosmos DB, PostgreSQL), and the platform discovers all matching resources across connected subscriptions using ARM resource list APIs with `$filter` by resource type.
- **D-05:** Discovered resources display with name + region badge (e.g., "SWEDENCENTRAL") + managed identity info, mirroring the Foundry Knowledge dropdown pattern.

### Connection Management
- **D-06:** Agent's discretion — downstream planner decides connection model structure (per-agent vs connection profiles), health check strategy (polling interval, health criteria), and connection picker UI integration into agent config.

### Tool Catalog & Knowledge UX
- **D-07:** Mirror Foundry's exact 3-tab tool selector modal: **Configured** (tools already set up and ready to use), **Catalog** (browse all available connectors from the catalog with filter dropdowns: Type, Provider, Category, Registry, Supported auth), **Custom** (user-defined tools). Each catalog entry shows as a card with icon, name, description, and badges (e.g., "Local MCP", "Preview").
- **D-08:** Knowledge is a separate section — both as a sidebar nav item AND as a collapsible section within the agent config page (matching Foundry's "Knowledge" section alongside Tools, Memory, Guardrails). Knowledge uses an AI Search resource picker dropdown → user selects auth type (API Key or Managed Identity) → clicks "Connect" → then browses/selects indexes from that resource.
- **D-09:** Initial catalog connectors for v1: Azure AI Search, Azure Cosmos DB, Azure Database for PostgreSQL. These match the connectors shown in Foundry's catalog. Additional connectors (Redis, SQL Server, Elasticsearch, etc.) are deferred to v2.
- **D-10:** Knowledge integration connects to the existing RAG pipeline from Phase 4 — when a user connects an AI Search resource and selects indexes, those indexes become available as data sources for RAG retrieval during agent execution.

### UI Visual Design
- **D-11:** The UI must match Azure AI Foundry's look and feel — purple accent color (#7C3AED or similar Foundry purple), clean white backgrounds, the same card styling with subtle borders, region badges with colored backgrounds, collapsible sections with chevrons, table layouts matching Foundry's agent list (Name, Version, Type, Created on, Description columns), search bars with filter dropdowns.
- **D-12:** Agent config page layout mirrors Foundry's playground: left panel with collapsible sections (Instructions, Tools, Knowledge, Memory, Guardrails) + right panel with Chat/YAML/Code tabs. The existing chat page from Phase 3 should evolve toward this split-pane layout.
- **D-13:** Sidebar navigation should include entries mirroring Foundry: Agents, Workflows, Models, Fine-tune, Tools, Knowledge, Data, Evaluations, Guardrails. Items for features not yet built (Workflows, Fine-tune, some Data tabs) show as disabled/coming-soon with a "Preview" badge.

### Agent's Discretion
- **D-14:** ARM API pagination strategy and caching for resource discovery results.
- **D-15:** OAuth token refresh and storage mechanism for the Azure subscription connection.
- **D-16:** How the tool catalog data is stored (hardcoded registry vs database-driven catalog entries).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture
- `docs/architecture/HLD-ARCHITECTURE.md` — Full HLD with:
  - §"AI Services Integration" (line ~397) — Platform tool adapter, managed auth, usage metering
  - §"Agent Execution Engine" (line ~144) — Core loop with tool call flow
  - §"Tool Management" (line ~291) — Tool Registry API, attachment, sandbox, marketplace

### Prior Phase Context
- `.planning/phases/04-tools-data-sources-rag-platform-ai-services/04-CONTEXT.md` — Decisions D-07/D-08 (Platform Tool Adapter pattern, 7-service adapters), D-04/D-05 (Azure AI Search RAG), D-06 (Fernet credential storage for PoC)
- `.planning/phases/03-agent-core-model-abstraction/03-CONTEXT.md` — Decisions D-06/D-07 (Dual auth: Entra ID + API key, Key Vault for secrets)

### Project Context
- `.planning/PROJECT.md` — Key decisions: Microsoft services as extensively as possible, model-agnostic, multi-tenant
- `.planning/REQUIREMENTS.md` — Requirements AZURE-01 through AZURE-05
- `.planning/ROADMAP.md` — Phase 9 requirements and success criteria, depends on Phase 4

### Existing Code
- `backend/app/services/platform_tools.py` — PlatformToolAdapter ABC + 7 Azure AI adapters (reusable pattern for new connectors)
- `backend/app/services/rag_service.py` — RAG retrieval service (connects to Knowledge integration)
- `backend/app/models/tool.py` — Tool model with `is_platform_tool` flag + AgentTool join table
- `backend/app/services/secret_store.py` — Fernet encrypt/decrypt for credentials
- `backend/app/services/model_abstraction.py` — LiteLLM with Azure OpenAI provider routing

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PlatformToolAdapter` ABC in `platform_tools.py`: Pattern for all Azure service adapters — extend for new catalog connectors
- `secret_store.py`: Fernet encrypt/decrypt — reuse for storing Azure subscription credentials/tokens
- `Tool` model with `is_platform_tool` flag: Distinguishes system vs tenant tools — extend for catalog entries
- `apiFetch<T>()` in `frontend/src/lib/api.ts`: Typed API client with 204 handling
- Agent detail sub-pages pattern: `dashboard/agents/[id]/` with chat, tools, data-sources, ai-services, versions tabs

### Established Patterns
- Backend: SQLAlchemy models with `Base`, `UUIDMixin`, `TimestampMixin` → new models (AzureSubscription, AzureConnection, CatalogEntry)
- Backend: FastAPI router registration in `api/v1/router.py` → new azure_subscriptions, catalog routes
- Backend: Pydantic schemas with `model_config = {"from_attributes": True}` in `schemas.py`
- Backend: `get_tenant_id()` dependency for tenant-scoped queries
- Frontend: Dashboard layout with sidebar + content area in `dashboard/layout.tsx`

### Integration Points
- Agent config page needs to evolve into Foundry-style split-pane layout
- RAG service needs to accept connected AI Search indexes as data sources
- Tool attachment flow needs to use catalog modal instead of direct CRUD
- Sidebar nav needs new entries (Knowledge, expanded Tools)

</code_context>

<specifics>
## Specific Ideas

### Visual Reference: Azure AI Foundry Portal (screenshots provided by user)
- **Agent list page**: Table with Name, Version, Type, Created on, Description columns. "Create agent" purple button top-right. Search bar with "Ask AI" suggestion chips.
- **Agent config (Playground)**: Split pane — left: Model selector dropdown, collapsible Instructions/Tools/Knowledge/Memory/Guardrails sections. Right: Chat/YAML/Code tabs with chat playground.
- **Tool selector modal**: "Select a tool" heading, 3 tabs (Configured/Catalog/Custom). Configured shows card grid (icon + name + description). Catalog adds filter dropdowns (Type, Provider, Category, Registry, Supported auth) and "Featured" sort, card grid with badges.
- **Knowledge (Foundry IQ)**: "Knowledge bases" / "Indexes" tabs. Resource picker dropdown showing discovered AI Search resources with region badges (e.g., SWEDENCENTRAL) + managed identity metadata. Auth Type dropdown (API Key). "Connect" button. "Create new resource" link.
- **Sidebar nav**: Agents, Workflows, Models, Fine-tune, Tools, Knowledge, Data, Evaluations, Guardrails — each with an icon.
- **Color scheme**: Purple accent (#7C3AED-ish), white backgrounds, light gray borders, dark text, "Preview" badges in gray pill.

</specifics>

<deferred>
## Deferred Ideas

- Workflows page (sidebar nav item — Phase 6)
- Fine-tune page (sidebar nav item — v2)
- Data page with Datasets/Files/Synthetic data generation/Stored completions tabs (Phase 8+)
- Evaluations page with Evaluator catalog and Red team tabs (Phase 8)
- Guardrails page with Guardrails/Blocklists/Integrations tabs (Phase 7)
- Memory section in agent config (Phase 5)
- Additional catalog connectors beyond AI Search, Cosmos DB, PostgreSQL (v2)
- "Ask AI" search bar and suggestion chips (v2)
- Voice mode toggle in agent config (v2)

None of these are in Phase 9 scope — they will show as disabled/coming-soon sidebar items.

</deferred>

---

*Phase: 09-azure-subscription-integration-foundry-style-ai-services*
*Context gathered: 2026-03-24*
