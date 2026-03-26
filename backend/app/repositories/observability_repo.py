"""ExecutionLog repository for observability."""

from app.repositories.base import CosmosRepository


class ExecutionLogRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("execution_logs")

    async def list_by_agent(self, tenant_id: str, agent_id: str, limit: int = 50) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT TOP @limit * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid ORDER BY c.created_at DESC",
            [
                {"name": "@tid", "value": tenant_id},
                {"name": "@aid", "value": agent_id},
                {"name": "@limit", "value": limit},
            ],
        )

    async def list_by_thread(self, tenant_id: str, thread_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.thread_id = @thid ORDER BY c.created_at DESC",
            [{"name": "@tid", "value": tenant_id}, {"name": "@thid", "value": thread_id}],
        )
