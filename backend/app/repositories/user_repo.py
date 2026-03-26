"""User repository for Cosmos DB."""

from __future__ import annotations

from app.repositories.base import CosmosRepository


class UserRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("users")

    async def get_by_email(self, tenant_id: str, email: str) -> dict | None:
        results = await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.email = @email",
            [{"name": "@tid", "value": tenant_id}, {"name": "@email", "value": email}],
        )
        return results[0] if results else None
