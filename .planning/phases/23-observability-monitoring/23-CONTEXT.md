---
phase: 23-observability-monitoring
auto_generated: true
---

# Phase 23: Observability & Monitoring — Context

## Decisions

- D-01: Use OpenTelemetry SDK for Python instrumentation (industry standard, Azure-compatible)
- D-02: Export traces/metrics to Azure Application Insights via azure-monitor-opentelemetry-exporter
- D-03: All telemetry includes tenant_id dimension for per-tenant filtering
- D-04: Use Azure Monitor alert rules (Bicep) for automated alerting
- D-05: Structured JSON logging with tenant_id context propagation

## Deferred Ideas

- Custom Grafana dashboards (Azure Monitor dashboards sufficient for v3.0)
- Real-time streaming metrics (batch export adequate)

## Agent's Discretion

- OpenTelemetry instrumentation granularity (auto-instrument vs manual spans)
- Alert threshold values (reasonable defaults)
- Log level configuration
