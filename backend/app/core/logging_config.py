"""Structured JSON logging with OpenTelemetry trace context."""

import logging
import sys

from opentelemetry import trace
from pythonjsonlogger import json as json_logger


class TraceContextFilter(logging.Filter):
    """Injects trace_id, span_id, and tenant_id into every log record."""

    def __init__(self, service_name: str = "unknown"):
        super().__init__()
        self.service_name = service_name

    def filter(self, record):
        record.service = self.service_name

        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None

        if ctx and ctx.is_valid:
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
        else:
            record.trace_id = ""
            record.span_id = ""

        return True


def configure_logging(service_name: str, level: int = logging.INFO) -> None:
    """Configure structured JSON logging with trace context for all loggers."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    formatter = json_logger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(service)s %(trace_id)s %(span_id)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
        },
    )
    handler.setFormatter(formatter)

    trace_filter = TraceContextFilter(service_name=service_name)
    handler.addFilter(trace_filter)

    root_logger.addHandler(handler)
