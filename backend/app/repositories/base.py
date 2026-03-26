"""Base Cosmos DB repository with CRUD operations and ETag optimistic concurrency."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from azure.core import MatchConditions
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.repositories.cosmos_client import get_cosmos_container


class CosmosRepository:
    """Base repository providing CRUD + ETag concurrency for a Cosmos DB container."""

    def __init__(self, container_name: str) -> None:
        self.container_name = container_name

    async def _container(self):
        return await get_cosmos_container(self.container_name)

    async def create(self, tenant_id: str, item: dict) -> dict:
        container = await self._container()
        if container is None:
            raise RuntimeError("Database not configured. Set COSMOS_ENDPOINT in .env")
        item["tenant_id"] = tenant_id
        item["id"] = item.get("id", str(uuid4()))
        now = datetime.now(timezone.utc).isoformat()
        item.setdefault("created_at", now)
        item["updated_at"] = now
        return await container.create_item(body=item)

    async def get(self, tenant_id: str, item_id: str) -> dict | None:
        container = await self._container()
        if container is None:
            return None
        try:
            return await container.read_item(item=item_id, partition_key=tenant_id)
        except CosmosResourceNotFoundError:
            return None

    async def query(self, tenant_id: str, query: str, parameters: list | None = None) -> list[dict]:
        container = await self._container()
        if container is None:
            return []
        items = []
        async for item in container.query_items(
            query=query,
            parameters=parameters or [],
            partition_key=tenant_id,
        ):
            items.append(item)
        return items

    async def list_all(self, tenant_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid",
            [{"name": "@tid", "value": tenant_id}],
        )

    async def update(self, tenant_id: str, item_id: str, item: dict, etag: str | None = None) -> dict:
        container = await self._container()
        if container is None:
            raise RuntimeError("Database not configured. Set COSMOS_ENDPOINT in .env")
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        if etag:
            return await container.replace_item(
                item=item_id,
                body=item,
                etag=etag,
                match_condition=MatchConditions.IfNotModified,
            )
        return await container.replace_item(item=item_id, body=item)

    async def delete(self, tenant_id: str, item_id: str) -> None:
        container = await self._container()
        if container is None:
            raise RuntimeError("Database not configured. Set COSMOS_ENDPOINT in .env")
        await container.delete_item(item=item_id, partition_key=tenant_id)

    async def upsert(self, tenant_id: str, item: dict) -> dict:
        container = await self._container()
        if container is None:
            raise RuntimeError("Database not configured. Set COSMOS_ENDPOINT in .env")
        item["tenant_id"] = tenant_id
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        item.setdefault("created_at", item["updated_at"])
        return await container.upsert_item(body=item)

    async def count(self, tenant_id: str, filter_clause: str = "", parameters: list | None = None) -> int:
        container = await self._container()
        if container is None:
            return 0
        query_text = "SELECT VALUE COUNT(1) FROM c WHERE c.tenant_id = @tid"
        if filter_clause:
            query_text += f" AND {filter_clause}"
        params = [{"name": "@tid", "value": tenant_id}]
        if parameters:
            params.extend(parameters)
        result = []
        async for item in container.query_items(query=query_text, parameters=params, partition_key=tenant_id):
            result.append(item)
        return result[0] if result else 0
