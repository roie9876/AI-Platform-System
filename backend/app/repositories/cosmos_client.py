"""Cosmos DB client singleton with WorkloadIdentityCredential / DefaultAzureCredential."""

from __future__ import annotations

import logging
import os

from azure.cosmos.aio import CosmosClient, ContainerProxy, DatabaseProxy
from azure.identity.aio import DefaultAzureCredential, WorkloadIdentityCredential

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: CosmosClient | None = None
_credential: DefaultAzureCredential | WorkloadIdentityCredential | None = None
_unavailable = False


async def get_cosmos_client() -> CosmosClient | None:
    """Return a singleton CosmosClient using WorkloadIdentityCredential or DefaultAzureCredential.
    Returns None if COSMOS_ENDPOINT is not configured."""
    global _client, _credential, _unavailable
    if _unavailable:
        return None
    if _client is None:
        if not settings.COSMOS_ENDPOINT:
            logger.warning("COSMOS_ENDPOINT not configured — database operations will return empty results")
            _unavailable = True
            return None
        # Use WorkloadIdentityCredential explicitly when available,
        # because AZURE_CLIENT_ID env var is the SPA app ID (for JWT validation),
        # not the workload identity client ID needed for Cosmos DB auth.
        workload_client_id = settings.AZURE_WORKLOAD_CLIENT_ID
        token_file = os.environ.get("AZURE_FEDERATED_TOKEN_FILE")
        if workload_client_id and token_file:
            logger.info("Using WorkloadIdentityCredential with client_id=%s", workload_client_id)
            _credential = WorkloadIdentityCredential(
                client_id=workload_client_id,
                tenant_id=settings.AZURE_TENANT_ID,
                token_file_path=token_file,
            )
        else:
            logger.info("Using DefaultAzureCredential (no workload identity config found)")
            _credential = DefaultAzureCredential()
        _client = CosmosClient(url=settings.COSMOS_ENDPOINT, credential=_credential)
    return _client


async def get_cosmos_container(container_name: str) -> ContainerProxy | None:
    """Get a container proxy for the specified container. Returns None if Cosmos is unavailable."""
    client = await get_cosmos_client()
    if client is None:
        return None
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
