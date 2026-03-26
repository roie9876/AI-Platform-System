---
phase: 20-microservice-extraction-aks-deployment
plan: 02
subsystem: api
tags: [fastapi, microservices, service-client, inter-service-communication]

requires:
  - phase: 20-microservice-extraction-aks-deployment
    provides: ServiceClient HTTP client and microservice entry points

provides:
  - AgentExecutionService using HTTP for tool/MCP calls in microservice mode
  - WorkflowEngine using HTTP for agent execution in microservice mode
  - Internal /api/v1/internal/agents/{agent_id}/execute endpoint on agent-executor

affects: [20-03]

tech-stack:
  added: []
  patterns: [conditional-service-mode, auth-token-forwarding]

key-files:
  created: []
  modified:
    - backend/app/services/agent_execution.py
    - backend/app/services/workflow_engine.py
    - backend/microservices/agent_executor/main.py

key-decisions:
  - "Dual-mode pattern: SERVICE_NAME controls direct import (monolith) vs HTTP (microservice)"
  - "Auth token forwarded through execute() parameter, passed to ServiceClient for inter-service auth"
  - "Internal endpoint collects SSE stream and returns JSON response for synchronous inter-service calls"

patterns-established:
  - "Conditional service init: if settings.SERVICE_NAME == 'service-name' → use ServiceClient, else direct import"
  - "Auth token threading: auth_token parameter propagated through service methods to inter-service calls"

requirements-completed: [COMPUTE-08]

duration: 6min
completed: 2026-03-26
---

# Plan 20-02: Inter-Service HTTP Communication Summary

**AgentExecutionService and WorkflowEngine refactored to use HTTP-based ServiceClient in microservice mode, breaking direct Python import coupling between subsystems.**

## Performance

- **Duration:** 6 min
- **Tasks:** 2/2 completed
- **Files modified:** 3

## Accomplishments
- Refactored AgentExecutionService to use ServiceClient for tool execution and MCP tool calls when running as agent-executor microservice
- Refactored WorkflowEngine to use ServiceClient for agent execution when running as workflow-engine microservice
- Added internal endpoint on agent-executor for workflow-engine to invoke agent execution via HTTP
- Preserved backward compatibility — monolith mode (SERVICE_NAME=monolith) still uses direct imports

## Task Commits

1. **Task 1: Refactor AgentExecutionService to use HTTP for tool and MCP calls** - `9def995` (feat)
2. **Task 2: Refactor WorkflowEngine and add agent-executor internal endpoint** - `7b3bb66` (feat)

## Files Created/Modified
- `backend/app/services/agent_execution.py` - Added ServiceClient conditional init, HTTP paths for tool/MCP execution, auth_token threading
- `backend/app/services/workflow_engine.py` - Added ServiceClient conditional init, HTTP path for agent execution
- `backend/microservices/agent_executor/main.py` - Added internal /api/v1/internal/agents/{agent_id}/execute endpoint

## Decisions Made
None - followed plan as specified.

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All inter-service communication paths are wired via ServiceClient
- Microservices can now run independently with proper SERVICE_NAME configuration
- Ready for Plan 20-03 K8s manifests and tenant isolation

---
*Phase: 20-microservice-extraction-aks-deployment*
*Completed: 2026-03-26*
