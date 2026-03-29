import logging
from typing import List, Optional
from uuid import uuid4

from app.core.config import settings
from app.repositories.agent_repo import AgentRepository
from app.repositories.thread_repo import ThreadMessageRepository, AgentMemoryRepository
from app.services.model_abstraction import _build_client
from app.services.secret_store import decrypt_api_key

logger = logging.getLogger(__name__)

_memory_repo = AgentMemoryRepository()
_message_repo = ThreadMessageRepository()


class MemoryService:
    """Manages long-term agent memory with embeddings."""

    async def embed(self, text: str, model_endpoint: dict) -> List[float]:
        """Generate embedding vector using OpenAI SDK."""
        try:
            embedding_model = settings.EMBEDDING_MODEL
            client = _build_client(model_endpoint)

            response = await client.embeddings.create(
                model=embedding_model,
                input=[text],
            )
            return response.data[0].embedding
        except Exception:
            logger.warning("Failed to generate embedding, storing memory without vector", exc_info=True)
            return []

    async def store_memory(
        self,
        agent_id: str,
        user_id: str,
        tenant_id: str,
        content: str,
        model_endpoint: Optional[dict] = None,
        memory_type: str = "knowledge",
        source_thread_id: Optional[str] = None,
    ) -> dict:
        """Store a memory with optional embedding."""
        embedding = None
        if model_endpoint:
            vector = await self.embed(content, model_endpoint)
            if vector:
                embedding = vector

        memory = {
            "id": str(uuid4()),
            "agent_id": agent_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "content": content,
            "embedding": embedding,
            "memory_type": memory_type,
            "source_thread_id": source_thread_id,
        }
        return await _memory_repo.create(tenant_id, memory)

    async def retrieve_relevant(
        self,
        query: str,
        agent_id: str,
        user_id: str,
        tenant_id: str,
        model_endpoint: Optional[dict] = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Retrieve relevant memories using recency (vector search not available in Cosmos)."""
        memories = await _memory_repo.query(
            tenant_id,
            "SELECT TOP @top_k * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid AND c.user_id = @uid ORDER BY c._ts DESC",
            [
                {"name": "@tid", "value": tenant_id},
                {"name": "@aid", "value": agent_id},
                {"name": "@uid", "value": user_id},
                {"name": "@top_k", "value": top_k},
            ],
        )
        return memories

    async def extract_memories_from_thread(
        self,
        thread_id: str,
        agent_id: str,
        user_id: str,
        tenant_id: str,
        model_endpoint: Optional[dict] = None,
    ) -> int:
        """Extract memories from assistant messages in a thread. Returns count stored."""
        messages = await _message_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.thread_id = @thid AND c.role = 'assistant' ORDER BY c.sequence_number",
            [{"name": "@thid", "value": thread_id}],
        )

        count = 0
        for msg in messages:
            if len(msg.get("content", "")) > 50:
                await self.store_memory(
                    agent_id=agent_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    content=msg["content"],
                    model_endpoint=model_endpoint,
                    memory_type="knowledge",
                    source_thread_id=thread_id,
                )
                count += 1
        return count
