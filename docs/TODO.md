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

### 3. Agent Workspace Initial Files via Platform
**Status:** Not started  
**Problem:** Agent has no `MEMORY.md` or custom instructions beyond system prompt.  
**Solution:** Allow platform users to upload/edit workspace files (MEMORY.md, AGENTS.md, custom skills) via the agent config UI. Inject them via `spec.workspace.initialFiles` in the CR.  
**Options:**
- **A) Simple textarea** — edit MEMORY.md and AGENTS.md from agent settings page
- **B) File manager** — full workspace file browser in the UI
- **C) Git sync** — point to a git repo with workspace files

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

### 5. OpenClaw → Cosmos DB Memory Sync Service
**Status:** Architecture designed, not built  
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

### 7. Channel Analytics Dashboard
**Status:** Not started  
**Problem:** No visibility into message volumes, response times, channel health across WhatsApp/Telegram/Gmail.  
**Solution:** Collect metrics from OpenClaw session data, display in platform monitoring tab.  
**Metrics:** Messages/day per channel, avg response time, active users, memory usage, session count.

### 8. Automated PVC Cleanup & Archival
**Status:** Not started  
**Problem:** PVC fills up over time with old sessions. Manual cleanup is risky.  
**Solution:** Scheduled job that archives old session JSONL to blob storage and prunes PVC.  
**Depends on:** Item 5 (data must be synced to Cosmos before pruning)

### 9. KeyVault Separation — Platform vs Tenant Secrets
**Status:** Not started  
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

**Risk:** Medium — fallback pattern ensures backward compatibility. Rollback = revert `TENANT_KEY_VAULT_NAME` to same value as `KEY_VAULT_NAME`.  
**Depends on:** Nothing — can be done independently  
**Files:** See touchpoints above (~15 files across infra/k8s/backend/scripts)

---

## 📋 Backlog (Ideas / Future)

- **Policy Engine & Governance** (deferred from v1.0 Phase 7) — content filtering, rate limiting, audit trail
- **Agent Marketplace** — share agent configs, skills, workspace templates between tenants
- **Voice channel** — integrate with Azure Communication Services for voice calls
- **Scheduled messages** — agent sends periodic updates/summaries via WhatsApp/Telegram
- **Multi-tenant WhatsApp** — one WhatsApp Business account shared across tenants with routing

---

*Last updated: 2026-04-02*
