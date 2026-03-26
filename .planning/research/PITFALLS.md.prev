# Pitfalls Research: AI Agent Platform as a Service

## Critical Pitfalls

### 1. Model Abstraction Leaks

**Warning signs:** Different models return different response formats, tool calling semantics vary, streaming protocols differ across providers.

**Prevention:**
- Build a strict internal format (adopt OpenAI's format as canonical)
- Normalize ALL model responses through an adapter layer before they reach agent logic
- Test with at least 2 model providers from day one (don't assume OpenAI format is universal)
- Handle edge cases: some models don't support function calling, some don't stream, some have different token counting

**Phase to address:** Phase 2 (Agent Core / Model Abstraction)

### 2. Multi-Tenant Data Leaks

**Warning signs:** Missing tenant_id filters in queries, shared caches without namespace isolation, logs containing cross-tenant data.

**Prevention:**
- Enforce tenant_id at the ORM/repository layer (middleware that auto-filters, not manual WHERE clauses)
- Use PostgreSQL Row-Level Security (RLS) as a second defense layer
- Namespace Redis keys with tenant_id prefix
- Audit every database query during code review for tenant isolation
- Never log sensitive data; always include tenant_id in log context

**Phase to address:** Phase 1 (Foundation — bake this in from the start)

### 3. Runaway Agent Costs

**Warning signs:** Agent loops calling models repeatedly, workflows with no termination condition, tool calls that trigger more model calls.

**Prevention:**
- Hard limits: max iterations per agent run (default: 10), max tokens per run, max execution time
- Circuit breakers on model calls (stop after N consecutive errors)
- Cost tracking in real-time, not just post-hoc
- Budget enforcement middleware that rejects calls when quota exceeded
- Workflow termination conditions are REQUIRED, not optional

**Phase to address:** Phase 2 (Agent Core) for basic limits, Phase 7 (Observability) for dashboards

### 4. Memory/Context Window Overflow

**Warning signs:** Conversations that grow beyond model context limits, RAG retrievals that add too much context, system prompts that consume most of the window.

**Prevention:**
- Token budgeting: allocate context window between system prompt, memory, RAG, conversation history
- Sliding window for conversation history (keep last N messages, or last N tokens)
- Memory summarization: compress old messages into summaries
- RAG result limits: max chunks, max tokens from retrieval
- Always count tokens before sending to model, truncate if necessary

**Phase to address:** Phase 4 (Memory & Threads)

### 5. Tool Execution Security

**Warning signs:** Tools that execute arbitrary code, tools that access internal network resources, tools that leak credentials.

**Prevention:**
- Sandboxed tool execution (don't run tools in the main process)
- Tool input validation against JSON Schema before execution
- Network isolation for tool execution (no access to internal services)
- Tool output size limits (prevent memory exhaustion)
- Timeouts on every tool execution
- Never pass tenant credentials to tool execution environment

**Phase to address:** Phase 3 (Tools & Data)

### 6. Workflow Deadlocks and Infinite Loops

**Warning signs:** Agent A waits for Agent B which waits for Agent A, autonomous agents that never reach a terminal state.

**Prevention:**
- Workflow engine must validate DAGs for cycles before execution
- Global timeout per workflow execution
- Maximum depth for sub-agent spawning (prevent recursive agent creation)
- Autonomous mode requires explicit termination conditions
- Dead letter queue for stuck workflow nodes

**Phase to address:** Phase 5 (Orchestration)

### 7. Database Schema Rigidity vs. Agent Config Flexibility

**Warning signs:** Frequent schema migrations as agent configs evolve, rigid column definitions for flexible agent parameters.

**Prevention:**
- Use JSONB columns for agent configuration (flexible schema within a typed container)
- Keep relational structure for queries that need indexing (status, tenant_id, created_at)
- Version agent configs: store the full config blob per version, don't diff
- Define a core schema that's stable, use JSONB for everything that might change

**Phase to address:** Phase 1 (Foundation — database schema design)

### 8. WebSocket Scalability

**Warning signs:** WebSocket connections break on server restart, connections don't survive load balancer routing changes, message ordering issues.

**Prevention:**
- Use Redis pub-sub for WebSocket message delivery (not in-memory)
- Connection registry in Redis (which server handles which connection)
- Reconnection logic on the client with exponential backoff
- Consider Server-Sent Events (SSE) as simpler alternative for streaming (one-way is usually sufficient)
- Heartbeat/ping-pong to detect dead connections

**Phase to address:** Phase 2 (Agent Core — streaming)

### 9. Evaluation That Doesn't Measure What Matters

**Warning signs:** Evaluating string similarity when task is creative, measuring latency when quality is the issue, no baseline to compare against.

**Prevention:**
- Define evaluation criteria per agent type (not one-size-fits-all)
- Always include human evaluation in the loop (automated metrics are supplementary)
- LLM-as-judge pattern: use a stronger model to evaluate a weaker model's output
- Track metrics over time, not just point-in-time scores
- Test suite should cover edge cases, not just happy path

**Phase to address:** Phase 7 (Evaluation)

### 10. PoC vs Production Gap

**Warning signs:** PoC works for 1 user but breaks at 10, PoC has hardcoded configs, PoC skips auth/security entirely.

**Prevention:**
- Build with multi-tenancy from day one (even if PoC has one tenant)
- Use real auth (even if simplified — JWT tokens, not hardcoded API keys)
- Use real database (PostgreSQL, not SQLite in memory)
- Build observability hooks from the start (even if dashboard comes later)
- Use environment variables for config, not hardcoded values

**Phase to address:** Phase 1 (Foundation — establish patterns)

## Common Mistakes by Phase

| Phase | Common Mistake | Better Approach |
|-------|---------------|-----------------|
| Foundation | Building auth from scratch | Use Microsoft Entra ID / standard JWT; don't reinvent |
| Agent Core | Tight coupling to one model SDK | Abstract early; model-agnostic interface |
| Tools | Running tools in main process | Isolated execution; separate process/container |
| Memory | Treating memory as simple key-value | Structured memory with metadata, TTL, scope |
| Orchestration | Sequential-only at first, parallel "later" | Build async execution from start; sequential is a special case of parallel |
| Governance | Adding policies as afterthought | Policy middleware from day one; retroactive policies miss edge cases |
| Observability | Logging everything | Structured telemetry with sampling; log less, measure more |

---
*Researched: 2026-03-23*
