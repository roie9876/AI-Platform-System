# Phase 4: Tools, Data Sources, RAG & Platform AI Services — Research

**Researched:** 2026-03-23
**Status:** Complete
**Discovery Level:** 2 (Standard Research — multiple new external libraries)

## 1. Docker SDK for Python — Sandboxed Tool Execution

### Library: `docker` (docker-py)
- **Package:** `docker>=7.0.0`
- **Key API:** `docker.from_env()` creates client from environment (reads DOCKER_HOST or Unix socket)
- **Container run pattern:**
  ```python
  client = docker.from_env()
  container = client.containers.run(
      image="tool-image:latest",
      command=["python", "run_tool.py"],
      environment={"INPUT": json.dumps(tool_input)},
      mem_limit="256m",
      cpu_period=100000, cpu_quota=50000,  # 50% CPU
      network_mode="none",  # no network for sandboxed tools
      detach=True,
      stdout=True, stderr=True,
  )
  result = container.wait(timeout=timeout_seconds)
  output = container.logs(stdout=True, stderr=False).decode()
  container.remove(force=True)
  ```
- **Resource limits:** `mem_limit`, `cpu_period`/`cpu_quota`, `network_mode="none"`
- **Timeout:** `container.wait(timeout=N)` raises `ConnectionError` on timeout; catch and kill
- **Docker-in-Docker:** Since backend runs in Docker Compose, need to mount host Docker socket:
  ```yaml
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
  ```
- **PoC simplification:** For PoC, can use subprocess-based execution as a simpler alternative to Docker. This avoids Docker-in-Docker complexity while still demonstrating the sandbox architecture. The Docker adapter can be swapped in for production.

### Recommendation
Use a **ToolExecutor abstraction** with two backends:
1. `SubprocessToolExecutor` — for PoC/local dev (runs tool as subprocess with timeout)
2. `DockerToolExecutor` — for production (Docker container sandbox)

This matches the project's pattern of local-dev vs production abstractions (like Fernet vs Key Vault for secrets).

## 2. LiteLLM Tool Calling Support

### Current State
LiteLLM already supports OpenAI-format tool calling via `litellm.acompletion()`:

```python
response = await litellm.acompletion(
    model="azure/gpt-4o",
    messages=messages,
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            }
        }
    }],
    tool_choice="auto",
    stream=True,
)
```

### Streaming with Tool Calls
- When streaming, tool calls come as deltas: `chunk.choices[0].delta.tool_calls`
- Tool call deltas have `index`, `id`, `function.name`, `function.arguments` (accumulated)
- Need to accumulate tool call arguments across chunks, then execute when complete
- After tool execution, append tool result as `{"role": "tool", "tool_call_id": id, "content": result}` and re-call the model

### Integration with Existing Code
- `_build_litellm_params()` in `model_abstraction.py` needs a `tools` parameter
- `ModelAbstractionService.complete()` needs to yield tool call events (not just content tokens)
- `AgentExecutionService.execute()` needs the tool-calling loop:
  1. Send message with tools → get response
  2. If response has tool_calls → execute each tool → append results → re-send
  3. Repeat until model returns content (final response)
  4. Stream final content tokens to SSE

## 3. Azure AI Search SDK — RAG Pipeline

### Library: `azure-search-documents>=11.6.0`
- **Index management:** `SearchIndexClient` creates/manages indexes
- **Document operations:** `SearchClient` for uploading and searching documents
- **Vector search:** Supports vector fields with configurable dimensions
- **Hybrid search:** Combine vector + keyword in a single query

### Index Schema Pattern
```python
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType,
    VectorSearch, HnswAlgorithmConfiguration, VectorSearchProfile,
    SearchableField, SimpleField,
)

fields = [
    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
    SimpleField(name="data_source_id", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="tenant_id", type=SearchFieldDataType.String, filterable=True),
    SearchableField(name="content", type=SearchFieldDataType.String),
    SearchField(name="embedding", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True, vector_search_dimensions=1536, vector_search_profile_name="default"),
    SimpleField(name="metadata", type=SearchFieldDataType.String),
]
```

### Search Pattern (Hybrid)
```python
from azure.search.documents.models import VectorizedQuery

vector_query = VectorizedQuery(vector=query_embedding, k_nearest_neighbors=5, fields="embedding")
results = search_client.search(
    search_text=query_text,
    vector_queries=[vector_query],
    filter=f"tenant_id eq '{tenant_id}' and data_source_id eq '{ds_id}'",
    top=5,
)
```

### PoC Consideration
- For local dev without Azure AI Search, use **pgvector** as a fallback (already in stack decision)
- Create a `SearchService` abstraction:
  1. `PgVectorSearchService` — for local dev (uses pgvector extension in PostgreSQL)
  2. `AzureSearchService` — for production (uses Azure AI Search)
- This aligns with project's dual-mode pattern

### Embedding Generation
- Use the existing `ModelAbstractionService` to generate embeddings via LiteLLM
- LiteLLM supports `litellm.aembedding(model, input)` for embedding generation
- Embedding dimension depends on model (ada-002 = 1536, text-embedding-3-small = 1536)

## 4. Document Parsing Libraries

### File Types Required: PDF, TXT, MD, DOCX

| Format | Library | Package | Notes |
|--------|---------|---------|-------|
| PDF | pypdf | `pypdf>=4.0.0` | Pure Python, no system deps, extracts text per page |
| DOCX | python-docx | `python-docx>=1.1.0` | Extracts paragraphs and tables |
| TXT/MD | Built-in | N/A | `open().read()` — no library needed |

### Chunking Strategy
- **Recursive character splitting** is the most practical for PoC:
  1. Split by paragraph (`\n\n`)
  2. If chunk > max_size, split by sentence (`. `)
  3. If still too large, split by character with overlap
- **Parameters:** `chunk_size=1000`, `chunk_overlap=200` (tokens or characters)
- Implement as a simple `TextChunker` class — no need for LangChain's chunker

## 5. Azure AI Services — Platform Tool Adapters

### The 7 Services from D-07

| Service | SDK Package | Key Operation | PoC Priority |
|---------|-------------|---------------|--------------|
| Azure AI Search | `azure-search-documents` | Search indexed documents | HIGH (core to RAG) |
| Content Safety | `azure-ai-contentsafety` | Analyze text/image safety | HIGH (governance demo) |
| Document Intelligence | `azure-ai-documentintelligence` | Extract text from documents | MEDIUM |
| Language | `azure-ai-textanalytics` | Sentiment, NER, summarization | LOW |
| Translation | N/A (REST API) | Translate text | LOW |
| Speech | `azure-cognitiveservices-speech` | Speech-to-text, text-to-speech | LOW |
| Vision | `azure-ai-vision-imageanalysis` | Image analysis | LOW |

### PoC Recommendation
- **Implement fully:** Azure AI Search (already needed for RAG), Content Safety (governance demo value)
- **Implement as stubs with interface:** Document Intelligence, Language, Translation, Speech, Vision
- All 7 services get the adapter interface defined, but only 2-3 have real SDK calls
- This demonstrates the architecture without requiring 7 Azure service subscriptions

### Platform Tool Adapter Pattern
```python
class PlatformToolAdapter(ABC):
    """Base class for all platform AI service tools."""
    
    @abstractmethod
    def get_tool_schema(self) -> dict:
        """Return JSON Schema for this tool's input."""
        
    @abstractmethod
    async def execute(self, input_data: dict) -> dict:
        """Execute the AI service call and return result."""
        
    @abstractmethod
    def service_name(self) -> str:
        """Return the Azure AI service name."""
```

### Authentication
- **Production:** `DefaultAzureCredential()` from `azure-identity` — Managed Identity
- **Local dev:** API key from environment variables
- Pattern: `credential = DefaultAzureCredential()` with fallback to `AzureKeyCredential(api_key)`

## 6. Architecture Decisions

### Tool-Calling Loop Architecture
The agent execution loop needs restructuring for tool support:

```
User message → Build messages (with RAG context) → Send to model (with tool schemas)
    ↓
Model response:
  - If tool_calls → Execute tools → Append results → Re-send to model (loop)
  - If content → Stream to user (done)
```

**Max iterations:** Cap tool-calling loop at 10 iterations to prevent runaway agents.

### RAG Context Injection Points
Two approaches:
1. **System prompt injection:** Append retrieved chunks to system prompt — simpler, works with all models
2. **Separate context message:** Add a `{"role": "system", "content": "Relevant context: ..."}` message — cleaner separation

**Recommendation:** System prompt injection for PoC (simpler, per D-11).

### Database Models Needed
- `Tool` — id, name, description, input_schema (JSONB), output_schema (JSONB), docker_image, tenant_id, is_platform_tool
- `AgentTool` — agent_id, tool_id (many-to-many join table)
- `DataSource` — id, name, type (file/url), config (JSONB), tenant_id, status
- `AgentDataSource` — agent_id, data_source_id (many-to-many join table)
- `Document` — id, data_source_id, filename, content_hash, status, chunk_count
- `DocumentChunk` — id, document_id, content, embedding (vector), chunk_index, metadata (JSONB)

### File Upload Handling
- FastAPI `UploadFile` for file upload endpoint
- Store files in `uploads/` directory (local for PoC)
- Process asynchronously: upload → parse → chunk → embed → index
- For PoC, process synchronously (simpler, acceptable for demo)

## 7. Scope Assessment for Planning

### Subsystem Breakdown
1. **Tool Registry & Execution** (~30% of phase): Models, CRUD API, sandbox executor, tool-calling loop
2. **Data Sources & RAG** (~40% of phase): Models, CRUD API, file upload, URL scraping, parsing, chunking, embedding, indexing, retrieval, context injection
3. **Platform AI Services** (~15% of phase): Adapter framework, 2-3 real implementations, toggle UI
4. **Frontend UI** (~15% of phase): Tool management pages, data source pages, AI services toggle

### Dependencies
- Tool calling loop depends on tool registry
- RAG retrieval depends on data source ingestion pipeline
- Platform AI services depend on tool adapter framework
- Frontend depends on backend APIs

### Risk Areas
- Docker-in-Docker for tool sandbox — mitigated by subprocess fallback for PoC
- Azure AI Search availability — mitigated by pgvector fallback for PoC
- Embedding cost — use small batches for PoC demo

## Validation Architecture

### Testable Behaviors
1. Tool CRUD: create/list/get/delete tools via API → verify 200/201/204 responses
2. Tool attachment: attach tool to agent → verify agent-tool relationship exists
3. Tool execution: invoke tool during agent chat → verify tool result in response
4. Data source CRUD: create/list/get/delete data sources → verify responses
5. Document ingestion: upload file → verify chunks created
6. RAG retrieval: query with context → verify relevant chunks returned
7. Platform tool toggle: enable/disable platform tool on agent → verify in config

### Integration Test Strategy
- Use pytest with httpx AsyncClient against FastAPI app
- Mock Docker SDK calls for tool sandbox tests
- Mock Azure AI Search for RAG tests (or use pgvector in test DB)
- Mock LiteLLM for tool-calling loop tests

---

## RESEARCH COMPLETE

**Key findings:**
- LiteLLM already supports tool calling — minimal changes to `ModelAbstractionService`
- Docker SDK viable for production, subprocess for PoC sandbox
- Azure AI Search SDK well-documented, pgvector as local fallback
- Document parsing straightforward with pypdf + python-docx
- Platform AI Services: implement 2-3 real adapters, stub the rest
- 4 new database models + 2 join tables needed
- Estimated 5-6 plans across 2-3 waves
