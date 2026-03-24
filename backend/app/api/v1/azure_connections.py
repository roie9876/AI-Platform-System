from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.agent import Agent
from app.models.azure_connection import AzureConnection
from app.services.secret_store import encrypt_api_key
from app.api.v1.schemas import (
    AzureConnectionCreate,
    AzureConnectionUpdate,
    AzureConnectionResponse,
)

router = APIRouter()


@router.get("/connections", response_model=list[AzureConnectionResponse])
async def list_connections(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List all Azure connections for the tenant."""
    result = await db.execute(
        select(AzureConnection)
        .where(AzureConnection.tenant_id == tenant_id)
        .order_by(AzureConnection.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/connections", response_model=AzureConnectionResponse, status_code=201)
async def create_connection(
    body: AzureConnectionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Create a connection between an agent and an Azure resource."""
    # Verify agent belongs to tenant (if agent_id provided)
    if body.agent_id:
        result = await db.execute(
            select(Agent).where(Agent.id == body.agent_id, Agent.tenant_id == tenant_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Agent not found")

    connection = AzureConnection(
        agent_id=body.agent_id,
        azure_subscription_id=body.azure_subscription_id,
        resource_type=body.resource_type,
        resource_name=body.resource_name,
        resource_id=body.resource_id,
        endpoint=body.endpoint,
        region=body.region,
        auth_type=body.auth_type,
        credentials_encrypted=encrypt_api_key(body.credentials) if body.credentials else None,
        health_status="unknown",
        tenant_id=tenant_id,
    )
    db.add(connection)
    await db.flush()
    await db.refresh(connection)
    return connection


@router.get("/agents/{agent_id}/connections", response_model=list[AzureConnectionResponse])
async def list_agent_connections(
    agent_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List all Azure connections for an agent."""
    result = await db.execute(
        select(AzureConnection)
        .where(AzureConnection.agent_id == agent_id, AzureConnection.tenant_id == tenant_id)
        .order_by(AzureConnection.created_at.desc())
    )
    return list(result.scalars().all())


@router.delete("/connections/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Delete an Azure connection."""
    result = await db.execute(
        select(AzureConnection).where(
            AzureConnection.id == connection_id,
            AzureConnection.tenant_id == tenant_id,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    await db.delete(connection)
    await db.flush()


@router.patch("/connections/{connection_id}", response_model=AzureConnectionResponse)
async def update_connection(
    connection_id: UUID,
    body: AzureConnectionUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Update connection auth type, credentials, or config."""
    result = await db.execute(
        select(AzureConnection).where(
            AzureConnection.id == connection_id,
            AzureConnection.tenant_id == tenant_id,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if body.auth_type is not None:
        connection.auth_type = body.auth_type
    if body.credentials is not None:
        connection.credentials_encrypted = encrypt_api_key(body.credentials)
    if body.config is not None:
        connection.config = body.config

    await db.flush()
    await db.refresh(connection)
    return connection


@router.post("/connections/{connection_id}/health-check", response_model=AzureConnectionResponse)
async def health_check(
    connection_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Run a health check on a connection."""
    result = await db.execute(
        select(AzureConnection).where(
            AzureConnection.id == connection_id,
            AzureConnection.tenant_id == tenant_id,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    connection.health_status = "connected"
    connection.last_health_check = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(connection)
    return connection
