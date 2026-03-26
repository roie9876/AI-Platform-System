"""Tenant service with lifecycle state machine and settings management."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.repositories.tenant_repo import TenantRepository

logger = logging.getLogger(__name__)

TENANT_STATES = ["provisioning", "active", "suspended", "deactivated", "deleted"]

VALID_TRANSITIONS = {
    "provisioning": ["active", "deleted"],
    "active": ["suspended", "deactivated"],
    "suspended": ["active", "deactivated"],
    "deactivated": ["deleted"],
    "deleted": [],
}

DEFAULT_SETTINGS = {
    "display_name": "",
    "allowed_providers": [],
    "token_quota": 100000,
    "feature_flags": {},
}

ALLOWED_SETTING_KEYS = {"display_name", "allowed_providers", "token_quota", "feature_flags"}


class TenantService:
    def __init__(self) -> None:
        self.repo = TenantRepository()

    async def create_tenant(
        self, name: str, slug: str, admin_email: str, settings: dict | None = None
    ) -> dict:
        existing = await self.repo.get_by_slug(slug)
        if existing:
            raise ValueError(f"Tenant with slug '{slug}' already exists")

        tenant_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        tenant_settings = {**DEFAULT_SETTINGS, "display_name": name}
        if settings:
            for key in ALLOWED_SETTING_KEYS:
                if key in settings:
                    tenant_settings[key] = settings[key]

        tenant = {
            "id": tenant_id,
            "tenant_id": tenant_id,
            "name": name,
            "slug": slug,
            "admin_email": admin_email,
            "status": "provisioning",
            "settings": tenant_settings,
            "created_at": now,
            "updated_at": now,
        }

        created = await self.repo.create(tenant_id, tenant)
        logger.info("Tenant created: %s (slug=%s)", tenant_id, slug)

        # Trigger provisioning asynchronously
        try:
            from app.services.tenant_provisioning import TenantProvisioningService

            provisioning = TenantProvisioningService()
            await provisioning.provision_tenant(created)
        except Exception:
            logger.error(
                "Provisioning failed for tenant %s — left in 'provisioning' state",
                tenant_id,
                exc_info=True,
            )

        return created

    async def get_tenant(self, tenant_id: str) -> dict | None:
        return await self.repo.get(tenant_id, tenant_id)

    async def list_tenants(self, status: str | None = None) -> list[dict]:
        if status:
            return await self.repo.get_by_status(status)
        return await self.repo.list_all_tenants()

    async def update_tenant(self, tenant_id: str, updates: dict) -> dict:
        tenant = await self.repo.get(tenant_id, tenant_id)
        if not tenant:
            raise ValueError(f"Tenant '{tenant_id}' not found")

        allowed_fields = {"name", "admin_email"}
        for key, value in updates.items():
            if key in allowed_fields:
                tenant[key] = value

        return await self.repo.upsert(tenant_id, tenant)

    async def transition_state(self, tenant_id: str, new_state: str) -> dict:
        tenant = await self.repo.get(tenant_id, tenant_id)
        if not tenant:
            raise ValueError(f"Tenant '{tenant_id}' not found")

        current_state = tenant.get("status", "provisioning")
        valid_next = VALID_TRANSITIONS.get(current_state, [])

        if new_state not in valid_next:
            raise ValueError(
                f"Invalid transition: '{current_state}' → '{new_state}'. "
                f"Valid transitions from '{current_state}': {valid_next}"
            )

        tenant["status"] = new_state
        updated = await self.repo.upsert(tenant_id, tenant)
        logger.info("Tenant %s transitioned: %s → %s", tenant_id, current_state, new_state)
        return updated

    async def update_settings(self, tenant_id: str, settings: dict) -> dict:
        tenant = await self.repo.get(tenant_id, tenant_id)
        if not tenant:
            raise ValueError(f"Tenant '{tenant_id}' not found")

        current_settings = tenant.get("settings", {**DEFAULT_SETTINGS})
        for key, value in settings.items():
            if key in ALLOWED_SETTING_KEYS:
                current_settings[key] = value

        tenant["settings"] = current_settings
        return await self.repo.upsert(tenant_id, tenant)

    async def delete_tenant(self, tenant_id: str) -> dict:
        tenant = await self.repo.get(tenant_id, tenant_id)
        if not tenant:
            raise ValueError(f"Tenant '{tenant_id}' not found")

        current_state = tenant.get("status", "provisioning")
        if current_state != "deactivated":
            raise ValueError(
                f"Cannot delete tenant in '{current_state}' state. "
                "Tenant must be deactivated before deletion."
            )

        return await self.transition_state(tenant_id, "deleted")
