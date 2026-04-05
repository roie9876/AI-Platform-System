---
phase: 31-auth-gateway-native-ui-access
plan: 03
subsystem: frontend
tags: [openclaw, gateway, config, frontend, react, nextjs]

requires:
  - phase: 31-01
    provides: Auth gateway FastAPI service
  - phase: 31-02
    provides: K8s infrastructure with AGENTS_DOMAIN in configmap
provides:
  - OpenClaw gateway-proxy conditional external binding
  - Frontend "Open Agent Console" button for native UI access
  - Agent slug field for subdomain routing
affects: [openclaw, frontend, agents]

tech-stack:
  added: []
  patterns: [conditional gateway binding, config-driven UI feature gating]

key-files:
  modified:
    - backend/app/services/openclaw_service.py
    - backend/app/core/config.py
    - backend/app/api/v1/agents.py
    - frontend/src/app/api/config/route.ts
    - frontend/src/app/dashboard/agents/[id]/page.tsx

key-decisions:
  - "Agent slug field added to agent creation (name.lower().replace(' ', '-'))"
  - "Button uses agent.slug with fallback to agent.id for subdomain URL"
  - "Button conditionally rendered only when agentsDomain is set"
  - "Gateway bind conditional: 0.0.0.0 + 10.0.0.0/8 trust when AGENTS_DOMAIN set"

patterns-established:
  - "Config-gated UI features: fetch /api/config → conditionally render"

requirements-completed: [NATIVEUI-01, NATIVEUI-05]

duration: 5min
completed: 2026-04-05
---

# Plan 31-03: OpenClaw Gateway Wiring + Frontend UI Button Summary

**OpenClaw gateway conditionally binds externally when AGENTS_DOMAIN is set; frontend shows "Open Agent Console" button linking to native UI via auth gateway.**

## Performance

- **Duration:** 5 min
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- OpenClaw gateway-proxy conditionally binds to 0.0.0.0 and trusts cluster CIDR when AGENTS_DOMAIN configured
- Added AGENTS_DOMAIN to Settings class for shared access
- Agent documents now get a `slug` field at creation time
- Frontend config endpoint returns `agentsDomain` from env
- Agent detail page shows "Open Agent Console" button (purple, external link icon, new tab)
- Button hidden entirely when no agents domain configured

## Task Commits

1. **Task 1: Update OpenClaw gateway config and Settings** - `26dc897` (feat)
2. **Task 2: Frontend config and Open Agent Console button** - `bb58d97` (feat)
3. **Task 3: AGENTS_DOMAIN in configmap** - Already done in 31-02

## Files Created/Modified
- `backend/app/core/config.py` - Added AGENTS_DOMAIN setting
- `backend/app/services/openclaw_service.py` - Conditional gateway bind/trustedProxies
- `backend/app/api/v1/agents.py` - Added slug field to agent creation
- `frontend/src/app/api/config/route.ts` - Added agentsDomain to config response
- `frontend/src/app/dashboard/agents/[id]/page.tsx` - Added Open Agent Console button
