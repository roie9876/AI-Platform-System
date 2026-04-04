"""Azure OpenAI embedding client with in-memory LRU cache."""

from __future__ import annotations

import hashlib
import logging
import os
from collections import OrderedDict

from openai import AsyncAzureOpenAI

logger = logging.getLogger(__name__)

_MAX_CACHE_SIZE = 1000


class EmbeddingService:
    """Generates embeddings via Azure OpenAI with an in-memory LRU cache."""

    def __init__(self) -> None:
        self._client = AsyncAzureOpenAI(
            azure_endpoint=os.getenv(
                "AZURE_OPENAI_BASE",
                "https://ai-platform-system.openai.azure.com",
            ),
            api_key=os.getenv("AZURE_API_KEY", ""),
            api_version="2024-10-21",
        )
        self._model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self._cache: OrderedDict[str, list[float]] = OrderedDict()

    @staticmethod
    def _cache_key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def embed_text(self, text: str) -> list[float]:
        """Return the embedding vector for *text*, using cache when available."""
        key = self._cache_key(text)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=[text],
            )
            vector = response.data[0].embedding

            # LRU eviction
            if len(self._cache) >= _MAX_CACHE_SIZE:
                self._cache.popitem(last=False)
            self._cache[key] = vector
            return vector
        except Exception:
            logger.warning("Failed to generate embedding", exc_info=True)
            return []
