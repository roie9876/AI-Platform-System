from __future__ import annotations

import re
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

# In-memory slug → UUID cache (TTL same as tenant status)
_slug_to_id_cache: dict[str, tuple[str, float]] = {}

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

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

                # Override tenant context from X-Tenant-Id header.
                # Accepts a UUID (tenant id) or a slug (resolved to UUID).
                x_tenant_id = request.headers.get("X-Tenant-Id")
                if x_tenant_id:
                    request.state.tenant_id = await _resolve_tenant_id(x_tenant_id)
            elif not request.url.path.startswith("/api/v1/internal"):
                # Token was provided but is invalid — reject immediately
                # (skip for internal inter-service calls that forward tokens)
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or expired bearer token"},
                    headers={"WWW-Authenticate": "Bearer"},
                )

        return await call_next(request)


async def _resolve_tenant_id(value: str) -> str:
    """Resolve a tenant slug to its UUID. If already a UUID, return as-is."""
    if _UUID_RE.match(value):
        return value

    now = time.time()
    cached = _slug_to_id_cache.get(value)
    if cached:
        tid, cached_at = cached
        if (now - cached_at) < _CACHE_TTL:
            return tid

    repo = TenantRepository()
    # get_by_slug may return a deleted tenant if slug was re-used.
    # Query directly for active tenant with this slug.
    container = await repo._container()
    if container:
        results = []
        async for item in container.query_items(
            query="SELECT c.id, c.status FROM c WHERE c.slug = @slug",
            parameters=[{"name": "@slug", "value": value}],
        ):
            results.append(item)
        # Prefer active tenant; fall back to any match
        active = [r for r in results if r.get("status") == "active"]
        tenant = (active or results or [None])[0]
        if tenant:
            _slug_to_id_cache[value] = (tenant["id"], now)
            return tenant["id"]

    # Slug not found — return as-is and let downstream handle the error
    return value


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
