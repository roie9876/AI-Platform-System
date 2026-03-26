from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.config_repo import CatalogEntryRepository
from app.api.v1.schemas import CatalogEntryCreate, CatalogEntryResponse

router = APIRouter()

catalog_repo = CatalogEntryRepository()


@router.get("/entries", response_model=list[CatalogEntryResponse])
async def list_catalog_entries(
    request: Request,
    category: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    connector_type: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List catalog entries — builtin (system) + tenant custom entries."""
    entries = await catalog_repo.list_by_tenant(tenant_id)
    if category:
        entries = [e for e in entries if e.get("category") == category]
    if provider:
        entries = [e for e in entries if e.get("provider") == provider]
    if connector_type:
        entries = [e for e in entries if e.get("connector_type") == connector_type]
    return entries


@router.post("/entries", response_model=CatalogEntryResponse, status_code=201)
async def create_catalog_entry(
    body: CatalogEntryCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Create a custom catalog entry (tenant-scoped)."""
    entry_data = {
        "name": body.name,
        "description": body.description,
        "connector_type": body.connector_type,
        "category": body.category,
        "provider": body.provider,
        "icon_name": body.icon_name,
        "badges": body.badges,
        "config_schema": body.config_schema,
        "auth_types": body.auth_types,
        "is_builtin": False,
    }
    entry = await catalog_repo.create(tenant_id, entry_data)
    return entry


@router.get("/entries/{entry_id}", response_model=CatalogEntryResponse)
async def get_catalog_entry(
    entry_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Get a single catalog entry."""
    entry = await catalog_repo.get(tenant_id, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Catalog entry not found")
    return entry
