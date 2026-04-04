---
phase: 29-token-proxy
plan: 03
subsystem: api
tags: [openclaw, token-usage, api-router, integration-tests]

requires:
  - phase: 29-token-proxy
    provides: TokenLogRepository, token proxy service, K8s manifests
provides:
  - Proxy URL auto-injection in OpenClaw CR deploy/update
  - Token usage API endpoints (/api/v1/token-usage, /api/v1/token-usage/summary)
  - Unit tests for proxy integration
affects: [agents-api, openclaw, frontend-dashboard]

tech-stack:
  added: []
  patterns: [TOKEN_PROXY_URL env var for proxy routing control]

key-files:
  created:
    - backend/app/api/v1/token_usage.py
    - backend/tests/test_token_proxy.py
  modified:
    - backend/app/services/openclaw_service.py
    - backend/app/api/v1/agents.py
    - backend/microservices/api_gateway/main.py

key-decisions:
  - "TOKEN_PROXY_URL env var with default http://token-proxy.aiplatform.svc:8080 — allows disabling proxy"
  - "agent_id parameter added to update_agent() for proxy URL injection"
  - "Budget limits deferred to future phase — usage read API implemented first"

patterns-established:
  - "Proxy URL injection pattern: after base_url resolution, replace with proxy path"
  - "Agent ID passthrough for update operations"

requirements-completed: [PROXY-04, PROXY-05]

duration: 8min
completed: 2025-07-16
---

# Plan 29-03: Wiring, Usage API, and Tests

**Wired token proxy into OpenClaw deploy/update flow, added usage API endpoints, and created unit tests.**

## Accomplishments
- Modified `openclaw_service.py` to inject proxy URL in both deploy and update paths
- Added `agent_id` parameter to `update_agent()` method and updated all callers
- Created token usage API with `/token-usage` (logs) and `/token-usage/summary` (aggregated) endpoints
- Registered token_usage_router in api_gateway
- Created 6 unit tests — all passing: repository, proxy URL injection, API routes

## Task Commits

1. **Task 1: Proxy URL injection in openclaw_service.py** - `5cf3b3c` (feat)
2. **Task 2: Token usage API endpoints** - `5cf3b3c` (feat)
3. **Task 3: Unit tests** - `5cf3b3c` (test)
