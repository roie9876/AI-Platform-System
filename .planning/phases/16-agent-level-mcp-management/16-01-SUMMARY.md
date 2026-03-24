---
phase: 16-agent-level-mcp-management
plan: 01
status: complete
started: "2026-03-24"
completed: "2026-03-24"
---

# Summary: Agent MCP Tool API (Plan 01)

## What Was Built

REST API endpoints for attaching, detaching, and listing MCP tools on agents, following the existing agent-tool attachment pattern.

### Files Created

| File | Purpose |
|------|---------|
| `backend/app/api/v1/agent_mcp_tools.py` | Agent MCP tool attach/detach/list API endpoints |
| `backend/tests/test_agent_mcp_tools_api.py` | 8 unit tests covering all endpoints and error cases |

### Files Modified

| File | Change |
|------|--------|
| `backend/app/api/v1/schemas.py` | Added AgentMCPToolAttachRequest, AgentMCPToolResponse schemas |
| `backend/app/api/v1/router.py` | Registered agent_mcp_tools_router at /agents prefix |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/agents/{id}/mcp-tools | Attach MCP tool to agent |
| DELETE | /api/v1/agents/{id}/mcp-tools/{tool_id} | Detach MCP tool from agent |
| GET | /api/v1/agents/{id}/mcp-tools | List MCP tools attached to agent |

## Key Decisions

- AgentMCPToolResponse includes denormalized tool_name, description, server_id, server_name, is_available — avoids N+1 queries on frontend
- Follows exact same pattern as existing AgentTool endpoints (tenant verification, duplicate 409, not-found 404)
- List endpoint joins AgentMCPTool → MCPDiscoveredTool → MCPServer for complete data

## Requirements Addressed

- **MCP-16**: Attach and detach MCP tools to specific agents ✅
- **MCP-17**: Per-agent MCP server configuration (via tool-level granularity) ✅

## Verification

- 8/8 tests pass (`pytest tests/test_agent_mcp_tools_api.py`)
- Router imports cleanly (`from app.api.v1.agent_mcp_tools import router`)
