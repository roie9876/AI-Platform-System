# Research Summary: AI Agent Platform as a Service

## Stack Decision

**Backend:** Python 3.12+ / FastAPI — AI ecosystem is Python-native, FastAPI provides async performance + auto-generated OpenAPI docs. Use Semantic Kernel as the agent framework for Microsoft alignment.

**Frontend:** Next.js 15+ / React 19+ with Shadcn/ui + Tailwind. React Flow for the visual workflow builder. Zustand for state, TanStack Query for data fetching.

**Database:** PostgreSQL 16+ with pgvector for RAG embeddings. Redis 7+ for cache, pub-sub, and task queue backend.

**Model Abstraction:** OpenAI-compatible API format as canonical interface. Custom adapter layer normalizing all model responses. Customer-provided endpoints registered in model registry.

**Microsoft Product Mapping:** AKS/Container Apps for compute, Azure PostgreSQL for DB, Azure OpenAI as default model, Entra ID for auth, Key Vault for secrets, Azure Monitor for observability, API Management for gateway.

## Table Stakes Features (must have)

1. **Agent CRUD + Configuration** — create, configure, version agents through UI
2. **Tool Registry + Execution** — register tools, attach to agents, sandboxed execution
3. **Data Source Management + RAG** — connect sources, ingest/embed/retrieve pipeline
4. **Model Endpoint Registry** — register model endpoints, standardized API, streaming
5. **Thread Management** — create, persist, resume conversations
6. **Memory (Short + Long term)** — conversation history + persistent semantic memory
7. **Sequential + Parallel Orchestration** — chain and parallelize agents
8. **Workflow Builder UI** — visual drag-and-drop flow editor
9. **Policy Engine** — content filtering, rate limits, RBAC, audit logging
10. **Token Counting + Cost Dashboard** — per-agent cost tracking and visualization
11. **Evaluation Engine** — test suites, automated metrics, manual rating
12. **CLI Execution** — programmatic agent interaction via terminal

## Architecture Pattern

**Control Plane / Runtime Plane separation:**
- Control Plane: configuration, management, monitoring, governance (API + UI)
- Runtime Plane: execution, isolation, data flow, model interaction

**Multi-tenant:** Row-level security, namespace isolation, tenant-scoped secrets.

**Agent Execution Flow:** Request → Auth → Policy Pre-check → Load Memory/RAG → Build Context → Model Router → Tool Execution Loop → Policy Post-check → Telemetry → Memory Save → Response.

## Critical Pitfalls to Avoid

| Priority | Pitfall | Prevention |
|----------|---------|------------|
| P0 | Multi-tenant data leaks | Enforce tenant_id at ORM layer + RLS from day one |
| P0 | Model abstraction leaks | Strict internal format, adapter layer, test with 2+ providers |
| P0 | Runaway agent costs | Hard iteration/token/time limits, budget enforcement middleware |
| P1 | Tool execution security | Sandboxed execution, input validation, network isolation |
| P1 | Context window overflow | Token budgeting, sliding window, RAG limits |
| P1 | Workflow deadlocks | DAG cycle validation, global timeouts, max sub-agent depth |
| P2 | WebSocket scalability | Redis pub-sub, SSE as alternative, reconnection logic |
| P2 | Schema rigidity | JSONB for configs, relational for queryable fields |

## Suggested Build Order (8 phases)

1. **Foundation** — Database schema, API skeleton, auth, multi-tenant foundation
2. **HLD + Architecture Docs** — Vendor-agnostic HLD with Mermaid, Microsoft product mapping
3. **Agent Core** — Agent CRUD, model abstraction, basic execution, streaming
4. **Tools & Data** — Tool registry, tool execution, data sources, RAG pipeline
5. **Memory & Threads** — Thread management, short/long-term memory, state management
6. **Orchestration** — Workflow engine, parallel execution, sub-agents, workflow UI
7. **Governance** — Policy engine, RBAC, content filtering, audit
8. **Observability & Evaluation** — Cost dashboard, token tracking, evaluation engine, CLI, marketplace

## Key Design Decisions for Presentation

| Decision | Why | Alternative Considered |
|----------|-----|----------------------|
| Control Plane / Runtime Plane split | Same pattern as Kubernetes, clear separation of concerns, independent scaling | Monolithic API (doesn't scale) |
| PostgreSQL + pgvector (not separate vector DB) | Reduces operational complexity, pgvector sufficient at PoC scale | Pinecone/Weaviate (overkill for PoC) |
| OpenAI-compatible canonical format | Industry standard, most providers support it | Custom format (more work, no standard) |
| Semantic Kernel (not LangChain) | Microsoft-native, more stable API, plugin model maps to tool marketplace | LangChain (frequent breaking changes) |
| Multi-tenancy from day one | Avoids costly retrofit, demonstrates production thinking | Add multi-tenancy later (technical debt) |
| JSONB for agent configs | Flexible schema, avoids migration churn as configs evolve | Strict columns (too rigid for agent platform) |

---
*Synthesized: 2026-03-23*
