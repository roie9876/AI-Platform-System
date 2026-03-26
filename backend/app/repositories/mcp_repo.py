"""MCPServer, MCPDiscoveredTool, and AgentMCPTool repositories."""

from app.repositories.base import CosmosRepository


class MCPServerRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("mcp_servers")

    async def list_by_tenant(self, tenant_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid",
            [{"name": "@tid", "value": tenant_id}],
        )

    async def get_by_name(self, tenant_id: str, name: str) -> dict | None:
        results = await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.name = @name",
            [{"name": "@tid", "value": tenant_id}, {"name": "@name", "value": name}],
        )
        return results[0] if results else None


class MCPDiscoveredToolRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("mcp_discovered_tools")

    async def list_by_server(self, tenant_id: str, server_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.server_id = @sid",
            [{"name": "@tid", "value": tenant_id}, {"name": "@sid", "value": server_id}],
        )


class AgentMCPToolRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("agent_mcp_tools")

    async def list_by_agent(self, tenant_id: str, agent_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid",
            [{"name": "@tid", "value": tenant_id}, {"name": "@aid", "value": agent_id}],
        )
