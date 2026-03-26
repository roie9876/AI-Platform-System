from fastapi import APIRouter, Depends, HTTPException, Header, Request

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.config_repo import AzureSubscriptionRepository
from app.services.azure_arm import AzureARMService
from app.services.secret_store import encrypt_api_key, decrypt_api_key
from app.api.v1.schemas import (
    AzureSubscriptionCreate,
    AzureSubscriptionResponse,
    ResourceDiscoveryResponse,
    DiscoveredResource,
)

router = APIRouter()
sub_repo = AzureSubscriptionRepository()
arm_service = AzureARMService()


@router.post("/subscriptions", response_model=AzureSubscriptionResponse, status_code=201)
async def connect_subscription(
    body: AzureSubscriptionCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Connect an Azure subscription to the platform (upserts if already connected)."""
    existing_list = await sub_repo.query(
        tenant_id,
        "SELECT * FROM c WHERE c.tenant_id = @tid AND c.subscription_id = @sid",
        [
            {"name": "@tid", "value": tenant_id},
            {"name": "@sid", "value": body.subscription_id},
        ],
    )

    if existing_list:
        existing = existing_list[0]
        existing["access_token_encrypted"] = encrypt_api_key(body.access_token)
        if body.refresh_token:
            existing["refresh_token_encrypted"] = encrypt_api_key(body.refresh_token)
        existing["display_name"] = body.display_name
        updated = await sub_repo.update(tenant_id, existing["id"], existing)
        return updated

    sub_data = {
        "subscription_id": body.subscription_id,
        "display_name": body.display_name,
        "tenant_azure_id": body.tenant_azure_id,
        "access_token_encrypted": encrypt_api_key(body.access_token),
        "refresh_token_encrypted": encrypt_api_key(body.refresh_token) if body.refresh_token else None,
    }
    subscription = await sub_repo.create(tenant_id, sub_data)
    return subscription


@router.get("/subscriptions", response_model=list[AzureSubscriptionResponse])
async def list_subscriptions(
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List connected Azure subscriptions for the current tenant."""
    subscriptions = await sub_repo.list_all(tenant_id)
    return subscriptions


@router.delete("/subscriptions/{subscription_db_id}", status_code=204)
async def disconnect_subscription(
    subscription_db_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Disconnect an Azure subscription (cascades to connections)."""
    subscription = await sub_repo.get(tenant_id, subscription_db_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await sub_repo.delete(tenant_id, subscription_db_id)


@router.get(
    "/subscriptions/{subscription_db_id}/resources",
    response_model=ResourceDiscoveryResponse,
)
async def discover_resources(
    subscription_db_id: str,
    resource_type: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Discover Azure resources of a given type within a connected subscription."""
    subscription = await sub_repo.get(tenant_id, subscription_db_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    access_token = decrypt_api_key(subscription["access_token_encrypted"])
    resources = await arm_service.list_resources_by_type(
        access_token, subscription["subscription_id"], resource_type
    )

    discovered = [
        DiscoveredResource(
            resource_id=r["id"],
            name=r["name"],
            resource_type=r["type"],
            region=r["location"],
            resource_group=r.get("resourceGroup"),
        )
        for r in resources
    ]

    return ResourceDiscoveryResponse(
        subscription_id=subscription["subscription_id"],
        resource_type=resource_type,
        resources=discovered,
        count=len(discovered),
    )


@router.get("/subscriptions/discover")
async def discover_subscriptions(
    request: Request,
    x_azure_token: str = Header(..., alias="X-Azure-Token"),
    current_user: dict = Depends(get_current_user),
):
    """Discover Azure subscriptions using an OAuth access token."""
    subscriptions = await arm_service.list_subscriptions(x_azure_token)
    return subscriptions
