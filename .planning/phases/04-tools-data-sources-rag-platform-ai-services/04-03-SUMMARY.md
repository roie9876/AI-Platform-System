# Plan 04-03 Summary: RAG Pipeline

## What Was Built
- **DocumentParser** (`backend/app/services/document_parser.py`): Parses PDF (pypdf), TXT, MD, DOCX (python-docx) files. Supports both file path and bytes input. Computes SHA-256 content hash for deduplication.
- **TextChunker** (`backend/app/services/document_parser.py`): Splits text into configurable-size chunks (default 1000 chars, 200 overlap). Uses paragraph-first splitting, falls back to sentence splitting for large paragraphs.
- **RAGService** (`backend/app/services/rag_service.py`): Orchestrates ingestion and retrieval. `ingest_file()` parses, chunks, stores in DB with dedup check. `ingest_url()` fetches HTML, strips tags, chunks and stores. `retrieve()` performs keyword-based search scoped to agent's attached data sources (PoC — production uses Azure AI Search).
- **Document upload endpoint** (`POST /data-sources/{id}/documents`): Validates file extension (pdf/txt/md/docx) and size (10MB max), ingests via RAGService.
- **URL ingestion endpoint** (`POST /data-sources/{id}/ingest-url`): Accepts URL, scrapes and ingests via RAGService.
- **List documents endpoint** (`GET /data-sources/{id}/documents`): Lists documents for a data source with tenant scoping.
- **RAG context injection** (`backend/app/services/agent_execution.py`): `_inject_rag_context()` retrieves relevant chunks before model completion and injects as system message after the agent's system prompt.

## Files Created
- `backend/app/services/document_parser.py` — DocumentParser + TextChunker classes
- `backend/app/services/rag_service.py` — RAGService class

## Files Modified
- `backend/app/api/v1/data_sources.py` — Added upload, ingest-url, list-documents endpoints
- `backend/app/api/v1/schemas.py` — Added DocumentResponse, DocumentListResponse, IngestURLRequest
- `backend/app/services/agent_execution.py` — Added RAGService import, `_inject_rag_context()`, called in execute()
- `backend/requirements.txt` — Added pypdf>=4.0.0, python-docx>=1.1.0

## Key Decisions
- Keyword-based retrieval for PoC (production will use Azure AI Search with hybrid vector + keyword)
- RAG context injected as second system message (after agent system prompt, before conversation)
- Document deduplication via SHA-256 content hash
- HTML extraction uses basic regex tag stripping (no BeautifulSoup dependency)

## Commits
- `c38a617` — feat(04-03): add DocumentParser TextChunker and RAGService
- `c94b026` — feat(04-03): add document upload ingest-url endpoints and RAG context injection
