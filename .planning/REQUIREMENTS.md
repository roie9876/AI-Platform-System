# Requirements: v2.0 MCP Tool Integration

## MCP Client

- [ ] **MCP-01**: User can connect to any MCP-compliant server via JSON-RPC over Streamable HTTP transport
- [ ] **MCP-02**: User can list available tools from a connected MCP server via tools/list
- [ ] **MCP-03**: User can invoke tools on a connected MCP server via tools/call with proper parameter passing

## MCP Server Management

- [ ] **MCP-04**: User can register a new MCP server connection with URL, authentication, and metadata
- [ ] **MCP-05**: User can list, update, and delete registered MCP server connections
- [ ] **MCP-06**: User can view connection status and health of registered MCP servers

## MCP Tool Discovery

- [ ] **MCP-07**: Platform automatically discovers tools from registered MCP servers on registration and periodic refresh
- [ ] **MCP-08**: User can see all discovered MCP tools across all registered servers in a unified view
- [ ] **MCP-09**: Platform performs health checks on MCP servers and handles reconnection on failure

## Agent MCP Integration

- [ ] **MCP-10**: Agent execution loop can invoke MCP tools alongside platform adapters and sandbox tools
- [ ] **MCP-11**: MCP tool calls follow the same observability pipeline (cost tracking, execution logs, traces)
- [ ] **MCP-12**: Agent can use MCP tools in workflows (sequential, parallel, autonomous, custom DAG)

## MCP Tool Catalog UI

- [ ] **MCP-13**: User can browse and search MCP tools in a Foundry-style catalog interface
- [ ] **MCP-14**: User can filter MCP tools by server, category, and capability
- [ ] **MCP-15**: User can view tool details including input schema, description, and server source

## Agent-Level MCP Management

- [ ] **MCP-16**: User can attach and detach MCP tools to specific agents
- [ ] **MCP-17**: User can configure per-agent MCP server connections
- [ ] **MCP-18**: Agent detail page shows attached MCP tools with status

## Future Requirements

- [ ] Policy engine — governance, guardrails, and access control (deferred from v1.0)

## Out of Scope

- MCP server implementation — platform is MCP client only, not a server host
- Stdio transport — Streamable HTTP only for remote MCP servers
- MCP resource/prompt capabilities — tools only for v2.0

## Traceability

| Requirement | Phase | Plan | Status |
|-------------|-------|------|--------|
| MCP-01 | 11 | — | Pending |
| MCP-02 | 11 | — | Pending |
| MCP-03 | 11 | — | Pending |
| MCP-04 | 12 | — | Pending |
| MCP-05 | 12 | — | Pending |
| MCP-06 | 12 | — | Pending |
| MCP-07 | 13 | — | Pending |
| MCP-08 | 13 | — | Pending |
| MCP-09 | 13 | — | Pending |
| MCP-10 | 14 | — | Pending |
| MCP-11 | 14 | — | Pending |
| MCP-12 | 14 | — | Pending |
| MCP-13 | 15 | — | Pending |
| MCP-14 | 15 | — | Pending |
| MCP-15 | 15 | — | Pending |
| MCP-16 | 16 | — | Pending |
| MCP-17 | 16 | — | Pending |
| MCP-18 | 16 | — | Pending |

---
*Created: 2026-03-24*
