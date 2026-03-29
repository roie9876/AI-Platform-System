from fastapi import APIRouter, Depends, HTTPException, Request

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.config_repo import AzureConnectionRepository, AzureSubscriptionRepository
from app.services.azure_arm import AzureARMService
from app.services.secret_store import decrypt_api_key, encrypt_api_key
from app.api.v1.schemas import (
    AzureConnectionResponse,
    SearchIndex,
    SearchIndexListResponse,
    SelectIndexesRequest,
    AgentKnowledgeIndexInfo,
    AgentKnowledgeResponse,
)

router = APIRouter()
conn_repo = AzureConnectionRepository()
sub_repo = AzureSubscriptionRepository()
arm_service = AzureARMService()


@router.get(
    "/connections/{connection_id}/indexes",
    response_model=SearchIndexListResponse,
)
async def list_search_indexes(
    connection_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List AI Search indexes for a connected search service."""
    connection = await conn_repo.get(tenant_id, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if connection.get("resource_type") != "Microsoft.Search/searchServices":
        raise HTTPException(
            status_code=400,
            detail="Connection is not an Azure AI Search service",
        )

    subscription = await sub_repo.get(tenant_id, connection.get("azure_subscription_id", ""))
    if not subscription or not subscription.get("access_token_encrypted"):
        raise HTTPException(status_code=400, detail="Subscription token not available")

    access_token = decrypt_api_key(subscription["access_token_encrypted"])
    indexes = await arm_service.list_search_indexes(access_token, connection["resource_id"])

    admin_key = await arm_service._get_search_admin_key(access_token, connection["resource_id"])
    if admin_key:
        config = connection.get("config") or {}
        config["cached_admin_key"] = encrypt_api_key(admin_key)
        connection["config"] = config
        await conn_repo.update(tenant_id, connection_id, connection)

    return SearchIndexListResponse(
        connection_id=connection["id"],
        resource_name=connection["resource_name"],
        indexes=[SearchIndex(name=idx["name"]) for idx in indexes],
        count=len(indexes),
    )


@router.post(
    "/connections/{connection_id}/indexes",
    response_model=AzureConnectionResponse,
)
async def select_indexes(
    connection_id: str,
    body: SelectIndexesRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Select AI Search indexes for RAG retrieval."""
    connection = await conn_repo.get(tenant_id, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    config = connection.get("config") or {}
    config["selected_indexes"] = body.index_names
    if body.knowledge_name:
        config["knowledge_name"] = body.knowledge_name
    connection["config"] = config

    updated = await conn_repo.update(tenant_id, connection_id, connection)
    return updated


@router.get(
    "/agents/{agent_id}/indexes",
    response_model=AgentKnowledgeResponse,
)
async def list_agent_knowledge(
    agent_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    "List all selected AI Search indexes explicitly attached to an agent."""
    all_connections = await conn_repo.query(
        tenant_id,
        "SELECT * FROM c WHERE c.tenant_id = @tid AND c.resource_type = 'Microsoft.Search/searchServices' AND (c.agent_id = @aid OR ARRAY_CONTAINS(c.agent_ids, @aid))",
        [{"name": "@tid", "value": tenant_id}, {"name": "@aid", "value": agent_id}],
    )

    knowledge_connections = []
    total = 0
    for conn in all_connections:
        selected = (conn.get("config") or {}).get("selected_indexes", [])
        if selected:
            knowledge_connections.append(
                AgentKnowledgeIndexInfo(
                    connection_id=conn["id"],
                    resource_name=conn["resource_name"],
                    knowledge_name=(conn.get("config") or {}).get("knowledge_name"),
                    index_names=selected,
                )
            )
            total += len(selected)

    return AgentKnowledgeResponse(
        agent_id=agent_id,
        connections=knowledge_connections,
        total_indexes=total,
    )


@router.post(
    "/agents/{agent_id}/attach/{connection_id}",
    response_model=AzureConnectionResponse,
)
async def attach_knowledge_to_agent(
    agent_id: str,
    connection_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Attach a knowledge connection to an agent."""
    connection = await conn_repo.get(tenant_id, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    agent_ids = connection.get("agent_ids") or []
    if agent_id not in agent_ids:
        agent_ids.append(agent_id)
    connection["agent_ids"] = agent_ids

    updated = await conn_repo.update(tenant_id, connection_id, connection)
    return updated


@router.delete(
    "/agents/{agent_id}/detach/{connection_id}",
    response_model=AzureConnectionResponse,
)
async def detach_knowledge_from_agent(
    agent_id: str,
    connection_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Detach a knowledge connection from an agent."""
    connection = await conn_repo.get(tenant_id, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    agent_ids = connection.get("agent_ids") or []
    if agent_id in agent_ids:
        agent_ids.remove(agent_id)
    connection["agent_ids"] = agent_ids

    # Also clear legacy agent_id if it matches
    if connection.get("agent_id") == agent_id:
        connection["agent_id"] = None

    updated = await conn_repo.update(tenant_id, connection_id, connection)
    return updated
