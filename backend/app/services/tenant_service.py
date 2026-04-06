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
        self, name: str, slug: str, admin_email: str | None = None,
        settings: dict | None = None, entra_group_id: str | None = None,
    ) -> dict:
        existing = await self.repo.get_by_slug(slug)
        if existing and existing.get("status") != "deleted":
            raise ValueError(f"Tenant with slug '{slug}' already exists")

        tenant_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        tenant_settings = {**DEFAULT_SETTINGS, "display_name": name}
        if settings:
            for key in ALLOWED_SETTING_KEYS:
                if key in settings:
                    tenant_settings[key] = settings[key]

        resolved_email = admin_email or f"{slug}-admin@platform.local"

        tenant = {
            "id": tenant_id,
            "tenant_id": tenant_id,
            "name": name,
            "slug": slug,
            "admin_email": resolved_email,
            "entra_group_id": entra_group_id or "",
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
        tenants = await self.repo.list_all_tenants()
        return [t for t in tenants if t.get("status") != "deleted"]

    async def update_tenant(self, tenant_id: str, updates: dict) -> dict:
        tenant = await self.repo.get(tenant_id, tenant_id)
        if not tenant:
            raise ValueError(f"Tenant '{tenant_id}' not found")

        allowed_fields = {"name", "admin_email", "entra_group_id"}
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
        if current_state not in ("deactivated", "provisioning"):
            raise ValueError(
                f"Cannot delete tenant in '{current_state}' state. "
                "Tenant must be deactivated (or stuck in provisioning) before deletion."
            )

        result = await self.transition_state(tenant_id, "deleted")

        # Cascade delete: remove ALL tenant data from Cosmos DB
        await self._cascade_delete_cosmos_data(tenant_id)

        # Deprovision K8s resources + Entra group
        try:
            from app.services.tenant_provisioning import TenantProvisioningService

            provisioning = TenantProvisioningService()
            await provisioning.deprovision_tenant(tenant)
        except Exception:
            logger.error(
                "K8s deprovisioning failed for tenant %s — namespace may need manual cleanup",
                tenant_id,
                exc_info=True,
            )

        # Finally, remove the tenant record itself
        try:
            await self.repo.delete(tenant_id, tenant_id)
            logger.info("Deleted tenant record %s", tenant_id)
        except Exception:
            logger.warning("Failed to delete tenant record %s — left in 'deleted' state", tenant_id, exc_info=True)

        return result

    async def _cascade_delete_cosmos_data(self, tenant_id: str) -> None:
        """Delete all tenant data from every Cosmos DB container."""
        from app.repositories.agent_repo import AgentRepository, AgentConfigVersionRepository
        from app.repositories.data_source_repo import (
            AgentDataSourceRepository,
            DataSourceRepository,
            DocumentChunkRepository,
            DocumentRepository,
        )
        from app.repositories.evaluation_repo import (
            EvaluationResultRepository,
            EvaluationRunRepository,
            TestCaseRepository,
            TestSuiteRepository,
        )
        from app.repositories.execution_repo import ExecutionResultRepository
        from app.repositories.mcp_repo import (
            AgentMCPToolRepository,
            MCPDiscoveredToolRepository,
            MCPServerRepository,
        )
        from app.repositories.observability_repo import ExecutionLogRepository
        from app.repositories.thread_repo import (
            AgentMemoryRepository,
            ThreadMessageRepository,
            ThreadRepository,
        )
        from app.repositories.token_log_repository import TokenLogRepository
        from app.repositories.tool_repo import AgentToolRepository, ToolRepository
        from app.repositories.user_repo import UserRepository
        from app.repositories.workflow_repo import (
            WorkflowEdgeRepository,
            WorkflowExecutionRepository,
            WorkflowNodeExecutionRepository,
            WorkflowNodeRepository,
            WorkflowRepository,
        )

        # Also catalog_entries and config repos
        from app.repositories.config_repo import (
            CatalogEntryRepository,
            CostAlertRepository,
            ModelEndpointRepository,
            ModelPricingRepository,
        )

        repos: list[tuple[str, CosmosRepository]] = [
            ("agents", AgentRepository()),
            ("agent_config_versions", AgentConfigVersionRepository()),
            ("tools", ToolRepository()),
            ("agent_tools", AgentToolRepository()),
            ("mcp_servers", MCPServerRepository()),
            ("mcp_discovered_tools", MCPDiscoveredToolRepository()),
            ("agent_mcp_tools", AgentMCPToolRepository()),
            ("threads", ThreadRepository()),
            ("thread_messages", ThreadMessageRepository()),
            ("agent_memories", AgentMemoryRepository()),
            ("workflows", WorkflowRepository()),
            ("workflow_nodes", WorkflowNodeRepository()),
            ("workflow_edges", WorkflowEdgeRepository()),
            ("workflow_executions", WorkflowExecutionRepository()),
            ("workflow_node_executions", WorkflowNodeExecutionRepository()),
            ("data_sources", DataSourceRepository()),
            ("agent_data_sources", AgentDataSourceRepository()),
            ("documents", DocumentRepository()),
            ("document_chunks", DocumentChunkRepository()),
            ("test_suites", TestSuiteRepository()),
            ("test_cases", TestCaseRepository()),
            ("evaluation_runs", EvaluationRunRepository()),
            ("evaluation_results", EvaluationResultRepository()),
            ("token_logs", TokenLogRepository()),
            ("execution_logs", ExecutionLogRepository()),
            ("execution_results", ExecutionResultRepository()),
            ("users", UserRepository()),
            ("model_endpoints", ModelEndpointRepository()),
            ("model_pricing", ModelPricingRepository()),
            ("cost_alerts", CostAlertRepository()),
            ("catalog_entries", CatalogEntryRepository()),
        ]

        total_deleted = 0
        for name, repo in repos:
            try:
                items = await repo.list_all(tenant_id)
                for item in items:
                    await repo.delete(tenant_id, item["id"])
                if items:
                    total_deleted += len(items)
                    logger.info(
                        "Cascade-deleted %d items from '%s' for tenant %s",
                        len(items), name, tenant_id,
                    )
            except Exception:
                logger.warning(
                    "Failed to cascade-delete '%s' for tenant %s",
                    name, tenant_id, exc_info=True,
                )

        logger.info("Cascade delete complete: %d total items removed for tenant %s", total_deleted, tenant_id)
