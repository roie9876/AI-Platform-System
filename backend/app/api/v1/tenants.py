"""Tenant management API endpoints — platform admin only."""

from fastapi import APIRouter, HTTPException, Request

from app.api.v1.schemas import (
    TenantCreateRequest,
    TenantListResponse,
    TenantResponse,
    TenantSettingsUpdateRequest,
    TenantStateTransitionRequest,
    TenantUpdateRequest,
)
from app.services.tenant_service import TenantService

router = APIRouter()


def _require_platform_admin(request: Request) -> None:
    user_context = getattr(request.state, "user_context", None)
    if not user_context:
        raise HTTPException(status_code=403, detail="Authentication required")
    roles = user_context.get("roles", [])
    if "platform_admin" not in roles:
        raise HTTPException(status_code=403, detail="Platform admin role required")


@router.post("/", status_code=201, response_model=TenantResponse)
async def create_tenant(body: TenantCreateRequest, request: Request):
    _require_platform_admin(request)
    service = TenantService()
    try:
        tenant = await service.create_tenant(
            name=body.name, slug=body.slug, admin_email=body.admin_email
        )
        return tenant
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/", response_model=TenantListResponse)
async def list_tenants(request: Request, status: str | None = None):
    _require_platform_admin(request)
    service = TenantService()
    tenants = await service.list_tenants(status=status)
    return {"tenants": tenants}


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: str, request: Request):
    _require_platform_admin(request)
    service = TenantService()
    tenant = await service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(tenant_id: str, body: TenantUpdateRequest, request: Request):
    _require_platform_admin(request)
    service = TenantService()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        tenant = await service.update_tenant(tenant_id, updates)
        return tenant
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{tenant_id}/state", response_model=TenantResponse)
async def transition_tenant_state(
    tenant_id: str, body: TenantStateTransitionRequest, request: Request
):
    _require_platform_admin(request)
    service = TenantService()
    try:
        tenant = await service.transition_state(tenant_id, body.state)
        return tenant
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{tenant_id}/settings", response_model=TenantResponse)
async def update_tenant_settings(
    tenant_id: str, body: TenantSettingsUpdateRequest, request: Request
):
    _require_platform_admin(request)
    service = TenantService()
    settings = body.model_dump(exclude_none=True)
    if not settings:
        raise HTTPException(status_code=400, detail="No settings to update")
    try:
        tenant = await service.update_settings(tenant_id, settings)
        return tenant
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(tenant_id: str, request: Request):
    _require_platform_admin(request)
    service = TenantService()
    try:
        await service.delete_tenant(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
