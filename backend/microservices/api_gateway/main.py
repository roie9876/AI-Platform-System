"""API Gateway microservice — routes for auth, agents, model-endpoints, catalog, marketplace, observability, evaluations, azure-*, ai-services."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.telemetry import init_telemetry
from app.core.logging_config import configure_logging
from app.middleware.tenant import TenantMiddleware
from app.middleware.telemetry import TelemetryMiddleware
from app.repositories.cosmos_client import close_cosmos_client
from app.health import health_router

from app.api.v1.auth import router as auth_router
from app.api.v1.agents import router as agents_router
from app.api.v1.model_endpoints import router as model_endpoints_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.marketplace import router as marketplace_router
from app.api.v1.observability import router as observability_router
from app.api.v1.evaluations import router as evaluations_router
from app.api.v1.azure_subscriptions import router as azure_subscriptions_router
from app.api.v1.azure_connections import router as azure_connections_router
from app.api.v1.azure_auth import router as azure_auth_router
from app.api.v1.ai_services import router as ai_services_router
from app.api.v1.tenants import router as tenants_router

import logging as _logging
import os as _os
_startup_logger = _logging.getLogger(__name__)

def _log_auth_config(svc: str):
    from app.core.config import settings
    env_cid = _os.environ.get("AZURE_CLIENT_ID", "")
    entra_cid = _os.environ.get("ENTRA_APP_CLIENT_ID", "")
    resolved = settings.ENTRA_APP_CLIENT_ID or settings.AZURE_CLIENT_ID
    _startup_logger.warning(
        "[%s] AUTH CONFIG: AZURE_CLIENT_ID(env)=...%s  ENTRA_APP_CLIENT_ID(env)=...%s  "
        "resolved_jwt_audience=...%s  AZURE_TENANT_ID=...%s  WORKLOAD_CLIENT_ID=...%s",
        svc,
        env_cid[-4:] if env_cid else "UNSET",
        entra_cid[-4:] if entra_cid else "UNSET",
        resolved[-4:] if resolved else "UNSET",
        settings.AZURE_TENANT_ID[-4:] if settings.AZURE_TENANT_ID else "UNSET",
        settings.AZURE_WORKLOAD_CLIENT_ID[-4:] if settings.AZURE_WORKLOAD_CLIENT_ID else "UNSET",
    )


@asynccontextmanager
async def lifespan(app):
    configure_logging(service_name="api-gateway")
    init_telemetry(service_name="api-gateway")
    _log_auth_config("api-gateway")
    yield
    await close_cosmos_client()


app = FastAPI(title="AI Platform - API Gateway", version="0.1.0", lifespan=lifespan)
app.add_middleware(TelemetryMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(agents_router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(model_endpoints_router, prefix="/api/v1/model-endpoints", tags=["model-endpoints"])
app.include_router(catalog_router, prefix="/api/v1/catalog", tags=["catalog"])
app.include_router(marketplace_router, prefix="/api/v1/marketplace", tags=["marketplace"])
app.include_router(observability_router, prefix="/api/v1/observability", tags=["observability"])
app.include_router(evaluations_router, prefix="/api/v1/evaluations", tags=["evaluations"])
app.include_router(azure_subscriptions_router, prefix="/api/v1/azure", tags=["azure"])
app.include_router(azure_connections_router, prefix="/api/v1/azure", tags=["azure-connections"])
app.include_router(azure_auth_router, prefix="/api/v1/azure", tags=["azure-auth"])
app.include_router(ai_services_router, prefix="/api/v1/ai-services", tags=["ai-services"])
app.include_router(tenants_router, prefix="/api/v1/tenants", tags=["tenants"])
