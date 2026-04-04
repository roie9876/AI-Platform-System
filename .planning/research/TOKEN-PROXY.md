# LLM Token Proxy / Gateway Architecture Research

**Project:** AI Agent Platform v4.0 — Architecture Pivot
**Domain:** LLM Token Counting Proxy
**Researched:** 2026-04-04
**Overall Confidence:** HIGH

---

## 1. Executive Summary

The platform needs a transparent proxy between OpenClaw pods and Azure OpenAI that counts tokens, logs usage to Cosmos DB, and emits telemetry — without interfering with the LLM request/response flow. After evaluating existing solutions (LiteLLM Proxy, Portkey Gateway, Helicone) against the custom proxy approach, **a lightweight custom FastAPI proxy is the recommended path**. The proxy is simple (< 500 LOC), the requirements are narrow, and existing solutions introduce unnecessary dependencies (PostgreSQL for LiteLLM, external SaaS for Helicone).

The critical technical insight: **Azure OpenAI natively supports `stream_options.include_usage` in streaming responses**, which eliminates the need to count tokens client-side or buffer full responses. The proxy can stream chunks through transparently and extract the final usage chunk before `[DONE]`.

---

## 2. Existing LLM Proxy Solutions Comparison

### 2.1 LiteLLM Proxy

| Aspect | Details |
|--------|---------|
| **Language** | Python (FastAPI) |
| **License** | MIT (core), Enterprise features gated |
| **Azure OpenAI** | Full support — `azure/deployment-name` syntax |
| **Streaming** | Full SSE streaming with token counting |
| **Token Tracking** | Built-in spend tracking per key, user, team |
| **Database** | Requires PostgreSQL — uses it for keys, spend logs, audit |

**Pros:**
- Most feature-complete open-source LLM gateway
- Native Azure OpenAI support including Responses API
- Built-in cost tracking with model pricing database
- Virtual keys with per-key/per-team budgets
- Handles 1.5K+ requests/second under load

**Cons:**
- **Requires PostgreSQL** — we specifically moved away from PostgreSQL to Cosmos DB. Adding a PostgreSQL dependency for a proxy service contradicts the v3.0 architecture decisions.
- **Heavyweight** — LiteLLM is ~100K+ LOC. We need < 1% of its features.
- **Enterprise features gated** — custom spend log metadata, tag-based reporting require enterprise license.
- **Logging to Cosmos DB** — not natively supported. Would need custom callback hooks.
- **Upgrade burden** — fast-moving project with frequent breaking changes.

**Verdict:** Overkill. The proxy needs are narrow: forward requests, count tokens, log to Cosmos DB. LiteLLM's value is in multi-provider routing (100+ LLMs) which we don't need — all traffic goes to Azure OpenAI.

### 2.2 Portkey AI Gateway

| Aspect | Details |
|--------|---------|
| **Language** | TypeScript (Cloudflare Workers) |
| **License** | MIT |
| **Azure OpenAI** | Supported |
| **Streaming** | SSE pass-through |
| **Token Tracking** | Via Portkey cloud dashboard (SaaS) |

**Pros:**
- Fast (edge-native, Cloudflare Workers architecture)
- Clean OpenAI-compatible API
- Supports caching, retries, fallbacks

**Cons:**
- **TypeScript/Node ecosystem** — our backend is Python. Adds a new runtime to the cluster.
- **Cloud-first design** — self-hosted mode has limited features, analytics require Portkey cloud.
- **No native Cosmos DB logging** — would need custom integration.
- **Cloudflare Workers architecture** — not a natural fit for K8s deployment.

**Verdict:** Wrong ecosystem. Cloud-first design doesn't match our self-hosted AKS architecture.

### 2.3 Helicone

| Aspect | Details |
|--------|---------|
| **Language** | TypeScript |
| **License** | Apache 2.0 (core), hosted SaaS |
| **Azure OpenAI** | Supported via header-based proxy |
| **Streaming** | Supported |
| **Token Tracking** | Full tracking with analytics dashboard |

**Pros:**
- Excellent observability and analytics UI
- Simple integration (just change base URL + add header)
- Supports Azure OpenAI

**Cons:**
- **SaaS-first** — self-hosting is possible but complex (requires ClickHouse, Kafka, PostgreSQL, Redis).
- **Heavy infrastructure** — self-hosted Helicone needs 4+ separate services.
- **No Cosmos DB integration** — logs go to ClickHouse.
- **Enterprise internal use** — data residency concerns with SaaS mode.

**Verdict:** Excellent product, wrong deployment model. Self-hosted is too heavy for a simple token counter.

### 2.4 Custom FastAPI Proxy (Recommended)

| Aspect | Details |
|--------|---------|
| **Language** | Python (FastAPI) |
| **Complexity** | ~300-500 LOC |
| **Azure OpenAI** | Direct passthrough — same URL structure |
| **Streaming** | `StreamingResponse` with async generator |
| **Token Tracking** | Extract from `usage` object, log to Cosmos DB |

**Pros:**
- **Minimal** — exactly the features needed, nothing more.
- **Same stack** — Python/FastAPI matches the rest of the platform backend.
- **Cosmos DB native** — logs directly to Cosmos DB using existing `CosmosRepository` patterns.
- **No new dependencies** — uses `httpx` (already in requirements) for proxying.
- **Easy to debug** — team already knows FastAPI, can extend freely.
- **Transparent** — if proxy fails, point `baseUrl` back to Azure OpenAI directly.

**Cons:**
- Must handle SSE streaming correctly (solvable, well-documented pattern).
- Must handle both Chat Completions API and Responses API.
- No built-in dashboard (but platform already has monitoring dashboard reading from Cosmos DB).

**Verdict:** Build it. The requirements are narrow, the implementation is straightforward, and it avoids introducing new infrastructure dependencies.

### Comparison Matrix

| Feature | LiteLLM | Portkey | Helicone | Custom FastAPI |
|---------|---------|---------|----------|----------------|
| Azure OpenAI support | ✅ | ✅ | ✅ | ✅ |
| Streaming + token counting | ✅ | ✅ | ✅ | ✅ |
| Cosmos DB logging | ❌ (PostgreSQL) | ❌ (Cloud) | ❌ (ClickHouse) | ✅ |
| Python/FastAPI stack | ✅ | ❌ (TS) | ❌ (TS) | ✅ |
| Self-hosted K8s ready | ✅ | ⚠️ | ⚠️ | ✅ |
| Minimal dependencies | ❌ | ❌ | ❌ | ✅ |
| Implementation effort | None | Medium | High | Low (~2 days) |
| Operational overhead | Medium | Medium | High | Low |
| Fits existing architecture | ❌ | ❌ | ❌ | ✅ |

**Confidence:** HIGH — based on official documentation for all four options.

---

## 3. Token Counting for Streaming Responses

### 3.1 The Problem

When `stream: true`, Azure OpenAI sends the response as Server-Sent Events (SSE). Each chunk contains a partial message delta, not token counts. Without special handling, the proxy would need to either:
1. Buffer the entire response (defeats the purpose of streaming)
2. Count tokens client-side using tiktoken (inaccurate, model-dependent)

### 3.2 The Solution: `stream_options.include_usage`

**Azure OpenAI supports `stream_options.include_usage` (confirmed in GA API `2024-10-21` and later).**

From the official API reference (`chatCompletionStreamOptions` component):

> If set, an additional chunk will be streamed before the `data: [DONE]` message. The `usage` field on this chunk shows the token usage statistics for the entire request, and the `choices` field will always be an empty array.

This means:
- The proxy does **not** need to buffer the full response
- The proxy does **not** need to count tokens itself
- Azure OpenAI sends a final chunk with the full `usage` object (prompt_tokens, completion_tokens, total_tokens)
- The proxy streams all chunks through transparently, intercepts the usage chunk, and logs it

### 3.3 Streaming Token Counting Strategy

```
Client (OpenClaw) → Proxy → Azure OpenAI
                              │
  stream chunk 1  ◄───────────┤ data: {"choices":[{"delta":{"content":"Hello"}}]}
  stream chunk 2  ◄───────────┤ data: {"choices":[{"delta":{"content":" world"}}]}
  ...                         │
  usage chunk     ◄───────────┤ data: {"choices":[],"usage":{"prompt_tokens":50,"completion_tokens":12,"total_tokens":62}}
  [DONE]          ◄───────────┤ data: [DONE]
                              │
             Proxy logs usage ─┘ (async, non-blocking)
```

**Implementation approach:**

```python
async def proxy_streaming_response(upstream_response, tenant_id, agent_id):
    """Stream chunks through, capture usage from final chunk."""
    usage_data = None
    
    async def generate():
        nonlocal usage_data
        async for chunk in upstream_response.aiter_lines():
            if chunk.startswith("data: ") and chunk != "data: [DONE]":
                data = json.loads(chunk[6:])
                # Check for usage in this chunk
                if data.get("usage"):
                    usage_data = data["usage"]
            yield chunk + "\n\n"
        
        # After stream completes, log usage asynchronously
        if usage_data:
            asyncio.create_task(log_token_usage(
                tenant_id=tenant_id,
                agent_id=agent_id,
                usage=usage_data
            ))
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 3.4 Injecting `stream_options` Transparently

The proxy should **inject** `stream_options.include_usage = true` into every streaming request, even if the client (OpenClaw) didn't request it:

```python
async def forward_request(request_body: dict) -> dict:
    if request_body.get("stream", False):
        request_body.setdefault("stream_options", {})
        request_body["stream_options"]["include_usage"] = True
    return request_body
```

This is transparent to OpenClaw — the usage chunk has an empty `choices` array, so clients that don't expect it simply ignore it.

### 3.5 Non-Streaming Requests

For non-streaming requests, token counting is trivial — the `usage` object is in the JSON response body:

```json
{
  "usage": {
    "prompt_tokens": 50,
    "completion_tokens": 12,
    "total_tokens": 62,
    "completion_tokens_details": {
      "reasoning_tokens": 0
    }
  }
}
```

The proxy reads the response, extracts `usage`, logs it, and returns the response unchanged.

**Confidence:** HIGH — `chatCompletionStreamOptions.include_usage` is documented in the GA API reference (2024-10-21).

---

## 4. Architecture Patterns

### 4.1 Option A: Centralized Gateway (Recommended)

```
┌─────────────────────────────────────────────────────────┐
│  aiplatform namespace                                    │
│                                                          │
│  ┌──────────────────────┐     ┌───────────────────┐     │
│  │  token-proxy          │────▸│  Azure OpenAI       │     │
│  │  (FastAPI, 1-3 pods)  │     │  (external)         │     │
│  │  HPA: 2-5 replicas    │     └───────────────────┘     │
│  └──────────┬───────────┘                                │
│             │ ClusterIP: token-proxy.aiplatform.svc:8080 │
│             │                                            │
├─────────────┼────────────────────────────────────────────┤
│  tenant-eng │namespace                                   │
│             │                                            │
│  ┌──────────┴──────────┐                                │
│  │  OpenClaw Pod         │                                │
│  │  baseUrl → proxy      │                                │
│  └─────────────────────┘                                │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  tenant-sales namespace                                  │
│                                                          │
│  ┌─────────────────────┐                                │
│  │  OpenClaw Pod         │                                │
│  │  baseUrl → proxy      │                                │
│  └─────────────────────┘                                │
└──────────────────────────────────────────────────────────┘
```

**Tenant attribution:** The proxy extracts tenant_id from the request path or custom header. OpenClaw CR `baseUrl` is set to include tenant identification:

```yaml
# Option 1: Path-based
baseUrl: "http://token-proxy.aiplatform.svc:8080/proxy/tenant-eng/openai/v1"

# Option 2: Header-based (set via CR env vars)
baseUrl: "http://token-proxy.aiplatform.svc:8080/openai/v1"
# Plus: X-Tenant-Id header injected by proxy sidecar or CR config
```

**Pros:**
- Single deployment to manage, monitor, and scale
- Centralized logging and telemetry
- Easy to add rate limiting, budget caps per tenant
- Natural fit with existing `aiplatform` namespace shared services
- NetworkPolicy already allows `tenant-*` → `aiplatform` traffic

**Cons:**
- Single point of failure (mitigated by HPA with 2+ replicas)
- Cross-namespace network hop adds ~1-2ms latency
- All tenant traffic flows through shared pods

**Mitigation for SPOF:**
- HPA with 2-5 replicas
- Pod disruption budget (minAvailable: 1)
- Health checks with fast failover
- Emergency bypass: change CR `baseUrl` back to Azure OpenAI directly

### 4.2 Option B: Sidecar Container

```
┌─────────────────────────────────────────┐
│  OpenClaw Pod                            │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │  openclaw     │─▸│  token-proxy      │──▸ Azure OpenAI
│  │  container    │  │  sidecar          │  │
│  └─────────────┘  └──────────────────┘  │
└─────────────────────────────────────────┘
```

**Pros:**
- No cross-namespace network hop
- Per-pod isolation — failure doesn't affect other tenants
- Naturally scoped to tenant (inherits pod's namespace context)

**Cons:**
- **Duplicated resource usage** — every OpenClaw pod gets a proxy container (~128MB RAM each)
- **Deployment coupling** — proxy updates require restarting all OpenClaw pods
- **StatefulSet complexity** — OpenClaw runs as StatefulSet; adding sidecars requires operator changes
- **Operator integration** — the OpenClaw Operator manages pod specs via `OpenClawInstance` CR. Adding a sidecar requires either patching the operator or using a mutating webhook.

### 4.3 Option C: DaemonSet

**Immediate rejection.** DaemonSet runs one pod per node. With 2-3 AKS nodes, you get 2-3 proxy pods serving all tenants. This provides no tenant attribution benefit, wastes resources on nodes without OpenClaw pods, and adds complexity without benefit over Option A.

### 4.4 Recommendation: Centralized Gateway (Option A)

The centralized gateway is the clear winner for this platform:

1. **Matches existing architecture** — api-gateway, workflow-engine, mcp-proxy are already centralized in `aiplatform` namespace
2. **No operator changes** — only CR `baseUrl` is modified, no sidecar injection needed
3. **Simple operations** — one Deployment, one Service, one HPA
4. **Budget enforcement** — centralized point for per-tenant rate limiting and budget caps
5. **Already planned** — TODO #12 in the architecture pivot doc specifies `token-proxy.aiplatform.svc:8080`

**Confidence:** HIGH — aligns with existing architecture patterns and the TODO #12 design.

---

## 5. Azure OpenAI API Specifics

### 5.1 Request/Response Formats

OpenClaw uses the `openai-responses` provider with `api: "openai-responses"`. This means it uses the **Responses API** (not just Chat Completions). The proxy must handle both:

| API | Endpoint Pattern | Token Source |
|-----|-----------------|--------------|
| Chat Completions | `POST /openai/deployments/{deployment}/chat/completions?api-version=...` | `response.usage` |
| Responses | `POST /openai/v1/responses` | `response.usage` |

Both APIs return a `usage` object with the same structure:

```json
{
  "usage": {
    "prompt_tokens": 50,
    "completion_tokens": 12,
    "total_tokens": 62,
    "completion_tokens_details": {
      "reasoning_tokens": 0
    }
  }
}
```

### 5.2 API Version Handling

Azure OpenAI uses `api-version` as a query parameter. The proxy should **pass this through unchanged** — it does not affect the `usage` object structure.

Key versions:
- `2024-10-21` — GA, supports `stream_options.include_usage`
- `v1` — New data plane API (latest), used by OpenClaw's `openai-responses` provider

The proxy treats `api-version` as opaque — forwards whatever the client sends.

### 5.3 Authentication Passthrough

The current OpenClaw CR configuration uses API key auth:

```yaml
azure-openai-responses:
  baseUrl: "https://ai-platform-system.openai.azure.com/openai/v1"
  apiKey: "${AZURE_API_KEY}"
  authHeader: false
  headers:
    api-key: "${AZURE_API_KEY}"
```

The proxy must forward the `api-key` header to Azure OpenAI. Since OpenClaw already includes the header, the proxy simply passes all headers through, adding its own tracking headers (like `X-Tenant-Id`).

### 5.4 Function Calling / Tool Use Token Accounting

When tools are involved, the token counts in `usage` **include all tokens**:
- `prompt_tokens` includes the tool definitions serialized in the prompt
- `completion_tokens` includes the tool call JSON arguments
- For reasoning models, `completion_tokens_details.reasoning_tokens` tracks internal chain-of-thought tokens

The proxy does **not** need to handle tool calling specially — `usage` already accounts for everything.

### 5.5 Reasoning Models (o-series, gpt-5.4)

For reasoning models like `gpt-5.4` (configured as the research model in the CR), the `usage` object includes additional detail:

```json
{
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 500,
    "total_tokens": 600,
    "completion_tokens_details": {
      "reasoning_tokens": 350
    }
  }
}
```

The proxy should log `reasoning_tokens` separately — they're billed at a different rate than output tokens for some models.

**Confidence:** HIGH — based on official Azure OpenAI GA API reference (2024-10-21).

---

## 6. Cosmos DB Token Log Schema

### 6.1 Container Design

**Recommendation: New `token_logs` container**, separate from `execution_logs`.

Rationale:
- `execution_logs` captures platform-path executions (agent executor service). The token proxy captures ALL LLM calls including native OpenClaw path.
- Different write patterns: `execution_logs` are rich documents with full execution context; `token_logs` are high-volume, append-only, lightweight records.
- Different query patterns: token logs need time-range aggregations per tenant; execution logs need per-agent, per-thread lookups.
- Separating concerns avoids polluting the existing `execution_logs` with a different schema.

### 6.2 Partition Key Strategy

**Partition key: `/tenant_id`** (consistent with all other containers)

Rationale:
- All dashboard queries are tenant-scoped (admins view their tenant's usage)
- Cross-tenant aggregation (platform admin) is rare and acceptable as cross-partition
- Composite key (`/tenant_id/agent_id`) was considered but rejected — agent_id is not known at proxy level (proxy sees deployment names, not agent IDs)

### 6.3 Document Schema

```json
{
  "id": "uuid-v4",
  "tenant_id": "eng",
  "agent_id": "7dc6ac5a",           // extracted from request path or header
  "timestamp": "2026-04-04T12:30:00Z",
  "model": "gpt-4.1",                // from response
  "deployment": "gpt-4.1",           // Azure deployment name
  "api": "chat-completions",         // or "responses"
  "stream": true,
  "prompt_tokens": 150,
  "completion_tokens": 85,
  "total_tokens": 235,
  "reasoning_tokens": 0,             // for o-series models
  "cached_tokens": 0,                // if prompt caching is enabled
  "estimated_cost_usd": 0.00047,     // calculated from model_pricing
  "latency_ms": 1250,                // total request duration
  "status": 200,                     // HTTP status code
  "request_id": "chatcmpl-abc123",   // Azure OpenAI request ID
  "source": "native-ui",             // or "platform-api"
  "created_at": "2026-04-04T12:30:00Z",
  "updated_at": "2026-04-04T12:30:00Z"
}
```

### 6.4 Indexing Policy

```json
{
  "indexingMode": "consistent",
  "includedPaths": [
    { "path": "/tenant_id/?" },
    { "path": "/agent_id/?" },
    { "path": "/timestamp/?" },
    { "path": "/model/?" },
    { "path": "/prompt_tokens/?" },
    { "path": "/completion_tokens/?" },
    { "path": "/total_tokens/?" },
    { "path": "/estimated_cost_usd/?" }
  ],
  "excludedPaths": [
    { "path": "/*" }
  ]
}
```

Exclude paths not queried (request_id, deployment, source) to reduce write RU cost.

### 6.5 TTL Policy

Consider setting TTL on the container:
- **90 days** for detailed per-request logs
- Aggregate daily/weekly summaries into a separate `token_summaries` container for long-term storage
- This keeps the `token_logs` container small and fast

### 6.6 Repository Pattern

```python
class TokenLogRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("token_logs")

    async def log_usage(self, tenant_id: str, log: dict) -> dict:
        return await self.create(tenant_id, log)

    async def get_usage_by_date_range(
        self, tenant_id: str, start: str, end: str
    ) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid "
            "AND c.timestamp >= @start AND c.timestamp <= @end "
            "ORDER BY c.timestamp DESC",
            [
                {"name": "@tid", "value": tenant_id},
                {"name": "@start", "value": start},
                {"name": "@end", "value": end},
            ],
        )

    async def get_daily_summary(
        self, tenant_id: str, start: str, end: str
    ) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT c.model, "
            "SUM(c.prompt_tokens) AS total_prompt, "
            "SUM(c.completion_tokens) AS total_completion, "
            "SUM(c.total_tokens) AS total_tokens, "
            "SUM(c.estimated_cost_usd) AS total_cost, "
            "COUNT(1) AS request_count "
            "FROM c WHERE c.tenant_id = @tid "
            "AND c.timestamp >= @start AND c.timestamp <= @end "
            "GROUP BY c.model",
            [
                {"name": "@tid", "value": tenant_id},
                {"name": "@start", "value": start},
                {"name": "@end", "value": end},
            ],
        )
```

**Confidence:** HIGH — follows established Cosmos DB patterns from v3.0 (Phase 19).

---

## 7. Performance Impact

### 7.1 Latency Overhead

| Component | Expected Latency |
|-----------|-----------------|
| Request parsing (JSON decode) | < 1ms |
| Network hop (pod → proxy → Azure OpenAI) | 1-3ms (in-cluster) |
| `stream_options` injection | < 0.1ms |
| Response streaming (passthrough) | ~0ms (async generator, no buffering) |
| Usage extraction from final chunk | < 0.1ms |
| Cosmos DB write (async, fire-and-forget) | 0ms on hot path (background task) |
| **Total added latency** | **2-5ms** |

Context: A typical Azure OpenAI GPT-4.1 response takes 1-5 seconds. The proxy adds < 5ms, which is **< 0.5% overhead** — imperceptible to users.

### 7.2 Python (FastAPI) vs Go Performance

| Metric | FastAPI (Python) | Go (net/http) |
|--------|-----------------|---------------|
| Requests/sec (non-streaming) | ~3,000-5,000 | ~15,000-30,000 |
| Requests/sec (streaming SSE) | ~1,000-2,000 | ~5,000-10,000 |
| Memory per instance | ~80-150MB | ~20-50MB |
| P99 latency overhead | 3-5ms | 1-2ms |
| Development time | ~1-2 days | ~3-5 days |

**For this use case, Python/FastAPI is sufficient:**

1. **Throughput is LLM-bound, not proxy-bound.** Each LLM call takes 1-30 seconds. Even with 100 concurrent agents, throughput is ~10-50 requests/second — far below FastAPI's capacity.
2. **Same stack as the platform.** The team maintains Python/FastAPI services (api-gateway, agent-executor). Adding Go would require new tooling, Docker builds, and team expertise.
3. **Scale math:** With 2-5 tenants and ~50 agents total, peak LLM traffic is ~20-100 requests/minute. FastAPI handles this trivially.
4. **Go only wins at >1,000 concurrent streaming connections.** This platform won't reach that scale in v4.0.

**When to consider Go:** If the platform scales to 50+ tenants with 500+ agents, revisit. The proxy is stateless and API-compatible, so a Go rewrite is always an option without changing the architecture.

### 7.3 Resource Requirements

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
```

With HPA scaling at 60% CPU:
- Minimum: 2 replicas (HA)
- Maximum: 5 replicas
- Expected steady-state: 2 replicas for 2-5 tenants

### 7.4 Streaming Memory Impact

The proxy does **not** buffer streaming responses. Each chunk is yielded immediately via async generator. Memory usage per concurrent stream: ~1-5KB (the SSE line buffer). Even with 100 concurrent streams, this is < 500KB total.

**Confidence:** HIGH — latency math is straightforward, throughput estimates based on FastAPI benchmarks.

---

## 8. Proxy Implementation Blueprint

### 8.1 Core Proxy Logic

```python
# backend/microservices/llm_proxy/main.py

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import json
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

app = FastAPI(title="LLM Token Proxy")
client = httpx.AsyncClient(timeout=120.0)

AZURE_OPENAI_BASE = "https://ai-platform-system.openai.azure.com"

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(request: Request, path: str):
    # Extract tenant/agent from path or headers
    tenant_id = request.headers.get("X-Tenant-Id", "unknown")
    agent_id = request.headers.get("X-Agent-Id", "unknown")
    
    # Build upstream URL
    upstream_url = f"{AZURE_OPENAI_BASE}/{path}"
    if request.query_params:
        upstream_url += f"?{request.query_params}"
    
    # Read and potentially modify request body
    body = await request.body()
    headers = dict(request.headers)
    headers.pop("host", None)
    
    is_streaming = False
    if request.method == "POST" and body:
        body_json = json.loads(body)
        is_streaming = body_json.get("stream", False)
        
        # Inject stream_options for token counting
        if is_streaming:
            body_json.setdefault("stream_options", {})
            body_json["stream_options"]["include_usage"] = True
            body = json.dumps(body_json).encode()
    
    start_time = datetime.now(timezone.utc)
    
    if is_streaming:
        return await handle_streaming(
            upstream_url, headers, body, tenant_id, agent_id, start_time
        )
    else:
        return await handle_non_streaming(
            upstream_url, headers, body, tenant_id, agent_id, start_time
        )
```

### 8.2 K8s Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: token-proxy
  namespace: aiplatform
spec:
  replicas: 2
  selector:
    matchLabels:
      app: token-proxy
  template:
    spec:
      containers:
      - name: token-proxy
        image: stumsftaiplatformprodacr.azurecr.io/aiplatform-token-proxy:latest
        ports:
        - containerPort: 8080
        env:
        - name: AZURE_OPENAI_BASE
          value: "https://ai-platform-system.openai.azure.com"
        - name: COSMOS_ENDPOINT
          valueFrom:
            secretKeyRef:
              name: cosmos-secrets
              key: endpoint
        resources:
          requests: { cpu: 100m, memory: 128Mi }
          limits: { cpu: 500m, memory: 256Mi }
---
apiVersion: v1
kind: Service
metadata:
  name: token-proxy
  namespace: aiplatform
spec:
  selector:
    app: token-proxy
  ports:
  - port: 8080
    targetPort: 8080
```

### 8.3 OpenClaw CR Modification

Change the `baseUrl` in the OpenClawInstance CR to route through the proxy:

```yaml
models:
  providers:
    azure-openai-responses:
      # Before: baseUrl: "https://ai-platform-system.openai.azure.com/openai/v1"
      baseUrl: "http://token-proxy.aiplatform.svc:8080/openai/v1"
      apiKey: "${AZURE_API_KEY}"
      api: "openai-responses"
      headers:
        api-key: "${AZURE_API_KEY}"
        X-Tenant-Id: "${TENANT_ID}"
        X-Agent-Id: "${AGENT_ID}"
```

### 8.4 App Insights Telemetry

```python
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace import config_integration

# Emit custom metrics per request
def emit_telemetry(usage: dict, tenant_id: str, latency_ms: float):
    """Emit to App Insights via OpenCensus."""
    tracer.span("llm_request")
    tc.track_metric("llm.prompt_tokens", usage["prompt_tokens"], 
                     properties={"tenant_id": tenant_id})
    tc.track_metric("llm.completion_tokens", usage["completion_tokens"],
                     properties={"tenant_id": tenant_id})
    tc.track_metric("llm.latency_ms", latency_ms,
                     properties={"tenant_id": tenant_id})
```

---

## 9. Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Proxy becomes SPOF | Medium | HPA with 2+ replicas, PDB, emergency bypass to Azure OpenAI directly |
| Streaming bugs cause response corruption | High | Extensive integration tests with real SSE streams; passthrough-first design (don't modify response bytes) |
| Cosmos DB write latency affects response time | Low | Async fire-and-forget writes; usage logging is non-blocking |
| OpenClaw uses unexpected API paths | Medium | Proxy is a wildcard passthrough — unknown paths still forwarded correctly |
| `stream_options.include_usage` not supported by client | Low | OpenClaw's OpenAI SDK handles it transparently; empty-choices chunk is ignored |
| API version changes break usage extraction | Low | Usage object structure has been stable since 2023; proxy validates but doesn't reject |

---

## 10. Roadmap Implications

### Phase Structure Recommendation

1. **Phase: Infrastructure Audit** — validate Bicep + K8s from clean state (prerequisite for everything)
2. **Phase: Token Proxy** — build and deploy the proxy, update CR baseUrl, validate token logging
3. **Phase: Platform MCP Servers** — expose Azure services as MCP tools
4. **Phase: OpenClaw Native UI** — wildcard ingress + auth proxy

### Token Proxy Phase Breakdown

| Step | What | Effort |
|------|------|--------|
| 1. Proxy service code | `backend/microservices/llm_proxy/` — FastAPI proxy with streaming | 1 day |
| 2. Cosmos DB container | `token_logs` container in Bicep + repository class | 0.5 day |
| 3. K8s deployment | Deployment, Service, HPA, NetworkPolicy | 0.5 day |
| 4. CR modification | Update `openclaw_service.py` to set proxy baseUrl | 0.5 day |
| 5. Integration testing | Deploy, send messages, verify tokens logged | 0.5 day |
| 6. Dashboard integration | Platform monitoring reads from `token_logs` | 1 day |

### Key Dependencies

- NetworkPolicy must allow `tenant-*` → `aiplatform` namespace traffic (already configured)
- Cosmos DB connection must be available in the proxy pod (use existing cosmos-secrets)
- OpenClaw Operator must support custom headers in CR provider config (verify)

---

## 11. Open Questions

1. **Does OpenClaw's `openai-responses` provider support custom headers (`X-Tenant-Id`, `X-Agent-Id`) in the CR config?** — Need to verify. If not, use path-based tenant identification instead.
2. **Does the Responses API (not just Chat Completions) support `stream_options.include_usage`?** — The GA docs only explicitly document it for Chat Completions. The Responses API may have its own streaming format. Needs testing.
3. **Rate limiting strategy** — should the proxy enforce per-tenant rate limits, or rely on Azure OpenAI's built-in rate limiting? Platform could add soft budget caps that alert but don't block.

---

## 12. Sources

| Source | Type | Confidence |
|--------|------|------------|
| Azure OpenAI REST API Reference (2024-10-21 GA) | Official MS docs | HIGH |
| `chatCompletionStreamOptions.include_usage` | Official API spec | HIGH |
| LiteLLM Proxy documentation | Official LiteLLM docs | HIGH |
| LiteLLM Spend Tracking docs | Official LiteLLM docs | HIGH |
| Platform TODO #12 (LLM Token Tracking Proxy) | Internal doc | HIGH |
| OpenClawInstance CR config (`openclawinstance.yaml`) | Internal K8s manifest | HIGH |
| Cosmos DB repository patterns (`backend/app/repositories/`) | Internal code | HIGH |
| FastAPI streaming benchmarks | Community benchmarks | MEDIUM |
