from uuid import UUID as PyUUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.mcp_server import MCPServer
from app.services.mcp_discovery import MCPDiscoveryService
from app.api.v1.schemas import (
    MCPDiscoveredToolListResponse,
    MCPDiscoveredToolResponse,
    MCPDiscoverySummaryResponse,
    MCPServerResponse,
)

router = APIRouter()


@router.get("/tools", response_model=MCPDiscoveredToolListResponse)
async def list_discovered_tools(
    request: Request,
    server_id: Optional[PyUUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List all discovered MCP tools, optionally filtered by server."""
    tools = await MCPDiscoveryService.get_all_discovered_tools(
        db, tenant_id=tenant_id, server_id=server_id
    )
    return MCPDiscoveredToolListResponse(tools=tools, total=len(tools))


@router.post("/discover-all", response_model=MCPDiscoverySummaryResponse)
async def discover_all_tools(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Trigger tool discovery across all active MCP servers for the tenant."""
    summary = await MCPDiscoveryService.discover_all_servers(db, tenant_id=tenant_id)
    return MCPDiscoverySummaryResponse(
        servers_scanned=len(summary),
        tools_discovered=summary,
    )


@router.post(
    "/servers/{server_id}/discover",
    response_model=MCPDiscoveredToolListResponse,
)
async def discover_tools_from_server(
    server_id: PyUUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Trigger tool discovery from a specific MCP server."""
    result = await db.execute(
        select(MCPServer).where(
            MCPServer.id == server_id, MCPServer.tenant_id == tenant_id
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")

    tools = await MCPDiscoveryService.discover_tools_from_server(db, server)
    return MCPDiscoveredToolListResponse(tools=tools, total=len(tools))


@router.post(
    "/servers/{server_id}/health-check",
    response_model=MCPServerResponse,
)
async def health_check_server(
    server_id: PyUUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Check MCP server health and update its status."""
    result = await db.execute(
        select(MCPServer).where(
            MCPServer.id == server_id, MCPServer.tenant_id == tenant_id
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")

    await MCPDiscoveryService.health_check_server(db, server)
    await db.refresh(server)
    return server
