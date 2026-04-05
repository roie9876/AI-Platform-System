---
phase: 31-auth-gateway-native-ui-access
plan: 01
subsystem: auth
tags: [oidc, msal, fastapi, httpx, websockets, proxy, session]

requires: []
provides:
  - Auth gateway FastAPI service with OIDC login, session management, HTTP/WebSocket proxy
  - Dockerfile for auth-gateway microservice
affects: [auth-gateway, k8s, openclaw, frontend]

tech-stack:
  added: [msal, itsdangerous]
  patterns: [OIDC authorization code flow, signed session cookies, agent slug resolution, bidirectional WebSocket relay]

key-files:
  created:
    - backend/microservices/auth_gateway/__init__.py
    - backend/microservices/auth_gateway/main.py
    - backend/microservices/auth_gateway/Dockerfile
  modified:
    - backend/requirements.txt

key-decisions:
  - "MSAL ConfidentialClientApplication for OIDC, reusing same Entra app registration (per D-09)"
  - "In-memory sessions with itsdangerous-signed cookies (per D-06, D-07)"
  - "Subdomain routing: agent-{slug}.agents.{domain} hostname parsing"
  - "Tenant access check: compare session tenant_id vs agent tenant_id, platform_admin bypass"
  - "Port 8000 matching other microservices"

patterns-established:
  - "Auth gateway proxy pattern: authenticate → resolve agent → resolve tenant → proxy to pod"
  - "WebSocket bidirectional relay with asyncio.wait FIRST_COMPLETED"
  - "Agent/tenant TTL cache pattern matching existing middleware/tenant.py"

requirements-completed: [NATIVEUI-01, NATIVEUI-02, NATIVEUI-03, NATIVEUI-04]

duration: 8min
completed: 2026-04-05
---

# Plan 31-01: Auth Gateway FastAPI Service Summary

**FastAPI auth gateway service with OIDC login, session management, agent-to-pod resolution, and transparent HTTP/WebSocket proxying to OpenClaw native UIs.**

## Performance

- **Duration:** 8 min
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created auth gateway with full OIDC authorization code flow via MSAL
- Implemented in-memory session store with signed httpOnly cookies on `.agents.{domain}`
- Built agent and tenant resolution from Cosmos DB with TTL caching
- HTTP catch-all proxy forwarding all methods to OpenClaw pods via httpx
- WebSocket bidirectional relay via websockets library
- Tenant access validation (403 on cross-tenant access unless platform_admin)
- Health endpoints reusing shared health_router

## Task Commits

1. **Task 1: Create auth gateway FastAPI service** - `e62bd20` (feat)
2. **Task 2: Create auth gateway Dockerfile** - `e62bd20` (feat)

## Files Created/Modified
- `backend/microservices/auth_gateway/__init__.py` - Package init
- `backend/microservices/auth_gateway/main.py` - Complete auth gateway service (~350 LOC)
- `backend/microservices/auth_gateway/Dockerfile` - Docker image for auth gateway (port 8000)
- `backend/requirements.txt` - Added msal>=1.31.0, itsdangerous>=2.1.0
