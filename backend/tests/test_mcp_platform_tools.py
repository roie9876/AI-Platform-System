"""Unit tests for MCP Platform Tools — memory tools and embedding cache."""

import sys
from pathlib import Path
from hashlib import sha256
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from microservices.mcp_platform_tools.embedding import EmbeddingService
from microservices.mcp_platform_tools.memory import (
    memory_get_structured,
    memory_search,
    memory_store,
    memory_store_structured,
    set_embedding_service,
)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

FAKE_EMBEDDING = [0.1] * 1536
TENANT = "test-tenant"
AGENT = "test-agent"


class FakeContainer:
    """Minimal async mock of Cosmos ContainerProxy."""

    def __init__(self):
        self.created: list[dict] = []
        self.upserted: list[dict] = []
        self._query_results: list[dict] = []

    async def create_item(self, body: dict, **kw) -> dict:
        self.created.append(body)
        return body

    async def upsert_item(self, body: dict, **kw) -> dict:
        self.upserted.append(body)
        return body

    async def query_items(self, query: str, parameters: list = None, partition_key: str = None, **kw):
        for item in self._query_results:
            yield item

    def set_results(self, results: list[dict]):
        self._query_results = results


class FakeEmbeddingService:
    """Records calls so we can verify caching behaviour."""

    def __init__(self):
        self.call_count = 0

    async def embed_text(self, text: str) -> list[float]:
        self.call_count += 1
        return list(FAKE_EMBEDDING)


@pytest.fixture(autouse=True)
def _setup_embedding():
    svc = FakeEmbeddingService()
    set_embedding_service(svc)
    yield svc
    set_embedding_service(None)


# ---------------------------------------------------------------------------
#  memory_store
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_memory_store():
    container = FakeContainer()
    with patch(
        "microservices.mcp_platform_tools.memory.get_cosmos_container",
        return_value=container,
    ):
        result = await memory_store(TENANT, AGENT, "Important fact", memory_type="knowledge")

    assert result["content"] == "Important fact"
    assert result["memory_type"] == "knowledge"
    assert "id" in result
    assert "created_at" in result

    doc = container.created[0]
    assert doc["tenant_id"] == TENANT
    assert doc["agent_id"] == AGENT
    assert isinstance(doc["embedding"], list)
    assert len(doc["embedding"]) == 1536


# ---------------------------------------------------------------------------
#  memory_search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_memory_search():
    container = FakeContainer()
    container.set_results([
        {"id": "m1", "content": "Hello", "memory_type": "knowledge", "agent_id": AGENT,
         "user_id": "", "created_at": "2024-01-01T00:00:00", "similarity_score": 0.95},
    ])
    with patch(
        "microservices.mcp_platform_tools.memory.get_cosmos_container",
        return_value=container,
    ):
        result = await memory_search(TENANT, AGENT, "greeting")

    assert result["count"] == 1
    assert result["results"][0]["content"] == "Hello"
    assert result["results"][0]["similarity_score"] == 0.95


# ---------------------------------------------------------------------------
#  memory_store_structured
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_memory_store_structured():
    container = FakeContainer()
    with patch(
        "microservices.mcp_platform_tools.memory.get_cosmos_container",
        return_value=container,
    ):
        result = await memory_store_structured(TENANT, AGENT, "lang", "Hebrew", category="preference")

    assert result["key"] == "lang"
    assert result["value"] == "Hebrew"
    assert result["category"] == "preference"

    doc = container.upserted[0]
    expected_id = sha256(f"{TENANT}:{AGENT}:lang".encode()).hexdigest()
    assert doc["id"] == expected_id
    assert doc["type"] == "structured"


# ---------------------------------------------------------------------------
#  memory_get_structured
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_memory_get_structured():
    container = FakeContainer()
    container.set_results([
        {"id": "x", "key": "lang", "value": "Hebrew", "category": "preference", "updated_at": "2024-01-01"},
    ])
    with patch(
        "microservices.mcp_platform_tools.memory.get_cosmos_container",
        return_value=container,
    ):
        result = await memory_get_structured(TENANT, AGENT, key="lang")

    assert result["count"] == 1
    assert result["memories"][0]["key"] == "lang"


# ---------------------------------------------------------------------------
#  Embedding cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_embedding_cache():
    """EmbeddingService should cache embeddings and avoid redundant API calls."""
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=FAKE_EMBEDDING)]

    svc = EmbeddingService()
    svc._client = AsyncMock()
    svc._client.embeddings.create = AsyncMock(return_value=mock_response)

    v1 = await svc.embed_text("hello world")
    v2 = await svc.embed_text("hello world")

    assert v1 == v2
    assert len(v1) == 1536
    # Only ONE API call — second was cached
    assert svc._client.embeddings.create.call_count == 1


# ---------------------------------------------------------------------------
#  Search with failed embedding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_memory_search_embedding_failure():
    """If embedding fails, memory_search should return an error dict."""

    class FailingEmbedding:
        async def embed_text(self, text: str) -> list[float]:
            return []

    set_embedding_service(FailingEmbedding())

    with patch(
        "microservices.mcp_platform_tools.memory.get_cosmos_container",
        return_value=FakeContainer(),
    ):
        result = await memory_search(TENANT, AGENT, "anything")

    assert "error" in result
    assert "embedding" in result["error"].lower()
