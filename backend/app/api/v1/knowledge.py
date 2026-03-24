from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.azure_connection import AzureConnection
from app.models.azure_subscription import AzureSubscription
from app.services.azure_arm import AzureARMService
from app.services.secret_store import decrypt_api_key
from app.api.v1.schemas import (
    AzureConnectionResponse,
    SearchIndex,
    SearchIndexListResponse,
    SelectIndexesRequest,
    AgentKnowledgeIndexInfo,
    AgentKnowledgeResponse,
)

router = APIRouter()
arm_service = AzureARMService()


@router.get(
    "/connections/{connection_id}/indexes",
    response_model=SearchIndexListResponse,
)
async def list_search_indexes(
    connection_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List AI Search indexes for a connected search service."""
    result = await db.execute(
        select(AzureConnection).where(
            AzureConnection.id == connection_id,
            AzureConnection.tenant_id == tenant_id,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if connection.resource_type != "Microsoft.Search/searchServices":
        raise HTTPException(
            status_code=400,
            detail="Connection is not an Azure AI Search service",
        )

    # Get access token from the subscription
    sub_result = await db.execute(
        select(AzureSubscription).where(
            AzureSubscription.id == connection.azure_subscription_id
        )
    )
    subscription = sub_result.scalar_one_or_none()
    if not subscription or not subscription.access_token_encrypted:
        raise HTTPException(status_code=400, detail="Subscription token not available")

    access_token = decrypt_api_key(subscription.access_token_encrypted)
    indexes = await arm_service.list_search_indexes(access_token, connection.resource_id)

    return SearchIndexListResponse(
        connection_id=connection.id,
        resource_name=connection.resource_name,
        indexes=[SearchIndex(name=idx["name"]) for idx in indexes],
        count=len(indexes),
    )


@router.post(
    "/connections/{connection_id}/indexes",
    response_model=AzureConnectionResponse,
)
async def select_indexes(
    connection_id: UUID,
    body: SelectIndexesRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Select AI Search indexes for RAG retrieval."""
    result = await db.execute(
        select(AzureConnection).where(
            AzureConnection.id == connection_id,
            AzureConnection.tenant_id == tenant_id,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    config = connection.config or {}
    config["selected_indexes"] = body.index_names
    connection.config = config

    await db.flush()
    await db.refresh(connection)
    return connection


@router.get(
    "/agents/{agent_id}/indexes",
    response_model=AgentKnowledgeResponse,
)
async def list_agent_knowledge(
    agent_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List all selected AI Search indexes for an agent."""
    result = await db.execute(
        select(AzureConnection).where(
            AzureConnection.agent_id == agent_id,
            AzureConnection.tenant_id == tenant_id,
            AzureConnection.resource_type == "Microsoft.Search/searchServices",
        )
    )
    connections = list(result.scalars().all())

    knowledge_connections = []
    total = 0
    for conn in connections:
        selected = (conn.config or {}).get("selected_indexes", [])
        if selected:
            knowledge_connections.append(
                AgentKnowledgeIndexInfo(
                    connection_id=conn.id,
                    resource_name=conn.resource_name,
                    index_names=selected,
                )
            )
            total += len(selected)

    return AgentKnowledgeResponse(
        agent_id=agent_id,
        connections=knowledge_connections,
        total_indexes=total,
    )
