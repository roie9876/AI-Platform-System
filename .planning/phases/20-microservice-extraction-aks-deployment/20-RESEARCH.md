# Phase 20: Microservice Extraction & AKS Deployment — Research

**Researched:** 2026-03-26
**Phase Goal:** Split the monolith into 5 microservices running as isolated workloads on AKS with per-tenant compute boundaries

## 1. Current Monolith Architecture

### API Routes (24 total, registered in `backend/app/api/v1/router.py`)

| Route Module | Prefix | Dependencies (Service/Repo) |
|---|---|---|
| auth | /auth | — (stateless /me from token) |
| agents | /agents | AgentRepository, AgentConfigVersionRepository |
| model_endpoints | /model-endpoints | ModelEndpointRepository |
| chat | /agents | AgentExecutionService → ToolExecutor, MCPClient, RAGService, MemoryService |
| tools | /tools, /agents | ToolRepository, AgentToolRepository |
| data_sources | /data-sources, /agents | DataSourceRepository, AgentDataSourceRepository, DocumentRepository |
| ai_services | /ai-services | AgentRepository, ToolRepository |
| azure_subscriptions | /azure | AzureSubscriptionRepository |
| azure_connections | /azure | AzureConnectionRepository |
| azure_auth | /azure | — |
| catalog | /catalog | CatalogEntryRepository |
| knowledge | /knowledge | AzureConnectionRepository |
| threads | /threads | ThreadRepository, ThreadMessageRepository |
| workflows | /workflows | WorkflowEngine → AgentExecutionService |
| memories | /agents | AgentRepository, AgentMemoryRepository |
| observability | /observability | ObservabilityService, ModelPricingRepository |
| evaluations | /evaluations | EvaluationService |
| marketplace | /marketplace | MarketplaceService |
| mcp_servers | /mcp-servers | MCPServerRepository |
| mcp_discovery | /mcp | MCPServerRepository, MCPDiscoveredToolRepository |
| agent_mcp_tools | /agents | AgentMCPToolRepository, MCPServerRepository |

### Service Dependencies (Critical Cross-Cuts)

```
AgentExecutionService
  ├── ToolExecutor (direct import)
  ├── MCPClient (direct import)
  ├── RAGService (direct import)
  ├── MemoryService (direct import)
  └── ModelAbstractionService (direct import)

WorkflowEngine
  └── AgentExecutionService (direct import — circular risk)
```

### Shared Infrastructure
- `app/core/config.py` — Settings (Cosmos, Entra ID, CORS)
- `app/core/security.py` — Entra ID token validation, JWKS
- `app/middleware/tenant.py` — TenantMiddleware (Bearer token → tenant_id)
- `app/repositories/` — 15 Cosmos DB repository files
- `app/repositories/cosmos_client.py` — CosmosClient singleton
- `app/repositories/base.py` — CosmosRepository base class

## 2. Service Boundary Mapping (D-01)

### Decision: Route-to-Service Assignment

| Microservice | Routes | Services | Repositories |
|---|---|---|---|
| **api-gateway** | auth, agents, model_endpoints, catalog, marketplace, observability, evaluations, azure_*, ai_services | MarketplaceService, ObservabilityService, EvaluationService | agent_repo, config_repo, evaluation_repo, marketplace_repo, observability_repo, tenant_repo, user_repo |
| **agent-executor** | chat, threads, memories | AgentExecutionService, MemoryService, RAGService, ModelAbstractionService | agent_repo, thread_repo, tool_repo, mcp_repo, config_repo, observability_repo |
| **workflow-engine** | workflows | WorkflowEngine | workflow_repo, agent_repo, thread_repo |
| **tool-executor** | tools, data_sources, knowledge | ToolExecutor, DocumentParser | tool_repo, data_source_repo |
| **mcp-proxy** | mcp_servers, mcp_discovery, agent_mcp_tools | MCPClient, MCPDiscovery | mcp_repo |

### Rationale
- **api-gateway** handles all CRUD management and admin operations — high request volume, low compute
- **agent-executor** is the hot path for LLM calls — needs independent scaling and longer timeouts
- **workflow-engine** runs multi-step orchestration — can be slow, needs to call agent-executor over HTTP
- **tool-executor** runs sandboxed tool subprocess — isolates untrusted code execution
- **mcp-proxy** manages external MCP server connections — network-bound, isolated for security

## 3. Inter-Service Communication (D-02)

### Decision: Synchronous HTTP via K8s internal DNS

**Pattern:** `http://{service-name}.{namespace}.svc.cluster.local:8000/api/v1/internal/...`

**Why HTTP over gRPC:**
- All existing code is REST/JSON — no schema (protobuf) rewrite needed
- 2-5 tenants, <100 RPS — latency overhead of HTTP vs gRPC is negligible
- Simpler debugging (curl, logs)
- FastAPI already handles JSON serialization

**Why not async messaging:**
- Current interaction patterns are request-reply (chat → tool call → response)
- Event-driven adds infrastructure (Service Bus) and eventual consistency complexity
- Can add later for fire-and-forget patterns (telemetry, auditing)

### Inter-Service Call Map

| Caller | Callee | Purpose |
|---|---|---|
| agent-executor | tool-executor | `POST /api/v1/internal/tools/execute` — run tool during agent conversation |
| agent-executor | mcp-proxy | `POST /api/v1/internal/mcp/call-tool` — invoke MCP tool during agent conversation |
| workflow-engine | agent-executor | `POST /api/v1/internal/agents/{id}/execute` — run agent step in workflow |

### Internal API Convention
- Prefix: `/api/v1/internal/` — not exposed via ingress
- Auth: Forward the original Bearer token (service acts on behalf of user)
- Timeout: 120s for tool/agent execution, 30s for data operations

## 4. Shared Code Strategy (D-03)

### Decision: Monorepo, shared `app/` package copied into each Docker image

**Structure:**
```
backend/
  app/                          # Shared library (repos, core, middleware, services, models)
    core/config.py              # Per-service env vars (SERVICE_NAME identifies which service)
    health.py                   # Shared liveness/readiness/startup endpoints (NEW)
    services/service_client.py  # Inter-service HTTP client (NEW)
  microservices/
    api_gateway/
      main.py                   # FastAPI app mounting api-gateway routes only
      Dockerfile
    agent_executor/
      main.py
      Dockerfile
    workflow_engine/
      main.py
      Dockerfile
    tool_executor/
      main.py
      Dockerfile
    mcp_proxy/
      main.py
      Dockerfile
```

**Each Dockerfile:**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY microservices/{service_name}/main.py ./main.py
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Why this approach:**
- Zero code duplication — repos/middleware/security shared across all services
- Each image is self-contained — no runtime dependency on shared volume
- Simple to add a new service — create directory + main.py + Dockerfile
- Docker build context is `backend/` — all services build from same root

## 5. K8s Manifest Approach (D-04)

### Decision: Kustomize overlays

**Why Kustomize over Helm:**
- Built into kubectl (`kubectl apply -k`) — no extra tooling
- Simpler for template-based per-tenant namespaces
- Overlay pattern maps cleanly to tenant differentiation
- Helm's templating engine is overkill for this scale (2-5 tenants)

**Directory Structure:**
```
k8s/
  base/
    kustomization.yaml
    namespace.yaml
    api-gateway/
      deployment.yaml
      service.yaml
    agent-executor/
      deployment.yaml
      service.yaml
    workflow-engine/
      deployment.yaml
      service.yaml
    tool-executor/
      deployment.yaml
      service.yaml
    mcp-proxy/
      deployment.yaml
      service.yaml
    ingress.yaml
    configmap.yaml
  overlays/
    tenant-template/
      kustomization.yaml
      namespace.yaml
      network-policy.yaml
      resource-quota.yaml
      limit-range.yaml
      hpa.yaml
    prod/
      kustomization.yaml
      patches/
```

## 6. Ingress & Tenant Routing (D-05)

### Decision: NGINX Ingress Controller with header-based tenant routing

**Pattern:** All requests carry tenant context via the Entra ID JWT token. The ingress routes by URL path prefix to the correct microservice. Tenant isolation happens at the application layer (TenantMiddleware) and infrastructure layer (NetworkPolicy).

**Ingress Rules:**
```
/api/v1/agents/*        → api-gateway or agent-executor (context-dependent)
/api/v1/chat/*          → agent-executor
/api/v1/threads/*       → agent-executor
/api/v1/workflows/*     → workflow-engine
/api/v1/tools/*         → tool-executor
/api/v1/data-sources/*  → tool-executor
/api/v1/mcp-*           → mcp-proxy
/api/v1/*               → api-gateway (catch-all)
```

**Why not multi-tenant ingress with tenant subdomains:**
- 2-5 internal tenants — URL path routing is sufficient
- Tenant isolation via JWT claims + middleware, not network routing
- Avoids DNS management complexity

## 7. Tenant Namespace Isolation

### Per-Tenant Resources
Each tenant gets its own K8s namespace (`tenant-{slug}`) containing:

1. **NetworkPolicy** — deny-all ingress/egress except:
   - Allow ingress from NGINX ingress controller
   - Allow egress to Cosmos DB (Azure backbone)
   - Allow egress to external model endpoints
   - Block all cross-namespace pod traffic

2. **ResourceQuota** — per tenant:
   - CPU: 4 cores request / 8 cores limit
   - Memory: 8Gi request / 16Gi limit
   - Pods: 20 max
   - Services: 10 max

3. **LimitRange** — per container defaults:
   - Default request: 100m CPU, 128Mi memory
   - Default limit: 500m CPU, 512Mi memory
   - Max: 2 CPU, 4Gi memory

4. **HPA** — per microservice deployment:
   - Min replicas: 1
   - Max replicas: 5
   - Target CPU: 70%
   - Target Memory: 80%

## 8. Health Check Design

### Endpoints per microservice:
- `GET /healthz` — Liveness: process alive, return 200
- `GET /readyz` — Readiness: Cosmos DB reachable, return 200
- `GET /startupz` — Startup: application loaded, return 200

### K8s Probe Config:
```yaml
livenessProbe:
  httpGet: { path: /healthz, port: 8000 }
  initialDelaySeconds: 5
  periodSeconds: 10
readinessProbe:
  httpGet: { path: /readyz, port: 8000 }
  initialDelaySeconds: 10
  periodSeconds: 5
startupProbe:
  httpGet: { path: /startupz, port: 8000 }
  initialDelaySeconds: 3
  failureThreshold: 30
  periodSeconds: 2
```

## 9. Risk Assessment

| Risk | Mitigation |
|---|---|
| Circular dependency (WorkflowEngine ↔ AgentExecutionService) | Break via HTTP: workflow-engine calls agent-executor over HTTP |
| Shared state in service singletons (module-level repos) | Each container gets its own process — no shared memory |
| Docker image size bloat from shared code | All services share same base requirements; unused code adds <5MB |
| Inter-service latency on hot path (chat → tool → response) | K8s internal DNS is <1ms; HTTP overhead <5ms for JSON payloads |
| Cosmos DB connection count scaling with service count | Each service creates 1 CosmosClient singleton; 5 services × N tenants = manageable for Cosmos |

## 10. Validation Architecture

### Key Verification Points
1. Each Docker image builds independently: `docker build -f microservices/{svc}/Dockerfile .`
2. Each microservice starts and passes health checks: `curl http://localhost:8000/healthz`
3. Inter-service calls work: agent-executor can call tool-executor
4. NetworkPolicy blocks cross-namespace: pods in tenant-a cannot reach tenant-b
5. HPA scales under load: CPU spike triggers pod creation

---

## RESEARCH COMPLETE
