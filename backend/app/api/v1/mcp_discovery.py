from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Optional

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.mcp_repo import MCPServerRepository, MCPDiscoveredToolRepository
from app.services.mcp_discovery import MCPDiscoveryService
from app.api.v1.schemas import (
    MCPDiscoveredToolListResponse,
    MCPDiscoveredToolResponse,
    MCPDiscoverySummaryResponse,
    MCPServerResponse,
)

router = APIRouter()

server_repo = MCPServerRepository()
tool_repo = MCPDiscoveredToolRepository()


@router.get("/tools", response_model=MCPDiscoveredToolListResponse)
async def list_discovered_tools(
    request: Request,
    server_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List all discovered MCP tools, optionally filtered by server."""
    tools = await MCPDiscoveryService.get_all_discovered_tools(
        tenant_id=tenant_id, server_id=server_id
    )
    return MCPDiscoveredToolListResponse(tools=tools, total=len(tools))


@router.post("/discover-all", response_model=MCPDiscoverySummaryResponse)
async def discover_all_tools(
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Trigger tool discovery across all active MCP servers for the tenant."""
    summary = await MCPDiscoveryService.discover_all_servers(tenant_id=tenant_id)
    return MCPDiscoverySummaryResponse(
        servers_scanned=len(summary),
        tools_discovered=summary,
    )


@router.post(
    "/servers/{server_id}/discover",
    response_model=MCPDiscoveredToolListResponse,
)
async def discover_tools_from_server(
    server_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Trigger tool discovery from a specific MCP server."""
    server = await server_repo.get(tenant_id, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")

    tools = await MCPDiscoveryService.discover_tools_from_server(server, tenant_id=tenant_id)
    return MCPDiscoveredToolListResponse(tools=tools, total=len(tools))


@router.post(
    "/servers/{server_id}/health-check",
    response_model=MCPServerResponse,
)
async def health_check_server(
    server_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Check MCP server health and update its status."""
    server = await server_repo.get(tenant_id, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")

    await MCPDiscoveryService.health_check_server(server, tenant_id=tenant_id)
    updated = await server_repo.get(tenant_id, server_id)
    return updated
