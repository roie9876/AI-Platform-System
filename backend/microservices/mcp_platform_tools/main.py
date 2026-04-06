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
#  Execution log tool (enables OpenClaw → Traces in AI Platform UI)
# ---------------------------------------------------------------------------

@mcp.tool()
async def tool_create_execution_log(
    tenant_id: str,
    agent_id: str,
    event_type: str,
    input_text: str = "",
    output_text: str = "",
    tool_calls_count: int = 0,
    duration_ms: int = 0,
    source: str = "openclaw",
    channel: str = "",
    model_name: str = "",
) -> dict:
    """Create an execution log entry for observability. Called by OpenClaw plugin after each conversation turn."""
    from uuid import uuid4
    from app.repositories.observability_repo import ExecutionLogRepository
    repo = ExecutionLogRepository()
    log_entry = {
        "id": str(uuid4()),
        "event_type": event_type,
        "state_snapshot": {
            "input_text": input_text[:2000] if input_text else "",
            "output_text": output_text[:5000] if output_text else "",
            "response_length": len(output_text) if output_text else 0,
            "tool_calls_count": tool_calls_count,
            "source": source,
            "channel": channel,
            "model_name": model_name,
        },
        "duration_ms": duration_ms,
        "agent_id": agent_id,
        "tenant_id": tenant_id,
    }
    created = await repo.create(tenant_id, log_entry)
    logger.info("Created execution log %s for agent %s (type=%s)", created.get("id"), agent_id, event_type)
    return {"status": "ok", "id": created.get("id")}


# ---------------------------------------------------------------------------
#  Conversation history search (long-term memory via execution_logs)
# ---------------------------------------------------------------------------

@mcp.tool()
async def tool_search_conversation_history(
    tenant_id: str,
    agent_id: str,
    query: str = "",
    channel: str = "",
    limit: int = 10,
    days_back: int = 30,
) -> dict:
    """Search past conversation history stored in the platform database.
    Use this to recall older conversations when local/session memory doesn't have the answer.
    Searches both user messages and assistant responses by keyword.
    Args:
        query: keyword or phrase to search for in conversations (empty = recent conversations)
        channel: filter by channel e.g. 'whatsapp', 'chat' (empty = all channels)
        limit: max results to return (default 10, max 50)
        days_back: how many days back to search (default 30)
    """
    from datetime import datetime, timedelta, timezone
    from app.repositories.cosmos_client import get_cosmos_container

    container = await get_cosmos_container("execution_logs")
    if container is None:
        return {"status": "error", "message": "Database not available"}

    limit = min(max(1, limit), 50)
    days_back = min(max(1, days_back), 365)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

    params = [
        {"name": "@tid", "value": tenant_id},
        {"name": "@aid", "value": agent_id},
        {"name": "@cutoff", "value": cutoff},
        {"name": "@limit", "value": limit},
    ]

    conditions = [
        "c.tenant_id = @tid",
        "c.agent_id = @aid",
        "c.event_type = 'model_response'",
        "c.created_at >= @cutoff",
    ]

    if query:
        conditions.append(
            "(CONTAINS(c.state_snapshot.input_text, @query, true) "
            "OR CONTAINS(c.state_snapshot.output_text, @query, true))"
        )
        params.append({"name": "@query", "value": query})

    if channel:
        conditions.append("c.state_snapshot.channel = @channel")
        params.append({"name": "@channel", "value": channel})

    sql = (
        f"SELECT TOP @limit c.id, c.created_at, c.state_snapshot.input_text AS user_message, "
        f"c.state_snapshot.output_text AS assistant_response, "
        f"c.state_snapshot.channel AS channel, c.state_snapshot.model_name AS model, "
        f"c.state_snapshot.tool_calls_count AS tool_calls "
        f"FROM c WHERE {' AND '.join(conditions)} "
        f"ORDER BY c.created_at DESC"
    )

    results = []
    async for item in container.query_items(
        query=sql, parameters=params, partition_key=tenant_id
    ):
        # Truncate long texts for readability
        if item.get("user_message"):
            item["user_message"] = item["user_message"][:500]
        if item.get("assistant_response"):
            item["assistant_response"] = item["assistant_response"][:1000]
        results.append(item)

    return {
        "status": "ok",
        "count": len(results),
        "query": query or "(recent)",
        "days_back": days_back,
        "conversations": results,
    }


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
