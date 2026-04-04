# Phase 29: Token Proxy - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Build and deploy a transparent LLM proxy that sits between OpenClaw pods and Azure OpenAI. The proxy captures token usage from streaming and non-streaming responses, logs every request to Cosmos DB with tenant/agent attribution, enforces per-tenant budget limits with alerts, and wires into the OpenClaw CR automatically on agent deploy. Agent behavior is unchanged — the proxy is invisible to the LLM client.

</domain>

<decisions>
## Implementation Decisions

### Tenant & Agent Attribution
- **D-01:** Path-based identification. The proxy URL encodes tenant and agent IDs: `http://token-proxy.aiplatform.svc:8080/proxy/{tenant_id}/{agent_id}/openai/v1`. The proxy extracts both from the URL path on every request.
- **D-02:** No fallback identification method. All CRs are generated programmatically by `openclaw_service.py`, which embeds the correct tenant/agent path in `baseUrl`. Path-only is sufficient.
- **D-03:** No custom headers needed (avoids dependency on OpenClaw passing through `X-Tenant-Id` / `X-Agent-Id`).

### Budget Enforcement Strategy
- **D-04:** Both soft and hard limits. Soft limits are the default — alerts fire when thresholds are reached but requests continue. Hard limits are opt-in per tenant — when enabled, the proxy returns HTTP 429 once the budget is exceeded.
- **D-05:** Tenant self-service. Tenant admins configure their own token budget limits via the Tenant Admin UI. This requires API endpoints and UI components for budget management.
- **D-06:** Dashboard + notifications for alerts. Budget status is visible in the platform monitoring dashboard (reading from Cosmos DB). When thresholds are hit, webhook/email notifications are sent proactively.

### API Compatibility Scope
- **D-07:** Pluggable multi-provider design with Azure OpenAI as the only implementation in this phase. The proxy has a provider abstraction layer so adding Anthropic/Gemini/generic OpenAI-compatible providers later is a config change, not a rewrite.
- **D-08:** Chat Completions API and Responses API are explicitly handled for token extraction. Any other API paths are forwarded as wildcard passthrough (proxied transparently without token extraction).
- **D-09:** Token counting uses Azure OpenAI's native `stream_options.include_usage` for streaming responses — the proxy injects this flag, extracts the final usage chunk, and logs it asynchronously. No client-side token counting.

### Architecture (from prior research)
- **D-10:** Centralized gateway pattern. The proxy runs as a shared Deployment in `aiplatform` namespace with a ClusterIP Service (`token-proxy.aiplatform.svc:8080`). Matches existing api-gateway, mcp-proxy patterns.
- **D-11:** Custom FastAPI proxy (~300-500 LOC). LiteLLM, Portkey, and Helicone were evaluated and rejected — they introduce unnecessary dependencies (PostgreSQL, SaaS, TypeScript runtime).
- **D-12:** HPA with 2-5 replicas for high availability. PodDisruptionBudget ensures at least 1 replica is always available. Emergency bypass: change CR `baseUrl` back to Azure OpenAI directly.

### Agent's Discretion
- K8s Deployment, Service, HPA, PDB, and NetworkPolicy specifics
- Cosmos DB `TokenLogRepository` implementation details (follows existing `CosmosRepository` pattern)
- App Insights telemetry integration approach (OpenCensus vs OpenTelemetry)
- Cost estimation logic (model pricing lookup for `estimated_cost_usd`)
- Notification delivery mechanism (Azure Monitor action groups, custom webhook, or email SDK)
- Provider abstraction interface design (abstract base class vs protocol)
- `openclaw_service.py` changes for proxy baseUrl injection

### Folded Todos
No todos matched this phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Research
- `.planning/research/TOKEN-PROXY.md` — Comprehensive architecture research: solution comparison, streaming token counting strategy, Cosmos DB schema, K8s deployment blueprint, performance analysis

### Architecture Docs
- `docs/v2-architecture-pivot.md` — Architecture pivot overview; Token Proxy is Phase 2 in the original pivot doc
- `docs/TODO.md` §12 — Original TODO item #12 (LLM Token Tracking Proxy) with architecture diagram and implementation plan

### Phase 28 Dependencies
- `.planning/phases/28-infrastructure-audit-foundation/28-CONTEXT.md` — D-08: `token_logs` Cosmos DB container; D-14-D-19: Key Vault separation

### Existing Code
- `backend/app/services/openclaw_service.py` — Builds OpenClawInstance CR with `baseUrl` (line ~1232). Must be modified for PROXY-05 (auto-route through proxy).
- `backend/app/repositories/base.py` — `CosmosRepository` base class. `TokenLogRepository` follows this pattern.
- `backend/microservices/api_gateway/main.py` — Existing FastAPI microservice pattern for reference.
- `infra/modules/cosmos.bicep` — `token_logs` container definition (added by Phase 28).
- `k8s/base/kustomization.yaml` — Add proxy Deployment, Service, HPA resources here.
- `k8s/base/ingress.yaml` — Reference for existing AGC Ingress routing pattern.

### Requirements
- `.planning/REQUIREMENTS.md` §Token Proxy — PROXY-01 through PROXY-05

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CosmosRepository` base class (`backend/app/repositories/base.py`): Provides `create()`, `query()`, `get()` methods with tenant_id partitioning. `TokenLogRepository` extends this directly.
- `openclaw_service.py` CR builder: Already constructs `baseUrl` dynamically per agent — needs a one-line change to point at the proxy instead of Azure OpenAI directly.
- `backend/microservices/api_gateway/main.py`: Existing FastAPI microservice with Dockerfile, health checks. Use as a template for the proxy service structure.
- `backend/app/services/model_abstraction.py` line 205: Already uses `stream_options.include_usage` in the platform path — validates the approach.

### Established Patterns
- All microservices are Python/FastAPI with `Dockerfile` in their directory.
- Cosmos DB containers use `/tenant_id` partition key universally.
- K8s deployments in `aiplatform` namespace follow the same structure: Deployment + Service + HPA.
- NetworkPolicy already allows `tenant-*` → `aiplatform` namespace traffic.

### Integration Points
- `openclaw_service.py` `_build_cr_body()` method — set `baseUrl` to proxy URL instead of Azure OpenAI endpoint.
- `k8s/base/kustomization.yaml` — add proxy K8s resources.
- Cosmos DB `token_logs` container — already provisioned by Phase 28.
- App Insights — existing telemetry infrastructure for custom metrics emission.

</code_context>

<specifics>
## Specific Ideas

- The proxy URL format is: `http://token-proxy.aiplatform.svc:8080/proxy/{tenant_id}/{agent_id}/openai/v1`
- Research doc has a complete implementation blueprint (§8) with proxy core logic, K8s deployment YAML, and CR modification examples.
- The `stream_options.include_usage` approach is confirmed working for Chat Completions API. Needs verification for Responses API streaming format during implementation.

</specifics>

<deferred>
## Deferred Ideas

- **Token usage dashboard UI** — Platform monitoring already reads from Cosmos DB. A dedicated token analytics page with per-agent/per-model breakdowns belongs in a future phase.
- **Cost attribution with model pricing** — The `estimated_cost_usd` field in token logs requires a model pricing table. Basic implementation can hardcode prices; a dynamic pricing config is a future enhancement.
- **Aggregation service** — Roll up per-request `token_logs` into daily/weekly summaries in a `token_summaries` container for long-term storage. Not needed for initial proxy launch.

</deferred>

---

*Phase: 29-token-proxy*
*Context gathered: 2026-04-04*
