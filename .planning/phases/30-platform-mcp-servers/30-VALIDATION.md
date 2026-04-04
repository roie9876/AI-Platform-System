---
phase: 30
slug: platform-mcp-servers
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 30 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && python -m pytest tests/test_mcp_platform_tools.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/test_mcp_platform_tools.py -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_mcp_platform_tools.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/test_mcp_platform_tools.py -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 30-01-01 | 01 | 1 | MCPSRV-01, MCPSRV-02 | unit | `pytest tests/test_mcp_platform_tools.py::test_memory_search -x` | ❌ W0 | ⬜ pending |
| 30-01-02 | 01 | 1 | MCPSRV-04, MCPSRV-05 | unit | `pytest tests/test_mcp_platform_tools.py::test_group_instructions -x` | ❌ W0 | ⬜ pending |
| 30-02-01 | 02 | 2 | MCPSRV-07 | infra | `grep -q 'memory_query_cache\|structured_memories' infra/modules/cosmos.bicep` | ❌ W0 | ⬜ pending |
| 30-02-02 | 02 | 2 | MCPSRV-06 | unit | `pytest tests/test_mcp_platform_tools.py::test_mcp_injection -x` | ❌ W0 | ⬜ pending |
| 30-03-01 | 03 | 3 | MCPSRV-01 | integration | `pytest tests/test_mcp_platform_tools.py::test_mcp_protocol -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_mcp_platform_tools.py` — stubs for MCPSRV-01, MCPSRV-02, MCPSRV-04, MCPSRV-05, MCPSRV-06, MCPSRV-07
- [ ] Test fixtures for mocked Cosmos containers and OpenAI embedding responses

*Existing pytest infrastructure and conftest.py cover framework setup.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| MCP tool appears in OpenClaw agent | MCPSRV-06 | Requires deployed K8s cluster | Deploy agent, check CR has `mcpServers.platform-tools` |
| DiskANN index operational | MCPSRV-07 | Requires live Cosmos DB | Run vector query against `agent_memories`, verify results ordered by similarity |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
