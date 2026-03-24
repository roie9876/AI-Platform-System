# Phase 10: Agent-Level Traces & Monitor Tabs - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the **Traces** and **Monitor** sub-tabs on the agent detail page, providing per-agent execution tracing and per-agent monitoring dashboard. The top-bar tab switching already exists in `AgentConfigTopBar` (4 tabs defined: playground, traces, monitor, evaluation) but is NOT wired in the parent page — this phase wires it and implements the traces and monitor content panels. All backend observability APIs already support `agent_id` filtering.

This phase does NOT include the Evaluation tab, global (cross-agent) dashboard changes, alerting, or log export features.

</domain>

<decisions>
## Implementation Decisions

### Traces Table Layout
- **D-01:** Traces tab displays a filterable, paginated table modeled on Azure AI Foundry's Traces view. Columns: **Thread ID**, **Response ID**, **Status**, **Start Time**, **Duration**, **Tokens In**, **Tokens Out**, **Estimated Cost** — matching Foundry's layout.
- **D-02:** Two additional columns beyond Foundry: **Model Used** and **Tools Called** — providing agent admins with immediate visibility into which model handled each call and what tools were invoked, without expanding the row.
- **D-03:** Table includes a date range picker control at the top for filtering traces by time window.

### Trace Detail Panel
- **D-04:** Agent's discretion — the downstream planner/implementer decides the best layout for displaying trace details (Foundry-style split panel with execution tree + input/output pane, inline expandable row, or sidebar drawer). Choose whichever pattern best fits the data model (`ExecutionLog.state_snapshot` JSONB with model_name, tool_calls, RAG sources + `token_count` JSONB with input_tokens, output_tokens).

### Monitor KPI Tiles
- **D-05:** Monitor tab shows 6 KPI tiles in the full-picture configuration:
  1. **Total Requests** — count of execution logs for this agent
  2. **Error Rate %** — percentage of failed executions
  3. **Avg Latency** — mean duration_ms across executions
  4. **Total Tokens** — sum of input + output tokens consumed
  5. **Total Cost** — estimated cost based on token usage
  6. **P95 Latency** — 95th percentile duration for performance monitoring
- **D-06:** Tiles must use the existing `KpiTile` / `KpiTileGrid` components from the global observability dashboard.

### Monitor Charts
- **D-07:** Agent's discretion — the downstream planner/implementer picks the most useful chart combination from available data. Options include token usage over time, cost trends, latency distribution, request volume, and error rate trends. Use existing `ChartCard` component with Recharts.

### Tab Wiring & Content Switching
- **D-08:** The agent detail page (`agents/[id]/page.tsx`) must wire `activeTab` and `onTabChange` props to `AgentConfigTopBar`. Conditional rendering shows: playground content (existing) when playground tab is active, traces panel when traces tab is active, monitor panel when monitor tab is active. Evaluation tab remains placeholder/disabled.
- **D-09:** Traces and Monitor panels are new React components — they should follow the existing component organization pattern under `frontend/src/components/agent/`.

### Data Freshness & Controls
- **D-10:** Agent's discretion — reuse or adapt the existing `AnalyticsToolbar` (time range buttons: 1h/24h/7d/30d + granularity selector + refresh) for both Traces and Monitor tabs. The planner decides whether to use the toolbar as-is, adapt it, or build a simpler date range control.

</decisions>

<specifics>
## Specific Ideas

- **Azure AI Foundry as visual reference:** User explicitly provided Azure AI Foundry screenshots as the design model. The Traces table should feel like Foundry's Traces view — clean table with status badges, date range picker, and sortable columns. The Foundry Monitor tab was mostly placeholder ("Scheduled evaluations"), so our Monitor can go beyond Foundry's current state.
- **Admin visibility priority:** User wants comprehensive agent-level observability: "tools used, tokens, errors, threads view and any other helpful data for the agent admin."
- **Traces table should show tools called inline** — no need to expand a row just to see which tools were invoked.
- **Model Used column** — agents may use different models across calls; the admin should see this at a glance.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Backend Observability APIs
- `backend/app/services/observability_service.py` — All query functions support `agent_id` filtering:
  - `get_dashboard_summary()` — total_requests, tokens, cost, latency (avg/p50/p95), error_count, success_count
  - `get_token_usage_over_time()` — time-series: time, input_tokens, output_tokens, total_tokens
  - `get_cost_breakdown()` — grouped by agent or model: name, total_tokens, total_cost, request_count
  - `get_execution_logs()` — paginated logs with full detail
- `backend/app/api/v1/observability.py` — REST endpoints: `/dashboard`, `/tokens`, `/costs`, `/logs` — all accept `agent_id` query param

### Data Model
- `backend/app/models/execution_log.py` — ExecutionLog model:
  - `thread_id` (FK, indexed), `event_type` (String50), `duration_ms` (Integer)
  - `token_count` (JSONB): `{input_tokens, output_tokens}`
  - `state_snapshot` (JSONB): `{model_name, tool_calls, RAG sources}`
  - `created_at` (DateTime)

### Frontend — Parent Component
- `frontend/src/app/dashboard/agents/[id]/page.tsx` — Agent detail page (~870 lines). Currently renders `AgentConfigTopBar` but only passes `agentName, agentId, version, onSave, isSaving`. Missing `activeTab` and `onTabChange` props.

### Frontend — Tab Bar
- `frontend/src/components/agent/agent-config-top-bar.tsx` — Defines 4 tabs: playground, traces, monitor, evaluation. Has `activeTab`/`onTabChange` props but they're not wired by parent.

### Frontend — Reusable Components
- `frontend/src/components/ui/kpi-tile.tsx` — KpiTile + KpiTileGrid (4-column responsive grid with trend indicators)
- `frontend/src/components/ui/chart-card.tsx` — ChartCard wrapper for Recharts with loading state
- `frontend/src/components/ui/analytics-toolbar.tsx` — Time range buttons + granularity + refresh
- `frontend/src/components/ui/collapsible-section.tsx` — Expandable sections
- `frontend/src/lib/api.ts` — `apiFetch<T>()` typed API utility

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **KpiTile / KpiTileGrid**: Ready to use for Monitor tab's 6 KPI tiles — supports title, value, change%, trend icon, 4-column grid
- **ChartCard**: Recharts wrapper with title, loading state, min-height 250px — ready for Monitor charts
- **AnalyticsToolbar**: Time range selector (1h/24h/7d/30d) + granularity + refresh button — adaptable for both tabs
- **apiFetch<T>()**: Typed fetch utility with credentials, base URL from env — established pattern for all API calls

### Established Patterns
- **Component organization**: Agent components live in `frontend/src/components/agent/`
- **Data fetching**: `useEffect` + `apiFetch` in page/component, local state for loading/error
- **Tab pattern**: `AgentConfigTopBar` already implements sub-tab UI with purple #7C3AED active indicator
- **Right panel tabs**: Existing `rightTab` state in agent page for chat/yaml/code — similar pattern needed for top-level tabs

### Integration Points
- Agent detail page (`agents/[id]/page.tsx`) — add `activeTab` state, pass props to `AgentConfigTopBar`, conditionally render traces/monitor content
- Observability API endpoints — call with `?agent_id=<id>` to scope data to current agent
- ExecutionLog model — source of all trace data via `/logs` endpoint

</code_context>

<deferred>
## Deferred Ideas

- **Evaluation tab**: Fourth tab in top bar, not implemented in this phase — future phase for evaluation/testing
- **Log export/download**: Exporting trace data as CSV/JSON — not in scope
- **Alerting rules**: Setting threshold alerts on monitor KPIs — future feature
- **Real-time streaming**: WebSocket-based live trace streaming — out of scope, polling/manual refresh sufficient for PoC
- **Comparison mode**: Comparing metrics across time periods or agent versions — future enhancement

</deferred>

---

*Phase: 10-agent-level-traces-monitor-tabs*
