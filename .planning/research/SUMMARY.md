# Project Research Summary

**Project:** AI Agent Platform v4.0 — Architecture Pivot: Platform as Infrastructure Provider
**Domain:** Multi-tenant AI agent platform infrastructure
**Researched:** 2026-04-04
**Confidence:** HIGH

## Executive Summary

The v4.0 milestone transforms the platform from a "UI wrapper" around OpenClaw into an "infrastructure provider" — exposing OpenClaw's native web UI to end users while the platform provides multi-tenancy, authentication, token metering, Azure service integrations, and per-group rules as invisible infrastructure. Research across all four domains confirms this is architecturally sound and achievable with the existing stack. The recommended approach centers on four new components: (1) a custom FastAPI auth gateway for authenticated subdomain routing to OpenClaw pods, (2) a lightweight FastAPI token-counting proxy for universal LLM usage tracking, (3) three platform MCP servers exposing Cosmos DB memory, AI Search, and group rules as tools OpenClaw agents can call natively, and (4) infrastructure updates including wildcard DNS/TLS and Cosmos DB vector search enablement.

The critical technical insight across all research is that **every new component follows existing platform patterns exactly**. The auth gateway reuses `validate_entra_token()` and Cosmos DB tenant resolution. The token proxy mirrors the centralized deployment pattern of `api-gateway` and `workflow-engine`. The MCP servers replicate the hand-rolled JSON-RPC 2.0 pattern from `mcp_server_web_tools.py`. No new languages, no new infrastructure dependencies, no new ingress controllers. The riskiest unknowns are (1) whether Cosmos DB's DiskANN vector index can be added to the existing `agent_memories` container without data migration, and (2) AGC's behavior with wildcard Ingress resources alongside the existing platform Ingress.

Key risks are manageable: the auth gateway is the sole auth boundary for OpenClaw pods (which run with `auth.mode: none`), so any misconfiguration is a direct security exposure — defense-in-depth via NetworkPolicy is essential. The token proxy is a potential SPOF for all LLM traffic but is mitigated by HPA + emergency bypass (revert CR `baseUrl` to Azure OpenAI directly). The three MCP servers add pod overhead but are lightweight (~128Mi each) and stateless.

## Key Findings

### Recommended Stack Additions

**New components to build (all Python/FastAPI):**

| Component | Purpose | LOC | Namespace |
|-----------|---------|-----|-----------|
| **auth-gateway** | OIDC login + Entra ID JWT validation + HTTP/WebSocket proxy to OpenClaw pods | ~600 | `aiplatform` |
| **token-proxy** | Transparent LLM proxy: count tokens, log to Cosmos DB, emit App Insights telemetry | ~300-500 | `aiplatform` |
| **mcp-cosmos-memory** | Cosmos DB vector search for agent long-term memory | ~200 | `aiplatform` |
| **mcp-azure-search** | Azure AI Search hybrid queries exposed as MCP tools | ~250 | `aiplatform` |
| **mcp-platform-context** | Per-group rules and agent config exposed as MCP tools | ~200 | `aiplatform` |

**Infrastructure additions:**
- Wildcard DNS record: `*.agents.stumsft.com` → AGC public IP
- Wildcard TLS cert via cert-manager (DNS-01 challenge against Azure DNS)
- Wildcard Ingress resource on AGC (`ingressClassName: azure-alb-external`)
- New Cosmos DB container: `token_logs` (partition by `tenant_id`, 90-day TTL)
- Cosmos DB `agent_memories` container: add DiskANN vector embedding policy
- NetworkPolicy updates: allow auth-gateway → tenant pods on port 18789

**Key technology decisions confirmed by research:**
- **Custom FastAPI proxy over LiteLLM/Portkey/Helicone** — existing solutions require PostgreSQL, external SaaS, or TypeScript runtime. Custom proxy is ~300 LOC and logs directly to Cosmos DB.
- **Custom auth gateway over oauth2-proxy** — oauth2-proxy can't do dynamic upstream routing (agent-{id} → pod resolution). Custom gateway reuses existing `validate_entra_token()`.
- **AGC with wildcard Ingress over adding NGINX Ingress** — no second ingress controller needed. AGC supports WebSocket natively.
- **Subdomain routing over path-based** — OpenClaw's SPA assumes root `/`. Path rewriting breaks client-side routing.
- **Encrypted cookies (Fernet) over Redis sessions** — stateless, no new infrastructure dependency. Sufficient for 2-5 tenants.
- **Separate MCP servers (3 deployments) over combined** — matches existing 1:1 pattern, independent scaling and failure isolation.
- **URL-path tenant scoping for MCP servers** — OpenClaw doesn't support custom headers on MCP calls. Inject tenant-scoped URLs at CR generation time.

### Feature Table Stakes (v4.0 Must-Haves)

**Must have:**
- Authenticated access to OpenClaw native UI via `agent-{id}.agents.stumsft.com`
- Universal token counting across all UI paths (platform + native OpenClaw)
- Cosmos DB vector search for agent memory (replacing recency-only retrieval)
- Platform MCP servers auto-injected into every OpenClaw agent
- Per-group rules accessible as MCP tools (not just system message injection)
- Wildcard DNS + TLS for agent subdomains
- NetworkPolicy updates for new traffic patterns

**Should have:**
- Token usage dashboard integration (reads from `token_logs` container)
- Cost estimation per request (model pricing lookup)
- Reasoning token tracking for o-series models
- "Open Console" link in platform UI pointing to native OpenClaw UI

**Defer (v4.1+):**
- Per-tenant rate limiting / budget caps in token proxy
- Azure AI Search index management tools in MCP (read-only for v4.0)
- Redis session store for auth gateway (encrypted cookies sufficient now)
- Go rewrite of token proxy (only needed at 50+ tenants / 500+ agents)

### Architecture Approach

All new components deploy as centralized services in the `aiplatform` namespace, consistent with existing shared services (api-gateway, workflow-engine, mcp-proxy). Tenant isolation is maintained through Cosmos DB partition keys, NetworkPolicy, and URL-path tenant scoping — not through per-tenant pod duplication.

**Traffic flow for native UI access:**
```
Browser → DNS (*.agents.stumsft.com) → AGC (TLS terminate) → auth-gateway (OIDC + proxy) → OpenClaw pod (tenant-{slug})
```

**Traffic flow for LLM requests:**
```
OpenClaw pod → token-proxy (aiplatform) → Azure OpenAI → response streams back through proxy → usage logged to Cosmos DB
```

**Traffic flow for MCP tools:**
```
OpenClaw agent → mcp-{server}.aiplatform.svc/mcp/{tenant}/{agent} → Cosmos DB / AI Search → response
```

**Major components and responsibilities:**

1. **Auth Gateway** — OIDC login flow via MSAL, encrypted session cookies, agent-to-pod resolution via Cosmos DB lookup, bidirectional HTTP + WebSocket proxying, tenant access validation
2. **Token Proxy** — transparent request forwarding with `stream_options.include_usage` injection, async Cosmos DB logging, App Insights telemetry emission, path-based or header-based tenant attribution
3. **MCP Cosmos Memory** — vector similarity search via DiskANN `VectorDistance()`, query embedding generation via `text-embedding-3-small`, partition-scoped queries
4. **MCP Azure Search** — hybrid (keyword + vector) search against Azure AI Search indexes, schema-agnostic field mapping, Managed Identity auth
5. **MCP Platform Context** — per-group rules lookup from agent config in Cosmos DB, agent configuration exposure as tool calls

### Critical Pitfalls

1. **Auth gateway is the sole security boundary** — OpenClaw runs with `auth.mode: none`. If the auth gateway has a bug or misconfiguration, agents are publicly accessible. **Mitigation:** NetworkPolicy blocks all external access to port 18789; only auth-gateway pods in `aiplatform` namespace can reach OpenClaw UI. Defense-in-depth, not single-layer.

2. **Entra ID doesn't support wildcard redirect URIs** — `https://*.agents.stumsft.com/auth/callback` is invalid. **Mitigation:** Use a single auth subdomain (`https://auth.agents.stumsft.com/auth/callback`) with `state` parameter to redirect to the correct agent subdomain after login. One redirect URI in the Entra ID app registration.

3. **Cosmos DB DiskANN vector index migration risk** — the existing `agent_memories` container may not accept a vector embedding policy retroactively if indexing policy constraints prevent it. **Mitigation:** Test policy addition on non-prod first. Worst case: create new container, migrate data, swap queries.

4. **Token proxy as SPOF for all LLM traffic** — all OpenClaw → Azure OpenAI calls route through the proxy. **Mitigation:** HPA (2-5 replicas), PodDisruptionBudget (minAvailable: 1), emergency bypass by reverting CR `baseUrl` to Azure OpenAI directly.

5. **Responses API streaming usage format uncertainty** — `stream_options.include_usage` is confirmed for Chat Completions but may differ for the Responses API (`/openai/v1/responses`). OpenClaw uses `openai-responses` provider. **Mitigation:** Test both API paths during implementation. For Responses API, usage may be available in the response object directly without streaming options.

## Implications for Roadmap

### Phase 1: Infrastructure Audit & Foundation
**Rationale:** Every subsequent phase depends on a working infrastructure baseline. Wildcard DNS/TLS, cert-manager, and Cosmos DB container provisioning must be validated before building services that depend on them.
**Delivers:** Clean provision-from-zero validation of Bicep + K8s, wildcard DNS zone, cert-manager ClusterIssuer, wildcard certificate, `token_logs` Cosmos DB container, `agent_memories` vector index policy update.
**Avoids:** Building services against infrastructure that doesn't actually work (the v3.0→v4.0 gap may have drift).
**Research flag:** LOW — well-documented Bicep/K8s patterns, cert-manager DNS-01 is standard.

### Phase 2: Token Proxy
**Rationale:** Independent of UI exposure. Can be deployed and validated by simply changing the CR `baseUrl`. Provides immediate value (token tracking) before native UI is exposed.
**Delivers:** FastAPI proxy service, `token_logs` Cosmos DB repository, CR `baseUrl` modification in `openclaw_service.py`, App Insights telemetry. Universal token counting for all LLM calls regardless of UI path.
**Uses:** `stream_options.include_usage` for streaming token extraction. Centralized deployment pattern in `aiplatform` namespace.
**Avoids:** Introducing LiteLLM/PostgreSQL dependency; proxy-as-SPOF via HPA + bypass.
**Research flag:** MEDIUM — need to verify Responses API streaming usage format. Chat Completions path is confirmed.

### Phase 3: Platform MCP Servers
**Rationale:** Independent of UI exposure. Agents gain memory search, document retrieval, and group rules tools immediately through the existing CR injection mechanism. No UI changes needed.
**Delivers:** Three MCP servers (cosmos-memory, azure-search, platform-context), auto-injection in `openclaw_service.py`, Cosmos DB vector search enablement.
**Uses:** Existing JSON-RPC 2.0 MCP server pattern, URL-path tenant scoping, Managed Identity for Azure services.
**Avoids:** Combined server single-point-of-failure; agent trust issues via URL-path scoping (not tool argument scoping).
**Research flag:** MEDIUM — DiskANN vector index migration needs testing. AI Search tool is straightforward.

### Phase 4: Auth Gateway & Native UI Exposure
**Rationale:** Depends on Phase 1 (wildcard DNS/TLS) and benefits from Phase 2/3 being validated (full platform value-adds working before exposing native UI). This is the most complex phase — OIDC flow, WebSocket proxy, dynamic routing.
**Delivers:** Auth gateway service, wildcard AGC Ingress, NetworkPolicy updates, OIDC login flow, WebSocket proxy, agent-to-pod routing, "Open Console" link in platform UI.
**Uses:** Existing `validate_entra_token()`, MSAL ConfidentialClientApplication, `httpx` for HTTP proxy, `websockets` for WebSocket proxy.
**Avoids:** oauth2-proxy (static upstreams), NGINX Ingress (second ingress controller), path-based routing (breaks SPA).
**Research flag:** MEDIUM — AGC wildcard Ingress + auth gateway need integration testing. Entra ID redirect URI pattern (single auth subdomain) needs verification.

### Phase 5: Dual-Mode Operation & Platform UI Simplification
**Rationale:** Only after native UI is accessible. Evaluate which platform UI pages are redundant with OpenClaw's native UI and deprecate them. Add cross-links between platform dashboard and native UI.
**Delivers:** Platform UI links to native consoles, deprecated redundant pages, dual-mode documentation.
**Research flag:** LOW — mostly UI/UX decisions, not technical research.

### Phase Ordering Rationale

- **Phase 1 first** because wildcard TLS/DNS is a prerequisite for Phase 4, and Cosmos DB container setup is a prerequisite for Phases 2-3.
- **Phases 2 and 3 before Phase 4** because they add platform value (token tracking, MCP tools) independently of native UI exposure. If Phase 4 encounters blockers, Phases 2-3 are still valuable.
- **Phases 2 and 3 are parallelizable** — token proxy and MCP servers have no dependency on each other. Both modify `openclaw_service.py` but in different sections (baseUrl vs mcpServers).
- **Phase 4 last among infrastructure phases** because it has the most unknowns (AGC wildcard, OIDC flow, WebSocket proxy) and benefits from all other pieces being in place.
- **Phase 5 is cleanup/polish** — low risk, no infrastructure changes.

### Research Flags Summary

| Phase | Needs Research | Reason |
|-------|---------------|--------|
| Phase 1: Infra Audit | NO | Standard Bicep/K8s/cert-manager patterns |
| Phase 2: Token Proxy | MAYBE | Verify Responses API streaming usage format |
| Phase 3: MCP Servers | MAYBE | Test DiskANN vector index migration on existing container |
| Phase 4: Auth Gateway | YES | AGC wildcard behavior, Entra ID redirect URI pattern, WebSocket proxy integration |
| Phase 5: Dual-Mode | NO | UI/UX decisions, not technical |

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| OpenClaw MCP & Native UI | HIGH | Verified from production codebase — CR config, gateway ports, WebSocket protocol, MCP injection |
| Token Proxy | HIGH | Azure OpenAI `stream_options.include_usage` is GA-documented; custom proxy pattern is well-understood |
| Auth Gateway | HIGH | Reuses existing Entra ID patterns; AGC WebSocket support confirmed; OIDC flow is standard |
| Platform MCP Servers | HIGH | Directly replicates existing MCP server pattern; Cosmos DB vector search is GA |
| Infrastructure (DNS/TLS) | MEDIUM | cert-manager + DNS-01 is standard but AGC wildcard Ingress alongside existing Ingress needs validation |

**Overall confidence:** HIGH — all four research streams converge on the same approach (FastAPI, Cosmos DB, existing patterns), with clear recommendations and no contradictions between documents.

### Gaps to Address

- **Responses API streaming usage:** `stream_options.include_usage` is confirmed for Chat Completions but needs testing for the Responses API path (`/openai/v1/responses`). If unsupported, the proxy may need to parse the non-streaming response body for usage data on that path.
- **Cosmos DB DiskANN minimum RU/s:** DiskANN vector indexing may require higher RU throughput than currently provisioned. Verify against current account settings before enabling.
- **AGC multiple frontends:** The wildcard Ingress needs a separate ALB frontend (`agents-frontend`). AGC documentation confirms multiple frontends are supported but this hasn't been tested on this specific deployment.
- **Entra ID app registration redirect URIs:** Current app registration is configured for the platform UI. Adding `https://auth.agents.stumsft.com/auth/callback` (or equivalent) requires updating the registration. May need a second app registration if scope separation is desired.
- **OpenClaw header passthrough for tenant attribution:** The token proxy prefers `X-Tenant-Id` / `X-Agent-Id` headers in requests. The CR supports custom headers in provider config, but this needs verification with the specific `openai-responses` provider. Fallback: path-based tenant identification.

### Contradictions Between Research Documents

**None found.** All four documents converge on the same architectural patterns:
- All recommend FastAPI/Python (consistent stack)
- All recommend centralized deployment in `aiplatform` namespace
- All reference the same Cosmos DB, NetworkPolicy, and Managed Identity patterns
- The auth gateway research and OpenClaw UI research agree on subdomain routing and AGC
- The token proxy and MCP server research agree on URL-path tenant scoping as the preferred identification mechanism

## Sources

### Primary (HIGH confidence — direct codebase verification)
- `backend/app/services/openclaw_service.py` — CR builder, gateway config, MCP injection, WebSocket protocol
- `backend/app/services/memory_service.py` — current memory retrieval (recency-only)
- `backend/app/services/rag_service.py` — AI Search integration patterns
- `backend/app/core/security.py` — Entra ID token validation
- `backend/app/middleware/tenant.py` — tenant resolution
- `k8s/base/ingress.yaml` — current AGC Ingress config
- `k8s/overlays/tenant-template/network-policy.yaml` — tenant NetworkPolicy
- `k8s/base/mcp-github/` — existing MCP server deployment pattern
- `infra/modules/agc.bicep` — AGC infrastructure

### Secondary (HIGH confidence — official documentation)
- Azure OpenAI API Reference (2024-10-21 GA) — `stream_options.include_usage`, `chatCompletionStreamOptions`
- Azure Cosmos DB NoSQL Vector Search (GA November 2024) — DiskANN, `VectorDistance()`
- Azure AI Search Python SDK (`azure-search-documents>=11.6.0`) — hybrid search, `VectorizedQuery`
- cert-manager DNS-01 challenge documentation
- MSAL Python library documentation
- AGC (Application Gateway for Containers) WebSocket support

### Tertiary (MEDIUM confidence — needs validation)
- AGC wildcard Ingress behavior alongside existing Ingress resources
- Entra ID redirect URI wildcard constraints
- Responses API streaming usage format (vs Chat Completions)

---
*Research completed: 2026-04-04*
*Ready for roadmap: yes*
