"""Execution results repository — stores async agent execution results in Cosmos DB."""

from app.repositories.base import CosmosRepository


class ExecutionResultRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("execution_results")

    async def get_by_correlation_id(self, tenant_id: str, correlation_id: str) -> dict | None:
        results = await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.correlation_id = @cid",
            [
                {"name": "@tid", "value": tenant_id},
                {"name": "@cid", "value": correlation_id},
            ],
        )
        return results[0] if results else None
