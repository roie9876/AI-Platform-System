from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.mcp_server import MCPServer
from app.api.v1.schemas import (
    MCPServerCreateRequest,
    MCPServerUpdateRequest,
    MCPServerResponse,
    MCPServerListResponse,
)

router = APIRouter()


@router.post("/", response_model=MCPServerResponse, status_code=201)
async def create_mcp_server(
    body: MCPServerCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    server = MCPServer(
        name=body.name,
        url=body.url,
        description=body.description,
        auth_type=body.auth_type,
        auth_header_name=body.auth_header_name,
        auth_credential_ref=body.auth_credential_ref,
        tenant_id=tenant_id,
    )
    db.add(server)
    await db.flush()
    await db.refresh(server)
    return server


@router.get("/", response_model=MCPServerListResponse)
async def list_mcp_servers(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(MCPServer)
        .where(MCPServer.tenant_id == tenant_id)
        .order_by(MCPServer.created_at.desc())
    )
    servers = list(result.scalars().all())
    return MCPServerListResponse(servers=servers, total=len(servers))


@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_mcp_server(
    server_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(MCPServer).where(
            MCPServer.id == server_id, MCPServer.tenant_id == tenant_id
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return server


@router.patch("/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: UUID,
    body: MCPServerUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(MCPServer).where(
            MCPServer.id == server_id, MCPServer.tenant_id == tenant_id
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(server, field, value)

    await db.flush()
    await db.refresh(server)
    return server


@router.delete("/{server_id}", status_code=204)
async def delete_mcp_server(
    server_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(MCPServer).where(
            MCPServer.id == server_id, MCPServer.tenant_id == tenant_id
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")

    await db.delete(server)
    await db.flush()


@router.post("/{server_id}/check-status", response_model=MCPServerResponse)
async def check_mcp_server_status(
    server_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Attempt to connect to the MCP server and update its status."""
    from app.services.mcp_client import MCPClient, MCPClientError

    result = await db.execute(
        select(MCPServer).where(
            MCPServer.id == server_id, MCPServer.tenant_id == tenant_id
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")

    headers = {}
    if server.auth_type == "bearer" and server.auth_credential_ref:
        headers["Authorization"] = f"Bearer {server.auth_credential_ref}"
    elif server.auth_type == "api_key" and server.auth_credential_ref:
        header_name = server.auth_header_name or "X-API-Key"
        headers[header_name] = server.auth_credential_ref
    elif server.auth_type == "custom_header" and server.auth_header_name and server.auth_credential_ref:
        headers[server.auth_header_name] = server.auth_credential_ref

    client = MCPClient(server.url, timeout=10.0, headers=headers)
    try:
        init_result = await client.connect()
        server.status = "connected"
        server.status_message = f"Connected to {init_result.serverInfo.name} v{init_result.serverInfo.version}"
    except MCPClientError as e:
        server.status = "error"
        server.status_message = str(e)
    finally:
        await client.disconnect()

    await db.flush()
    await db.refresh(server)
    return server
