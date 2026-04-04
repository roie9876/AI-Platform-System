---
phase: 30-platform-mcp-servers
plan: 02
subsystem: mcp
tags: [fastmcp, cosmos-db, agent-config, whatsapp-groups]

requires:
  - phase: 30-01
    provides: FastMCP server, main.py with tool registration pattern
provides:
  - Platform config tools (get_group_instructions, get_agent_config, list_configured_groups)
  - 7 total MCP tools on the server
affects: [30-03-infra]

tech-stack:
  added: []
  patterns: [read_item for single-doc lookup from agents container]

key-files:
  created:
    - backend/microservices/mcp_platform_tools/platform_config.py
    - backend/tests/test_mcp_platform_config.py
  modified:
    - backend/microservices/mcp_platform_tools/main.py

key-decisions:
  - "Direct Cosmos read_item instead of query (agent_id is the document ID)"
  - "system_prompt truncated to 100 chars in list_configured_groups to reduce token usage"
  - "openclaw_config stripped from get_agent_config response to avoid leaking sensitive config"

patterns-established:
  - "Platform config tools read from agents container via read_item with partition_key=tenant_id"

requirements-completed: [MCPSRV-04, MCPSRV-05]

duration: 8min
completed: 2026-04-04
---

# Phase 30, Plan 02: Platform Config Tools Summary

**3 platform config tools reading agent/group configuration from Cosmos DB — 7 total tools on server**

## What Was Built

- `platform_config.py`: Three tools: `get_group_instructions` (per-group systemPrompt + settings), `get_agent_config` (safe fields only), `list_configured_groups` (all groups with truncated prompts)
- Updated `main.py` with 3 additional `@mcp.tool()` registrations (7 total)
- 4 unit tests covering found/not-found groups, agent config safety, group listing

## Self-Check: PASSED

- [x] 3 platform config tools implemented
- [x] All read from Cosmos agents container — no K8s API dependency
- [x] Sensitive config (openclaw_config internals) not exposed in tool responses
- [x] 7 total @mcp.tool() registrations
- [x] All 4 unit tests passing
