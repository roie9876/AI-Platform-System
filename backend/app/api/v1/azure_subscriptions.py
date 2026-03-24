from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.azure_subscription import AzureSubscription
from app.services.azure_arm import AzureARMService
from app.services.secret_store import encrypt_api_key, decrypt_api_key
from app.api.v1.schemas import (
    AzureSubscriptionCreate,
    AzureSubscriptionResponse,
    ResourceDiscoveryResponse,
    DiscoveredResource,
)

router = APIRouter()
arm_service = AzureARMService()


@router.post("/subscriptions", response_model=AzureSubscriptionResponse, status_code=201)
async def connect_subscription(
    body: AzureSubscriptionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Connect an Azure subscription to the platform (upserts if already connected)."""
    # Check if subscription already exists for this tenant
    result = await db.execute(
        select(AzureSubscription).where(
            AzureSubscription.subscription_id == body.subscription_id,
            AzureSubscription.tenant_id == tenant_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update the token on the existing subscription
        existing.access_token_encrypted = encrypt_api_key(body.access_token)
        if body.refresh_token:
            existing.refresh_token_encrypted = encrypt_api_key(body.refresh_token)
        existing.display_name = body.display_name
        await db.flush()
        await db.refresh(existing)
        return existing

    subscription = AzureSubscription(
        subscription_id=body.subscription_id,
        display_name=body.display_name,
        tenant_azure_id=body.tenant_azure_id,
        tenant_id=tenant_id,
        access_token_encrypted=encrypt_api_key(body.access_token),
        refresh_token_encrypted=encrypt_api_key(body.refresh_token) if body.refresh_token else None,
    )
    db.add(subscription)
    await db.flush()
    await db.refresh(subscription)
    return subscription


@router.get("/subscriptions", response_model=list[AzureSubscriptionResponse])
async def list_subscriptions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List connected Azure subscriptions for the current tenant."""
    result = await db.execute(
        select(AzureSubscription)
        .where(AzureSubscription.tenant_id == tenant_id)
        .order_by(AzureSubscription.created_at.desc())
    )
    return list(result.scalars().all())


@router.delete("/subscriptions/{subscription_db_id}", status_code=204)
async def disconnect_subscription(
    subscription_db_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Disconnect an Azure subscription (cascades to connections)."""
    result = await db.execute(
        select(AzureSubscription).where(
            AzureSubscription.id == subscription_db_id,
            AzureSubscription.tenant_id == tenant_id,
        )
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await db.delete(subscription)
    await db.flush()


@router.get(
    "/subscriptions/{subscription_db_id}/resources",
    response_model=ResourceDiscoveryResponse,
)
async def discover_resources(
    subscription_db_id: UUID,
    resource_type: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Discover Azure resources of a given type within a connected subscription."""
    result = await db.execute(
        select(AzureSubscription).where(
            AzureSubscription.id == subscription_db_id,
            AzureSubscription.tenant_id == tenant_id,
        )
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    access_token = decrypt_api_key(subscription.access_token_encrypted)
    resources = await arm_service.list_resources_by_type(
        access_token, subscription.subscription_id, resource_type
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
        subscription_id=subscription.subscription_id,
        resource_type=resource_type,
        resources=discovered,
        count=len(discovered),
    )


@router.get("/subscriptions/discover")
async def discover_subscriptions(
    request: Request,
    x_azure_token: str = Header(..., alias="X-Azure-Token"),
    current_user: User = Depends(get_current_user),
):
    """Discover Azure subscriptions using an OAuth access token."""
    subscriptions = await arm_service.list_subscriptions(x_azure_token)
    return subscriptions
