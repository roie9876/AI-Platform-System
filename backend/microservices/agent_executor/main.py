"""Agent Executor microservice — routes for chat, threads, memories + internal agent execution endpoint."""

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

from app.api.v1.chat import router as chat_router
from app.api.v1.threads import router as threads_router
from app.api.v1.memories import router as memories_router
from app.repositories.agent_repo import AgentRepository
from app.services.agent_execution import AgentExecutionService

_agent_repo = AgentRepository()

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
    configure_logging(service_name="agent-executor")
    init_telemetry(service_name="agent-executor")
    _log_auth_config("agent-executor")
    yield
    await close_cosmos_client()


app = FastAPI(title="AI Platform - Agent Executor", version="0.1.0", lifespan=lifespan)
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
app.include_router(chat_router, prefix="/api/v1/agents", tags=["chat"])
app.include_router(threads_router, prefix="/api/v1/threads", tags=["threads"])
app.include_router(memories_router, prefix="/api/v1/agents", tags=["agent-memories"])

# Internal endpoint for inter-service agent execution (used by workflow-engine)
internal_router = APIRouter(prefix="/api/v1/internal", tags=["internal"])


@internal_router.post("/agents/{agent_id}/execute")
async def internal_execute_agent(agent_id: str, request: Request):
    body = await request.json()
    tenant_id = body["tenant_id"]
    agent = await _agent_repo.get(tenant_id, agent_id)
    if not agent:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Agent not found"})

    auth_header = request.headers.get("Authorization", "")
    auth_token = auth_header[7:] if auth_header.startswith("Bearer ") else None

    service = AgentExecutionService()
    collected = []
    import json
    async for sse_line in service.execute(
        agent=agent,
        user_message=body["message"],
        tenant_id=tenant_id,
        thread_id=body.get("thread_id"),
        user_id=body.get("user_id"),
        auth_token=auth_token,
    ):
        if sse_line.startswith("data: "):
            try:
                payload = json.loads(sse_line[6:].strip())
                if payload.get("error"):
                    return {"error": payload["error"]}
                content = payload.get("content", "")
                if content and not payload.get("done"):
                    collected.append(content)
            except json.JSONDecodeError:
                continue

    return {"response": "".join(collected)}


app.include_router(internal_router)
