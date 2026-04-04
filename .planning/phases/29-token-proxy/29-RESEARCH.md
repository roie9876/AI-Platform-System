# Phase 29: Token Proxy — Research

**Researched:** 2026-04-04
**Confidence:** HIGH
**Source:** `.planning/research/TOKEN-PROXY.md` (comprehensive architecture research) + codebase verification

## Summary

Build a transparent FastAPI proxy (~300-500 LOC) between OpenClaw pods and Azure OpenAI. Custom proxy chosen over LiteLLM (PostgreSQL dependency), Portkey (TypeScript), and Helicone (SaaS-heavy). See TOKEN-PROXY.md §2 for full comparison.

## Standard Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Runtime | Python 3.12 / FastAPI | Same as all other microservices |
| HTTP Client | httpx (async) | Already in requirements.txt |
| Data Store | Cosmos DB `token_logs` container | Provisioned by Phase 28 (cosmos.bicep) |
| K8s Pattern | Deployment + ClusterIP Service in `aiplatform` namespace | Matches api-gateway, mcp-proxy |
| Scaling | HPA 2-5 replicas | Same pattern as other services |

## Architecture Pattern: Centralized Gateway

Proxy runs as shared service at `token-proxy.aiplatform.svc:8080`. OpenClaw pods in `tenant-*` namespaces call it via CR `baseUrl`. Path-based tenant/agent identification: `/proxy/{tenant_id}/{agent_id}/...`.

## Token Counting Strategy

Azure OpenAI supports `stream_options.include_usage` (GA since 2024-10-21). Proxy injects this flag into streaming requests, streams all chunks through transparently, captures the usage chunk (empty `choices[]` + `usage` object), and logs asynchronously. No buffering, no client-side counting.

## Key Codebase Patterns Verified

1. **CosmosRepository** (`backend/app/repositories/base.py`): `create()`, `query()`, `get()`, `list_all()`, `upsert()` — all take `tenant_id` as first arg. `TokenLogRepository` extends this.
2. **Microservice structure**: Each service has `main.py` + `Dockerfile` in `backend/microservices/{name}/`. Dockerfile copies `app/` (shared lib) + service entry point.
3. **Health checks**: Shared `health_router` from `app.health` with `/healthz`, `/readyz`, `/startupz`.
4. **K8s manifests**: `k8s/base/{name}/deployment.yaml` + `service.yaml`. `kustomization.yaml` lists resources.
5. **Port convention**: Existing services use port 8000. Token proxy uses 8080 (per D-10, CONTEXT.md).
6. **`openclaw_service.py` baseUrl**: `_resolve_model()` returns `base_url`, set via `providers_config[provider_name]["baseUrl"]`. Change point: inject proxy URL instead of direct Azure OpenAI URL.
7. **Workload Identity**: All pods use `serviceAccountName: aiplatform-workload` + `azure.workload.identity/use: "true"` label for Managed Identity auth to Cosmos DB.

## Cosmos DB Container

`token_logs` already defined in `infra/modules/cosmos.bicep` with:
- Partition key: `/tenant_id`
- TTL: 90 days (`defaultTtl: 7776000`)

## Risk: Responses API Streaming

The Responses API (`/openai/v1/responses`) may have a different streaming format than Chat Completions. `stream_options.include_usage` is confirmed for Chat Completions API. For Responses API, the proxy should extract `usage` from the response body (non-streaming) or from SSE events (streaming). Fallback: if no usage found, log with `null` tokens and emit a warning metric.

## Don't Hand-Roll

- Token counting (use Azure OpenAI's native `stream_options.include_usage`)
- Cosmos DB client management (use existing `cosmos_client.py` singleton)
- Health checks (use existing `health_router`)
- Auth to Cosmos DB (use existing Workload Identity pattern)
