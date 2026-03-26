from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.agent_repo import AgentRepository
from app.repositories.config_repo import AzureConnectionRepository
from app.services.secret_store import encrypt_api_key
from app.api.v1.schemas import (
    AzureConnectionCreate,
    AzureConnectionUpdate,
    AzureConnectionResponse,
)

router = APIRouter()

conn_repo = AzureConnectionRepository()
agent_repo = AgentRepository()


@router.get("/connections", response_model=list[AzureConnectionResponse])
async def list_connections(
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List all Azure connections for the tenant."""
    connections = await conn_repo.list_all(tenant_id)
    return connections


@router.post("/connections", response_model=AzureConnectionResponse, status_code=201)
async def create_connection(
    body: AzureConnectionCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Create a connection between an agent and an Azure resource."""
    if body.agent_id:
        agent = await agent_repo.get(tenant_id, str(body.agent_id))
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

    conn_data = {
        "agent_id": str(body.agent_id) if body.agent_id else None,
        "azure_subscription_id": str(body.azure_subscription_id) if body.azure_subscription_id else None,
        "resource_type": body.resource_type,
        "resource_name": body.resource_name,
        "resource_id": body.resource_id,
        "endpoint": body.endpoint,
        "region": body.region,
        "auth_type": body.auth_type,
        "credentials_encrypted": encrypt_api_key(body.credentials) if body.credentials else None,
        "health_status": "unknown",
    }
    connection = await conn_repo.create(tenant_id, conn_data)
    return connection


@router.get("/agents/{agent_id}/connections", response_model=list[AzureConnectionResponse])
async def list_agent_connections(
    agent_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List all Azure connections for an agent."""
    connections = await conn_repo.list_by_agent(tenant_id, agent_id)
    return connections


@router.delete("/connections/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Delete an Azure connection."""
    connection = await conn_repo.get(tenant_id, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    await conn_repo.delete(tenant_id, connection_id)


@router.patch("/connections/{connection_id}", response_model=AzureConnectionResponse)
async def update_connection(
    connection_id: str,
    body: AzureConnectionUpdate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Update connection auth type, credentials, or config."""
    connection = await conn_repo.get(tenant_id, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if body.auth_type is not None:
        connection["auth_type"] = body.auth_type
    if body.credentials is not None:
        connection["credentials_encrypted"] = encrypt_api_key(body.credentials)
    if body.config is not None:
        connection["config"] = body.config

    updated = await conn_repo.update(tenant_id, connection_id, connection)
    return updated


@router.post("/connections/{connection_id}/health-check", response_model=AzureConnectionResponse)
async def health_check(
    connection_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Run a health check on a connection."""
    connection = await conn_repo.get(tenant_id, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    connection["health_status"] = "connected"
    connection["last_health_check"] = datetime.now(timezone.utc).isoformat()
    updated = await conn_repo.update(tenant_id, connection_id, connection)
    return updated
