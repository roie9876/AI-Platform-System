---
phase: 08-observability-evaluation-marketplace-cli
plan: 01
subsystem: database, api, services
tags: [sqlalchemy, postgresql, fastapi, observability, cost-tracking, tokens]

requires:
  - phase: 06-orchestration-workflow-engine
    provides: Migration chain (revision 007)
provides:
  - ModelPricing, CostAlert SQLAlchemy models
  - Migration 008 creating model_pricing and cost_alerts tables with seed data
  - ObservabilityService for token aggregation, cost calculation, alert checking
  - Observability REST API with dashboard, cost alert, and pricing config endpoints
  - Token tracking integration in agent execution
affects: [08-04-observability-dashboard-frontend]

tech-stack:
  added: []
  patterns: [token-tracking-per-execution, model-pricing-lookup, cost-alert-thresholds]

key-files:
  created:
    - backend/app/models/cost_config.py
    - backend/alembic/versions/008_observability_cost_schema.py
    - backend/app/services/observability_service.py
    - backend/app/api/v1/observability.py
  modified:
    - backend/app/models/__init__.py
    - backend/app/api/v1/schemas.py
    - backend/app/api/v1/router.py
    - backend/app/services/agent_execution.py

key-decisions:
  - "ModelPricing stores per-model input/output cost per 1K tokens"
  - "CostAlert with threshold + period (daily/weekly/monthly) + active toggle"
  - "Seed pricing for gpt-4.1, gpt-4o, gpt-4o-mini, gpt-3.5-turbo"
  - "ObservabilityService aggregates tokens and cost by agent, model, and tenant"
  - "Token counts extracted from LiteLLM response in agent execution"

patterns-established:
  - "Observability data scoped per-tenant following existing multi-tenant patterns"
  - "Cost calculation via pricing table lookup against recorded token usage"

requirements-completed: [COST-01, COST-02, COST-03, COST-04]

completed: 2026-03-24
---

# Plan 08-01: Observability & Cost Tracking Backend Summary

**Token tracking, model pricing, cost aggregation APIs, and alert system establish the observability data layer.**

## Accomplishments
- Created ModelPricing and CostAlert SQLAlchemy models for cost configuration
- Built migration 008 creating model_pricing and cost_alerts tables with seed pricing data
- Built ObservabilityService with token aggregation, cost calculation, and alert checking
- Created observability REST API endpoints for dashboard data, cost alerts, and pricing config
- Integrated token extraction from LiteLLM responses in agent execution service

## Task Commits

1. **Observability backend** - `36dddc3` (feat)

## Files Created/Modified
- `backend/app/models/cost_config.py` - ModelPricing, CostAlert models
- `backend/alembic/versions/008_observability_cost_schema.py` - Migration with seed data
- `backend/app/services/observability_service.py` - Aggregation and cost calculation
- `backend/app/api/v1/observability.py` - REST endpoints
- `backend/app/api/v1/schemas.py` - Observability Pydantic schemas
- `backend/app/api/v1/router.py` - Registered observability router
- `backend/app/models/__init__.py` - Registered new models
