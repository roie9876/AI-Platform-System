"""Telemetry middleware — injects tenant_id into OpenTelemetry spans."""

from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware


class TelemetryMiddleware(BaseHTTPMiddleware):
    """Adds tenant_id and user_id as span attributes after TenantMiddleware has run."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        span = trace.get_current_span()
        if span and span.is_recording():
            tenant_id = getattr(request.state, "tenant_id", None)
            if tenant_id:
                span.set_attribute("tenant_id", tenant_id)

            user_id = getattr(request.state, "user_id", None)
            if user_id:
                span.set_attribute("user_id", user_id)

        return response
