import logging
from typing import List, Optional
from uuid import UUID

import litellm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_memory import AgentMemory
from app.models.model_endpoint import ModelEndpoint
from app.models.thread_message import ThreadMessage
from app.services.secret_store import decrypt_api_key

logger = logging.getLogger(__name__)


class MemoryService:
    """Manages long-term agent memory with pgvector embeddings."""

    async def embed(self, text: str, model_endpoint: ModelEndpoint) -> List[float]:
        """Generate embedding vector using LiteLLM."""
        try:
            provider = model_endpoint.provider_type
            if provider == "azure_openai":
                model_str = f"azure/{model_endpoint.model_name}"
            elif provider == "openai":
                model_str = model_endpoint.model_name
            else:
                model_str = f"{provider}/{model_endpoint.model_name}"

            kwargs: dict = {
                "model": model_str,
                "input": [text],
            }

            if model_endpoint.endpoint_url:
                kwargs["api_base"] = model_endpoint.endpoint_url

            if model_endpoint.api_key_encrypted:
                decrypted = decrypt_api_key(model_endpoint.api_key_encrypted)
                kwargs["api_key"] = decrypted

            response = await litellm.aembedding(**kwargs)
            return response.data[0]["embedding"]
        except Exception:
            logger.warning("Failed to generate embedding, storing memory without vector", exc_info=True)
            return []

    async def store_memory(
        self,
        agent_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        content: str,
        db: AsyncSession,
        model_endpoint: Optional[ModelEndpoint] = None,
        memory_type: str = "knowledge",
        source_thread_id: Optional[UUID] = None,
    ) -> AgentMemory:
        """Store a memory with optional embedding."""
        embedding = None
        if model_endpoint:
            vector = await self.embed(content, model_endpoint)
            if vector:
                embedding = vector

        memory = AgentMemory(
            agent_id=agent_id,
            user_id=user_id,
            tenant_id=tenant_id,
            content=content,
            embedding=embedding,
            memory_type=memory_type,
            source_thread_id=source_thread_id,
        )
        db.add(memory)
        await db.commit()
        await db.refresh(memory)
        return memory

    async def retrieve_relevant(
        self,
        query: str,
        agent_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        db: AsyncSession,
        model_endpoint: Optional[ModelEndpoint] = None,
        top_k: int = 5,
    ) -> List[AgentMemory]:
        """Retrieve relevant memories using cosine similarity or recency fallback."""
        base_filter = [
            AgentMemory.agent_id == agent_id,
            AgentMemory.user_id == user_id,
            AgentMemory.tenant_id == tenant_id,
        ]

        if model_endpoint:
            query_embedding = await self.embed(query, model_endpoint)
            if query_embedding:
                # Use cosine distance for similarity search
                result = await db.execute(
                    select(AgentMemory)
                    .where(*base_filter)
                    .order_by(AgentMemory.embedding.cosine_distance(query_embedding))
                    .limit(top_k)
                )
                return list(result.scalars().all())

        # Fallback: return most recent memories
        result = await db.execute(
            select(AgentMemory)
            .where(*base_filter)
            .order_by(AgentMemory.created_at.desc())
            .limit(top_k)
        )
        return list(result.scalars().all())

    async def extract_memories_from_thread(
        self,
        thread_id: UUID,
        agent_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        db: AsyncSession,
        model_endpoint: Optional[ModelEndpoint] = None,
    ) -> int:
        """Extract memories from assistant messages in a thread. Returns count stored."""
        result = await db.execute(
            select(ThreadMessage)
            .where(
                ThreadMessage.thread_id == thread_id,
                ThreadMessage.role == "assistant",
            )
            .order_by(ThreadMessage.sequence_number)
        )
        messages = result.scalars().all()

        count = 0
        for msg in messages:
            if len(msg.content) > 50:
                await self.store_memory(
                    agent_id=agent_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    content=msg.content,
                    db=db,
                    model_endpoint=model_endpoint,
                    memory_type="knowledge",
                    source_thread_id=thread_id,
                )
                count += 1
        return count
