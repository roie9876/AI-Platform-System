# Phase 30: Platform MCP Servers - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** 30-platform-mcp-servers
**Areas discussed:** Memory Architecture Depth, Memory Data Model, Embedding & Search Strategy, MCP Server Architecture, Group Rules & Agent Config Scope

---

## Memory Architecture Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Tier 1+2 (recommended) | Core memory (store/retrieve/vector search) + High Value (entity extraction, structured memory, query cache, time-decay) | ✓ |
| Tier 1 only | Minimal — just store/retrieve/vector search | |
| Tier 1+2+3 | Everything including graph, episodes, procedural, reranking, event sourcing | |

**User's choice:** Tier 1 + Tier 2
**Notes:** Tier 3 deferred to future phase. Architecture inspired by ClawMongo's 26 capabilities but ported to Azure-native services.

---

## Memory Data Model

| Option | Description | Selected |
|--------|-------------|----------|
| A: Single container | Everything in `agent_memories` with `type` field | |
| B: Multiple containers | Separate containers per concern (~15 containers like ClawMongo) | |
| C: Hybrid (recommended) | `agent_memories` (DiskANN) primary + `memory_query_cache` (TTL) + `structured_memories` (key-value) | ✓ |

**User's choice:** Option C — Hybrid
**Notes:** Avoids over-fragmenting while keeping cache and structured facts separate from vector-searchable memories.

---

## Embedding & Search Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| A: Cosmos DiskANN only | All search through DiskANN, no AI Search | |
| B: Azure AI Search only | All search through AI Search, requires extra resource | |
| C: DiskANN + AI Search split (recommended) | DiskANN for memory, AI Search for document retrieval only | ✓ |

**User's choice:** Option C — Split by domain
**Notes:** AI Search resource and MCPSRV-03 (`search_documents`) deferred until document indexes are actually needed. Phase 30 ships with DiskANN only.

---

## MCP Server Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| A: Single monolithic server | One service, all tools, no internal separation | |
| B: Separate servers per domain | `mcp-memory` + `mcp-platform`, two deployments | |
| C: Single modular server (recommended) | One deployment, separate internal modules per domain, Python MCP SDK | ✓ |

**User's choice:** Option C — Single modular server with Python MCP SDK
**Notes:** Adopts proper MCP SDK instead of raw HTTP pattern used by existing servers. One URL simplifies agent configuration. Modular code supports splitting later if needed.

---

## Group Rules & Agent Config Scope

| Option | Description | Selected |
|--------|-------------|----------|
| A: Read from K8s CR | MCP server calls K8s API to read OpenClawInstance CR | |
| B: Read from Cosmos (duplicate) | Dual-write to Cosmos, read from there | |
| C: Read from Cosmos (source of truth) (recommended) | Cosmos is already the source of truth, CR is generated from it | ✓ |

**User's choice:** Option C — Cosmos DB as source of truth
**Notes:** Matches existing architecture. `openclaw_service.py` already builds CRs from Cosmos data. MCP server reads the same data. No K8s API dependency, no duplication.

---

## Agent's Discretion

- Memory document schema (fields, metadata)
- Entity extraction approach (regex vs LLM)
- Query cache TTL and eviction
- Time-decay scoring formula
- Structured memory key conventions
- K8s resource limits and HPA thresholds
- Health check endpoint design
- MCP tool parameter schemas
- Tenant/agent identification method for MCP tools

## Deferred Ideas

- Tier 3 memory capabilities (knowledge graph, episodes, procedural, reranking, event sourcing, LLM planner)
- Azure AI Search resource provisioning and MCPSRV-03 (`search_documents`)
- MCP server splitting into separate services
