---
phase: 20-microservice-extraction-aks-deployment
plan: 01
subsystem: infra
tags: [fastapi, microservices, docker, health-checks, service-client]

requires:
  - phase: 19-data-layer-migration-cosmos-db
    provides: Cosmos DB repositories and client singleton

provides:
  - 5 standalone FastAPI microservice entry points (api-gateway, agent-executor, workflow-engine, tool-executor, mcp-proxy)
  - Shared health check router (/healthz, /readyz, /startupz)
  - Inter-service HTTP client (ServiceClient) for K8s DNS-based communication
  - Per-service Dockerfiles building independent container images

affects: [20-02, 20-03, 22-ci-cd]

tech-stack:
  added: [httpx]
  patterns: [microservice-per-domain, shared-library-pattern, k8s-dns-service-discovery]

key-files:
  created:
    - backend/app/health.py
    - backend/app/services/service_client.py
    - backend/microservices/api_gateway/main.py
    - backend/microservices/agent_executor/main.py
    - backend/microservices/workflow_engine/main.py
    - backend/microservices/tool_executor/main.py
    - backend/microservices/mcp_proxy/main.py
    - backend/microservices/api_gateway/Dockerfile
    - backend/microservices/agent_executor/Dockerfile
    - backend/microservices/workflow_engine/Dockerfile
    - backend/microservices/tool_executor/Dockerfile
    - backend/microservices/mcp_proxy/Dockerfile
  modified:
    - backend/app/core/config.py
    - backend/app/middleware/tenant.py

key-decisions:
  - "Each microservice mounts routes from existing app/api/v1/ — no code duplication"
  - "ServiceClient uses settings-based URLs defaulting to K8s DNS names"
  - "Internal endpoints (/api/v1/internal/*) on tool-executor and mcp-proxy for inter-service calls"
  - "Health check endpoints added to TenantMiddleware PUBLIC_PATHS to bypass auth"

patterns-established:
  - "Microservice pattern: FastAPI app + TenantMiddleware + CORS + health_router + domain routes"
  - "Dockerfile pattern: python:3.12-slim, copy shared app/, copy service main.py, HEALTHCHECK directive"
  - "Inter-service communication: ServiceClient wrapping httpx with Bearer token forwarding"

requirements-completed: [COMPUTE-08, COMPUTE-07]

duration: 8min
completed: 2026-03-26
---

# Plan 20-01: Microservice Scaffolding Summary

**5 standalone FastAPI microservices created with per-service Dockerfiles, shared health endpoints, and inter-service HTTP client ready for K8s deployment.**

## Performance

- **Duration:** 8 min
- **Tasks:** 2/2 completed
- **Files created:** 17
- **Files modified:** 2

## Accomplishments
- Created 5 microservice entry points each mounting only their designated route subset from the existing monolith
- Built shared health check router with /healthz, /readyz, /startupz probes for K8s liveness/readiness/startup
- Implemented ServiceClient for inter-service HTTP communication with auth token forwarding
- Added internal endpoints on tool-executor and mcp-proxy for cross-service tool/MCP execution
- Created 5 Dockerfiles with HEALTHCHECK directives, each building an independent container image

## Task Commits

1. **Task 1: Create microservice entry points with health checks and service client** - `47e547e` (feat)
2. **Task 2: Create per-service Dockerfiles** - `c3202bd` (feat)

## Files Created/Modified
- `backend/app/health.py` - Shared health check router with 3 K8s probe endpoints
- `backend/app/services/service_client.py` - Async HTTP client for inter-service calls via K8s DNS
- `backend/app/core/config.py` - Added inter-service URL settings and SERVICE_NAME
- `backend/app/middleware/tenant.py` - Added health endpoints to PUBLIC_PATHS
- `backend/microservices/api_gateway/main.py` - API Gateway: auth, agents, model-endpoints, catalog, marketplace, observability, evaluations, azure-*, ai-services
- `backend/microservices/agent_executor/main.py` - Agent Executor: chat, threads, memories
- `backend/microservices/workflow_engine/main.py` - Workflow Engine: workflows
- `backend/microservices/tool_executor/main.py` - Tool Executor: tools, data-sources, knowledge + internal execute endpoint
- `backend/microservices/mcp_proxy/main.py` - MCP Proxy: mcp-servers, mcp-discovery, agent-mcp-tools + internal call-tool endpoint
- `backend/microservices/*/Dockerfile` - 5 Dockerfiles with HEALTHCHECK, python:3.12-slim base

## Decisions Made
None - followed plan as specified.

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ServiceClient is ready for Plan 20-02 to refactor AgentExecutionService and WorkflowEngine
- Dockerfiles and microservice structure ready for Plan 20-03 K8s manifests
- Internal endpoints on tool-executor and mcp-proxy ready for inter-service communication

---
*Phase: 20-microservice-extraction-aks-deployment*
*Completed: 2026-03-26*
