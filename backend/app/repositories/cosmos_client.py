"""Cosmos DB client singleton with DefaultAzureCredential."""

from azure.cosmos.aio import CosmosClient, ContainerProxy, DatabaseProxy
from azure.identity.aio import DefaultAzureCredential

from app.core.config import settings

_client: CosmosClient | None = None
_credential: DefaultAzureCredential | None = None


async def get_cosmos_client() -> CosmosClient:
    """Return a singleton CosmosClient using DefaultAzureCredential."""
    global _client, _credential
    if _client is None:
        _credential = DefaultAzureCredential()
        _client = CosmosClient(url=settings.COSMOS_ENDPOINT, credential=_credential)
    return _client


async def get_cosmos_container(container_name: str) -> ContainerProxy:
    """Get a container proxy for the specified container."""
    client = await get_cosmos_client()
    database: DatabaseProxy = client.get_database_client(settings.COSMOS_DATABASE)
    return database.get_container_client(container_name)


async def close_cosmos_client() -> None:
    """Close the CosmosClient and credential on shutdown."""
    global _client, _credential
    if _client is not None:
        await _client.close()
        _client = None
    if _credential is not None:
        await _credential.close()
        _credential = None
