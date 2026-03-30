from fastapi import APIRouter, Depends, HTTPException, Request

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.mcp_repo import MCPServerRepository
from app.api.v1.schemas import (
    MCPServerCreateRequest,
    MCPServerUpdateRequest,
    MCPServerResponse,
    MCPServerListResponse,
)

router = APIRouter()

server_repo = MCPServerRepository()


@router.post("", response_model=MCPServerResponse, status_code=201)
async def create_mcp_server(
    body: MCPServerCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    server_data = {
        "name": body.name,
        "url": body.url,
        "description": body.description,
        "auth_type": body.auth_type,
        "auth_header_name": body.auth_header_name,
        "auth_credential_ref": body.auth_credential_ref,
        "is_active": True,
    }
    server = await server_repo.create(tenant_id, server_data)
    return server


@router.get("", response_model=MCPServerListResponse)
async def list_mcp_servers(
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    servers = await server_repo.list_by_tenant(tenant_id)
    return MCPServerListResponse(servers=servers, total=len(servers))


@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_mcp_server(
    server_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    server = await server_repo.get(tenant_id, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return server


@router.patch("/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: str,
    body: MCPServerUpdateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    server = await server_repo.get(tenant_id, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")

    update_data = body.model_dump(exclude_unset=True)
    server.update(update_data)
    updated = await server_repo.update(tenant_id, server_id, server)
    return updated


@router.delete("/{server_id}", status_code=204)
async def delete_mcp_server(
    server_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    server = await server_repo.get(tenant_id, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    await server_repo.delete(tenant_id, server_id)


@router.post("/{server_id}/check-status", response_model=MCPServerResponse)
async def check_mcp_server_status(
    server_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Attempt to connect to the MCP server and update its status."""
    from app.services.mcp_client import MCPClient, MCPClientError

    server = await server_repo.get(tenant_id, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")

    headers = {}
    if server.get("auth_type") == "bearer" and server.get("auth_credential_ref"):
        headers["Authorization"] = f"Bearer {server['auth_credential_ref']}"
    elif server.get("auth_type") == "api_key" and server.get("auth_credential_ref"):
        header_name = server.get("auth_header_name") or "X-API-Key"
        headers[header_name] = server["auth_credential_ref"]
    elif server.get("auth_type") == "custom_header" and server.get("auth_header_name") and server.get("auth_credential_ref"):
        headers[server["auth_header_name"]] = server["auth_credential_ref"]

    client = MCPClient(server["url"], timeout=10.0, headers=headers)
    try:
        init_result = await client.connect()
        server["status"] = "connected"
        server["status_message"] = f"Connected to {init_result.serverInfo.name} v{init_result.serverInfo.version}"
    except MCPClientError as e:
        server["status"] = "error"
        server["status_message"] = str(e)
    finally:
        await client.disconnect()

    # Ensure is_active is set for discovery queries
    if "is_active" not in server:
        server["is_active"] = True

    updated = await server_repo.update(tenant_id, server_id, server)
    return updated
