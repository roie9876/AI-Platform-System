---
phase: 10-agent-level-traces-monitor-tabs
plan: 02
subsystem: ui
tags: [observability, monitor, kpi, recharts, react]

requires:
  - phase: 10-agent-level-traces-monitor-tabs
    provides: Tab wiring (activeTab state, conditional rendering) from Plan 10-01

provides:
  - AgentMonitorPanel with 6 KPI tiles and 2 time-series charts
  - Fully integrated Monitor tab in agent detail page

affects: [evaluation-tab]

tech-stack:
  added: []
  patterns:
    - "Agent sub-panel with dual data fetches (summary + time-series) in parallel useEffects"
    - "Custom 3x2 KPI grid for 6 tiles (overriding default 4-col KpiTileGrid)"

key-files:
  created:
    - frontend/src/components/agent/agent-monitor-panel.tsx
  modified:
    - frontend/src/app/dashboard/agents/[id]/page.tsx

key-decisions:
  - "Used custom 3x2 grid instead of KpiTileGrid's 4-col layout for clean 6-tile arrangement"
  - "Token Consumption Trend chart uses LineChart showing total tokens as proxy for cost trend"

patterns-established:
  - "Dual-fetch pattern: summary KPIs + time-series chart data in parallel useCallback/useEffect"

requirements-completed: [MONITOR-01, MONITOR-02]

duration: 5min
completed: 2026-03-24
---

# Plan 10-02: Agent Monitor Panel with KPI Tiles and Charts

**Created agent-scoped monitoring dashboard with 6 KPI tiles (requests, errors, latency, tokens, cost, P95) and two Recharts time-series visualizations for token usage trends.**

## Performance

- **Duration:** ~5 min
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments
- Created AgentMonitorPanel with 6 KPI tiles: Total Requests, Error Rate %, Avg Latency, Total Tokens, Total Cost, P95 Latency
- Added Token Usage Over Time AreaChart (input vs output tokens)
- Added Token Consumption Trend LineChart (total tokens over time)
- Integrated Monitor tab into agent detail page, replacing placeholder

## Task Commits

1. **Task 1: Create AgentMonitorPanel** - `9378e77` (feat)
2. **Task 2: Integrate into agent detail page** - `9378e77` (feat)

## Files Created/Modified
- `frontend/src/components/agent/agent-monitor-panel.tsx` - New monitor panel with KPI tiles, AnalyticsToolbar, AreaChart, LineChart
- `frontend/src/app/dashboard/agents/[id]/page.tsx` - Added AgentMonitorPanel import, replaced monitor placeholder

## Decisions Made
- Used custom 3-col grid for 6 KPI tiles instead of KpiTileGrid's default 4-col layout
- Token Consumption Trend uses total tokens (input+output) as a line chart rather than cost-per-bucket

## Deviations from Plan
None - plan executed as written

## Issues Encountered
None

## Self-Check: PASSED
