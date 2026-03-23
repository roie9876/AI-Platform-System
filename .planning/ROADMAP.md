# Roadmap: AI Agent Platform as a Service

**Created:** 2026-03-23
**Milestone:** v1.0 — Full-featured AI Agent Platform PoC
**Granularity:** Standard (8 phases)

## Milestone 1: v1.0 — AI Agent Platform PoC

### Phase 1: Foundation & Project Scaffold
**Goal:** Establish the project structure, database schema, authentication, and API skeleton that all subsequent phases build on.
**Requirements:** [TERM-02]
**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — Project scaffold: backend skeleton + frontend scaffold + Docker
- [x] 01-02-PLAN.md — Database models + auth endpoints + multi-tenant middleware
- [x] 01-03-PLAN.md — Frontend auth UI + end-to-end integration verification

**Success Criteria:**
1. FastAPI backend serves requests on localhost with OpenAPI docs
2. Next.js frontend renders and connects to backend API
3. PostgreSQL database initialized with base schema (tenants, users)
4. JWT authentication works (login, token refresh, protected routes)
5. Multi-tenant middleware auto-filters queries by tenant_id

**UI hint**: yes

---

### Phase 2: HLD & Microsoft Architecture Documentation
**Goal:** Create comprehensive vendor-agnostic HLD with Mermaid diagrams and Microsoft product-mapped architecture with detailed system flows and decision rationale.
**Requirements:** [ARCH-01, ARCH-02, ARCH-03]
**Plans:** 2 plans

Plans:
- [x] 02-01-PLAN.md — Core HLD document with system architecture, Mermaid diagrams, Azure service mappings, SKUs, and pricing
- [x] 02-02-PLAN.md — ADR appendix, inline technology comparisons, and human verification

**Success Criteria:**
1. HLD document exists with Mermaid diagrams for control plane, runtime plane, data flows, and security boundaries
2. Microsoft architecture document maps every HLD component to specific Azure services
3. Each major decision has documented rationale explaining "the why"
4. Architecture covers all 11 feature areas from requirements

---

### Phase 3: Agent Core & Model Abstraction
**Goal:** Build the agent CRUD UI, model endpoint registry, and model abstraction layer so users can create agents, register model endpoints, and execute basic agent conversations with streaming.
**Requirements:** [AGNT-01, AGNT-02, AGNT-03, AGNT-04, MODL-01, MODL-02, MODL-03, MODL-04]
**Plans:** 4 plans

Plans:
- [x] 03-01-PLAN.md — Backend models, migrations, Agent + ModelEndpoint CRUD APIs
- [ ] 03-02-PLAN.md — Model abstraction layer (LiteLLM), agent execution engine, SSE streaming
- [ ] 03-03-PLAN.md — Frontend agent dashboard, model endpoint management UI
- [ ] 03-04-PLAN.md — Frontend AI Foundry-style chat interface + human verification

**Success Criteria:**
1. User can create/edit/delete an agent through the UI
2. User can register model endpoints and assign them to agents
3. Agent execution routes through model abstraction layer to configured endpoint
4. Model responses stream to the UI in real-time (SSE)
5. Fallback mechanism activates when primary model endpoint fails
6. Agent config versioning tracks changes with rollback capability

**UI hint**: yes

---

### Phase 4: Tools, Data Sources, RAG & Platform AI Services
**Goal:** Build the tool registry, sandboxed tool execution, data source management, RAG pipeline (via Azure AI Search), and platform-managed AI capabilities so agents can use custom tools, access knowledge from connected data sources, and leverage Azure AI Services as toggleable platform tools.
**Requirements:** [TOOL-01, TOOL-02, TOOL-03, DATA-01, DATA-02, DATA-03, AISV-01, AISV-02]
**Plans:** [To be planned]

**Success Criteria:**
1. User can register tools with JSON Schema and attach them to agents
2. Agent can invoke tools during execution with validated inputs
3. Tool execution runs in sandboxed environment with timeout
4. User can connect data sources and credentials are stored securely
5. RAG pipeline ingests documents via Azure AI Search (hybrid vector + keyword search) and retrieves relevant chunks
6. Agent responses incorporate RAG context from connected data sources
7. Platform AI Services (search, content safety, document intelligence) available as toggleable platform tools
8. Platform tool adapter authenticates to Azure AI Services via Managed Identity — no API keys exposed to users

**UI hint**: yes

---

### Phase 5: Memory & Thread Management
**Goal:** Build thread lifecycle management, short-term conversation memory, long-term persistent memory with vector search, and state management for agent executions.
**Requirements:** [MEMO-01, MEMO-02, MEMO-03, THRD-01, THRD-02]
**Plans:** [To be planned]

**Success Criteria:**
1. User can create, view, resume, and delete conversation threads
2. Short-term memory maintains conversation history within a thread
3. Long-term memory persists knowledge across sessions via vector store
4. Memory is isolated per-agent, per-user, and per-tenant
5. Execution history captures full audit trail with state snapshots

**UI hint**: yes

---

### Phase 6: Orchestration & Workflow Engine
**Goal:** Build the workflow engine supporting sequential, parallel, and autonomous agent execution with sub-agent delegation and a visual workflow builder UI.
**Requirements:** [ORCH-01, ORCH-02, ORCH-03, ORCH-04, ORCH-05, THRD-03]
**Plans:** [To be planned]

**Success Criteria:**
1. User can chain agents sequentially with output-to-input mapping
2. User can run agents in parallel with result aggregation
3. Agents can spawn sub-agents during execution
4. Visual workflow builder allows drag-and-drop agent flow creation
5. Autonomous mode allows agents to determine their own execution flow
6. Cross-agent threading maintains context across workflow nodes

**UI hint**: yes

---

### Phase 7: Policy Engine & Governance
**Goal:** Build the policy engine with content filtering, rate limiting, RBAC, and comprehensive audit logging to ensure secure and governed agent operations.
**Requirements:** [PLCY-01, PLCY-02, PLCY-03, PLCY-04]
**Plans:** [To be planned]

**Success Criteria:**
1. Content filtering blocks harmful inputs/outputs on agent execution
2. Rate limits enforce per-agent, per-user, and per-tenant thresholds
3. RBAC restricts access to agents, tools, and data sources by role
4. Audit logs capture all agent actions, user operations, and policy events
5. Policies apply at global, tenant, and agent levels with correct precedence

---

### Phase 8: Observability, Evaluation, Marketplace & CLI
**Goal:** Build the cost/token observability dashboard, evaluation engine, agent/tool marketplace, and CLI to complete the full platform feature set.
**Requirements:** [COST-01, COST-02, COST-03, COST-04, EVAL-01, EVAL-02, EVAL-03, AGNT-05, TOOL-04, TERM-01, AISV-03]
**Plans:** [To be planned]

**Success Criteria:**
1. Token counting tracks input/output tokens per request
2. Cost dashboard shows per-agent, per-team, per-model breakdowns
3. Cost alerts fire when spending exceeds configured thresholds
4. User can create test suites and run evaluations against agents
5. Evaluation dashboard compares agent versions
6. Agent marketplace allows discovering and importing agent templates
7. Tool marketplace allows discovering and importing shared tools
8. CLI can execute agents and display results

**UI hint**: yes

---

## Phase Dependencies

```
Phase 1 (Foundation)
    │
    ├──► Phase 2 (HLD & Architecture) — can start after foundation is understood but no code dependency
    │
    └──► Phase 3 (Agent Core & Model)
              │
              ├──► Phase 4 (Tools & Data & RAG)
              │         │
              │         └──► Phase 5 (Memory & Threads)
              │                   │
              │                   └──► Phase 6 (Orchestration)
              │
              └──► Phase 7 (Policy & Governance) — can start after Phase 3
              │
              └──► Phase 8 (Observability & Eval & Marketplace) — needs Phase 3+4+5
```

## Coverage Check

- v1 requirements: 45 total
- Mapped to phases: 45
- Unmapped: 0
- All requirements covered ✓

---
*Roadmap created: 2026-03-23*
*Last updated: 2026-03-23 after initialization*
