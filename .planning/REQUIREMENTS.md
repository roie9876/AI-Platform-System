# Requirements: v4.0 Architecture Pivot — Platform as Infrastructure Provider

**Defined:** 2026-04-04
**Core Value:** Product teams can go from zero to a working AI agent with tools, data sources, and orchestration — without writing infrastructure code or managing model deployments.

## v4.0 Requirements

Requirements for the architecture pivot: transforming the platform from an OpenClaw UI wrapper to an infrastructure provider with native UI exposure.

### Infrastructure Audit

- [ ] **AUDIT-01**: User can run `az deployment` + `kubectl apply` from scratch and get a fully working platform identical to production
- [ ] **AUDIT-02**: User can see Bicep template drift resolved — templates match all deployed Azure resources
- [ ] **AUDIT-03**: User can see K8s manifest drift resolved — manifests match all running workloads, ConfigMaps, and Secrets
- [ ] **AUDIT-04**: User can provision wildcard DNS record and TLS certificate for `*.agents.{domain}`
- [ ] **AUDIT-05**: User can see platform secrets and tenant secrets in separate Key Vaults with independent RBAC — tenant pods cannot read platform infrastructure secrets
- [ ] **AUDIT-06**: User can see existing tenant secrets migrated from platform vault to tenant vault with zero downtime

### Token Proxy

- [ ] **PROXY-01**: User can see all LLM requests transparently proxied through a centralized gateway with zero impact on agent behavior
- [ ] **PROXY-02**: User can see token usage captured from streaming responses via `stream_options.include_usage` without client-side counting
- [ ] **PROXY-03**: User can see token usage logged to Cosmos DB with tenant_id and agent_id attribution per request
- [ ] **PROXY-04**: User can configure per-tenant token budget limits with alerts when thresholds are reached
- [ ] **PROXY-05**: User can see OpenClaw CR `baseUrl` automatically routes through the proxy on agent deploy

### Platform MCP Servers

- [ ] **MCPSRV-01**: Agent can call `memory_search(query)` via MCP and get relevant memories from Cosmos DB
- [ ] **MCPSRV-02**: Agent can call `memory_store(content)` via MCP and persist new memories to Cosmos DB
- [ ] **MCPSRV-03**: Agent can call `search_documents(query, index)` via MCP and get results from Azure AI Search
- [ ] **MCPSRV-04**: Agent can call `get_group_instructions(group_jid)` via MCP and get per-group custom instructions
- [ ] **MCPSRV-05**: Agent can call `get_agent_config()` and `list_configured_groups()` via MCP for platform context
- [ ] **MCPSRV-06**: User can see MCP server URLs auto-injected into OpenClaw CR on agent deploy
- [ ] **MCPSRV-07**: User can see Cosmos DB DiskANN vector index enabled on agent_memories container

### Native UI Access

- [ ] **NATIVEUI-01**: User can access OpenClaw's full native web UI for any agent via `agent-{id}.agents.{domain}`
- [ ] **NATIVEUI-02**: User is authenticated via Entra ID OIDC before reaching OpenClaw UI
- [ ] **NATIVEUI-03**: User can only access agents belonging to their tenant
- [ ] **NATIVEUI-04**: User can use WebSocket-based features in native UI through the auth proxy
- [ ] **NATIVEUI-05**: User can click "Open Agent Console" in platform frontend to open native UI in new tab

### Dual-Mode Operation

- [ ] **DUAL-01**: User can interact with the same agent from both platform UI and OpenClaw native UI simultaneously
- [ ] **DUAL-02**: User can see token tracking works regardless of which UI path is used
- [ ] **DUAL-03**: User can see per-group rules work via platform injection (platform path) and MCP tool (native path)
- [ ] **DUAL-04**: User can confirm all existing platform features continue working with no regressions
## Future Requirements

Deferred to post-v4.0. Tracked but not in current roadmap.

### Architecture Pivot

- **PIVOT-F01**: Platform UI simplification — deprecate redundant pages that OpenClaw native UI handles better (system prompt editor, channel wizard, tool config, playground chat)
- **PIVOT-F02**: Cosmos DB memory sync service — bidirectional sync between OpenClaw local memory and Cosmos DB
- **PIVOT-F03**: OpenClaw → Cosmos DB conversation history bridge — unified conversation view
- **PIVOT-F04**: Scale-to-zero agent pods — suspend idle OpenClaw instances to save cost
- **PIVOT-F05**: Cross-channel identity linking — map same user across WhatsApp, Slack, Discord

### Carried Forward from v3.0

- **TENANT-F01**: Tenant configuration can be cloned as a template for new tenants
- **TENANT-F02**: Tenants auto-suspend after N days of inactivity
- **INFRA-F03**: GitHub Actions workflow runs az deployment what-if for infrastructure drift detection
- **DATA-F01**: Cosmos DB change feed enables event streaming for cross-service reactivity

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| UI simplification / page removal | Deferred — keep all platform UI pages in v4.0, add native UI as additive feature |
| Cosmos DB memory sync service | MCP tools provide explicit access; sync is a v5.0 concern |
| Multi-cloud deployment | Microsoft-first, single-cloud architecture |
| Billing / payment system | Internal enterprise platform — no customer billing |
| Custom OpenClaw fork | Vendor-managed runtime; only CR config and Dockerfile patches |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUDIT-01 | Phase 28 | Pending |
| AUDIT-02 | Phase 28 | Pending |
| AUDIT-03 | Phase 28 | Pending |
| AUDIT-04 | Phase 28 | Pending |
| AUDIT-05 | Phase 28 | Pending |
| AUDIT-06 | Phase 28 | Pending |
| PROXY-01 | Phase 29 | Pending |
| PROXY-02 | Phase 29 | Pending |
| PROXY-03 | Phase 29 | Pending |
| PROXY-04 | Phase 29 | Pending |
| PROXY-05 | Phase 29 | Pending |
| MCPSRV-01 | Phase 30 | Pending |
| MCPSRV-02 | Phase 30 | Pending |
| MCPSRV-03 | Phase 30 | Pending |
| MCPSRV-04 | Phase 30 | Pending |
| MCPSRV-05 | Phase 30 | Pending |
| MCPSRV-06 | Phase 30 | Pending |
| MCPSRV-07 | Phase 30 | Pending |
| NATIVEUI-01 | Phase 31 | Pending |
| NATIVEUI-02 | Phase 31 | Pending |
| NATIVEUI-03 | Phase 31 | Pending |
| NATIVEUI-04 | Phase 31 | Pending |
| NATIVEUI-05 | Phase 31 | Pending |
| DUAL-01 | Phase 32 | Pending |
| DUAL-02 | Phase 32 | Pending |
| DUAL-03 | Phase 32 | Pending |
| DUAL-04 | Phase 32 | Pending |

**Coverage:**
- v4.0 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0

---
*Requirements defined: 2026-04-04*
*Last updated: 2026-04-04 after v4.0 roadmap creation*
