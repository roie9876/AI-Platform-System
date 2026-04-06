"""MCP Platform Tools — FastMCP server with memory and platform config tools."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from app.core.logging_config import configure_logging
from app.core.telemetry import init_telemetry
from app.repositories.cosmos_client import close_cosmos_client

from .embedding import EmbeddingService
from .memory import (
    memory_delete,
    memory_delete_by_agent,
    memory_get_structured,
    memory_search,
    memory_store,
    memory_store_structured,
    set_embedding_service,
)
from .platform_config import (
    get_agent_config,
    get_group_instructions,
    list_configured_groups,
)

logger = logging.getLogger(__name__)

from mcp.server.transport_security import TransportSecuritySettings

# ---------------------------------------------------------------------------
#  FastMCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "mcp-platform-tools",
    stateless_http=True,
    json_response=True,
    host="0.0.0.0",
    port=8085,
)

# Allow K8s service hostname for in-cluster calls (DNS rebinding protection)
mcp.settings.transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        "127.0.0.1:*",
        "localhost:*",
        "[::1]:*",
        "mcp-platform-tools.aiplatform.svc.cluster.local:*",
    ],
)


# ---------------------------------------------------------------------------
#  Memory tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def tool_memory_store(
    tenant_id: str,
    agent_id: str,
    content: str,
    memory_type: str = "knowledge",
    user_id: str = "",
    source: str = "",
) -> dict:
    """Store a memory with semantic embedding for later retrieval."""
    return await memory_store(tenant_id, agent_id, content, memory_type, user_id, source)


@mcp.tool()
async def tool_memory_search(
    tenant_id: str,
    agent_id: str,
    query: str,
    top_k: int = 5,
    memory_type: str = "",
) -> dict:
    """Search memories by semantic similarity using vector search."""
    return await memory_search(tenant_id, agent_id, query, top_k, memory_type)


@mcp.tool()
async def tool_memory_store_structured(
    tenant_id: str,
    agent_id: str,
    key: str,
    value: str,
    category: str = "preference",
) -> dict:
    """Store a structured key-value fact (no embedding needed)."""
    return await memory_store_structured(tenant_id, agent_id, key, value, category)


@mcp.tool()
async def tool_memory_delete(
    tenant_id: str,
    agent_id: str,
    memory_id: str,
) -> dict:
    """Delete a single memory by ID."""
    return await memory_delete(tenant_id, agent_id, memory_id)


@mcp.tool()
async def tool_memory_delete_all(
    tenant_id: str,
    agent_id: str,
) -> dict:
    """Delete ALL memories for an agent. Use with caution."""
    return await memory_delete_by_agent(tenant_id, agent_id)


@mcp.tool()
async def tool_memory_get_structured(
    tenant_id: str,
    agent_id: str,
    key: str = "",
    category: str = "",
) -> dict:
    """Retrieve structured memories by key, category, or list all for an agent."""
    return await memory_get_structured(tenant_id, agent_id, key, category)


# ---------------------------------------------------------------------------
#  Platform config tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def tool_get_group_instructions(
    tenant_id: str,
    agent_id: str,
    group_jid: str,
) -> dict:
    """Get per-group instructions and settings for a WhatsApp group."""
    return await get_group_instructions(tenant_id, agent_id, group_jid)


@mcp.tool()
async def tool_get_agent_config(
    tenant_id: str,
    agent_id: str,
) -> dict:
    """Get agent configuration (name, system prompt, model)."""
    return await get_agent_config(tenant_id, agent_id)


@mcp.tool()
async def tool_list_configured_groups(
    tenant_id: str,
    agent_id: str,
) -> dict:
    """List all WhatsApp groups configured for an agent."""
    return await list_configured_groups(tenant_id, agent_id)


# ---------------------------------------------------------------------------
#  Health endpoints (plain Starlette — not MCP tools)
# ---------------------------------------------------------------------------

async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def readyz(request: Request) -> JSONResponse:
    from app.repositories.cosmos_client import get_cosmos_client

    try:
        await get_cosmos_client()
        return JSONResponse({"status": "ok"})
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)


async def startupz(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
#  Starlette app combining MCP + health routes
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: Starlette):
    configure_logging(service_name="mcp-platform-tools")
    init_telemetry(service_name="mcp-platform-tools")
    svc = EmbeddingService()
    set_embedding_service(svc)
    logger.info("MCP Platform Tools server starting")
    async with mcp.session_manager.run():
        yield
    await close_cosmos_client()


mcp.settings.streamable_http_path = "/mcp"

app = Starlette(
    routes=[
        Route("/healthz", healthz),
        Route("/readyz", readyz),
        Route("/startupz", startupz),
        Mount("/", app=mcp.streamable_http_app()),
    ],
    lifespan=lifespan,
)
