from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import validate_entra_token, extract_user_context

PUBLIC_PATHS = {
    "/api/v1/health",
    "/docs",
    "/openapi.json",
    "/redoc",
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

        return await call_next(request)


def get_tenant_id(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=403, detail="Tenant context required"
        )
    return tenant_id
