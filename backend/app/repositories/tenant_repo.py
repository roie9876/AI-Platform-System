"""Tenant repository for Cosmos DB."""

from app.repositories.base import CosmosRepository


class TenantRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("tenants")

    async def get_by_slug(self, slug: str) -> dict | None:
        """Cross-partition query to find tenant by slug."""
        container = await self._container()
        items = []
        async for item in container.query_items(
            query="SELECT * FROM c WHERE c.slug = @slug",
            parameters=[{"name": "@slug", "value": slug}],
            enable_cross_partition_query=True,
        ):
            items.append(item)
        return items[0] if items else None

    async def list_all_tenants(self) -> list[dict]:
        """Cross-partition query to list all tenants."""
        container = await self._container()
        items = []
        async for item in container.query_items(
            query="SELECT * FROM c",
            enable_cross_partition_query=True,
        ):
            items.append(item)
        return items

    async def get_by_status(self, status: str) -> list[dict]:
        """Cross-partition query to find tenants by status."""
        container = await self._container()
        items = []
        async for item in container.query_items(
            query="SELECT * FROM c WHERE c.status = @status",
            parameters=[{"name": "@status", "value": status}],
            enable_cross_partition_query=True,
        ):
            items.append(item)
        return items
