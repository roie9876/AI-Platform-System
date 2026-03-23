# Stack Research: AI Agent Platform as a Service

## Recommended Stack (2025-2026)

### Backend — Agent Runtime & Control Plane API

| Component | Recommendation | Version | Confidence | Rationale |
|-----------|---------------|---------|------------|-----------|
| Language | Python | 3.12+ | HIGH | AI/ML ecosystem is Python-native; all major agent frameworks (LangChain, AutoGen, Semantic Kernel, CrewAI) are Python-first |
| API Framework | FastAPI | 0.115+ | HIGH | Async-native, automatic OpenAPI spec generation, Pydantic validation, WebSocket support for streaming |
| Task Queue | Celery + Redis | 5.4+ | HIGH | Proven for async agent execution, supports priority queues, result backends, task chains |
| Agent Framework | Semantic Kernel (Python SDK) | 1.x | HIGH | Microsoft-native, supports multi-model routing, plugin architecture maps to tool marketplace, function calling built-in |
| Alternative Agent Framework | AutoGen | 0.4+ | MEDIUM | Microsoft Research project, strong multi-agent orchestration, but API is less stable |
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
| Vector Database | pgvector (PostgreSQL extension) | 0.7+ | HIGH | RAG embeddings, keeps infra simple vs. separate vector DB |
| Cache / Pub-Sub | Redis | 7+ | HIGH | Session cache, pub-sub for real-time updates, task queue backend |
| Object Storage | Azure Blob / S3-compatible | — | HIGH | File attachments, agent artifacts, large outputs |
| Search (optional) | Azure AI Search | — | MEDIUM | Full-text search across agents, tools, marketplace |

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
| LangChain (as core framework) | Heavy abstraction, frequent breaking changes, hard to debug at scale. Use Semantic Kernel instead for Microsoft alignment |
| Separate vector DB (Pinecone/Weaviate) | pgvector sufficient for PoC scale, reduces infrastructure complexity |
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
| Monitoring | Azure Monitor + Application Insights |
| API Gateway | Azure API Management |
| Message Queue | Azure Service Bus |
| Event Streaming | Azure Event Hubs (for high-throughput telemetry) |
| Container Registry | Azure Container Registry |

---
*Researched: 2026-03-23*
