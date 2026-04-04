"""Memory MCP tools — store, search (vector), and structured memory."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from app.repositories.cosmos_client import get_cosmos_container

logger = logging.getLogger(__name__)

# Late-bound singleton — set by main.py lifespan
_embedding_service = None


def set_embedding_service(svc) -> None:
    global _embedding_service
    _embedding_service = svc


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
#  memory_store
# ---------------------------------------------------------------------------

async def memory_store(
    tenant_id: str,
    agent_id: str,
    content: str,
    memory_type: str = "knowledge",
    user_id: str = "",
    source: str = "",
) -> dict:
    """Store a memory with an embedding vector in the agent_memories container."""
    container = await get_cosmos_container("agent_memories")
    if container is None:
        return {"error": "Database not configured"}

    embedding = await _embedding_service.embed_text(content) if _embedding_service else []

    now = _now_iso()
    doc = {
        "id": str(uuid4()),
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "user_id": user_id,
        "content": content,
        "memory_type": memory_type,
        "type": "memory",
        "embedding": embedding,
        "source": source,
        "created_at": now,
        "updated_at": now,
    }
    await container.create_item(body=doc)
    return {"id": doc["id"], "content": content, "memory_type": memory_type, "created_at": now}


# ---------------------------------------------------------------------------
#  memory_search
# ---------------------------------------------------------------------------

async def memory_search(
    tenant_id: str,
    agent_id: str,
    query: str,
    top_k: int = 5,
    memory_type: str = "",
) -> dict:
    """Search memories by vector similarity using Cosmos DB VectorDistance."""
    if not query.strip():
        return {"error": "Query must not be empty"}

    container = await get_cosmos_container("agent_memories")
    if container is None:
        return {"error": "Database not configured"}

    embedding = await _embedding_service.embed_text(query) if _embedding_service else []
    if not embedding:
        return {"error": "Failed to generate embedding for query"}

    sql = (
        "SELECT TOP @top_k c.id, c.content, c.memory_type, c.agent_id, "
        "c.user_id, c.created_at, "
        "VectorDistance(c.embedding, @query_vector) AS similarity_score "
        "FROM c "
        "WHERE c.tenant_id = @tenant_id AND c.agent_id = @agent_id"
    )
    params: list[dict] = [
        {"name": "@top_k", "value": top_k},
        {"name": "@query_vector", "value": embedding},
        {"name": "@tenant_id", "value": tenant_id},
        {"name": "@agent_id", "value": agent_id},
    ]

    if memory_type:
        sql += " AND c.memory_type = @memory_type"
        params.append({"name": "@memory_type", "value": memory_type})

    sql += " ORDER BY VectorDistance(c.embedding, @query_vector)"

    results: list[dict] = []
    async for item in container.query_items(query=sql, parameters=params, partition_key=tenant_id):
        item.pop("embedding", None)
        results.append(item)
    return {"results": results, "count": len(results)}


# ---------------------------------------------------------------------------
#  memory_store_structured
# ---------------------------------------------------------------------------

async def memory_store_structured(
    tenant_id: str,
    agent_id: str,
    key: str,
    value: str,
    category: str = "preference",
) -> dict:
    """Upsert a key-value structured fact (no embedding needed)."""
    container = await get_cosmos_container("structured_memories")
    if container is None:
        return {"error": "Database not configured"}

    now = _now_iso()
    doc_id = sha256(f"{tenant_id}:{agent_id}:{key}".encode()).hexdigest()
    doc = {
        "id": doc_id,
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "key": key,
        "value": value,
        "category": category,
        "type": "structured",
        "created_at": now,
        "updated_at": now,
    }
    await container.upsert_item(body=doc)
    return {"key": key, "value": value, "category": category, "updated_at": now}


# ---------------------------------------------------------------------------
#  memory_get_structured
# ---------------------------------------------------------------------------

async def memory_get_structured(
    tenant_id: str,
    agent_id: str,
    key: str = "",
    category: str = "",
) -> dict:
    """Retrieve structured memories by key, category, or list all for an agent."""
    container = await get_cosmos_container("structured_memories")
    if container is None:
        return {"error": "Database not configured"}

    if key:
        sql = (
            "SELECT c.id, c.key, c.value, c.category, c.updated_at "
            "FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid AND c.key = @key"
        )
        params = [
            {"name": "@tid", "value": tenant_id},
            {"name": "@aid", "value": agent_id},
            {"name": "@key", "value": key},
        ]
    elif category:
        sql = (
            "SELECT c.id, c.key, c.value, c.category, c.updated_at "
            "FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid AND c.category = @cat"
        )
        params = [
            {"name": "@tid", "value": tenant_id},
            {"name": "@aid", "value": agent_id},
            {"name": "@cat", "value": category},
        ]
    else:
        sql = (
            "SELECT c.id, c.key, c.value, c.category, c.updated_at "
            "FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid AND c.type = 'structured'"
        )
        params = [
            {"name": "@tid", "value": tenant_id},
            {"name": "@aid", "value": agent_id},
        ]

    items: list[dict] = []
    async for item in container.query_items(query=sql, parameters=params, partition_key=tenant_id):
        items.append(item)
    return {"memories": items, "count": len(items)}
