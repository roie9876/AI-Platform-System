---
phase: 10-agent-level-traces-monitor-tabs
plan: 01
subsystem: api, ui
tags: [observability, traces, tabs, fastapi, react]

requires:
  - phase: 08-observability-evaluation-marketplace-cli
    provides: ObservabilityService, /logs endpoint, ExecutionLog model, AnalyticsToolbar

provides:
  - Enhanced /logs API with thread_id, tool_calls, estimated_cost, state_snapshot, time_range filtering
  - AgentTracesPanel component with Foundry-style expandable trace table
  - Tab navigation system (activeTab state) in agent detail page

affects: [10-02, monitor-panel, evaluation]

tech-stack:
  added: []
  patterns:
    - "Tab routing via activeTab state + conditional rendering in agent detail page"
    - "Inline expandable rows in trace table via expandedId toggle"

key-files:
  created:
    - frontend/src/components/agent/agent-traces-panel.tsx
  modified:
    - backend/app/services/observability_service.py
    - backend/app/api/v1/observability.py
    - frontend/src/app/dashboard/agents/[id]/page.tsx

key-decisions:
  - "Used LEFT JOIN model_pricing for cost calculation — gracefully handles missing pricing"
  - "Tab state managed in page.tsx, not URL params — simpler for PoC"

patterns-established:
  - "Agent sub-panel pattern: component receives agentId prop, fetches scoped data via apiFetch"
  - "Tab system: activeTab state in page, conditional render of panels"

requirements-completed: [TRACE-01, TRACE-02]

duration: 8min
completed: 2026-03-24
---

# Plan 10-01: Backend Trace API + Traces Panel + Tab Wiring

**Enhanced execution logs API returns full trace data with cost estimation; Foundry-style traces table with expandable detail rows and tab navigation wired into agent detail page.**

## Performance

- **Duration:** ~8 min
- **Tasks:** 2 completed
- **Files modified:** 4

## Accomplishments
- Backend `/logs` endpoint now returns thread_id, tool_calls, estimated_cost, state_snapshot per log
- Added time_range filtering (1h/24h/7d/30d) to execution logs query
- Created AgentTracesPanel with paginated table, status badges, expandable detail rows
- Wired 4-tab navigation (Playground, Traces, Monitor, Evaluation) into agent detail page

## Task Commits

1. **Task 1: Enhance backend execution logs API** - `4e0d3df` (feat)
2. **Task 2: Create AgentTracesPanel + wire tab system** - `4e0d3df` (feat)

## Files Created/Modified
- `backend/app/services/observability_service.py` - Enhanced get_execution_logs with time_range, thread_id, tool_calls, estimated_cost via model_pricing JOIN
- `backend/app/api/v1/observability.py` - Added time_range query param to /logs endpoint
- `frontend/src/components/agent/agent-traces-panel.tsx` - New Foundry-style traces table with expandable rows
- `frontend/src/app/dashboard/agents/[id]/page.tsx` - Added activeTab state, tab wiring, conditional panel rendering

## Decisions Made
- Used inline conditional rendering for tabs rather than router-based tabs — simpler for PoC
- Cost calculation uses LEFT JOIN on model_pricing, returns 0 when no pricing configured

## Deviations from Plan
None - plan executed as written

## Issues Encountered
None

## Self-Check: PASSED
