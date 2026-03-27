"""Workflow Engine microservice — routes for workflows."""

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

from app.api.v1.workflows import router as workflows_router

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
    configure_logging(service_name="workflow-engine")
    init_telemetry(service_name="workflow-engine")
    _log_auth_config("workflow-engine")
    yield
    await close_cosmos_client()


app = FastAPI(title="AI Platform - Workflow Engine", version="0.1.0", lifespan=lifespan)
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
app.include_router(workflows_router, prefix="/api/v1/workflows", tags=["workflows"])
