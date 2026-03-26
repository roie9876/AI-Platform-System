import sys
from pathlib import Path

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uuid
from unittest.mock import AsyncMock, patch

import pytest


class MockCosmosContainer:
    """In-memory mock of a Cosmos DB ContainerProxy for unit testing."""

    def __init__(self):
        self._store: dict[tuple[str, str], dict] = {}

    def _key(self, partition_key: str, item_id: str) -> tuple[str, str]:
        return (partition_key, item_id)

    def _generate_etag(self) -> str:
        return f'"{uuid.uuid4().hex[:8]}"'

    async def create_item(self, body: dict, **kwargs) -> dict:
        pk = body.get("tenant_id", "")
        item_id = body.get("id", str(uuid.uuid4()))
        body["id"] = item_id
        key = self._key(pk, item_id)
        if key in self._store:
            raise Exception(f"Item with id '{item_id}' already exists in partition '{pk}'")
        body["_etag"] = self._generate_etag()
        self._store[key] = dict(body)
        return dict(body)

    async def read_item(self, item: str, partition_key: str, **kwargs) -> dict:
        key = self._key(partition_key, item)
        if key not in self._store:
            from azure.cosmos.exceptions import CosmosResourceNotFoundError
            raise CosmosResourceNotFoundError(status_code=404, message="Not found")
        return dict(self._store[key])

    async def query_items(self, query: str, parameters: list = None, partition_key: str = None, **kwargs):
        for key, doc in self._store.items():
            if partition_key is not None and key[0] != partition_key:
                continue
            # Simple parameter filtering for @tid
            if parameters:
                tid_param = next((p["value"] for p in parameters if p["name"] == "@tid"), None)
                if tid_param and doc.get("tenant_id") != tid_param:
                    continue
            yield doc

    async def upsert_item(self, body: dict, **kwargs) -> dict:
        pk = body.get("tenant_id", "")
        item_id = body.get("id", str(uuid.uuid4()))
        body["id"] = item_id
        body["_etag"] = self._generate_etag()
        self._store[self._key(pk, item_id)] = dict(body)
        return dict(body)

    async def replace_item(self, item: str, body: dict, etag: str = None, match_condition=None, **kwargs) -> dict:
        pk = body.get("tenant_id", "")
        key = self._key(pk, item)
        if key not in self._store:
            from azure.cosmos.exceptions import CosmosResourceNotFoundError
            raise CosmosResourceNotFoundError(status_code=404, message="Not found")
        if etag is not None and match_condition is not None:
            stored_etag = self._store[key].get("_etag")
            if stored_etag != etag:
                from azure.cosmos.exceptions import CosmosAccessConditionFailedError
                raise CosmosAccessConditionFailedError(status_code=412, message="Precondition failed")
        body["_etag"] = self._generate_etag()
        self._store[key] = dict(body)
        return dict(body)

    async def delete_item(self, item: str, partition_key: str, **kwargs) -> None:
        key = self._key(partition_key, item)
        if key not in self._store:
            from azure.cosmos.exceptions import CosmosResourceNotFoundError
            raise CosmosResourceNotFoundError(status_code=404, message="Not found")
        del self._store[key]

    def clear(self):
        self._store.clear()


class MockCosmosClient:
    """Mock CosmosClient that returns MockCosmosContainer for any db/container."""

    def __init__(self, container: MockCosmosContainer):
        self._container = container

    def get_database_client(self, database: str):
        return MockDatabaseProxy(self._container)

    async def close(self):
        pass


class MockDatabaseProxy:
    """Mock DatabaseProxy that returns the shared container."""

    def __init__(self, container: MockCosmosContainer):
        self._container = container

    def get_container_client(self, container_name: str) -> MockCosmosContainer:
        return self._container


@pytest.fixture
def mock_container():
    """Return a MockCosmosContainer directly for low-level assertions."""
    return MockCosmosContainer()


@pytest.fixture
def mock_cosmos_client(mock_container):
    """Patch get_cosmos_container to return MockCosmosContainer. Clears store between tests."""
    client = MockCosmosClient(mock_container)

    async def _get_container(name: str):
        return mock_container

    with patch("app.repositories.cosmos_client.get_cosmos_container", side_effect=_get_container):
        yield mock_container
    mock_container.clear()
