# AI Platform v2 — Architecture Pivot: Platform as Infrastructure, OpenClaw as Agent Runtime

> This document captures the complete context for the next major evolution of the AI Platform.
> It combines insights from platform analysis, TODO items 1-15, and architectural discussions.
> Use this as input for project planning (GSD or otherwise).

---

## 1. What We Have Today

### Platform Architecture (Current)
A multi-tenant AI agent platform running on AKS that **wraps OpenClaw** with a custom UI:

```
User's Browser
     │ HTTP/REST + SSE
     ▼
┌──────────────────────────┐
│  Next.js Frontend        │  ← Custom UI (agent mgmt, chat, channels, monitoring)
└────────────┬─────────────┘
             │ REST API
             ▼
┌──────────────────────────┐
│  Python Backend          │  ← Translates REST → WebSocket, injects memory/RAG
│  (FastAPI + 5 microsvcs) │
└────────────┬─────────────┘
             │ WebSocket JSON-RPC (in-cluster only)
             ▼
┌──────────────────────────┐
│  OpenClaw Pod (Headless) │  ← Has a UI, but nobody can reach it
│  4 containers per pod    │
└──────────────────────────┘
```

### Cosmos DB (34 containers, `aiplatform` database)
- **Tenant/User**: tenants, users, refresh_tokens
- **Agents**: agents, agent_config_versions, agent_templates
- **Tools**: tools, agent_tools, agent_mcp_tools, tool_templates
- **MCP**: mcp_servers, mcp_discovered_tools
- **RAG**: data_sources, agent_data_sources, documents, document_chunks
- **Conversations**: threads, thread_messages, agent_memories
- **Workflows**: workflows, workflow_nodes, workflow_edges, workflow_executions, workflow_node_executions
- **Observability**: execution_logs, model_pricing, cost_alerts
- **Azure/Marketplace**: model_endpoints, azure_subscriptions, azure_connections, catalog_entries
- **Testing**: test_suites, test_cases, evaluation_runs, evaluation_results

All 34 containers are read/written exclusively by the platform Python services. OpenClaw touches none of them — it stores everything on a PVC (local filesystem).

### AKS Multi-Tenant Model
- **Shared control plane** (namespace `aiplatform`): api-gateway, workflow-engine, mcp-proxy
- **Per-tenant pods** (namespace `tenant-{slug}`): agent-executor, tool-executor, OpenClaw StatefulSets
- Each tenant gets: Namespace, ServiceAccount, ResourceQuota, LimitRange, NetworkPolicy
- OpenClaw deployed as `OpenClawInstance` Custom Resource, managed by OpenClaw Operator
- Each OpenClaw pod: 4 containers (openclaw, wa-bridge, gateway-proxy, chromium)
- ACR: `stumsftaiplatformprodacr.azurecr.io`, AKS: `stumsft-aiplatform-prod-aks`

### OpenClaw Integration (How the UI Masks It)
The platform communicates with OpenClaw via WebSocket JSON-RPC:
- `chat.send` — send messages, receive streaming responses
- `web.login.start` / `web.login.wait` — WhatsApp QR code linking
- `channels.status` / `channels.logout` — channel management
- `sessions.list` — group discovery

OpenClaw's native web UI (port 18789) is never exposed — NetworkPolicy + ClusterIP only.

### Patched OpenClaw Image
Custom `Dockerfile.openclaw-patched` fixes critical WhatsApp bugs:
- `markOnlineOnConnect: true` (fix offline device)
- `shouldSyncHistoryMessage: () => true` (fix group message sync)
- Socket leak fix
- Stale creds backup disabled

---

## 2. The Problem

### OpenClaw Release Velocity
OpenClaw ships new features, channels, and improvements at an extremely high pace. Our custom UI masking approach exposes only ~60% of OpenClaw's capabilities and falls further behind with every release.

### Features NOT Exposed in Our UI
| Feature | OpenClaw Has It | Our UI |
|---|---|---|
| Slack channel | ✅ Native bot | ❌ No form |
| Discord channel | ✅ Native bot | ❌ No form |
| Deep Research mode | ✅ Secondary reasoning model | ❌ No toggle |
| Web Browsing on/off | ✅ Chromium sidecar | ❌ Always on |
| Session scope modes | ✅ per-sender / per-peer | ❌ Hardcoded |
| Memory search config | ✅ Vector + BM25 tuning | ❌ Not exposed |
| OpenAI-compatible API | ✅ `/v1/chat/completions` | ❌ Internal only |
| Pod storage/resources | ✅ Configurable PVC | ❌ Fixed |
| ReAct loop iterations | ✅ Max iteration cap | ❌ Not exposed |
| Email folder management | ✅ Himalaya CLI | ❌ Auto-configured |

### Infrastructure Drift
Changes were made directly to production during development. Unknown whether `az deployment` with current Bicep templates would reproduce a working platform. Need an infrastructure audit and clean provision-from-zero validation.

---

## 3. Platform Value-Adds (What We Built Beyond OpenClaw)

These are capabilities our platform provides that OpenClaw cannot do natively:

### Per-Group Custom Instructions (Critical)
- Per WhatsApp/Telegram group: policy (open/allowlist/blocked), require_mention, allowed_phones, **custom instructions**
- Human-readable group name mapping (Hebrew, etc.) — OpenClaw only knows JIDs
- Name-based group discovery — add group by name, auto-resolve JID on first message
- Group discovery polling endpoint — scans pod for new groups
- **Key insight:** Per-group custom instructions are injected as system messages by `agent_execution.py`. OpenClaw has zero concept of per-group behavioral differences. This is our unique value-add, not UI duplication.

### Azure Infrastructure Integration
OpenClaw is a standalone app designed for laptops/VMs. It has zero Azure SDK code:
| Azure Service | Current Bridge | Who Does It |
|---|---|---|
| Key Vault → Secrets | K8s CSI SecretProviderClass | **Kubernetes** (transparent) ✅ |
| Azure OpenAI → LLM | `baseUrl` in CR config | **CR config** (transparent) ✅ |
| Cosmos DB → Agent config | Platform stores in Cosmos, generates CR | **Platform** (OpenClaw never touches Cosmos) |
| AI Search → RAG | Platform injects RAG as system messages | **Platform interceptor** |
| Cosmos DB → Memory | Not bridged | **Nobody** — OpenClaw uses local files |

### Multi-Tenant Isolation
Namespace-per-tenant, NetworkPolicy, ResourceQuota, LimitRange — all platform-managed.

### Monitoring & Observability
Token tracking, execution logs, cost alerts, agent health — all platform-managed.

### Workflow Engine
Agent chaining, sequential workflows, node execution tracking — all platform-managed.

### Evaluation Framework
Test suites, test cases, evaluation runs, scoring — all platform-managed.

---

## 4. The Pivot: Platform as Infrastructure Provider

### New Architecture Model
The platform stops being a "UI wrapper" and becomes an "infrastructure provider":

| Layer | Owner | Responsibility |
|---|---|---|
| Tenant management | Platform | Create/delete tenants, RBAC, billing |
| Agent lifecycle | Platform | Deploy/destroy OpenClaw pods, scaling |
| Monitoring | Platform | Token usage, costs, health, logs |
| Agent chaining | Platform | Workflow engine, inter-agent routing |
| Azure infra bridge | Platform | Expose Azure services as MCP tools |
| Agent configuration | **OpenClaw native UI** | System prompt, tools, channels, skills |
| Agent capabilities | **OpenClaw** | Chat, ReAct, MCP tools, channels, memory |

### What OpenClaw Can Natively Extend (for end users)
| Mechanism | What It Does | How Users Add It |
|---|---|---|
| System Prompt | Agent behavior/persona | Edit in OpenClaw UI |
| MCP Servers | External tools (APIs, databases) | Add URL in OpenClaw UI |
| Skills | CLI tools (email, web browse) | Enable in CR config |
| Workspace Files | Context/knowledge (MEMORY.md) | Edit in OpenClaw UI |
| Plugins | Event hooks (Honcho) | Not yet implemented |

### What Can Be Bridged Transparently
| Azure Service | Method | Transparent? |
|---|---|---|
| Key Vault | K8s CSI | ✅ Yes (already done) |
| Azure OpenAI | URL in config | ✅ Yes (already done) |
| Token tracking | LLM proxy | ✅ Yes (new component) |
| App Insights | LLM proxy telemetry | ✅ Yes (new component) |

### What Requires MCP Tools (Explicit, Not Transparent)
| Azure Service | MCP Tool | Agent Must |
|---|---|---|
| Cosmos DB memory | `memory_search()`, `memory_store()` | Call tool explicitly |
| AI Search RAG | `search_documents()` | Call tool explicitly |
| Per-group rules | `get_group_instructions()` | Call tool on each group message |

---

## 5. Implementation Phases

### Phase 1: Infrastructure Foundation (Bicep + K8s)
**Goal:** Deploy new Azure resources alongside existing ones. Zero changes to running platform.

**Deliverables:**
- `infra/modules/keyvault-tenants.bicep` — new tenant Key Vault (TODO #9)
- LLM token counting proxy deployment (TODO #12)
- Wildcard DNS `*.agents.{domain}` + wildcard TLS cert (TODO #10 prep)
- Wildcard Ingress template for OpenClaw native UI access (TODO #10 prep)

**Validation:** `az deployment` succeeds, new resources visible in portal, no impact on running platform.

### Phase 2: Token Proxy Activation
**Goal:** Get token tracking for ALL agent activity (both platform chat and direct OpenClaw conversations).

**Deliverables:**
- Token counting proxy service (FastAPI or Go, deployed in `aiplatform` namespace)
- Update OpenClaw CR `baseUrl` to route through proxy → Azure OpenAI
- Cosmos DB collection for token logs
- Monitoring dashboard reads from token logs

**Validation:** Deploy one test agent, chat via WhatsApp, see tokens tracked in Cosmos DB.

### Phase 3: Platform MCP Servers
**Goal:** Expose Azure infrastructure as tools OpenClaw agents can call natively.

**Deliverables:**
- `mcp-cosmos-memory` — memory_search(), memory_store(), list_memories()
- `mcp-azure-search` — search_documents(), list_indexes(), index_document()
- `mcp-platform-context` — get_group_instructions(), get_agent_config(), list_configured_groups()
- Auto-inject MCP server URLs into OpenClaw CR on deploy

**Validation:** Agent calls `memory_search()` via MCP, gets results from Cosmos DB. Agent calls `get_group_instructions()`, gets per-group rules.

### Phase 4: Expose OpenClaw Native UI
**Goal:** Authenticated access to OpenClaw's full web UI for each agent.

**Deliverables:**
- Wildcard Ingress rules created dynamically on agent deploy
- Auth gateway validates Azure AD token, proxies to OpenClaw pod
- WebSocket upgrade support
- "Open Agent Console" button in platform frontend
- Each agent accessible at `agent-{id}.agents.{domain}`

**Validation:** User clicks button, sees full OpenClaw UI, can configure agent, changes take effect.

### Phase 5: Dual-Mode Operation
**Goal:** Both platform UI and OpenClaw native UI work simultaneously for every agent.

**Deliverables:**
- All existing platform features still work (no removals)
- OpenClaw native UI available alongside
- Token tracking works regardless of path
- Per-group rules accessible via both injection (platform path) and MCP tool (native path)

**Validation:** Same agent works from both UIs. Changes in one are reflected in the other where applicable.

### Phase 6: Simplify Platform UI (Only After Phase 5 Validation)
**Goal:** Remove redundant platform UI pages that OpenClaw native UI handles better.

**Deliverables:**
- Keep: Agent list/create/delete, monitoring, workflows, group rules, RBAC, billing
- Deprecate: System prompt editor, channel wizard, tool config, playground chat
- Document migration guide for users

**Validation:** Users confirm they prefer native UI for deprecated features.

---

## 6. Existing TODO Items (Carry Forward)

### Already Implemented
- ✅ **#1** OpenClaw Memory & Session Tools Config

### Independent Items (Can Be Done Anytime)
- **#2** Cross-Channel Identity Linking — platform concern, independent of pivot
- **#3** Agent Workspace Initial Files — still valuable for initial agent setup
- **#4** Honcho Plugin — evaluate after Phase 3 MCP memory tools
- **#9** Key Vault Separation — included in Phase 1

### Pivot-Dependent Items
- **#5** OpenClaw → Cosmos DB Memory Sync — partially addressed by Phase 3 MCP tools
- **#6** Multi-Agent WhatsApp Routing — independent, workflow engine concern
- **#7** Channel Analytics Dashboard — depends on Phase 2 token proxy data
- **#8** Automated PVC Cleanup — depends on #5 sync service
- **#10** Expose OpenClaw Native UI — Phase 4
- **#11** Platform MCP Servers — Phase 3
- **#12** LLM Token Tracking Proxy — Phase 2
- **#13** Memory as MCP Tool — Phase 3
- **#14** Agent Chaining via OpenAI-Compatible Endpoint — Phase 5
- **#15** Simplified Platform UI — Phase 6

---

## 7. Infrastructure Audit Requirement

### Problem
Production environment has drifted from Bicep/K8s templates. Unknown what works from a clean `az deployment`. Must audit before building on top.

### What Needs Checking
1. **Azure resources** — Compare deployed resources with Bicep templates (Cosmos, Key Vault, AKS, ACR, DNS, VNET, App Insights, Log Analytics)
2. **K8s manifests** — Compare running workloads with `k8s/` manifests (deployments, services, configmaps, secrets, ingress, network policies)
3. **OpenClaw Operator** — Is the operator deployment captured in IaC?
4. **ConfigMap values** — Are all env vars in `k8s/base/configmap.yaml` current?
5. **Secret references** — Do all `SecretProviderClass` entries match Key Vault contents?
6. **Docker images** — Are Dockerfiles + build commands documented for all images?

### Desired Outcome
A clean `az deployment` + `kubectl apply` produces a fully working platform identical to production, including:
- All Azure resources provisioned correctly
- All K8s workloads running
- OpenClaw Operator installed and functional
- At least one tenant namespace provisionable
- At least one OpenClaw agent deployable and functional

---

## 8. Known Limitations After Pivot

| Limitation | Why | Mitigation |
|---|---|---|
| Unified conversation history | Each OpenClaw instance owns its own sessions | Cosmos DB sync (TODO #5) or MCP memory tools |
| Custom platform UI widgets | Platform-specific config outside OpenClaw's UI | Use MCP server config |
| Scale-to-zero | OpenClaw needs a running pod | Accept cost (existing limitation) |
| Offline agents | Pod must be running to process messages | Same as today |
| Two memory systems | OpenClaw local + Cosmos via MCP | Agent has access to both; may cause confusion |

---

## 9. Success Criteria

1. **Clean deploy works** — `az deployment` + `kubectl apply` from scratch produces working platform
2. **Token tracking universal** — All LLM calls tracked regardless of UI path
3. **Azure services accessible via MCP** — Agent can search Cosmos, query AI Search, get group rules
4. **Native UI accessible** — Users can open OpenClaw's full UI for any agent
5. **No regressions** — All existing platform features continue working during and after pivot
6. **Per-group rules preserved** — Custom instructions work through both platform and native UI paths

---

*Created: 2026-04-04*
*Source: Platform analysis + TODO.md + architecture discussions*
