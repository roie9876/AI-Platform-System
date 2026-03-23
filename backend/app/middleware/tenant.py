import jwt
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

PUBLIC_PATHS = {
    "/api/v1/health",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
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

        access_token = request.cookies.get("access_token")
        if access_token:
            try:
                payload = jwt.decode(
                    access_token, settings.SECRET_KEY, algorithms=["HS256"]
                )
                request.state.user_id = payload.get("sub")
                request.state.tenant_id = payload.get("tenant_id")
            except jwt.InvalidTokenError:
                pass

        return await call_next(request)


def get_tenant_id(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=403, detail="Tenant context required"
        )
    return tenant_id
