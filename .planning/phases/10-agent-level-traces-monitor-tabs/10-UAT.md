---
status: testing
phase: 10-agent-level-traces-monitor-tabs
source: [10-01-SUMMARY.md, 10-02-SUMMARY.md]
started: "2026-03-24T15:10:00.000Z"
updated: "2026-03-24T15:10:00.000Z"
---

## Current Test

number: 1
name: Tab Navigation Between Playground, Traces, Monitor, Evaluation
expected: |
  On the agent detail page, click each tab in the top bar: Playground, Traces, Monitor, Evaluation.
  Each tab becomes visually active (highlighted). The content area switches to the corresponding panel.
  Playground shows the existing agent config/chat layout. Traces shows a trace table. Monitor shows KPI tiles and charts. Evaluation shows a placeholder message.
awaiting: user response

## Tests

### 1. Tab Navigation Between Playground, Traces, Monitor, Evaluation
expected: On the agent detail page, click each tab in the top bar: Playground, Traces, Monitor, Evaluation. Each tab becomes visually active (highlighted). The content area switches to the corresponding panel. Playground shows the existing agent config/chat layout. Traces shows a trace table. Monitor shows KPI tiles and charts. Evaluation shows a placeholder message.
result: [pending]

### 2. Traces Tab — Table with Correct Columns
expected: Click the Traces tab. A table appears with columns: Thread ID, Status, Start Time, Duration, Tokens In, Tokens Out, Cost, Model, Tools Called. Each row shows a trace entry with status badge (green for model_response, yellow for tool_call, red for error). If no traces exist, an empty state message appears: "No traces found for this agent in the selected time range".
result: [pending]

### 3. Traces Tab — Time Range Filtering
expected: On the Traces tab, click the time range buttons (1h, 24h, 7d, 30d) in the toolbar. The table reloads with traces filtered to the selected time window. The active time range button is highlighted purple.
result: [pending]

### 4. Traces Tab — Expandable Row Detail
expected: Click any trace row in the table. The row expands to reveal execution details: full Thread ID, Model, Duration, Input/Output Tokens, Estimated Cost. If tool calls exist, they appear with function names. Clicking the row again collapses it.
result: [pending]

### 5. Traces Tab — Pagination
expected: If more than 20 traces exist, pagination controls appear at the bottom showing "Showing 1–20 of N". Previous/Next buttons navigate between pages. If fewer than 20 traces, no pagination controls are shown.
result: [pending]

### 6. Monitor Tab — 6 KPI Tiles
expected: Click the Monitor tab. Six KPI tiles appear in a grid layout: Total Requests, Error Rate %, Avg Latency (ms), Total Tokens, Total Cost ($), P95 Latency (ms). Each tile has a colored left border, an icon, and the metric value. If no data exists, a "No monitoring data available" message appears.
result: [pending]

### 7. Monitor Tab — Time-Series Charts
expected: Below the KPI tiles on the Monitor tab, two charts appear side by side: "Token Usage Over Time" (area chart with input/output token regions) and "Token Consumption Trend" (line chart showing total tokens). A time range toolbar and granularity selector are at the top. Changing time range or granularity updates the charts.
result: [pending]

## Summary

total: 7
passed: 0
issues: 0
pending: 7
skipped: 0
blocked: 0

## Gaps

[none yet]
