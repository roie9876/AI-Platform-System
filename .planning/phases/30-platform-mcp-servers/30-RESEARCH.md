# Phase 30: Platform MCP Servers — Technical Research

**Researched:** 2026-04-04
**Confidence:** HIGH

---

## 1. MCP Python SDK (mcp v1.27.0)

### FastMCP Server Pattern

The Python MCP SDK provides `FastMCP` — a high-level API for building MCP servers with decorators:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Platform Tools", stateless_http=True, json_response=True)

@mcp.tool()
def memory_search(query: str, agent_id: str, tenant_id: str, top_k: int = 5) -> list[dict]:
    """Search agent memories by semantic similarity."""
    ...
```

Key features:
- `@mcp.tool()` decorator auto-generates tool schemas from function signatures and docstrings
- `stateless_http=True` — recommended for production, no session state needed (scales horizontally)
- `json_response=True` — returns JSON instead of SSE streams (simpler for stateless)
- Streamable HTTP transport at `/mcp` path by default — matches existing MCP servers
- Lifespan context for shared resources (Cosmos client, OpenAI client)

### Lifespan Pattern for Shared Resources

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

@dataclass
class AppContext:
    cosmos_client: CosmosClient
    openai_client: AsyncAzureOpenAI

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    cosmos = CosmosClient(...)
    openai = AsyncAzureOpenAI(...)
    try:
        yield AppContext(cosmos_client=cosmos, openai_client=openai)
    finally:
        await cosmos.close()

mcp = FastMCP("Platform Tools", lifespan=app_lifespan, stateless_http=True, json_response=True)
```

### Mounting in Starlette/ASGI

Can mount alongside FastAPI health endpoints using Starlette:

```python
from starlette.applications import Starlette
from starlette.routing import Mount, Route

app = Starlette(
    routes=[
        Mount("/", app=mcp.streamable_http_app()),
        # Health routes added separately
    ],
    lifespan=lifespan,
)
```

### Transport Note

Running `mcp.run(transport="streamable-http")` starts uvicorn directly. For K8s deployment, use uvicorn explicitly:
```bash
uvicorn main:app --host 0.0.0.0 --port 8085
```

### Compatibility with OpenClaw

OpenClaw MCP server config: `{"url": "http://mcp-platform-tools.aiplatform.svc:8085/mcp"}`. It sends JSON-RPC POST to the URL. The MCP SDK's streamable HTTP transport handles the same protocol at `/mcp`. Compatible.

---

## 2. Cosmos DB DiskANN Vector Search

### Query Syntax

```sql
SELECT TOP @top_k c.id, c.content, c.memory_type, c.agent_id, c.created_at,
    VectorDistance(c.embedding, @query_vector) AS similarity_score
FROM c
WHERE c.tenant_id = @tenant_id AND c.agent_id = @agent_id
ORDER BY VectorDistance(c.embedding, @query_vector)
```

Key points:
- `VectorDistance()` uses the index configuration (cosine, DiskANN) automatically when `bool_expr=false` (default)
- Requires `ORDER BY VectorDistance(...)` to leverage DiskANN index
- Can add `WHERE` filters (tenant_id, agent_id, memory_type) — DiskANN supports filtered search
- Optional `searchListSizeMultiplier` to trade latency for recall
- Returns similarity score (cosine: 0.0 = identical, 2.0 = opposite)

### Cross-Partition Query Caveat

The `agent_memories` container uses `/tenant_id` as partition key. Vector search with `WHERE c.tenant_id = @tenant_id` is partition-scoped — efficient. Cross-partition vector search would be expensive. Always scope by tenant_id.

### Python SDK Query Pattern

```python
container = cosmos_client.get_database_client("aiplatform").get_container_client("agent_memories")

query = """
SELECT TOP @top_k c.id, c.content, c.memory_type, c.agent_id, c.created_at,
    VectorDistance(c.embedding, @query_vector) AS similarity_score
FROM c
WHERE c.tenant_id = @tenant_id AND c.agent_id = @agent_id
ORDER BY VectorDistance(c.embedding, @query_vector)
"""

items = []
async for item in container.query_items(
    query=query,
    parameters=[
        {"name": "@tenant_id", "value": tenant_id},
        {"name": "@agent_id", "value": agent_id},
        {"name": "@query_vector", "value": query_embedding},
        {"name": "@top_k", "value": top_k},
    ],
    partition_key=tenant_id,
):
    items.append(item)
```

---

## 3. Azure OpenAI Embedding

### Existing Pattern (memory_service.py)

```python
from app.services.model_abstraction import _build_client

client = _build_client(model_endpoint)
response = await client.embeddings.create(
    model="text-embedding-3-small",
    input=[text],
)
embedding = response.data[0].embedding  # List[float], 1536 dimensions
```

### For MCP Server (standalone)

The MCP server runs in its own pod, not in the main API. It needs its own OpenAI client:

```python
from openai import AsyncAzureOpenAI

client = AsyncAzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_BASE"),
    api_key=os.getenv("AZURE_API_KEY"),  # From Key Vault via CSI
    api_version="2024-10-21",
)

response = await client.embeddings.create(
    model="text-embedding-3-small",
    input=[query_text],
)
```

`AZURE_OPENAI_BASE` and `AZURE_API_KEY` are already available via the SecretProviderClass (same as token-proxy).

---

## 4. Tenant/Agent Scoping for MCP Tools

### How OpenClaw Identifies Itself

OpenClaw sends `mcp_server_urls` to MCP servers. The MCP server needs to know which tenant and agent is calling. Options from D-18 context:

**URL-path tenant scoping** (per STATE.md decision): OpenClaw doesn't support custom headers on MCP calls. So tenant_id and agent_id must be passed as tool parameters.

Pattern: Each MCP tool takes `tenant_id` and `agent_id` as required parameters. The agent's system prompt includes these values (injected by OpenClaw CR config).

Alternative considered: URL path scoping (`/mcp/{tenant_id}/{agent_id}/mcp`) — but the MCP SDK's streamable HTTP transport has a fixed path structure. Tool parameters are simpler and more explicit.

---

## 5. Infrastructure Pattern (from Phase 29 Token Proxy)

### K8s Resources Needed

| Resource | Template From |
|----------|--------------|
| `k8s/base/mcp-platform-tools/deployment.yaml` | `k8s/base/token-proxy/deployment.yaml` |
| `k8s/base/mcp-platform-tools/service.yaml` | `k8s/base/token-proxy/service.yaml` |
| `k8s/base/mcp-platform-tools/hpa.yaml` | `k8s/base/token-proxy/hpa.yaml` |

Differences from token-proxy:
- Port: 8085 (not 8080) — distinguishes from token-proxy
- Image: `${ACR_SERVER}/aiplatform-mcp-platform-tools:latest`
- Needs: `COSMOS_ENDPOINT`, `AZURE_WORKLOAD_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_OPENAI_BASE`, `AZURE_API_KEY`
- Same: `serviceAccountName: aiplatform-workload`, `azure.workload.identity/use: "true"`, secrets-store volume

### Dockerfile

Same pattern as `backend/microservices/llm_proxy/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements-mcp-platform.txt .
RUN pip install --no-cache-dir -r requirements-mcp-platform.txt
COPY backend/microservices/mcp_platform_tools/ ./mcp_platform_tools/
CMD ["uvicorn", "mcp_platform_tools.main:app", "--host", "0.0.0.0", "--port", "8085"]
```

### openclaw_service.py Integration

Add platform MCP server URL to every agent's MCP server list:
```python
# In _build_cr_config, after building mcp_servers dict:
mcp_servers["platform-tools"] = {
    "url": "http://mcp-platform-tools.aiplatform.svc.cluster.local:8085/mcp"
}
```

---

## 6. New Cosmos Containers (from D-05, D-06)

### memory_query_cache

- Partition key: `/tenant_id`
- TTL: 3600 (1 hour default)
- No vector index
- Schema: `{id, tenant_id, query_hash, embedding, created_at, ttl}`

### structured_memories

- Partition key: `/tenant_id`  
- No vector index
- Schema: `{id, tenant_id, agent_id, key, value, category, created_at, updated_at}`
- Upsert by `tenant_id + agent_id + key`

Both need Bicep additions to `infra/modules/cosmos.bicep`.

---

## 7. Don't Hand-Roll

| Component | Use | Don't |
|-----------|-----|-------|
| MCP protocol | `mcp` SDK (`FastMCP`) | Raw `BaseHTTPRequestHandler` JSON-RPC |
| Vector search | Cosmos DB `VectorDistance()` | Custom similarity computation |
| Embeddings | `openai` SDK | Raw HTTP to Azure OpenAI |
| Cosmos CRUD | `azure-cosmos` SDK (existing `CosmosRepository`) | Raw HTTP to Cosmos |

---

## 8. Validation Architecture

### Critical Paths to Validate

1. **Memory store → embedding → Cosmos** — content in, embedding generated, stored with vector
2. **Memory search → embed query → VectorDistance** — query in, embedded, DiskANN search returns ranked results
3. **Group instructions → Cosmos read** — group JID in, instructions returned from agents container
4. **MCP injection → OpenClaw CR** — platform tools URL appears in deployed CR
5. **Query cache → skip embedding** — repeated query uses cached embedding instead of re-calling Azure OpenAI

### Test Strategy

- Unit tests: tool logic with mocked Cosmos + OpenAI
- Integration test: MCP protocol compliance (tools/list, tools/call roundtrip)
- End-to-end: Agent calls memory_store → memory_search returns the stored memory

---

## RESEARCH COMPLETE

Research covers MCP SDK patterns, Cosmos DB DiskANN query syntax, embedding integration, K8s deployment pattern, and infrastructure additions. Ready for planning.
