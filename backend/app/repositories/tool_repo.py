"""Tool and AgentTool repositories for Cosmos DB."""

from __future__ import annotations

from app.repositories.base import CosmosRepository


class ToolRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("tools")

    async def list_by_tenant(self, tenant_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid",
            [{"name": "@tid", "value": tenant_id}],
        )


class AgentToolRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("agent_tools")

    async def list_by_agent(self, tenant_id: str, agent_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid",
            [{"name": "@tid", "value": tenant_id}, {"name": "@aid", "value": agent_id}],
        )

    async def get_by_agent_and_tool(self, tenant_id: str, agent_id: str, tool_id: str) -> dict | None:
        results = await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid AND c.tool_id = @tool_id",
            [
                {"name": "@tid", "value": tenant_id},
                {"name": "@aid", "value": agent_id},
                {"name": "@tool_id", "value": tool_id},
            ],
        )
        return results[0] if results else None
