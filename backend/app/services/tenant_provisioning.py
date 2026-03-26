"""Tenant provisioning service — K8s namespace, seed data, admin user creation."""

import asyncio
import logging
from pathlib import Path

from app.repositories.config_repo import CatalogEntryRepository
from app.repositories.tool_repo import ToolRepository
from app.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)

SETUP_SCRIPT = Path(__file__).parent.parent.parent / "k8s" / "scripts" / "setup-tenant.sh"

DEFAULT_TOOLS = [
    {
        "name": "web_search",
        "type": "built-in",
        "description": "Search the web",
        "config": {},
        "is_platform_tool": True,
    },
    {
        "name": "code_interpreter",
        "type": "built-in",
        "description": "Execute Python code",
        "config": {},
        "is_platform_tool": True,
    },
]

DEFAULT_CATALOG = [
    {
        "name": "Getting Started",
        "type": "template",
        "description": "Default agent template",
        "config": {"system_prompt": "You are a helpful assistant."},
    },
]


class TenantProvisioningService:
    def __init__(self) -> None:
        self.tool_repo = ToolRepository()
        self.catalog_repo = CatalogEntryRepository()
        self.user_repo = UserRepository()

    async def provision_tenant(self, tenant: dict) -> None:
        tenant_id = tenant["id"]
        slug = tenant["slug"]
        admin_email = tenant["admin_email"]

        logger.info("Starting provisioning for tenant %s (slug=%s)", tenant_id, slug)

        await self._provision_k8s_namespace(slug)
        await self._seed_default_data(tenant_id)
        await self._create_admin_user(tenant_id, admin_email)

        # Transition to active
        from app.services.tenant_service import TenantService

        service = TenantService()
        await service.transition_state(tenant_id, "active")

        logger.info("Provisioning complete for tenant %s", tenant_id)

    async def _provision_k8s_namespace(self, slug: str) -> None:
        if not SETUP_SCRIPT.exists():
            logger.warning(
                "setup-tenant.sh not found at %s — skipping K8s provisioning",
                SETUP_SCRIPT,
            )
            return

        logger.info("Provisioning K8s namespace for tenant slug: %s", slug)
        proc = await asyncio.create_subprocess_exec(
            str(SETUP_SCRIPT),
            slug,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error("K8s provisioning failed: %s", error_msg)
            raise RuntimeError(f"K8s namespace provisioning failed: {error_msg}")

        if stdout:
            logger.info("K8s provisioning output: %s", stdout.decode().strip())

    async def _seed_default_data(self, tenant_id: str) -> None:
        logger.info("Seeding default data for tenant %s", tenant_id)

        for tool in DEFAULT_TOOLS:
            await self.tool_repo.create(tenant_id, {**tool})

        for entry in DEFAULT_CATALOG:
            await self.catalog_repo.create(tenant_id, {**entry})

        logger.info("Seeded %d tools and %d catalog entries", len(DEFAULT_TOOLS), len(DEFAULT_CATALOG))

    async def _create_admin_user(self, tenant_id: str, admin_email: str) -> None:
        existing = await self.user_repo.get_by_email(tenant_id, admin_email)
        if existing:
            logger.info("Admin user %s already exists for tenant %s", admin_email, tenant_id)
            return

        admin_user = {
            "email": admin_email,
            "full_name": "Tenant Admin",
            "role": "admin",
            "is_active": True,
        }
        await self.user_repo.create(tenant_id, admin_user)
        logger.info("Created admin user %s for tenant %s", admin_email, tenant_id)
