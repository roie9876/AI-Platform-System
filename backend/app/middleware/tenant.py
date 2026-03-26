from __future__ import annotations

import time

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.security import validate_entra_token, extract_user_context
from app.repositories.tenant_repo import TenantRepository

PUBLIC_PATHS = {
    "/api/v1/health",
    "/healthz",
    "/readyz",
    "/startupz",
    "/docs",
    "/openapi.json",
    "/redoc",
}

# In-memory tenant status cache with 60-second TTL
_tenant_status_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 60

_STATUS_RESPONSES = {
    "suspended": (403, "Tenant is suspended. Contact platform administrator."),
    "deactivated": (403, "Tenant is deactivated. Contact platform administrator."),
    "deleted": (403, "Tenant no longer exists."),
    "provisioning": (503, "Tenant is being provisioned. Please try again shortly."),
}


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS or not request.url.path.startswith(
            "/api/"
        ):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            claims = await validate_entra_token(token)
            if claims:
                user_context = extract_user_context(claims)
                request.state.user_context = user_context
                # Backward compat
                request.state.user_id = user_context["user_id"]
                request.state.tenant_id = user_context["tenant_id"]

                # Skip tenant status check for:
                # 1. Platform admin endpoints (tenants CRUD)
                # 2. Requests with X-Tenant-Id header (will use app tenant)
                x_tenant_id = request.headers.get("X-Tenant-Id")
                if x_tenant_id:
                    request.state.tenant_id = x_tenant_id

        return await call_next(request)


async def _check_tenant_status(tenant_id: str) -> JSONResponse | None:
    now = time.time()
    cached = _tenant_status_cache.get(tenant_id)
    if cached:
        status, cached_at = cached
        if (now - cached_at) < _CACHE_TTL:
            if status in _STATUS_RESPONSES:
                code, detail = _STATUS_RESPONSES[status]
                return JSONResponse(status_code=code, content={"detail": detail})
            return None

    repo = TenantRepository()
    tenant = await repo.get(tenant_id, tenant_id)

    if not tenant:
        return JSONResponse(status_code=403, content={"detail": "Tenant not found"})

    status = tenant.get("status", "active")
    _tenant_status_cache[tenant_id] = (status, now)

    if status in _STATUS_RESPONSES:
        code, detail = _STATUS_RESPONSES[status]
        return JSONResponse(status_code=code, content={"detail": detail})

    return None


def get_tenant_id(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=403, detail="Tenant context required"
        )
    return tenant_id
