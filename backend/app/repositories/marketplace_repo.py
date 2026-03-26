"""AgentTemplate and ToolTemplate repositories for marketplace."""

from app.repositories.base import CosmosRepository


class AgentTemplateRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("agent_templates")

    async def list_published(self, tenant_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.is_published = true",
            [{"name": "@tid", "value": tenant_id}],
        )


class ToolTemplateRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("tool_templates")

    async def list_published(self, tenant_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.is_published = true",
            [{"name": "@tid", "value": tenant_id}],
        )
