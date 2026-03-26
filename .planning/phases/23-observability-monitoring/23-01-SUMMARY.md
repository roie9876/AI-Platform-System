---
phase: 23-observability-monitoring
plan: 01
subsystem: observability
tags: [opentelemetry, azure-monitor, application-insights, structured-logging, tracing]

requires: []
provides:
  - OpenTelemetry SDK initialization (init_telemetry) for all FastAPI services
  - TelemetryMiddleware injecting tenant_id into trace spans
  - Structured JSON logging with trace context correlation
affects: [infra, deployment, monitoring]

tech-stack:
  added: [opentelemetry-api, opentelemetry-sdk, opentelemetry-instrumentation-fastapi, opentelemetry-instrumentation-httpx, azure-monitor-opentelemetry-exporter, python-json-logger]
  patterns: [otel-init-in-lifespan, tenant-aware-spans, json-structured-logging-with-trace-context]

key-files:
  created:
    - backend/app/core/telemetry.py
    - backend/app/middleware/telemetry.py
    - backend/app/core/logging_config.py
  modified:
    - backend/requirements.txt
    - backend/app/main.py
    - backend/microservices/api_gateway/main.py
    - backend/microservices/agent_executor/main.py
    - backend/microservices/workflow_engine/main.py
    - backend/microservices/tool_executor/main.py
    - backend/microservices/mcp_proxy/main.py

key-decisions:
  - "TelemetryMiddleware reads tenant_id after call_next so it works regardless of middleware ordering"
  - "Console exporters used as fallback when APPLICATIONINSIGHTS_CONNECTION_STRING not set (local dev)"

patterns-established:
  - "OpenTelemetry init via init_telemetry() in lifespan before yield"
  - "TelemetryMiddleware added after TenantMiddleware in middleware stack"
  - "TraceContextFilter injects trace_id/span_id into all log records"

requirements-completed: [OBS-01, OBS-02, OBS-03, OBS-04]

duration: 8min
completed: 2026-03-26
---

# Plan 23-01: OpenTelemetry Instrumentation Summary

**All 6 FastAPI services instrumented with OpenTelemetry tracing, metrics, tenant-aware spans, and structured JSON logging with trace context correlation.**

## Performance

- **Tasks:** 2 completed
- **Files modified:** 10

## Accomplishments
- OpenTelemetry SDK initialized with Azure Monitor exporters (traces + metrics) across all services
- TelemetryMiddleware tags every span with tenant_id for per-tenant observability queries
- Structured JSON logging includes trace_id, span_id, service name for log-trace correlation
- httpx auto-instrumented for distributed tracing across microservice boundaries

## Task Commits

1. **Task 1: OpenTelemetry SDK setup, telemetry middleware, structured logging** - `011c8b8` (feat)
2. **Task 2: Wire telemetry into all microservices** - `012e99a` (feat)

## Files Created/Modified
- `backend/app/core/telemetry.py` - OpenTelemetry init with Azure Monitor exporter + console fallback
- `backend/app/middleware/telemetry.py` - Middleware injecting tenant_id/user_id into spans
- `backend/app/core/logging_config.py` - JSON logging with TraceContextFilter
- `backend/requirements.txt` - Added 7 OpenTelemetry + logging dependencies
- `backend/app/main.py` - Monolith wired with telemetry
- `backend/microservices/api_gateway/main.py` - API Gateway wired
- `backend/microservices/agent_executor/main.py` - Agent Executor wired
- `backend/microservices/workflow_engine/main.py` - Workflow Engine wired
- `backend/microservices/tool_executor/main.py` - Tool Executor wired
- `backend/microservices/mcp_proxy/main.py` - MCP Proxy wired

## Decisions Made
- TelemetryMiddleware reads tenant_id after call_next returns, making it order-independent relative to TenantMiddleware
- Console span/metric exporters for local development when no connection string is set

## Deviations from Plan
None - plan executed exactly as written

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- APPLICATIONINSIGHTS_CONNECTION_STRING env var needed at runtime (provided by Plan 23-02 infra)
- All services ready to export telemetry once App Insights is provisioned
