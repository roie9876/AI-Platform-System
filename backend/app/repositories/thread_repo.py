"""Thread, ThreadMessage, and AgentMemory repositories for Cosmos DB."""

from app.repositories.base import CosmosRepository


class ThreadRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("threads")

    async def list_by_agent(self, tenant_id: str, agent_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid ORDER BY c.created_at DESC",
            [{"name": "@tid", "value": tenant_id}, {"name": "@aid", "value": agent_id}],
        )

    async def list_by_user(self, tenant_id: str, user_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.user_id = @uid ORDER BY c.created_at DESC",
            [{"name": "@tid", "value": tenant_id}, {"name": "@uid", "value": user_id}],
        )


class ThreadMessageRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("thread_messages")

    async def list_by_thread(self, tenant_id: str, thread_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.thread_id = @thid ORDER BY c.created_at ASC",
            [{"name": "@tid", "value": tenant_id}, {"name": "@thid", "value": thread_id}],
        )

    async def count_by_thread(self, tenant_id: str, thread_id: str) -> int:
        return await self.count(
            tenant_id,
            "c.thread_id = @thid",
            [{"name": "@thid", "value": thread_id}],
        )


class AgentMemoryRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("agent_memories")

    async def list_by_agent(self, tenant_id: str, agent_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid ORDER BY c.created_at DESC",
            [{"name": "@tid", "value": tenant_id}, {"name": "@aid", "value": agent_id}],
        )
