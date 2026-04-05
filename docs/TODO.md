# Platform TODO & Backlog

> Living document — things we've discussed and want to implement.
> Items are prioritized: 🔥 Quick Win | 🔧 Medium Effort | 🏗️ Major Feature

---

## 🔥 Quick Wins

### 1. ✅ OpenClaw Memory & Session Tools Config
**Status:** Implemented  
**Problem:** Agent can't search past conversations, no cross-session memory, no memory indexing.  
**Solution:** Update OpenClaw CR `config.raw` to enable:
- `agents.defaults.memorySearch` — hybrid vector+BM25 search over workspace files (uses Azure OpenAI embeddings)
- `experimental.sessionMemory: true` — index session transcripts for search
- `agents.defaults.sessionTools: "agent"` — enable `sessions_list`, `sessions_history`, `sessions_send` tools
- `session.dmScope: "per-peer"` — isolate DM sessions per user (not shared across all users)

**Files:** `backend/app/services/openclaw_service.py` → `_build_cr()` method  
**Risk:** Low — config-only change, operator reconciles automatically

---

## 🔧 Medium Effort

### 2. Cross-Channel Identity Linking
**Status:** Not started  
**Problem:** Same person messaging from WhatsApp (+972...) and Telegram (@user) appears as two different users.  
**Solution:** Add `session.identityLinks` config to OpenClaw CR that maps channel identities to a single user.  
**Options:**
- **A) Static config** — hardcode identity mappings in CR (fast, rigid)
- **B) Platform UI** — build identity linking page in frontend, store mappings in Cosmos DB, inject into CR on deploy
- **C) Auto-detect** — OpenClaw Honcho plugin can infer identity across channels (experimental)

**Files:** `openclaw_service.py` for CR config, `agents.py` API for identity CRUD  
**Depends on:** Item 1 (session tools must be enabled first)

### 3. 🟡 Agent Workspace Initial Files via Platform
**Status:** Partial — backend done, frontend editor missing  
**Problem:** Agent has no `MEMORY.md` or custom instructions beyond system prompt.  
**Solution:** Allow platform users to upload/edit workspace files (MEMORY.md, AGENTS.md, custom skills) via the agent config UI. Inject them via `spec.workspace.initialFiles` in the CR.  
**Options:**
- **A) Simple textarea** — edit MEMORY.md and AGENTS.md from agent settings page
- **B) File manager** — full workspace file browser in the UI
- **C) Git sync** — point to a git repo with workspace files

**Implemented:**
- `openclaw_service.py` builds `spec.workspace.initialFiles` in CR (SOUL.md instruction files injected)
- Workspace deletion logic for updates in `openclaw_service.py`

**Remaining:**
- Frontend agent settings page lacks workspace file editor UI (MEMORY.md / AGENTS.md editing)

**Files:** Frontend agent settings page, `openclaw_service.py` for CR workspace config

### 4. Honcho Plugin for Cross-Session AI Memory
**Status:** Not started  
**Problem:** OpenClaw's built-in memory is file-based. Honcho provides AI-native cross-session memory with user modeling.  
**Solution:** Deploy Honcho (PostgreSQL-backed) alongside OpenClaw, enable the plugin.  
**Options:**
- **A) Self-hosted Honcho** — deploy PostgreSQL + Honcho server in AKS, configure OpenClaw plugin
- **B) Honcho Cloud** — use hosted Honcho service (if available)

**Depends on:** Evaluating whether built-in memory (Item 1) is sufficient for near-term needs  
**Docs:** https://docs.openclaw.ai/concepts/memory-honcho

---

## 🏗️ Major Features

### 5. 🟡 OpenClaw → Cosmos DB Memory Sync Service
**Status:** Partial — MCP-based approach implemented (Phase 30), polling sync not built  
**Problem:** OpenClaw's file-based memory (SQLite + JSONL + Markdown on PVC) doesn't scale beyond ~6 weeks at 20K messages/day. No backup, no multi-instance, no enterprise-grade search.  
**Solution:** Background sync service that reads OpenClaw session data and stores it in platform's Cosmos DB + Azure AI Search.  
**Architecture:**
```
OpenClaw Pod (hot path)           Platform (cold path)
├── JSONL sessions     ──sync──►  Cosmos DB agent_memories
├── memory/*.md        ──sync──►  Cosmos DB document_chunks
└── MEMORY.md          ──sync──►  Azure AI Search (vector)
```
**Options:**
- **A) Sync Agent (recommended)** — background service in `backend/app/services/` polls OpenClaw via WS `sessions.get` every 5-10 min, stores in Cosmos DB with embeddings
- **B) Context Engine Plugin** — TypeScript plugin inside OpenClaw that writes directly to Cosmos DB via HTTP. Most integrated but requires OpenClaw plugin SDK knowledge.
- **C) Sidecar container** — runs alongside OpenClaw pod, reads PVC directly, pushes to Cosmos DB. Simple but tightly coupled to pod lifecycle.

**Scale analysis:**
- 20K msgs/day × 500 bytes = 10MB/day raw
- With embeddings (1536 dims): ~120MB/day in Cosmos DB
- 3 months: ~11GB in Cosmos DB (affordable, scalable, replicated)
- Azure AI Search handles millions of vectors with sub-second latency

**Implemented (alternative approach via Phase 30):**
- `backend/microservices/mcp_platform_tools/memory.py` — MCP tools: `memory_search()`, `memory_store()`, `memory_list()`, `get_structured()`
- Cosmos DB `agent_memories` collection read/write via MCP instead of file-based storage
- Embeddings with in-memory LRU cache
- Auto-injected into OpenClaw CR via `openclaw_service.py`

**Remaining:**
- Background polling sync service (`openclaw_sync_service.py`) not built — MCP approach may be sufficient
- Azure AI Search vector index not yet created

**Files:** New `backend/app/services/openclaw_sync_service.py`, scheduler in main app  
**Depends on:** Item 1 (need session tools + memory search working first)

### 6. Multi-Agent WhatsApp Routing
**Status:** Not started  
**Problem:** Currently one OpenClaw instance = one WhatsApp session. Enterprise users may want multiple agents accessible from one WhatsApp number.  
**Solution:** Routing layer that dispatches WhatsApp messages to different agents based on keywords/groups/contacts.  
**Options:**
- **A) OpenClaw multi-agent** — single OpenClaw instance with multiple agent configs and routing rules
- **B) Platform router** — platform intercepts WhatsApp webhooks and routes to different OpenClaw pods
- **C) WhatsApp Business API** — use official Business API with chatbot routing instead of linked device

### 7. 🟡 Channel Analytics Dashboard
**Status:** Partial — UI components exist, data population needs verification  
**Problem:** No visibility into message volumes, response times, channel health across WhatsApp/Telegram/Gmail.  
**Solution:** Collect metrics from OpenClaw session data, display in platform monitoring tab.  
**Metrics:** Messages/day per channel, avg response time, active users, memory usage, session count.

**Implemented:**
- `frontend/src/app/dashboard/observability/page.tsx` — observability dashboard page
- `frontend/src/components/observability/analytics-toolbar.tsx` — analytics toolbar
- `frontend/src/components/observability/kpi-tiles.tsx` — KPI tiles
- `frontend/src/components/observability/chart-card.tsx` — chart cards
- E2E tests: `frontend/tests/e2e/observability.spec.ts`

**Remaining:**
- Verify actual data population from OpenClaw sessions
- Channel-specific metrics breakdowns

### 8. ✅ Automated PVC Cleanup & Archival
**Status:** Implemented  
**Problem:** PVC fills up over time with old sessions. Manual cleanup is risky.  
**Solution:** Scheduled CronJob that archives old session files to Azure Blob Storage and prunes PVC.

**Implemented:**
- `infra/modules/storage.bicep` — Azure Storage account (Standard_LRS) with `agent-archives` blob container, 30-day soft delete, RBAC for workload identity
- `infra/main.bicep` — storage module wiring with `storageAccountName` and `blobEndpoint` outputs
- `backend/scripts/pvc_cleanup.py` — Python script: discovers OpenClaw pods across tenant namespaces, finds files older than RETENTION_DAYS (default 7), archives to tar.gz in Blob Storage, deletes from PVC. Supports DRY_RUN mode.
- `k8s/base/pvc-cleanup/cronjob.yaml` — CronJob running daily at 3AM UTC, uses `aiplatform-workload` ServiceAccount
- `k8s/base/configmap.yaml` — `STORAGE_ACCOUNT_NAME` placeholder
- `hooks/postprovision.sh` — wired `STORAGE_ACCOUNT_NAME` from Bicep outputs, CronJob ACR image substitution

**Depends on:** Nothing (standalone — archives before pruning, independent of Cosmos sync)

### 9. 🟡 KeyVault Separation — Platform vs Tenant Secrets
**Status:** Partial — infrastructure deployed, backend wiring incomplete  
**Priority:** High — security isolation + scalability  
**Problem:** A single Key Vault (`stumsft-aiplat-prod-kv`) stores both platform infrastructure secrets (Cosmos endpoint, Entra IDs, Service Bus, App Insights) and per-tenant secrets (Telegram bot tokens, Gmail app passwords, AI model API keys). This means:
- Every OpenClaw agent pod can read platform infra secrets (blast radius)
- KV audit logs mix platform and tenant operations (compliance)
- Approaching KV throttling limits as tenants scale (4K txn/10s per vault)
- No isolation between tenants' secrets

**Solution:** Two-vault model:
| Vault | Secrets | Access |
|---|---|---|
| `stumsft-aiplat-prod-kv` (existing) | Platform infra: `cosmos-endpoint`, `entra-*`, `service-bus-*`, `appinsights-*`, `platform-admin-*`, `workload-client-id` | Control-plane pods only |
| `stumsft-aiplat-prod-tenants-kv` (new) | Tenant secrets: `{slug}-telegram-bot-token-*`, `{slug}-gmail-app-password-*`, `azure-openai-api-key`, `azure-openai-api-base`, per-model API keys | Agent-executor / OpenClaw pods |

**Touchpoints (full audit):**

*Infrastructure (Bicep):*
- `infra/modules/keyvault.bicep` — existing vault, keep as-is for platform secrets
- NEW `infra/modules/keyvault-tenants.bicep` — deploy tenant vault with separate RBAC
- `infra/main.bicep` — add tenant vault module invocation, output `tenantKeyVaultName`/`tenantKeyVaultUri`
- `infra/modules/aks.bicep` — no change (CSI addon is cluster-wide)

*Kubernetes manifests:*
- `k8s/base/configmap.yaml` — add `TENANT_KEY_VAULT_NAME` entry alongside existing `KEY_VAULT_NAME`
- `k8s/base/secrets/secret-provider-class.yaml` — keep as-is (platform secrets only, used by control-plane)
- 9 deployment files mount `aiplatform-keyvault` — control-plane pods keep existing mount, agent-executor/tool-executor may need both

*Backend (Python) — biggest change:*
- `openclaw_service.py` L18 — add `TENANT_KEY_VAULT_NAME = os.getenv("TENANT_KEY_VAULT_NAME", KEY_VAULT_NAME)` with fallback
- `openclaw_service.py` `_get_kv_secret()` / `_set_kv_secret()` — add `vault_name` parameter, default to tenant vault
- `openclaw_service.py` `_build_secret_provider_class()` L895 — change `keyvaultName` from `KEY_VAULT_NAME` to `TENANT_KEY_VAULT_NAME`
- `openclaw_service.py` `_build_k8s_secret_data()` — read `azure-openai-*` from tenant vault, platform secrets from platform vault
- `agents.py` — all `_set_kv_secret()` calls already store tenant secrets, just need to target tenant vault
- `queue_service.py` — no change (uses env vars from CSI, not direct KV calls)

*Frontend:*
- No changes needed — UI references "Key Vault" generically, secret names are unchanged

*Scripts:*
- `scripts/deploy.sh` — extract and substitute `TENANT_KEY_VAULT_NAME` alongside `KEY_VAULT_NAME`
- `scripts/post-deploy-config.sh` — same: handle new placeholder in configmap
- `scripts/validate-deployment.sh` — validate `tenantKeyVaultUri` output exists

**Implementation order (safe rollout):**
1. **Bicep** — deploy tenant vault alongside existing vault (additive, zero risk)
2. **ConfigMap** — add `TENANT_KEY_VAULT_NAME` env var (additive, no breakage)
3. **Backend** — add `TENANT_KEY_VAULT_NAME` with fallback to `KEY_VAULT_NAME` (backward-compatible)
4. **Migrate secrets** — copy tenant secrets from platform vault → tenant vault (scripted)
5. **Switch** — update `openclaw_service.py` to use tenant vault for tenant operations
6. **Verify** — deploy one test agent, confirm it reads secrets from tenant vault
7. **Cleanup** — remove tenant secrets from platform vault after all agents verified

**AI Model Provisioning (related enhancement):**
When an admin provisions a new AI model (e.g., GPT-4o, Claude), the API key/endpoint should be stored in the **tenant vault** with a naming convention like `{model-slug}-api-key` and `{model-slug}-api-base`. The model wizard UI should write these via the existing `_set_kv_secret()` path (now targeting tenant vault). End users consuming the model get secrets injected via the per-agent CSI SecretProviderClass — no code access to raw keys.

**Implemented:**
- `infra/modules/keyvault-tenants.bicep` — tenant vault Bicep module deployed
- `scripts/migrate-tenant-secrets.sh` — migration script exists
- `hooks/postprovision.sh` — references `TENANT_KEY_VAULT_NAME`
- `openclaw_service.py` L18 — `TENANT_KEY_VAULT_NAME` env var with fallback to `KEY_VAULT_NAME`

**Remaining:**
- `openclaw_service.py` `_get_kv_secret()` / `_set_kv_secret()` still use `KEY_VAULT_NAME` directly — not parameterized
- `_build_secret_provider_class()` not yet updated to use tenant vault
- API endpoints in `agents.py` still target platform vault
- Need to run migration script and cut over

**Risk:** Medium — fallback pattern ensures backward compatibility. Rollback = revert `TENANT_KEY_VAULT_NAME` to same value as `KEY_VAULT_NAME`.  
**Depends on:** Nothing — can be done independently  
**Files:** See touchpoints above (~15 files across infra/k8s/backend/scripts)

---

## � Architecture Pivot: Platform as Infrastructure, OpenClaw as Agent Runtime

### Context & Motivation
OpenClaw's release cadence is extremely high — new features, channels, and improvements land daily. Our custom UI masking approach can never keep pace with upstream changes. We're currently exposing ~60% of OpenClaw's capabilities and falling further behind with every release.

**New model:** The platform becomes the **orchestration/infrastructure plane** and OpenClaw becomes the **agent plane**. Users configure agents through OpenClaw's native UI. The platform handles everything around it: tenant management, monitoring, token tracking, agent chaining, and Azure infrastructure services.

| Layer | Owner | Responsibility |
|---|---|---|
| Tenant management | Platform | Create/delete tenants, RBAC, billing |
| Agent lifecycle | Platform | Deploy/destroy OpenClaw pods, scaling |
| Monitoring | Platform | Token usage, costs, health, logs |
| Agent chaining | Platform | Workflow engine, inter-agent routing |
| Agent configuration | OpenClaw native UI | System prompt, tools, channels, skills |
| Agent capabilities | OpenClaw | Chat, ReAct, MCP tools, channels, memory |

### 10. ✅ Expose OpenClaw Native UI via Reverse Proxy
**Status:** Implemented (Phase 31 — completed 2026-04-05)
**Priority:** 🔥 Critical — enables the architecture pivot
**Problem:** OpenClaw's web UI runs on port 18789 inside the pod but is not accessible to end users. Users must configure everything through our limited custom UI.  
**Solution:** Reverse-proxy the native OpenClaw UI through the platform's API gateway/Ingress so authenticated users can access it directly.

**Approach — Subdomain routing (recommended):**
```
agent-{id}.your-platform.com  →  oc-{name}.tenant-{slug}.svc.cluster.local:18789
```
- Wildcard DNS (`*.your-platform.com`) + wildcard TLS cert
- Ingress rule per agent (created dynamically when agent is deployed)
- Platform gateway authenticates user (Azure AD), validates tenant access, then proxies

**Challenges:**
| Challenge | Severity | Solution |
|---|---|---|
| WebSocket proxy through multiple hops | Medium | Nginx/Envoy handles this well, Ingress already supports WS |
| OpenClaw UI assumes root `/` | High | Subdomain approach avoids path rewriting entirely |
| CORS / cookie isolation | Medium | Each agent on its own subdomain = naturally isolated |
| Auth — OpenClaw has its own auth | Low | Keep `auth.mode: none` since platform gateway handles auth |

**Alternative — Path-based routing:**
```
your-platform.com/agents/{id}/console/*  →  oc-{name}:18789/*
```
Simpler DNS but requires URL rewriting and may break OpenClaw's SPA routing.

**Files:**
- `k8s/base/ingress.yaml` or new `k8s/base/openclaw-ingress-template.yaml` — wildcard Ingress
- `backend/app/services/openclaw_service.py` — create Ingress rule on agent deploy
- `infra/modules/dns.bicep` — wildcard DNS record
- `infra/modules/aks.bicep` — wildcard TLS cert (Let's Encrypt or Azure-managed)
- Frontend — link to `agent-{id}.your-platform.com` from agent details page

**Implemented:**
- `backend/microservices/auth_gateway/main.py` — OIDC auth + HTTP/WebSocket proxy
- `k8s/base/auth-gateway/ingress-agents.yaml` — wildcard Ingress on AGC
- `k8s/base/auth-gateway/deployment.yaml` — auth gateway service
- Subdomain routing: `agent-{slug}.agents.{domain}` → OpenClaw pod port 18789
- OIDC login flow via MSAL
- WebSocket bidirectional relay
- Tenant access validation before proxying

**Risk:** Medium — WebSocket proxying needs careful testing  
**Depends on:** Nothing — can be done independently

### 11. 🟡 Platform MCP Servers as Azure Infrastructure Bridge
**Status:** Partial — memory tools done (Phase 30), Azure Search & Key Vault servers not built
**Priority:** 🔧 High — prevents losing Azure integration when users switch to native UI
**Problem:** When users configure agents through OpenClaw's native UI instead of our custom UI, we lose the ability to inject Azure infrastructure services (AI Search, Cosmos DB, Key Vault) into the agent's context.  
**Solution:** Expose Azure services as MCP servers that OpenClaw consumes natively.

**Architecture:**
```
OpenClaw Pod (native UI, full features)
│
│  MCP protocol (stdio or SSE)
│
├── mcp-azure-search     → Azure AI Search indexes (RAG)
├── mcp-cosmos-memory    → Cosmos DB agent memories (read/write)
├── mcp-key-vault        → Key Vault secret retrieval
├── mcp-jira             → Jira (already exists)
├── mcp-sharepoint       → SharePoint (already exists)
└── built-in tools       → web browse, code, etc. (OpenClaw native)
```

When the platform deploys an OpenClaw agent, it **auto-configures MCP server URLs** in the `OpenClawInstance` CR. Users see these tools in OpenClaw's native UI and can enable/disable them.

**New MCP servers to build:**
- `mcp-azure-search` — wraps Azure AI Search with tools: `search_documents(query)`, `list_indexes()`, `index_document(doc)`
- `mcp-cosmos-memory` — wraps Cosmos DB with tools: `memory_search(query)`, `memory_store(key, value)`, `list_memories()`
- `mcp-key-vault` — wraps Key Vault with tools: `get_secret(name)`, `list_secrets()`

**Files:**
- New `backend/mcp_server_azure_search.py`
- New `backend/mcp_server_cosmos_memory.py`
- New `backend/mcp_server_key_vault.py`
- `backend/app/services/openclaw_service.py` — inject MCP server URLs into CR `config.raw.mcpServers`
- K8s deployments for MCP servers (per-tenant or shared)

**Implemented (Phase 30 — completed 2026-04-04):**
- `backend/microservices/mcp_platform_tools/main.py` — FastMCP server with 4 tools
- `backend/microservices/mcp_platform_tools/memory.py` — `memory_search()`, `memory_store()`, `memory_list()`, `get_structured()`
- Cosmos DB memory access with embeddings + LRU cache
- Auto-injection of `platform-tools` MCP server URL into OpenClaw CR

**Remaining:**
- `mcp_server_azure_search.py` — Azure AI Search integration
- `mcp_server_key_vault.py` — Key Vault secret retrieval tool

**Risk:** Low — MCP is a standard protocol, OpenClaw already supports it natively  
**Depends on:** Item 10 (value is marginal without native UI exposure)

### 12. ✅ LLM Token Tracking Proxy
**Status:** Implemented (Phase 29 — completed 2025-07-16)
**Priority:** 🔧 High — required for monitoring/billing after pivot
**Problem:** When agents are configured through OpenClaw's native UI, the platform loses visibility into token consumption. Currently, tokens are tracked in the Agent Executor layer which won't be in the path anymore.  
**Solution:** Route OpenClaw's LLM calls through a thin platform proxy that counts tokens.

**Architecture:**
```
OpenClaw → token-proxy.aiplatform.svc:8080 → Azure OpenAI
```

**Proxy responsibilities:**
- Forward requests transparently (OpenAI-compatible passthrough)
- Log token counts (prompt + completion) per agent/tenant to Cosmos DB
- Enforce rate limits / budget caps per tenant
- Emit metrics to Application Insights
- Platform monitoring dashboard reads from same Cosmos DB collection

**Implementation:**
- Lightweight FastAPI or Go service
- Deployed as shared service in `aiplatform` namespace
- OpenClaw CR `models.providers.azure-openai-responses.baseUrl` points to proxy instead of Azure OpenAI directly
- Proxy adds `X-Agent-Id` and `X-Tenant-Id` headers for tracking

**Files:**
- New `backend/microservices/llm_proxy/` — proxy service
- `backend/app/services/openclaw_service.py` — set `baseUrl` to proxy URL in CR
- K8s deployment for the proxy
- Cosmos DB collection for token logs

**Implemented:**
- `backend/microservices/llm_proxy/main.py` — FastAPI proxy service
- `backend/microservices/llm_proxy/Dockerfile`
- `backend/app/repositories/token_log_repository.py` — Cosmos DB token logging
- Streaming support with `stream_options.include_usage` injection
- Token extraction from both streaming and non-streaming responses
- Fire-and-forget Cosmos DB logging (async, non-blocking)
- Path-based tenant/agent routing: `/proxy/{tenant_id}/{agent_id}/`
- `openclaw_service.py` injects proxy URL into agent CR config

**Risk:** Low — simple transparent proxy, easy to bypass in emergency by pointing back to Azure OpenAI  
**Depends on:** Nothing

### 13. ✅ Memory as MCP Tool (Replaces System Message Injection)
**Status:** Implemented (Phase 30 — completed 2026-04-04)
**Priority:** 🔧 Medium
**Problem:** Today the platform injects Cosmos DB memories as system messages before each chat. With the native UI pivot, we lose this injection point.  
**Solution:** Expose the memory system as an MCP tool so the agent can search/store memories on demand.

**Tools:**
- `memory_search(query, top_k)` — retrieves relevant past context from Cosmos DB
- `memory_store(key, value, tags)` — saves new memory to Cosmos DB
- `memory_list(filter)` — lists stored memories

**Why this is better:** The agent decides when to search memory (on-demand) rather than getting a dump every single message. More efficient and context-aware.

**Implemented:**
- MCP tools: `memory_search(query, top_k)`, `memory_store(key, value, tags)`, `memory_list(filter)`, `get_structured(key)`
- `backend/microservices/mcp_platform_tools/memory.py`
- Auto-injected into agent OpenClaw CR as `platform-tools` MCP server

**Files:** Part of Item 11 (`mcp-cosmos-memory` server)  
**Depends on:** Item 11

### 14. 🟡 Agent Chaining via OpenAI-Compatible Endpoint
**Status:** Partial — endpoint enabled in CR, orchestration not wired
**Priority:** 🔧 Medium
**Problem:** The workflow engine currently chains agents through internal Python calls. With standalone OpenClaw instances, agents need a standard API to call each other.  
**Solution:** Use OpenClaw's built-in `/v1/chat/completions` endpoint. Each agent pod exposes this endpoint. The workflow engine calls Agent B just like calling an LLM.

**Example workflow engine call:**
```python
response = await httpx.post(
    f"http://oc-agent-b.tenant-eng.svc:18789/v1/chat/completions",
    json={
        "model": "agent",
        "messages": [{"role": "user", "content": "Summarize today's Jira tickets"}]
    }
)
```

**Files:**
- `backend/microservices/workflow_engine/` — update agent-to-agent calls to use HTTP
- `backend/app/services/agent_execution.py` — add OpenAI-compatible proxy route for external consumers
- New API endpoint: `POST /api/v1/agents/{id}/openai/v1/chat/completions` — authenticates + proxies

**Implemented:**
- `openclaw_service.py` sets `gateway.http.endpoints.chatCompletions.enabled: true` in CR
- Each agent pod exposes `/v1/chat/completions` endpoint

**Remaining:**
- Workflow engine still uses internal Python calls, not HTTP to OpenClaw endpoints
- Need to update `backend/microservices/workflow_engine/` to use agent-to-agent HTTP calls
- Platform API proxy route `POST /api/v1/agents/{id}/openai/v1/chat/completions` not built

**Risk:** Low — OpenClaw already serves this endpoint  
**Depends on:** Nothing

### 15. Simplified Platform UI (Post-Pivot)
**Status:** Not started  
**Priority:** 🔧 Medium — after Items 10-12 are done  
**Problem:** After the pivot, the current agent config pages (system prompt, channels, tools) become redundant since users configure agents in OpenClaw's native UI.  
**Solution:** Simplify the platform UI to focus on what it owns:

**Keep:**
- Agent list / create / delete page
- Monitoring dashboard (pod health, token usage, costs)
- Agent chaining / workflow builder
- Tenant management / RBAC
- Link to OpenClaw native UI ("Open Agent Console" button)

**Remove or deprecate:**
- System prompt editor (OpenClaw handles this)
- Channel wizard (OpenClaw handles this)
- Tool configuration page (OpenClaw handles this)
- Playground chat (users chat via OpenClaw UI or channels directly)

**Files:** Frontend pages under `src/app/dashboard/agents/`  
**Depends on:** Items 10, 11, 12

### 16. ✅ Pod Resource Sizing (T-Shirt Sizes) for Agent Deployment
**Status:** Implemented  
**Priority:** 🔧 Medium  
**Problem:** When deploying an OpenClaw agent from the platform UI, there's no option to specify pod resource sizing. All agents get the same default CPU/memory/disk — no way to right-size for lightweight bots vs. heavy workloads.  
**Solution:** Added "Resource Profile" selector to the agent deployment flow with T-shirt sizes:

| Size | CPU Request/Limit | Memory Request/Limit | PVC | Use Case |
|---|---|---|---|---|
| Small | 250m / 500m | 256Mi / 512Mi | 1Gi | Low-traffic bot, single channel |
| Medium (default) | 500m / 1000m | 512Mi / 1Gi | 5Gi | Standard agent, multi-channel |
| Large | 1000m / 2000m | 1Gi / 2Gi | 10Gi | High-traffic, heavy memory/tools |

**Implemented:**
- `backend/app/api/v1/schemas.py` — `RESOURCE_PROFILES` dict with cpu/memory/pvc specs per size, `resource_profile` field on `AgentCreateRequest` (default "medium"), `AgentUpdateRequest` (optional), `AgentResponse`
- `backend/app/api/v1/agents.py` — `resource_profile` in create data, passed to `deploy_agent()`, update detects profile change and triggers CR redeploy
- `backend/app/services/openclaw_service.py` — `resource_profile` parameter on `deploy_agent()`, `update_agent()`, `_build_cr()`. CR spec now includes `resources.requests/limits` and `storage.persistence.size` from profile
- `frontend/src/app/dashboard/agents/new/page.tsx` — 3-card radio selector UI (Small/Medium/Large) with CPU/Memory/Disk specs and use case descriptions
- `frontend/src/app/dashboard/agents/[id]/page.tsx` — resource profile selector on edit page, dirty tracking, triggers redeploy on change

**Risk:** Low — purely additive. Current agents continue with existing defaults (medium).  
**Depends on:** Nothing

---

## ⚠️ Known Limitations After Pivot

| Limitation | Why | Mitigation |
|---|---|---|
| Unified conversation history | Each OpenClaw instance owns its own sessions — platform can't merge them | Item 5 (Cosmos DB sync) partially addresses this |
| Custom platform UI widgets for agent config | Platform-specific config (e.g., "link to Jira project X") needs to be outside OpenClaw's UI | Use MCP server config instead |
| Scale-to-zero | OpenClaw needs a running pod; no serverless mode | Accept cost — already the case today |
| Offline agents | Pod must be running to process messages | Same as today |

---

## 📋 Backlog (Ideas / Future)

- **Policy Engine & Governance** (deferred from v1.0 Phase 7) — content filtering, rate limiting, audit trail
- **Agent Marketplace** — share agent configs, skills, workspace templates between tenants
- **Voice channel** — integrate with Azure Communication Services for voice calls
- **Scheduled messages** — agent sends periodic updates/summaries via WhatsApp/Telegram
- **Multi-tenant WhatsApp** — one WhatsApp Business account shared across tenants with routing

---

---

## 📊 Implementation Summary

| # | Item | Status |
|---|------|--------|
| 1 | OpenClaw Memory & Session Tools | ✅ Done |
| 2 | Cross-Channel Identity Linking | ❌ Not started |
| 3 | Workspace Initial Files | 🟡 Partial (backend done, frontend missing) |
| 4 | Honcho Plugin | ❌ Not started (deferred) |
| 5 | Cosmos DB Memory Sync | 🟡 Partial (MCP approach, no polling sync) |
| 6 | Multi-Agent WhatsApp Routing | ❌ Not started |
| 7 | Channel Analytics Dashboard | 🟡 Partial (UI components exist, data TBD) |
| 8 | PVC Cleanup & Archival | ✅ Done |
| 9 | KeyVault Separation | 🟡 Partial (infra done, backend wiring incomplete) |
| 10 | OpenClaw Native UI Proxy | ✅ Done (Phase 31) |
| 11 | Platform MCP Servers | 🟡 Partial (memory done, Search/KV missing) |
| 12 | LLM Token Tracking Proxy | ✅ Done (Phase 29) |
| 13 | Memory as MCP Tool | ✅ Done (Phase 30) |
| 14 | Agent Chaining | 🟡 Partial (endpoint enabled, orchestration TBD) |
| 15 | Simplified Platform UI | ❌ Not started |
| 16 | Pod Resource Sizing | ✅ Done |

*Last updated: 2026-07-17*
