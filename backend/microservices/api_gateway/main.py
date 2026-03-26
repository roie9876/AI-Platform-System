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


@asynccontextmanager
async def lifespan(app):
    configure_logging(service_name="api-gateway")
    init_telemetry(service_name="api-gateway")
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
