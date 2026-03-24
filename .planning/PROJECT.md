# AI Agent Platform as a Service

## What This Is

A multi-tenant AI Agent Platform as a Service (PaaS) that enables product teams at STU-MSFT to create, configure, and orchestrate AI agents through a self-service UI. Teams can attach tools, connect data sources, build multi-agent workflows, and monitor agent performance — all within secure, isolated runtime environments. The platform is model-agnostic: customers bring their own model endpoints while Azure OpenAI serves as the default. v1.0 shipped with full agent lifecycle, tool execution, RAG, workflow orchestration, observability, evaluation, marketplace, CLI, and Azure integration. v2.0 adds MCP (Model Context Protocol) client support for 1500+ remote tool servers.

## Core Value

Product teams can go from zero to a working AI agent with tools, data sources, and orchestration — without writing infrastructure code or managing model deployments.

## Requirements

### Validated

- [x] HLD documentation — vendor-agnostic architecture with Mermaid diagrams (Validated in Phase 2)
- [x] Microsoft architecture design — maps HLD to concrete Azure/Microsoft services (Validated in Phase 2)
- [x] Agent control plane — UI for creating, configuring, and managing agents (Validated in Phase 3)
- [x] Model abstraction & routing layer — model-agnostic endpoint routing (Validated in Phase 3)
- [x] Multi-model routing — priority-based fallback chains with circuit breaker (Validated in Phase 3)
- [x] Tool marketplace — register, attach, discover, import tools (Validated in Phases 4, 8)
- [x] Data source management — connect and manage data sources per agent (Validated in Phase 4)
- [x] RAG system integration — Azure AI Search hybrid retrieval pipeline (Validated in Phase 4)
- [x] Platform AI Services — Azure AI capabilities as toggleable tools (Validated in Phase 4)
- [x] Memory management — short-term + long-term memory with pgvector (Validated in Phase 5)
- [x] Thread management — conversation thread lifecycle and persistence (Validated in Phase 5)
- [x] Sub-agent orchestration — parallel execution and sub-agent coordination (Validated in Phase 6)
- [x] Workflow builder — visual drag-and-drop flow editor (Validated in Phase 6)
- [x] Cost & token observability — dashboard with per-agent cost breakdowns (Validated in Phase 8)
- [x] Evaluation engine — test suites, metrics, version comparison (Validated in Phase 8)
- [x] Agent marketplace — discover, share, import agent templates (Validated in Phase 8)
- [x] Terminal & CLI execution — CLI with auth, agent listing, streamed execution (Validated in Phase 8)
- [x] Azure subscription integration — ARM discovery, connections, tool catalog (Validated in Phase 9)
- [x] Agent-level traces & monitoring — per-agent execution tracing and KPI dashboard (Validated in Phase 10)

### Active

- [ ] MCP client library — JSON-RPC client for MCP-compliant servers
- [ ] MCP server registry — CRUD for MCP server connections
- [ ] MCP tool discovery — automatic tool listing from servers
- [ ] MCP agent integration — MCP tools/call in agent execution loop
- [ ] MCP tool catalog UI — browse/search/filter MCP tools
- [ ] Agent-level MCP management — attach/detach MCP tools per agent
- [ ] Policy engine — governance, guardrails, and access control (deferred from v1.0)

### Out of Scope

- IaC / deployment scripts — focus is on architecture docs + running PoC code
- Mobile app — web-first platform
- Billing / payment system — internal enterprise platform, no customer billing
- Multi-cloud deployment — Microsoft-first, single-cloud architecture

## Context

- **Company:** STU-MSFT — internal enterprise AI platform team
- **Audience:** Manager presentation — demonstrate technical leadership, decisions made, and rationale
- **Deliverables:** Three-tier approach: (1) vendor-agnostic HLD with Mermaid diagrams, (2) Microsoft product-mapped architecture, (3) working PoC
- **Scale:** Designed for large-scale, multi-tenant enterprise deployment
- **Model strategy:** Bring-your-own-endpoint — customers provide model API endpoints, platform routes to them. Azure OpenAI as the default provider
- **Microsoft-first:** Product architecture maps to Microsoft services as extensively as possible
- **Current state:** v1.0 shipped (2026-03-24) — ~8,900 Python LOC (backend), ~10,800 TypeScript LOC (frontend), 10 Alembic migrations, 33 plans across 9 completed phases. v2.0 (MCP Tool Integration) in progress.

## Constraints

- **Tech Stack**: Python/FastAPI backend, React/Next.js frontend — chosen for AI ecosystem compatibility and modern web UX
- **Microsoft Products**: Use Microsoft services as extensively as possible for the product architecture mapping
- **Model Agnostic**: Must support any model endpoint provided by customers, not locked to a single vendor
- **Multi-tenant**: Secure isolation between tenants — agents, data, and execution environments must be fully isolated
- **Presentation-ready**: All documentation and PoC must be explainable — decisions documented with "why" rationale

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Custom execution loop + SK as optional SDK | All major platforms (Azure Foundry, Vertex AI, Bedrock) own their orchestration engine. SK provides Microsoft-aligned plugin abstractions without owning the core loop. LangGraph patterns borrowed for multi-agent graphs. | Decided |
| Azure AI Search as primary RAG + pgvector internal only | AI Search provides hybrid search, semantic ranking, indexers for tenant RAG at scale. pgvector limited to platform-internal embeddings (agent/tool similarity). | Decided |
| Platform-managed AI Services (Foundry-style) | Expose Azure AI Services as toggleable tools per agent. Platform handles auth (Managed Identity) and metering. Same pattern as Azure AI Foundry. | Decided |
| Python/FastAPI for backend | AI/ML ecosystem is Python-native; FastAPI provides async performance + automatic OpenAPI docs | — Pending |
| React/Next.js for frontend | Industry-standard for complex UIs; SSR for performance; rich component ecosystem | — Pending |
| Model-agnostic via customer endpoints | Avoids vendor lock-in; customers own their model relationships; platform focuses on orchestration not model hosting | — Pending |
| Three-tier deliverable (HLD → MSFT Arch → PoC) | Shows progression from abstract design thinking to concrete implementation; demonstrates architectural rigor for manager review | — Pending |
| Mermaid for HLD diagrams | Embeddable in markdown, version-controllable, no external tooling needed | — Pending |
| No IaC/deployment scripts | Keeps focus on architecture design + working code; deployment is separate concern for production readiness | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-24 after v1.0 milestone completion*
