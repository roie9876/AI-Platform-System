import logging
import re
from typing import List, Dict, Any, Optional
from uuid import uuid4

import httpx

from app.repositories.data_source_repo import (
    AgentDataSourceRepository,
    DocumentRepository,
    DocumentChunkRepository,
)
from app.repositories.config_repo import AzureConnectionRepository, AzureSubscriptionRepository
from app.services.document_parser import DocumentParser, TextChunker
from app.services.secret_store import decrypt_api_key

logger = logging.getLogger(__name__)

_agent_ds_repo = AgentDataSourceRepository()
_doc_repo = DocumentRepository()
_chunk_repo = DocumentChunkRepository()
_conn_repo = AzureConnectionRepository()
_sub_repo = AzureSubscriptionRepository()


class RAGService:
    """RAG pipeline: ingest documents (parse -> chunk -> store) and retrieve relevant chunks."""

    def __init__(self):
        self._parser = DocumentParser()
        self._chunker = TextChunker(chunk_size=1000, chunk_overlap=200)

    async def ingest_file(
        self,
        data_source_id: str,
        tenant_id: str,
        filename: str,
        file_content: bytes,
    ) -> dict:
        """Ingest a file: parse -> chunk -> store chunks. Returns Document record."""
        text_content = self._parser.parse_bytes(file_content, filename)
        content_hash = self._parser.compute_hash(file_content)

        # Check for duplicate
        existing = await _doc_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.data_source_id = @dsid AND c.content_hash = @hash",
            [{"name": "@dsid", "value": data_source_id}, {"name": "@hash", "value": content_hash}],
        )
        if existing:
            logger.info("Document with same hash already exists, skipping: %s", filename)
            return existing[0]

        doc_id = str(uuid4())
        doc = {
            "id": doc_id,
            "data_source_id": data_source_id,
            "filename": filename,
            "content_type": self._guess_content_type(filename),
            "file_size": len(file_content),
            "content_hash": content_hash,
            "status": "processing",
            "tenant_id": tenant_id,
        }
        await _doc_repo.create(tenant_id, doc)

        chunks = self._chunker.chunk(text_content)

        for idx, chunk_text in enumerate(chunks):
            chunk = {
                "id": str(uuid4()),
                "document_id": doc_id,
                "content": chunk_text,
                "chunk_index": idx,
                "chunk_metadata": {"filename": filename, "chunk_index": idx},
                "embedding": None,
                "tenant_id": tenant_id,
            }
            await _chunk_repo.create(tenant_id, chunk)

        doc["chunk_count"] = len(chunks)
        doc["status"] = "ready"
        await _doc_repo.update(tenant_id, doc_id, doc)

        logger.info("Ingested document '%s': %d chunks", filename, len(chunks))
        return doc

    async def ingest_url(
        self,
        data_source_id: str,
        tenant_id: str,
        url: str,
    ) -> dict:
        """Scrape URL content and ingest: fetch -> extract text -> chunk -> store."""
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

        content_text = self._extract_text_from_html(response.text)
        content_bytes = response.content
        content_hash = self._parser.compute_hash(content_bytes)

        doc_id = str(uuid4())
        doc = {
            "id": doc_id,
            "data_source_id": data_source_id,
            "filename": url,
            "content_type": "text/html",
            "file_size": len(content_bytes),
            "content_hash": content_hash,
            "status": "processing",
            "tenant_id": tenant_id,
        }
        await _doc_repo.create(tenant_id, doc)

        chunks = self._chunker.chunk(content_text)
        for idx, chunk_text in enumerate(chunks):
            chunk = {
                "id": str(uuid4()),
                "document_id": doc_id,
                "content": chunk_text,
                "chunk_index": idx,
                "chunk_metadata": {"url": url, "chunk_index": idx},
                "embedding": None,
                "tenant_id": tenant_id,
            }
            await _chunk_repo.create(tenant_id, chunk)

        doc["chunk_count"] = len(chunks)
        doc["status"] = "ready"
        await _doc_repo.update(tenant_id, doc_id, doc)

        logger.info("Ingested URL '%s': %d chunks", url, len(chunks))
        return doc

    async def retrieve(
        self,
        query: str,
        agent_id: str,
        tenant_id: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant document chunks for an agent's connected data sources.
        Uses keyword matching for PoC."""
        ds_links = await _agent_ds_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.agent_id = @aid",
            [{"name": "@aid", "value": agent_id}],
        )
        ds_ids = [link["data_source_id"] for link in ds_links]

        if not ds_ids:
            return []

        # Get ready documents for these data sources
        all_doc_ids = []
        for ds_id in ds_ids:
            docs = await _doc_repo.query(
                tenant_id,
                "SELECT c.id FROM c WHERE c.data_source_id = @dsid AND c.status = 'ready' AND c.tenant_id = @tid",
                [{"name": "@dsid", "value": ds_id}, {"name": "@tid", "value": tenant_id}],
            )
            all_doc_ids.extend(d["id"] for d in docs)

        if not all_doc_ids:
            return []

        # Keyword-based retrieval for PoC
        search_words = [w.lower() for w in query.split() if len(w) > 2]
        if not search_words:
            return []

        # Query chunks for each document, filter by keyword match client-side
        results = []
        for doc_id in all_doc_ids:
            chunks = await _chunk_repo.query(
                tenant_id,
                "SELECT * FROM c WHERE c.document_id = @did AND c.tenant_id = @tid",
                [{"name": "@did", "value": doc_id}, {"name": "@tid", "value": tenant_id}],
            )
            for chunk in chunks:
                content_lower = chunk.get("content", "").lower()
                if any(word in content_lower for word in search_words):
                    results.append({
                        "chunk_id": chunk["id"],
                        "document_id": chunk["document_id"],
                        "content": chunk["content"],
                        "chunk_index": chunk.get("chunk_index"),
                        "metadata": chunk.get("chunk_metadata"),
                    })
                    if len(results) >= top_k:
                        return results

        return results[:top_k]

    async def retrieve_from_azure_search(
        self,
        query: str,
        agent_id: str,
        tenant_id: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve documents from Azure AI Search indexes connected to the agent."""
        from app.services.azure_arm import AzureARMService

        # Find connections explicitly attached to this agent
        connections = await _conn_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.resource_type = 'Microsoft.Search/searchServices' AND (c.agent_id = @aid OR ARRAY_CONTAINS(c.agent_ids, @aid))",
            [{"name": "@tid", "value": tenant_id}, {"name": "@aid", "value": agent_id}],
        )
        if not connections:
            return []

        arm_service = AzureARMService()
        results: List[Dict[str, Any]] = []

        for conn in connections:
            selected_indexes = (conn.get("config") or {}).get("selected_indexes", [])
            if not selected_indexes:
                continue

            # Try cached admin key first
            cached_key_enc = (conn.get("config") or {}).get("cached_admin_key")
            admin_key = None
            if cached_key_enc:
                try:
                    admin_key = decrypt_api_key(cached_key_enc)
                except Exception:
                    pass

            # Fall back to ARM API if no cached key
            if not admin_key:
                subscription = await _sub_repo.get(tenant_id, conn.get("azure_subscription_id", ""))
                if not subscription or not subscription.get("access_token_encrypted"):
                    continue

                access_token = decrypt_api_key(subscription["access_token_encrypted"])
                admin_key = await arm_service._get_search_admin_key(access_token, conn["resource_id"])
                if not admin_key:
                    logger.warning("Could not get admin key for %s", conn.get("resource_name"))
                    continue

            # Derive data plane endpoint from resource name
            search_endpoint = f"https://{conn['resource_name']}.search.windows.net"

            for index_name in selected_indexes:
                search_url = f"{search_endpoint}/indexes/{index_name}/docs/search"
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(
                            search_url,
                            params={"api-version": "2024-07-01"},
                            headers={"api-key": admin_key},
                            json={"search": query, "top": top_k},
                        )
                        if resp.status_code in (403, 404):
                            continue
                        resp.raise_for_status()
                        data = resp.json()

                        for doc in data.get("value", []):
                            content = doc.get("content") or doc.get("chunk") or doc.get("text") or ""
                            if not content:
                                content = " ".join(
                                    str(v) for k, v in doc.items()
                                    if isinstance(v, str) and not k.startswith("@")
                                )
                            results.append({
                                "source": "azure_search",
                                "index": index_name,
                                "connection_id": conn["id"],
                                "content": content,
                                "metadata": {
                                    k: v for k, v in doc.items()
                                    if k not in ("content", "chunk", "text", "@search.score")
                                    and not k.startswith("@")
                                },
                                "score": doc.get("@search.score"),
                            })
                except httpx.HTTPStatusError as e:
                    logger.warning(
                        "Azure Search query failed for index %s: %s — HTTP %d: %s",
                        index_name, search_endpoint, e.response.status_code, e.response.text[:500],
                    )
                    continue
                except httpx.HTTPError as e:
                    logger.warning(
                        "Azure Search query failed for index %s: %s — %s",
                        index_name, search_endpoint, str(e),
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
