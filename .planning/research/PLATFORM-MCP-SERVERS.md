# Platform MCP Server Design Research

**Project:** AI Agent Platform v4.0 — Architecture Pivot
**Area:** Platform MCP Servers (Cosmos DB Memory, AI Search, Group Rules)
**Researched:** 2026-04-04
**Overall Confidence:** HIGH (based on existing codebase patterns + Azure documentation)

---

## 1. Existing MCP Server Patterns (Codebase Analysis)

### Pattern Summary

All three existing MCP servers (`mcp_server_web_tools.py`, `mcp_server_atlassian.py`, `mcp_server_github.py`) follow an identical architecture:

| Aspect | Pattern |
|--------|---------|
| **Protocol** | MCP JSON-RPC 2.0 over HTTP POST |
| **Transport** | Streamable HTTP at `/mcp` endpoint (single POST endpoint) |
| **SDK** | None — hand-rolled `http.server.HTTPServer` + `BaseHTTPRequestHandler` |
| **Protocol Version** | `2024-11-05` |
| **Methods** | `initialize`, `notifications/initialized`, `tools/list`, `tools/call` |
| **Tool Schema** | JSON dicts with `name`, `description`, `inputSchema` |
| **Dispatcher** | Single `execute_tool(name, arguments)` function with if/elif chain |
| **Response Format** | `{"content": [{"type": "text", "text": ...}], "isError": bool}` |
| **Session** | `Mcp-Session-Id` header (UUID, per-server instance) |

### JSON-RPC Handler Structure (Replicate This)

```python
def handle_jsonrpc(body: dict) -> dict:
    method = body.get("method", "")
    req_id = body.get("id")
    params = body.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "...", "version": "1.0.0"},
                "capabilities": {"tools": {"listChanged": False}},
            },
        }
    if method == "notifications/initialized":
        return None  # 202 Accepted, no body
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        result = execute_tool(params.get("name"), params.get("arguments", {}))
        text = result.get("error") or result.get("text") or json.dumps(result)
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {"content": [{"type": "text", "text": text}], "isError": "error" in result},
        }
```

### Deployment Model

Each MCP server is deployed as a separate K8s Deployment + Service in the `aiplatform` namespace:

```yaml
# k8s/base/mcp-github/deployment.yaml
spec:
  serviceAccountName: aiplatform-workload
  containers:
    - name: mcp-github
      image: ${ACR_SERVER}/aiplatform-mcp-github:latest
      ports: [{containerPort: 8084}]
      env:
        - name: GITHUB_TOKEN
          valueFrom: {secretKeyRef: {name: aiplatform-secrets, key: GITHUB_TOKEN}}
      volumeMounts:
        - name: secrets-store
          mountPath: "/mnt/secrets-store"
          readOnly: true
  volumes:
    - name: secrets-store
      csi: {driver: secrets-store.csi.k8s.io, secretProviderClass: aiplatform-keyvault}
```

Labels include `azure.workload.identity/use: "true"` for Managed Identity.

### OpenClaw MCP Server Discovery

OpenClaw discovers MCP servers through CR config injection in `openclaw_service.py`:

```python
# Line 1188-1192
for url in openclaw_config.get("mcp_server_urls", []):
    name = url.rstrip("/").split("/")[-1].split(".")
    mcp_servers[name] = {"url": url}

# Line 1275
raw_config["agents"]["defaults"]["mcpServers"] = mcp_servers
```

MCP server URLs are stored in `OpenClawConfig.mcp_server_urls: List[str]` per agent. The platform auto-injects them into the OpenClaw CR's `mcpServers` config map. OpenClaw expects `{name: {url: "http://..."}}` format.

**Key Insight:** MCP servers must be HTTP-reachable from OpenClaw pods in tenant namespaces. Since MCP servers deploy in `aiplatform` namespace, cross-namespace DNS works: `http://mcp-github.aiplatform.svc.cluster.local:8084/mcp`.

**Confidence:** HIGH — directly verified from codebase.

---

## 2. MCP Server Architecture Recommendation

### Decision: Three Separate MCP Servers (Not Combined)

**Recommendation:** Deploy each as a separate container, matching existing patterns.

| Server | Port | Image | Purpose |
|--------|------|-------|---------|
| `mcp-cosmos-memory` | 8090 | `aiplatform-mcp-cosmos-memory` | Agent memories in Cosmos DB |
| `mcp-azure-search` | 8091 | `aiplatform-mcp-azure-search` | Azure AI Search hybrid queries |
| `mcp-platform-context` | 8092 | `aiplatform-mcp-platform-context` | Group rules, agent config |

**Why separate:**
1. **Existing pattern** — all current MCP servers are 1:1 (server:image:deployment). Breaking convention adds confusion.
2. **Independent scaling** — memory search may get more traffic than platform context.
3. **Independent failure** — a Cosmos DB outage shouldn't break AI Search tools.
4. **Independent auth requirements** — each needs different Azure credentials/scopes.

**Why NOT combined:**
- Three separate deployments means 3x the pod overhead (~128Mi memory each). Acceptable for a platform running AKS at Standard_D4s_v5.
- A combined server would need all Azure SDK dependencies in one image (heavier, broader blast radius).

### Transport: Streamable HTTP (Current Pattern)

Keep the existing Streamable HTTP transport (`POST /mcp`). Do NOT introduce SSE or stdio:

- **SSE transport** only needed for server-initiated push (not our use case — agents call tools, servers respond).
- **stdio transport** requires the MCP server to be a subprocess of the calling agent. OpenClaw uses HTTP MCP natively — it connects to URLs.
- The `2024-11-05` protocol version with Streamable HTTP is what OpenClaw already uses.

### Auto-Injection of Platform MCP URLs

Modify `openclaw_service.py` to auto-inject platform MCP server URLs when generating OpenClaw CRs:

```python
# Auto-inject platform MCP servers (always available)
PLATFORM_MCP_SERVERS = {
    "cosmos-memory": {"url": "http://mcp-cosmos-memory.aiplatform.svc.cluster.local:8090/mcp"},
    "azure-search": {"url": "http://mcp-azure-search.aiplatform.svc.cluster.local:8091/mcp"},
    "platform-context": {"url": "http://mcp-platform-context.aiplatform.svc.cluster.local:8092/mcp"},
}
# Merge with user-configured MCP servers
mcp_servers = {**PLATFORM_MCP_SERVERS, **user_mcp_servers}
raw_config["agents"]["defaults"]["mcpServers"] = mcp_servers
```

**Confidence:** HIGH — follows established codebase patterns exactly.

---

## 3. Cosmos DB Vector Search

### Current State

`memory_service.py` (line 76) explicitly comments:
```python
"""Retrieve relevant memories using recency (vector search not available in Cosmos)."""
```

Memories store embeddings (via `text-embedding-3-small`, 1536 dimensions) in the `embedding` field but retrieve using `ORDER BY c._ts DESC` — pure recency, no vector similarity.

### Cosmos DB NoSQL Vector Search (GA since November 2024)

Cosmos DB NoSQL **does support vector search natively** via DiskANN indexing. This was GA'd in November 2024.

**Requirements:**
1. **Container vector policy** — must be defined at container creation or added to existing containers
2. **Vector index** — DiskANN (recommended), flat, or quantizedFlat
3. **Query syntax** — `VectorDistance()` function in SQL queries

**Container Configuration:**

```json
{
  "vectorEmbeddingPolicy": {
    "vectorEmbeddings": [
      {
        "path": "/embedding",
        "dataType": "float32",
        "dimensions": 1536,
        "distanceFunction": "cosine"
      }
    ]
  },
  "indexingPolicy": {
    "vectorIndexes": [
      {
        "path": "/embedding",
        "type": "diskANN"
      }
    ]
  }
}
```

**Vector Search Query:**

```sql
SELECT TOP @limit c.id, c.content, c.agent_id, c.memory_type, c.created_at,
       VectorDistance(c.embedding, @queryVector) AS score
FROM c
WHERE c.tenant_id = @tenant_id AND c.agent_id = @agent_id
ORDER BY VectorDistance(c.embedding, @queryVector)
```

**Python SDK Usage:**

```python
from azure.cosmos import CosmosClient

# Query with vector search
query = """
SELECT TOP @limit c.id, c.content, c.memory_type, c.created_at,
       VectorDistance(c.embedding, @queryVector) AS score
FROM c
WHERE c.tenant_id = @tid AND c.agent_id = @aid
ORDER BY VectorDistance(c.embedding, @queryVector)
"""
parameters = [
    {"name": "@limit", "value": limit},
    {"name": "@tid", "value": tenant_id},
    {"name": "@aid", "value": agent_id},
    {"name": "@queryVector", "value": query_embedding},
]
results = container.query_items(query=query, parameters=parameters, partition_key=tenant_id)
```

### Migration Required

The existing `agent_memories` Cosmos DB container likely doesn't have a vector embedding policy. A migration step is needed:

1. **Check current indexing policy** — if no `vectorEmbeddingPolicy`, must update container
2. **Update container** — add vector embedding policy and DiskANN index via Azure CLI or Bicep
3. **Backfill embeddings** — memories stored before embeddings were generated need backfill

```bash
# Azure CLI to update container with vector index
az cosmosdb sql container update \
  --account-name <account> \
  --database-name aiplatform \
  --name agent_memories \
  --resource-group <rg> \
  --vector-embedding-policy '[{"path":"/embedding","dataType":"float32","dimensions":1536,"distanceFunction":"cosine"}]' \
  --idx '[{"vectorIndexes":[{"path":"/embedding","type":"diskANN"}]}]'
```

**Embedding Flow for MCP Server:**

The MCP server needs to generate embeddings for search queries. Two options:

| Option | Pros | Cons |
|--------|------|------|
| **Embed in MCP server** | Self-contained, no dependency | Needs Azure OpenAI credentials |
| **Use LLM token proxy** | Tracking, unified billing | Extra hop, proxy must support embeddings |

**Recommendation:** Embed in the MCP server directly using the same `text-embedding-3-small` model. The MCP server already needs Azure credentials for Cosmos DB — adding OpenAI embedding adds minimal complexity.

**Confidence:** MEDIUM — Cosmos DB vector search is GA and well-documented, but container migration hasn't been tested on this specific account. DiskANN indexing requires minimum RU/s (may need verification against current provisioning).

---

## 4. Azure AI Search MCP Server

### Current Usage in Platform

The platform already uses Azure AI Search in two places:
1. `rag_service.py` — direct HTTP calls with `httpx` to Search REST API (`api-version: 2024-07-01`)
2. `platform_tools.py` — `AzureAISearchAdapter` using `azure-search-documents` SDK

The RAG service uses admin keys obtained via ARM API (`_get_search_admin_key`). The platform tools adapter uses `AZURE_SEARCH_ENDPOINT` + `AZURE_SEARCH_API_KEY` env vars.

### Python SDK

```
azure-search-documents>=11.6.0
```

**Key classes:**
- `SearchClient` — query documents (search, suggest, autocomplete)
- `SearchIndexClient` — manage indexes (create, list, delete)
- `SearchIndexerClient` — manage indexers (data source connections)

### Hybrid Search (Vector + Keyword)

```python
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential

# With Managed Identity (preferred)
client = SearchClient(
    endpoint=endpoint,
    index_name=index_name,
    credential=DefaultAzureCredential(),
)

# Hybrid search: keyword + vector
vector_query = VectorizedQuery(
    vector=query_embedding,  # float[]
    k_nearest_neighbors=top_k,
    fields="contentVector",  # field name in index
)

results = client.search(
    search_text=query,           # keyword component
    vector_queries=[vector_query], # vector component
    top=top_k,
    select=["content", "title", "url", "metadata"],
)
```

### MCP Tool Design

```python
TOOLS = [
    {
        "name": "search_documents",
        "description": "Search indexed documents using Azure AI Search with hybrid search (keyword + vector). Returns relevant documents with content and metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query text"},
                "index": {"type": "string", "description": "Name of the search index to query"},
                "top_k": {"type": "integer", "description": "Number of results (default: 5)", "default": 5},
            },
            "required": ["query", "index"],
        },
    },
    {
        "name": "list_indexes",
        "description": "List available Azure AI Search indexes and their document counts.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "index_document",
        "description": "Add or update a document in an Azure AI Search index.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Document text content"},
                "title": {"type": "string", "description": "Document title"},
                "metadata": {"type": "object", "description": "Additional metadata key-value pairs"},
                "index": {"type": "string", "description": "Target index name"},
            },
            "required": ["content", "index"],
        },
    },
]
```

### Index Schema Assumptions

The MCP server should be **index-schema agnostic** — query any index, map common field patterns:

```python
# Try common field names in order of preference
CONTENT_FIELDS = ["content", "chunk", "text", "body", "description"]
TITLE_FIELDS = ["title", "name", "subject", "heading"]
VECTOR_FIELDS = ["contentVector", "embedding", "vector", "content_vector"]

def _extract_content(doc: dict) -> str:
    for field in CONTENT_FIELDS:
        if field in doc and doc[field]:
            return doc[field]
    # Fallback: concatenate all string fields
    return " ".join(str(v) for k, v in doc.items()
                    if isinstance(v, str) and not k.startswith("@"))
```

### Authentication

**Use Managed Identity** (not API keys) for the MCP server → Azure AI Search connection:

```python
from azure.identity import DefaultAzureCredential
credential = DefaultAzureCredential()
client = SearchClient(endpoint=endpoint, index_name=index, credential=credential)
```

The MCP server pod runs with `azure.workload.identity/use: "true"` and `aiplatform-workload` service account. Assign the Search Index Data Reader role to the workload identity.

**Confidence:** HIGH — SDK is well-documented, current codebase already uses it.

---

## 5. Multi-Tenant MCP Server Design

### Decision: Shared MCP Servers in `aiplatform` Namespace

**Recommendation:** Deploy platform MCP servers in the shared `aiplatform` namespace, NOT per-tenant.

**Why shared:**
1. **All existing MCP servers are shared** (web_tools, atlassian, github, sharepoint all in `aiplatform`)
2. **MCP servers are stateless** — they query Cosmos DB / AI Search per-request with tenant context
3. **Cost** — 3 pods × N tenants vs 3 pods total
4. **Simpler management** — update once, all tenants get fixes

**Why NOT per-tenant:**
- Per-tenant MCP servers would duplicate infrastructure for no isolation benefit (data isolation is at Cosmos DB partition level, not pod level)
- Per-tenant only makes sense if MCP servers need different credentials per tenant (they don't — Managed Identity covers all)

### Tenant Scoping: How Does the MCP Server Know Which Tenant?

**Critical design question.** When OpenClaw calls `memory_search(query, limit)`, the MCP server needs `tenant_id` and `agent_id` to scope the Cosmos DB query.

**Options:**

| Option | How | Pros | Cons |
|--------|-----|------|------|
| **A. Headers** | OpenClaw sends `X-Tenant-Id` header | Clean, standard | OpenClaw doesn't support custom headers on MCP calls |
| **B. Tool args** | Add `tenant_id` to every tool's inputSchema | Always available | Agent must pass tenant_id (error-prone, security risk — agent could query another tenant) |
| **C. URL path** | `http://mcp-cosmos-memory:8090/mcp/{tenant_id}/{agent_id}` | Server extracts from URL | Clean separation, no trust issues |
| **D. Named MCP servers** | Different URL per tenant-agent combo | Isolated by config | Complex, must update CR on every change |

**Recommendation: Option C — Tenant-scoped URL paths.**

Inject per-agent MCP URLs during CR generation:

```python
# In openclaw_service.py when building CR config
tenant_slug = tenant["slug"]
agent_id = agent["id"]
PLATFORM_MCP_SERVERS = {
    "cosmos-memory": {
        "url": f"http://mcp-cosmos-memory.aiplatform.svc.cluster.local:8090/mcp/{tenant_slug}/{agent_id}"
    },
    "azure-search": {
        "url": f"http://mcp-azure-search.aiplatform.svc.cluster.local:8091/mcp/{tenant_slug}/{agent_id}"
    },
    "platform-context": {
        "url": f"http://mcp-platform-context.aiplatform.svc.cluster.local:8092/mcp/{tenant_slug}/{agent_id}"
    },
}
```

The MCP server extracts tenant context from the URL path:

```python
class MCPHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Parse /mcp/{tenant_id}/{agent_id}
        parts = self.path.strip("/").split("/")
        if len(parts) >= 3 and parts[0] == "mcp":
            tenant_id = parts[1]
            agent_id = parts[2]
        else:
            self.send_error(400, "Missing tenant/agent in URL")
            return
        # Pass tenant_id + agent_id to tool execution
        ...
```

**Security:** The MCP server still validates that:
1. The request comes from within the cluster (NetworkPolicy)
2. The tenant_id exists in Cosmos DB
3. No cross-tenant data leakage in queries (all queries use `WHERE c.tenant_id = @tid`)

### Cosmos DB Partition Key Usage

All repositories partition by `tenant_id`. The MCP server follows the same pattern:

```python
# Cosmos query is partition-scoped — prevents cross-tenant reads
results = container.query_items(
    query="SELECT ... FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid",
    parameters=[...],
    partition_key=tenant_id,  # Cosmos routes to correct partition
)
```

**Confidence:** HIGH — follows existing Cosmos DB partition isolation pattern from `base.py` repository.

---

## 6. MCP Server Authentication

### MCP Server → Azure Services

**Use Workload Identity** (already established pattern):

```yaml
# deployment.yaml
spec:
  template:
    metadata:
      labels:
        azure.workload.identity/use: "true"
    spec:
      serviceAccountName: aiplatform-workload
```

The `aiplatform-workload` service account has federated credentials linked to the Managed Identity. This gives the MCP server a token for:
- **Cosmos DB** — `DefaultAzureCredential` or `WorkloadIdentityCredential`
- **Azure AI Search** — `DefaultAzureCredential` with Search Index Data Reader role
- **Azure OpenAI** — for embedding generation (if needed)

No API keys needed. No secrets to rotate. Existing pattern from `mcp-proxy` and `mcp-github` deployments.

### OpenClaw Agent → MCP Server

OpenClaw calls MCP servers over plain HTTP within the cluster. Currently **no authentication** between OpenClaw and MCP servers — same as existing servers (web_tools, atlassian, github all accept unauthenticated requests).

**Is this acceptable?** YES, because:
1. **NetworkPolicy** restricts access to `aiplatform` namespace services from tenant namespaces only
2. MCP servers are `ClusterIP` (not externally accessible)
3. Tenant scoping via URL path prevents cross-tenant data access
4. This matches the security model of every existing MCP server

**Future enhancement (if needed):** Add a lightweight token verification:
- Platform generates a JWT with `tenant_id` + `agent_id` claims during CR deployment
- MCP server validates the JWT before processing
- But this is over-engineering for a cluster-internal service with NetworkPolicy

**Confidence:** HIGH — matches existing security model exactly.

---

## 7. mcp-platform-context: Group Rules Design

### Data Model

Group rules are stored in the agent document in Cosmos DB under `openclaw_config.whatsapp.whatsapp_group_rules[]`:

```python
class WhatsAppGroupRule(BaseModel):
    group_name: str = ""       # Human-readable (Hebrew, etc.)
    group_jid: str = ""        # WhatsApp JID (e.g. "120363012345678@g.us")
    policy: Literal["open", "allowlist", "blocked"] = "open"
    require_mention: bool = False
    allowed_phones: List[str] = []
    instructions: str = ""     # Per-group custom instructions (THE KEY VALUE-ADD)
```

### Current Injection Path

`agent_execution.py` (line 864-882) injects group rules as system messages:

```python
wa_rules = wa_cfg.get("whatsapp_group_rules") or []
named_groups = [r for r in wa_rules if r.get("group_name") and r.get("policy") != "blocked"]
if named_groups:
    messages.append({
        "role": "system",
        "content": "Configured WhatsApp groups for this agent:\n" + group_lines + ...
    })
```

### MCP Tool Design for Platform Context

```python
TOOLS = [
    {
        "name": "get_group_instructions",
        "description": "Get custom instructions for a specific WhatsApp/Telegram group. Call this when receiving a message from a group to check if there are special instructions for that group.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_jid": {
                    "type": "string",
                    "description": "The group JID (e.g. '120363012345678@g.us' for WhatsApp)"
                },
            },
            "required": ["group_jid"],
        },
    },
    {
        "name": "get_agent_config",
        "description": "Get the current agent configuration including system prompt, enabled channels, and tools.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_configured_groups",
        "description": "List all groups with custom instructions or policies. Returns group names, JIDs, and their configured instructions.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]
```

### Implementation

```python
async def _get_group_instructions(tenant_id: str, agent_id: str, group_jid: str) -> dict:
    """Fetch per-group instructions from agent config in Cosmos DB."""
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        return {"error": "Agent not found"}

    openclaw_cfg = agent.get("openclaw_config") or {}

    # Check WhatsApp rules
    wa_rules = (openclaw_cfg.get("whatsapp") or {}).get("whatsapp_group_rules", [])
    for rule in wa_rules:
        if rule.get("group_jid") and group_jid in rule["group_jid"]:
            return {
                "text": (
                    f"Group: {rule.get('group_name', 'Unknown')}\n"
                    f"JID: {rule.get('group_jid')}\n"
                    f"Policy: {rule.get('policy', 'open')}\n"
                    f"Require mention: {rule.get('require_mention', False)}\n"
                    f"Instructions: {rule.get('instructions', 'No special instructions')}"
                )
            }

    # Check Telegram rules
    tg_rules = (openclaw_cfg.get("channels") or {}).get("telegram_group_rules", [])
    for rule in tg_rules:
        if rule.get("group_id") == group_jid:
            return {"text": f"Group: {rule.get('group_name')}\nInstructions: {rule.get('instructions', 'None')}"}

    return {"text": "No custom instructions configured for this group."}
```

**Confidence:** HIGH — directly maps to existing data model.

---

## 8. Implementation Recommendations

### File Structure

```
backend/
  mcp_server_cosmos_memory.py    # ~200 lines
  mcp_server_azure_search.py     # ~250 lines
  mcp_server_platform_context.py # ~200 lines
  Dockerfile.mcp-cosmos-memory
  Dockerfile.mcp-azure-search
  Dockerfile.mcp-platform-context

k8s/base/
  mcp-cosmos-memory/
    deployment.yaml
    service.yaml
  mcp-azure-search/
    deployment.yaml
    service.yaml
  mcp-platform-context/
    deployment.yaml
    service.yaml
```

### Shared Dockerfile Pattern

All three can use a similar slim Dockerfile:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements-mcp-cosmos.txt .
RUN pip install --no-cache-dir -r requirements-mcp-cosmos.txt
COPY mcp_server_cosmos_memory.py .
EXPOSE 8090
CMD ["python", "mcp_server_cosmos_memory.py"]
```

### Dependencies Per Server

| Server | Dependencies |
|--------|-------------|
| `mcp-cosmos-memory` | `azure-cosmos`, `azure-identity`, `openai` (for embeddings) |
| `mcp-azure-search` | `azure-search-documents`, `azure-identity`, `openai` (for embed if hybrid) |
| `mcp-platform-context` | `azure-cosmos`, `azure-identity` |

### Resource Allocation

```yaml
resources:
  requests:
    cpu: 50m
    memory: 128Mi
  limits:
    cpu: 200m
    memory: 256Mi
```

Same as existing MCP servers. These are lightweight HTTP services.

---

## 9. Risk Assessment & Pitfalls

### Critical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Cosmos DB vector index migration** | `agent_memories` container may need recreation if vector policy can't be added to existing container | Test on non-prod first; if needed, create new container + data migration |
| **DiskANN minimum RU/s** | DiskANN vector index requires minimum throughput | Verify current RU provisioning; may need to increase from serverless/400 RU to 1000+ RU |
| **Embedding latency on search** | Each `memory_search()` call requires embedding the query (OpenAI API call) | Cache embeddings for repeated queries; latency ~100-200ms per embed |

### Moderate Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **OpenClaw MCP call format** | OpenClaw may not pass headers or custom auth to MCP servers | Use URL-path tenant scoping (confirmed: OpenClaw sends plain POST to MCP URL) |
| **Cross-namespace DNS** | OpenClaw pods in `tenant-{slug}` must resolve `*.aiplatform.svc.cluster.local` | Verified: K8s DNS resolves cross-namespace by default; NetworkPolicy must allow egress to `aiplatform` namespace |
| **Agent must call tools explicitly** | Unlike system message injection, the agent must decide to call `get_group_instructions()` | Add to agent system prompt: "When receiving a group message, always call get_group_instructions() first" |

### Minor Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Three new deployments** | More pods to manage | Same pattern as existing; add to CI/CD pipeline |
| **OpenClaw config size** | More MCP server URLs in CR config | Negligible (3 extra URLs) |

---

## 10. Sequence Diagram: Memory Search Flow

```
OpenClaw Pod (tenant-eng)          mcp-cosmos-memory (aiplatform)           Cosmos DB              Azure OpenAI
         |                                    |                                |                       |
         |--- POST /mcp/eng/{agent_id} ------>|                                |                       |
         |    {tools/call: memory_search}      |                                |                       |
         |                                    |--- embed(query) ---------------------------------------->|
         |                                    |<-- [1536-dim vector] -----------------------------------|
         |                                    |                                |                       |
         |                                    |--- VectorDistance query ------->|                       |
         |                                    |    partition_key=tenant_id      |                       |
         |                                    |<-- [{content, score}, ...] ----|                       |
         |                                    |                                |                       |
         |<-- {content: [{text: results}]} ---|                                |                       |
```

---

## 11. NetworkPolicy Consideration

Current NetworkPolicy in tenant namespaces restricts egress. Ensure platform MCP services are reachable:

```yaml
# In tenant namespace NetworkPolicy — allow egress to aiplatform namespace
- to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: aiplatform
      podSelector:
        matchLabels:
          app.kubernetes.io/component: mcp-server
  ports:
    - port: 8090
    - port: 8091
    - port: 8092
```

**Confidence:** HIGH — existing MCP servers (ports 8082, 8083, 8084) already require this pattern.

---

## Summary of Recommendations

1. **Follow existing patterns exactly** — hand-rolled JSON-RPC 2.0, separate Deployment per server, Streamable HTTP transport
2. **Tenant scoping via URL path** (`/mcp/{tenant_id}/{agent_id}`) — injected during CR generation, no agent trust required
3. **Enable Cosmos DB vector search** — update `agent_memories` container with DiskANN vector policy, use `VectorDistance()` queries
4. **Use Managed Identity throughout** — Workload Identity for Cosmos DB, AI Search, and OpenAI (zero API keys)
5. **Auto-inject platform MCP URLs** — modify `openclaw_service.py` to always include platform MCP servers in CR config
6. **Tell agents to call tools** — add system prompt guidance: "When in a group, call `get_group_instructions()` first"
