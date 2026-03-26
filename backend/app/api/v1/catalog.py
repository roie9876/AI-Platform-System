from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.models.catalog_entry import CatalogEntry
from app.api.v1.schemas import CatalogEntryCreate, CatalogEntryResponse

router = APIRouter()


@router.get("/entries", response_model=list[CatalogEntryResponse])
async def list_catalog_entries(
    request: Request,
    category: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    connector_type: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List catalog entries — builtin (system) + tenant custom entries."""
    query = select(CatalogEntry).where(
        or_(CatalogEntry.tenant_id.is_(None), CatalogEntry.tenant_id == tenant_id)
    )
    if category:
        query = query.where(CatalogEntry.category == category)
    if provider:
        query = query.where(CatalogEntry.provider == provider)
    if connector_type:
        query = query.where(CatalogEntry.connector_type == connector_type)

    query = query.order_by(CatalogEntry.name)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("/entries", response_model=CatalogEntryResponse, status_code=201)
async def create_catalog_entry(
    body: CatalogEntryCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Create a custom catalog entry (tenant-scoped)."""
    entry = CatalogEntry(
        name=body.name,
        description=body.description,
        connector_type=body.connector_type,
        category=body.category,
        provider=body.provider,
        icon_name=body.icon_name,
        badges=body.badges,
        config_schema=body.config_schema,
        auth_types=body.auth_types,
        is_builtin=False,
        tenant_id=tenant_id,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


@router.get("/entries/{entry_id}", response_model=CatalogEntryResponse)
async def get_catalog_entry(
    entry_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Get a single catalog entry."""
    result = await db.execute(
        select(CatalogEntry).where(
            CatalogEntry.id == entry_id,
            or_(CatalogEntry.tenant_id.is_(None), CatalogEntry.tenant_id == tenant_id),
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Catalog entry not found")
    return entry
