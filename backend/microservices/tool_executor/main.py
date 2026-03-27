"""Tool Executor microservice — routes for tools, data-sources, knowledge + internal tool execute endpoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter

from app.core.config import settings
from app.core.telemetry import init_telemetry
from app.core.logging_config import configure_logging
from app.middleware.tenant import TenantMiddleware
from app.middleware.telemetry import TelemetryMiddleware
from app.repositories.cosmos_client import close_cosmos_client
from app.health import health_router

from app.api.v1.tools import router as tools_router, agent_tools_router
from app.api.v1.data_sources import router as data_sources_router, agent_data_sources_router
from app.api.v1.knowledge import router as knowledge_router
from app.services.tool_executor import ToolExecutor

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
    configure_logging(service_name="tool-executor")
    init_telemetry(service_name="tool-executor")
    _log_auth_config("tool-executor")
    yield
    await close_cosmos_client()


app = FastAPI(title="AI Platform - Tool Executor", version="0.1.0", lifespan=lifespan)
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
app.include_router(tools_router, prefix="/api/v1/tools", tags=["tools"])
app.include_router(agent_tools_router, prefix="/api/v1/agents", tags=["agent-tools"])
app.include_router(data_sources_router, prefix="/api/v1/data-sources", tags=["data-sources"])
app.include_router(agent_data_sources_router, prefix="/api/v1/agents", tags=["agent-data-sources"])
app.include_router(knowledge_router, prefix="/api/v1/knowledge", tags=["knowledge"])

# Internal endpoint for inter-service tool execution
internal_router = APIRouter(prefix="/api/v1/internal", tags=["internal"])


@internal_router.post("/tools/execute")
async def internal_execute_tool(request: Request):
    body = await request.json()
    executor = ToolExecutor()
    result = await executor.execute(
        tool_name=body["tool_name"],
        input_data=body["input_data"],
        input_schema=body["input_schema"],
        execution_command=body.get("execution_command"),
        timeout_seconds=body.get("timeout_seconds", 30),
    )
    return result


app.include_router(internal_router)
