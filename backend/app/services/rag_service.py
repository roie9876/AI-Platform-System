import logging
import re
from typing import List, Dict, Any, Optional
from uuid import UUID

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.azure_connection import AzureConnection
from app.models.azure_subscription import AzureSubscription
from app.models.data_source import AgentDataSource
from app.models.document import Document, DocumentChunk
from app.services.document_parser import DocumentParser, TextChunker
from app.services.secret_store import decrypt_api_key

logger = logging.getLogger(__name__)


class RAGService:
    """RAG pipeline: ingest documents (parse -> chunk -> store) and retrieve relevant chunks."""

    def __init__(self):
        self._parser = DocumentParser()
        self._chunker = TextChunker(chunk_size=1000, chunk_overlap=200)

    async def ingest_file(
        self,
        data_source_id: UUID,
        tenant_id: UUID,
        filename: str,
        file_content: bytes,
        db: AsyncSession,
    ) -> Document:
        """Ingest a file: parse -> chunk -> store chunks in DB. Returns Document record."""
        text_content = self._parser.parse_bytes(file_content, filename)
        content_hash = self._parser.compute_hash(file_content)

        # Check for duplicate
        result = await db.execute(
            select(Document).where(
                Document.data_source_id == data_source_id,
                Document.content_hash == content_hash,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("Document with same hash already exists, skipping: %s", filename)
            return existing

        doc = Document(
            data_source_id=data_source_id,
            filename=filename,
            content_type=self._guess_content_type(filename),
            file_size=len(file_content),
            content_hash=content_hash,
            status="processing",
            tenant_id=tenant_id,
        )
        db.add(doc)
        await db.flush()

        chunks = self._chunker.chunk(text_content)

        for idx, chunk_text in enumerate(chunks):
            chunk = DocumentChunk(
                document_id=doc.id,
                content=chunk_text,
                chunk_index=idx,
                chunk_metadata={"filename": filename, "chunk_index": idx},
                embedding=None,
                tenant_id=tenant_id,
            )
            db.add(chunk)

        doc.chunk_count = len(chunks)
        doc.status = "ready"
        await db.flush()

        logger.info("Ingested document '%s': %d chunks", filename, len(chunks))
        return doc

    async def ingest_url(
        self,
        data_source_id: UUID,
        tenant_id: UUID,
        url: str,
        db: AsyncSession,
    ) -> Document:
        """Scrape URL content and ingest: fetch -> extract text -> chunk -> store."""
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

        content_text = self._extract_text_from_html(response.text)
        content_bytes = response.content
        content_hash = self._parser.compute_hash(content_bytes)

        doc = Document(
            data_source_id=data_source_id,
            filename=url,
            content_type="text/html",
            file_size=len(content_bytes),
            content_hash=content_hash,
            status="processing",
            tenant_id=tenant_id,
        )
        db.add(doc)
        await db.flush()

        chunks = self._chunker.chunk(content_text)
        for idx, chunk_text in enumerate(chunks):
            chunk = DocumentChunk(
                document_id=doc.id,
                content=chunk_text,
                chunk_index=idx,
                chunk_metadata={"url": url, "chunk_index": idx},
                embedding=None,
                tenant_id=tenant_id,
            )
            db.add(chunk)

        doc.chunk_count = len(chunks)
        doc.status = "ready"
        await db.flush()

        logger.info("Ingested URL '%s': %d chunks", url, len(chunks))
        return doc

    async def retrieve(
        self,
        query: str,
        agent_id: UUID,
        tenant_id: UUID,
        db: AsyncSession,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant document chunks for an agent's connected data sources.
        Uses keyword matching for PoC (full vector search via Azure AI Search in production)."""
        ds_result = await db.execute(
            select(AgentDataSource.data_source_id).where(
                AgentDataSource.agent_id == agent_id
            )
        )
        ds_ids = [row[0] for row in ds_result.fetchall()]

        if not ds_ids:
            return []

        doc_result = await db.execute(
            select(Document.id).where(
                Document.data_source_id.in_(ds_ids),
                Document.status == "ready",
                Document.tenant_id == tenant_id,
            )
        )
        doc_ids = [row[0] for row in doc_result.fetchall()]

        if not doc_ids:
            return []

        # Keyword-based retrieval for PoC
        search_words = [w.lower() for w in query.split() if len(w) > 2]
        if not search_words:
            return []

        # Build parameterized query for safe keyword search
        conditions = " OR ".join(
            [f"LOWER(content) LIKE :word_{i}" for i in range(len(search_words))]
        )
        params: Dict[str, Any] = {
            f"word_{i}": f"%{word}%" for i, word in enumerate(search_words)
        }
        params["tenant_id"] = str(tenant_id)
        params["top_k"] = top_k

        # Use parameterized IN clause
        doc_id_placeholders = ", ".join(
            [f":doc_id_{i}" for i in range(len(doc_ids))]
        )
        for i, doc_id in enumerate(doc_ids):
            params[f"doc_id_{i}"] = str(doc_id)

        query_sql = text(f"""
            SELECT id, document_id, content, chunk_index, metadata
            FROM document_chunks
            WHERE tenant_id = :tenant_id
            AND document_id IN ({doc_id_placeholders})
            AND ({conditions})
            LIMIT :top_k
        """)

        result = await db.execute(query_sql, params)
        rows = result.fetchall()

        return [
            {
                "chunk_id": str(row[0]),
                "document_id": str(row[1]),
                "content": row[2],
                "chunk_index": row[3],
                "metadata": row[4],
            }
            for row in rows
        ]

    async def retrieve_from_azure_search(
        self,
        query: str,
        agent_id: UUID,
        tenant_id: UUID,
        db: AsyncSession,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve documents from Azure AI Search indexes connected to the agent."""
        conn_result = await db.execute(
            select(AzureConnection).where(
                AzureConnection.agent_id == agent_id,
                AzureConnection.tenant_id == tenant_id,
                AzureConnection.resource_type == "Microsoft.Search/searchServices",
            )
        )
        connections = list(conn_result.scalars().all())
        if not connections:
            return []

        results: List[Dict[str, Any]] = []

        for conn in connections:
            selected_indexes = (conn.config or {}).get("selected_indexes", [])
            if not selected_indexes:
                continue

            # Get access token from subscription
            sub_result = await db.execute(
                select(AzureSubscription).where(
                    AzureSubscription.id == conn.azure_subscription_id
                )
            )
            subscription = sub_result.scalar_one_or_none()
            if not subscription or not subscription.access_token_encrypted:
                continue

            access_token = decrypt_api_key(subscription.access_token_encrypted)
            endpoint = conn.endpoint
            if not endpoint:
                continue

            for index_name in selected_indexes:
                search_url = f"{endpoint}/indexes/{index_name}/docs/search"
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(
                            search_url,
                            params={"api-version": "2024-07-01"},
                            headers={"Authorization": f"Bearer {access_token}"},
                            json={"search": query, "$top": top_k},
                        )
                        if resp.status_code in (403, 404):
                            continue
                        resp.raise_for_status()
                        data = resp.json()

                        for doc in data.get("value", []):
                            results.append({
                                "source": "azure_search",
                                "index": index_name,
                                "connection_id": str(conn.id),
                                "content": doc.get("content", ""),
                                "metadata": {
                                    k: v for k, v in doc.items()
                                    if k not in ("content", "@search.score")
                                },
                                "score": doc.get("@search.score"),
                            })
                except httpx.HTTPError:
                    logger.warning(
                        "Azure Search query failed for index %s: %s",
                        index_name,
                        endpoint,
                    )
                    continue

        # Sort by score descending, take top_k
        results.sort(key=lambda r: r.get("score") or 0, reverse=True)
        return results[:top_k]

    def _extract_text_from_html(self, html: str) -> str:
        """Basic HTML to text extraction — strip tags, decode entities."""
        text_content = re.sub(
            r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
        )
        text_content = re.sub(
            r"<style[^>]*>.*?</style>", "", text_content, flags=re.DOTALL | re.IGNORECASE
        )
        text_content = re.sub(r"<[^>]+>", " ", text_content)
        text_content = (
            text_content.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&nbsp;", " ")
        )
        text_content = re.sub(r"\s+", " ", text_content).strip()
        return text_content

    def _guess_content_type(self, filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return {
            "pdf": "application/pdf",
            "txt": "text/plain",
            "md": "text/markdown",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }.get(ext, "application/octet-stream")
