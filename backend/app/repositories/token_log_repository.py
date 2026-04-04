"""Cosmos DB repository for token usage logging."""

from __future__ import annotations

from app.repositories.base import CosmosRepository


class TokenLogRepository(CosmosRepository):
    """Repository for token usage logs in the token_logs Cosmos DB container."""

    def __init__(self) -> None:
        super().__init__("token_logs")

    async def log_usage(self, tenant_id: str, log: dict) -> dict:
        """Log a single token usage record."""
        return await self.create(tenant_id, log)

    async def get_usage_by_date_range(
        self, tenant_id: str, start: str, end: str
    ) -> list[dict]:
        """Get token usage logs within a date range for a tenant."""
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid "
            "AND c.timestamp >= @start AND c.timestamp <= @end "
            "ORDER BY c.timestamp DESC",
            [
                {"name": "@tid", "value": tenant_id},
                {"name": "@start", "value": start},
                {"name": "@end", "value": end},
            ],
        )

    async def get_tenant_total_tokens(
        self, tenant_id: str, start: str, end: str
    ) -> int:
        """Get total token count for a tenant within a date range."""
        result = await self.query(
            tenant_id,
            "SELECT VALUE SUM(c.total_tokens) FROM c WHERE c.tenant_id = @tid "
            "AND c.timestamp >= @start AND c.timestamp <= @end",
            [
                {"name": "@tid", "value": tenant_id},
                {"name": "@start", "value": start},
                {"name": "@end", "value": end},
            ],
        )
        return result[0] if result and result[0] else 0

    async def get_usage_summary_by_model(
        self, tenant_id: str, start: str, end: str
    ) -> list[dict]:
        """Get aggregated token usage grouped by model for a tenant."""
        return await self.query(
            tenant_id,
            "SELECT c.model, "
            "SUM(c.prompt_tokens) AS total_prompt, "
            "SUM(c.completion_tokens) AS total_completion, "
            "SUM(c.total_tokens) AS total_tokens, "
            "COUNT(1) AS request_count "
            "FROM c WHERE c.tenant_id = @tid "
            "AND c.timestamp >= @start AND c.timestamp <= @end "
            "GROUP BY c.model",
            [
                {"name": "@tid", "value": tenant_id},
                {"name": "@start", "value": start},
                {"name": "@end", "value": end},
            ],
        )
