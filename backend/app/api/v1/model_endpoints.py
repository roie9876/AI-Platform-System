import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.config_repo import ModelEndpointRepository
from app.api.v1.schemas import (
    ModelEndpointCreateRequest,
    ModelEndpointUpdateRequest,
    ModelEndpointResponse,
    ModelEndpointListResponse,
    VALID_PROVIDER_TYPES,
    VALID_AUTH_TYPES,
)
from app.services.keyvault_client import set_tenant_secret, TENANT_KV_NAME

logger = logging.getLogger(__name__)

router = APIRouter()

endpoint_repo = ModelEndpointRepository()


def _kv_secret_name(tenant_id: str, endpoint_id: str) -> str:
    """Deterministic KV secret name for an endpoint API key."""
    return f"ep-{endpoint_id}-apikey"


@router.post("", response_model=ModelEndpointResponse, status_code=201)
async def create_model_endpoint(
    body: ModelEndpointCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    if body.provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider_type. Must be one of: {', '.join(sorted(VALID_PROVIDER_TYPES))}",
        )
    if body.auth_type not in VALID_AUTH_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid auth_type. Must be one of: {', '.join(sorted(VALID_AUTH_TYPES))}",
        )

    if body.auth_type == "api_key" and not body.api_key:
        raise HTTPException(status_code=400, detail="API key is required for api_key auth type")

    endpoint_data = {
        "name": body.name,
        "provider_type": body.provider_type,
        "endpoint_url": body.endpoint_url,
        "model_name": body.model_name,
        "auth_type": body.auth_type,
        "priority": body.priority,
        "is_active": True,
        "has_api_key": body.auth_type == "api_key" and bool(body.api_key),
    }
    endpoint = await endpoint_repo.create(tenant_id, endpoint_data)

    # Store API key in tenant Key Vault (never in Cosmos)
    if body.api_key and TENANT_KV_NAME:
        secret_key = _kv_secret_name(tenant_id, endpoint["id"])
        if not set_tenant_secret(tenant_id, secret_key, body.api_key):
            logger.error("Failed to store API key in tenant KV for endpoint %s", endpoint["id"])

    return endpoint


@router.get("", response_model=ModelEndpointListResponse)
async def list_model_endpoints(
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    endpoints = await endpoint_repo.list_by_tenant(tenant_id)
    return ModelEndpointListResponse(endpoints=endpoints, total=len(endpoints))


@router.get("/{endpoint_id}", response_model=ModelEndpointResponse)
async def get_model_endpoint(
    endpoint_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    endpoint = await endpoint_repo.get(tenant_id, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Model endpoint not found")
    return endpoint


@router.put("/{endpoint_id}", response_model=ModelEndpointResponse)
async def update_model_endpoint(
    endpoint_id: str,
    body: ModelEndpointUpdateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    endpoint = await endpoint_repo.get(tenant_id, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Model endpoint not found")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "provider_type" in update_data and update_data["provider_type"] not in VALID_PROVIDER_TYPES:
        raise HTTPException(status_code=400, detail="Invalid provider_type")
    if "auth_type" in update_data and update_data["auth_type"] not in VALID_AUTH_TYPES:
        raise HTTPException(status_code=400, detail="Invalid auth_type")

    if "api_key" in update_data:
        raw_key = update_data.pop("api_key")
        if raw_key:
            endpoint["api_key_encrypted"] = _encrypt_api_key(raw_key)

    for field, value in update_data.items():
        endpoint[field] = value

    etag = endpoint.get("_etag")
    endpoint = await endpoint_repo.update(tenant_id, endpoint_id, endpoint, etag=etag)
    return endpoint


@router.delete("/{endpoint_id}", status_code=204)
async def delete_model_endpoint(
    endpoint_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    endpoint = await endpoint_repo.get(tenant_id, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Model endpoint not found")
    await endpoint_repo.delete(tenant_id, endpoint_id)
