"""MCP Proxy microservice — routes for mcp-servers, mcp-discovery, agent-mcp-tools + internal mcp call endpoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter

from app.core.config import settings
from app.middleware.tenant import TenantMiddleware
from app.repositories.cosmos_client import close_cosmos_client
from app.health import health_router

from app.api.v1.mcp_servers import router as mcp_servers_router
from app.api.v1.mcp_discovery import router as mcp_discovery_router
from app.api.v1.agent_mcp_tools import router as agent_mcp_tools_router
from app.services.mcp_client import MCPClient


@asynccontextmanager
async def lifespan(app):
    yield
    await close_cosmos_client()


app = FastAPI(title="AI Platform - MCP Proxy", version="0.1.0", lifespan=lifespan)
app.add_middleware(TenantMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(mcp_servers_router, prefix="/api/v1/mcp-servers", tags=["mcp-servers"])
app.include_router(mcp_discovery_router, prefix="/api/v1/mcp", tags=["mcp-discovery"])
app.include_router(agent_mcp_tools_router, prefix="/api/v1/agents", tags=["agent-mcp-tools"])

# Internal endpoint for inter-service MCP tool calls
internal_router = APIRouter(prefix="/api/v1/internal", tags=["internal"])


@internal_router.post("/mcp/call-tool")
async def internal_call_mcp_tool(request: Request):
    body = await request.json()
    client = MCPClient(server_url=body["server_url"])
    await client.initialize()
    try:
        result = await client.call_tool(name=body["tool_name"], arguments=body["arguments"])
        return {
            "content": [block.__dict__ for block in result.content],
            "is_error": result.is_error,
        }
    finally:
        await client.close()


app.include_router(internal_router)
