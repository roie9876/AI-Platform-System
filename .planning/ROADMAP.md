# Roadmap: AI Agent Platform as a Service

**Created:** 2026-03-23
**Active Milestone:** v2.0 — MCP Tool Integration

## Milestones

- ✅ **v1.0 AI Agent Platform PoC** — Phases 1-10 (shipped 2026-03-24) — [archive](milestones/v1.0-ROADMAP.md)
- 🚧 **v2.0 MCP Tool Integration** — Phases 11-16 (in progress)

<details>
<summary>✅ v1.0 AI Agent Platform PoC (Phases 1-10) — SHIPPED 2026-03-24</summary>

- [x] Phase 1: Foundation & Project Scaffold (3 plans)
- [x] Phase 2: HLD & Microsoft Architecture Documentation (2 plans)
- [x] Phase 3: Agent Core & Model Abstraction (4 plans)
- [x] Phase 4: Tools, Data Sources, RAG & Platform AI Services (5 plans)
- [x] Phase 5: Memory & Thread Management (3 plans)
- [x] Phase 6: Orchestration & Workflow Engine (3 plans)
- [ ] Phase 7: Policy Engine & Governance (skipped — deferred to future milestone)
- [x] Phase 8: Observability, Evaluation, Marketplace & CLI (6 plans)
- [x] Phase 9: Azure Subscription Integration & Foundry-Style AI Services (5 plans)
- [x] Phase 10: Agent-Level Traces & Monitor Tabs (2 plans)

**Known Gaps:**
- Phase 7 (Policy Engine & Governance) was not implemented — PLCY-01 through PLCY-04 deferred

</details>

## Milestone 2: v2.0 — MCP Tool Integration

**Goal:** Add Model Context Protocol (MCP) client support to unlock 1500+ Remote MCP tool servers, bringing Foundry-style tool catalog capabilities to the platform.

### Phase 11: MCP Client Library

**Goal:** Build a JSON-RPC client implementing initialize, tools/list, tools/call over HTTP (SSE/Streamable HTTP) to communicate with any MCP-compliant server.
**Requirements:** [MCP-01, MCP-02, MCP-03]
**Depends on:** Phase 4
**Plans:** 1 plan

Plans:
- [ ] 11-01-PLAN.md — MCP types, MCPClient class (Streamable HTTP transport), unit tests

### Phase 12: MCP Server Registry

**Goal:** Build DB models and CRUD APIs for registering Remote MCP server connections (URL, auth, metadata) so users can manage their MCP server fleet.
**Requirements:** [MCP-04, MCP-05, MCP-06]
**Depends on:** Phase 11
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 12 to break down)

### Phase 13: MCP Tool Discovery

**Goal:** Implement automatic tool discovery from registered MCP servers via tools/list, with health checking and reconnection logic to keep the tool catalog current.
**Requirements:** [MCP-07, MCP-08, MCP-09]
**Depends on:** Phase 11, Phase 12
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 13 to break down)

### Phase 14: Agent Execution Integration

**Goal:** Wire MCP tools/call into the existing agent tool-calling loop alongside platform adapters and sandbox tools, making MCP a third execution path.
**Requirements:** [MCP-10, MCP-11, MCP-12]
**Depends on:** Phase 11, Phase 13
**Plans:** 1 plan

Plans:
- [x] 14-01-PLAN.md — AgentMCPTool model, MCP execution path in agent loop, tests

### Phase 15: MCP Tool Catalog UI

**Goal:** Build a Foundry-style catalog UI to browse, search, and filter all available MCP tools across registered servers.
**Requirements:** [MCP-13, MCP-14, MCP-15]
**Depends on:** Phase 12, Phase 13
**Plans:** 1 plan

**UI hint**: yes

Plans:
- [ ] 15-01-PLAN.md — Sidebar nav, tool detail panel, Foundry-style catalog enhancements

### Phase 16: Agent-Level MCP Management

**Goal:** Enable attach/detach of MCP tools to agents with per-agent MCP server configuration, completing the agent-MCP integration.
**Requirements:** [MCP-16, MCP-17, MCP-18]
**Depends on:** Phase 14, Phase 15
**Plans:** 2 plans

**UI hint**: yes

Plans:
- [ ] 16-01-PLAN.md — Backend API for agent MCP tool attach/detach/list + tests
- [ ] 16-02-PLAN.md — Agent detail page MCP Tools section with attach/detach UI

## Phase Dependencies

```
Phase 11 (MCP Client Library)
    │
    ├──► Phase 12 (MCP Server Registry)
    │         │
    │         └──► Phase 13 (MCP Tool Discovery)
    │                   │
    │                   ├──► Phase 14 (Agent Execution Integration)
    │                   │         │
    │                   │         └──► Phase 16 (Agent-Level MCP Management)
    │                   │
    │                   └──► Phase 15 (MCP Tool Catalog UI)
    │                             │
    │                             └──► Phase 16 (Agent-Level MCP Management)
```

---
*Roadmap created: 2026-03-23*
*Last updated: 2026-03-24 after v1.0 milestone completion*
