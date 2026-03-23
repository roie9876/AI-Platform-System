# Stack Research: AI Agent Platform as a Service

## Recommended Stack (2025-2026)

### Backend — Agent Runtime & Control Plane API

| Component | Recommendation | Version | Confidence | Rationale |
|-----------|---------------|---------|------------|-----------|
| Language | Python | 3.12+ | HIGH | AI/ML ecosystem is Python-native; all major agent frameworks (LangChain, AutoGen, Semantic Kernel, CrewAI) are Python-first |
| API Framework | FastAPI | 0.115+ | HIGH | Async-native, automatic OpenAPI spec generation, Pydantic validation, WebSocket support for streaming |
| Task Queue | Celery + Redis | 5.4+ | HIGH | Proven for async agent execution, supports priority queues, result backends, task chains |
| Agent Orchestration | Custom execution loop | — | HIGH | Own the core ReAct/plan-execute cycle — same pattern used by Azure AI Foundry, Google Vertex AI, AWS Bedrock. Full control over execution, debugging, and extension |
| Agent SDK (optional) | Semantic Kernel (Python SDK) | 1.x | MEDIUM | Microsoft-native plugin/function-calling abstractions. Used as SDK layer for tool management and model routing, not as the orchestration engine |
| Multi-Agent Patterns | LangGraph-inspired | — | MEDIUM | Graph-based multi-agent patterns (fan-out, supervisor, handoff). Borrow design patterns, not the library dependency |
| ORM / DB Access | SQLAlchemy + Alembic | 2.0+ | HIGH | Async support, migration management, works with PostgreSQL |
| WebSocket | FastAPI WebSockets + Socket.IO | — | HIGH | Real-time agent streaming, thread updates |

### Frontend — Control Plane UI

| Component | Recommendation | Version | Confidence | Rationale |
|-----------|---------------|---------|------------|-----------|
| Framework | Next.js (App Router) | 15+ | HIGH | SSR/SSG for performance, API routes for BFF pattern, React Server Components |
| UI Library | React | 19+ | HIGH | Component ecosystem, hooks for state management |
| Component Library | Shadcn/ui + Tailwind CSS | latest | HIGH | Modern, customizable, accessible components without heavy dependency |
| State Management | Zustand | 5+ | HIGH | Lightweight, TypeScript-first, no boilerplate |
| Data Fetching | TanStack Query (React Query) | 5+ | HIGH | Caching, optimistic updates, real-time sync for agent status |
| Flow/Graph Editor | React Flow | 12+ | HIGH | Visual workflow builder for agent orchestration flows |
| Charts/Dashboards | Recharts or Tremor | latest | HIGH | Cost observability dashboards, token usage visualization |
| Code Editor | Monaco Editor | latest | MEDIUM | For inline prompt/config editing within the UI |

### Data Layer

| Component | Recommendation | Version | Confidence | Rationale |
|-----------|---------------|---------|------------|-----------|
| Primary Database | PostgreSQL | 16+ | HIGH | Relational data (agents, configs, users, policies), JSONB for flexible schemas |
| RAG & Search Engine | Azure AI Search | — | HIGH | Primary RAG engine for tenant data sources — hybrid search (vector + BM25), semantic ranking, built-in chunking/indexers, multi-tenant via index-per-tenant or security filters |
| Platform-Internal Vectors | pgvector (PostgreSQL extension) | 0.7+ | MEDIUM | Lightweight internal embeddings only — agent similarity, tool search, marketplace search. NOT for tenant RAG pipelines |
| Cache / Pub-Sub | Redis | 7+ | HIGH | Session cache, pub-sub for real-time updates, task queue backend |
| Object Storage | Azure Blob / S3-compatible | — | HIGH | File attachments, agent artifacts, large outputs |

### Platform AI Services (Managed Capabilities)

Azure AI Services exposed as toggleable platform-managed tools — users enable capabilities per agent without provisioning services. Mirrors Azure AI Foundry's approach.

| Capability | Azure Service | Tool Interface | Priority |
|-----------|---------------|----------------|----------|
| Search / Grounding | Azure AI Search | `search(query)`, `index(documents)` | P0 — core RAG |
| Content Safety | Azure AI Content Safety | `moderate(text)`, `analyze_image(url)` | P0 — governance |
| Document Extraction | Azure AI Document Intelligence | `extract(document)`, `analyze_layout(file)` | P1 — data source ingestion |
| Speech-to-Text | Azure AI Speech | `transcribe(audio)` | P1 — voice input |
| Text-to-Speech | Azure AI Speech | `synthesize(text)` | P2 — voice output |
| Vision / OCR | Azure AI Vision | `analyze_image(url)`, `ocr(image)` | P2 — multimodal |
| Language Analysis | Azure AI Language | `extract_entities(text)`, `summarize(text)`, `sentiment(text)` | P2 — NLP tools |
| Translation | Azure AI Translator | `translate(text, target_lang)` | P2 — multilingual |

**Architecture:** Platform authenticates to Azure AI Services via Managed Identity — users never handle API keys. Usage is metered per tenant/agent for cost dashboard.

### Infrastructure & Runtime

| Component | Recommendation | Version | Confidence | Rationale |
|-----------|---------------|---------|------------|-----------|
| Containerization | Docker | 25+ | HIGH | Agent runtime isolation, reproducible environments |
| Container Orchestration | Kubernetes (AKS) | 1.29+ | HIGH | Multi-tenant isolation via namespaces/pods, autoscaling |
| API Gateway | Azure API Management or Kong | — | HIGH | Rate limiting, auth, routing, API versioning |
| Identity | Microsoft Entra ID (Azure AD) | — | HIGH | Enterprise SSO, RBAC, managed identities |
| Secrets | Azure Key Vault | — | HIGH | Model API keys, connection strings, tenant secrets |

### Observability & Monitoring

| Component | Recommendation | Version | Confidence | Rationale |
|-----------|---------------|---------|------------|-----------|
| APM | OpenTelemetry + Azure Monitor | — | HIGH | Vendor-agnostic telemetry, traces per agent execution |
| Logging | Structured logging (structlog) | — | HIGH | JSON logs, correlation IDs per thread/agent |
| Metrics | Prometheus + Grafana (or Azure Monitor) | — | HIGH | Custom metrics for token usage, cost tracking |
| LLM Observability | Custom middleware | — | HIGH | Token counting, latency per model call, cost calculation |

### Model Abstraction

| Component | Recommendation | Confidence | Rationale |
|-----------|---------------|------------|-----------|
| Primary Interface | OpenAI-compatible API format | HIGH | Most models expose OpenAI-compatible endpoints; standardizes the abstraction layer |
| SDK | LiteLLM or custom abstraction | HIGH | LiteLLM provides 100+ model provider support with unified interface |
| Fallback/Routing | Custom router with circuit breaker | HIGH | Model failover, cost-based routing, latency-based selection |

## What NOT to Use

| Technology | Why Not |
|------------|---------|
| LangChain / LangGraph (as core framework) | Heavy abstraction, frequent breaking changes, hard to debug at scale. Borrow patterns from LangGraph for multi-agent graphs, but don't take the dependency. All major platforms (Azure, GCP, AWS) use custom loops |
| Separate vector DB (Pinecone/Weaviate) | Azure AI Search covers RAG needs with hybrid search; pgvector covers internal embeddings. No need for a third vector service |
| GraphQL | REST + WebSocket simpler for this domain, agent APIs are mostly CRUD + streaming |
| MongoDB | PostgreSQL with JSONB covers flexible schema needs without losing relational integrity |
| Electron/Desktop | Web-first platform, no desktop app needed |

## Microsoft Product Mapping (for Architecture Design)

| Logical Component | Microsoft Service |
|-------------------|-------------------|
| Compute (API) | Azure Container Apps / AKS |
| Compute (Agent Runtime) | Azure Container Apps (isolated containers per agent) |
| Database | Azure Database for PostgreSQL Flexible Server |
| Cache | Azure Cache for Redis |
| Object Storage | Azure Blob Storage |
| Identity | Microsoft Entra ID |
| Secrets | Azure Key Vault |
| AI Models | Azure OpenAI Service (default) + customer endpoints |
| Search / RAG | Azure AI Search |
| Content Safety | Azure AI Content Safety |
| Document Processing | Azure AI Document Intelligence |
| Speech | Azure AI Speech |
| Vision / OCR | Azure AI Vision |
| Language / NLP | Azure AI Language |
| Translation | Azure AI Translator |
| Monitoring | Azure Monitor + Application Insights |
| API Gateway | Azure API Management |
| Message Queue | Azure Service Bus |
| Event Streaming | Azure Event Hubs (for high-throughput telemetry) |
| Container Registry | Azure Container Registry |

---
*Researched: 2026-03-23*
