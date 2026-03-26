"""Agent and AgentConfigVersion repositories for Cosmos DB."""

from __future__ import annotations

from app.repositories.base import CosmosRepository


class AgentRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("agents")

    async def list_by_tenant(self, tenant_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid ORDER BY c.created_at DESC",
            [{"name": "@tid", "value": tenant_id}],
        )


class AgentConfigVersionRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("agent_config_versions")

    async def list_by_agent(self, tenant_id: str, agent_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid ORDER BY c.version DESC",
            [{"name": "@tid", "value": tenant_id}, {"name": "@aid", "value": agent_id}],
        )

    async def get_latest(self, tenant_id: str, agent_id: str) -> dict | None:
        results = await self.query(
            tenant_id,
            "SELECT TOP 1 * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid ORDER BY c.version DESC",
            [{"name": "@tid", "value": tenant_id}, {"name": "@aid", "value": agent_id}],
        )
        return results[0] if results else None
