"""Shared health check router used by all microservices."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.repositories.cosmos_client import get_cosmos_client

health_router = APIRouter(tags=["health"])


@health_router.get("/healthz")
async def liveness():
    """Liveness probe — process is alive."""
    return {"status": "ok"}


@health_router.get("/readyz")
async def readiness():
    """Readiness probe — dependencies reachable."""
    try:
        await get_cosmos_client()
        return {"status": "ok"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})


@health_router.get("/startupz")
async def startup():
    """Startup probe — application initialized."""
    return {"status": "ok"}
