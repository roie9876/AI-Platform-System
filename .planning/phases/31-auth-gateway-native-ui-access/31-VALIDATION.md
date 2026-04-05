---
phase: 31
slug: auth-gateway-native-ui-access
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-05
---

# Phase 31 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend), manual curl/browser (infra) |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && python -m pytest tests/test_auth_gateway.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 31-01-01 | 01 | 1 | NATIVEUI-01, NATIVEUI-02, NATIVEUI-03 | unit | `python -m pytest tests/test_auth_gateway.py -x` | ❌ W0 | ⬜ pending |
| 31-01-02 | 01 | 1 | NATIVEUI-04 | unit | `python -m pytest tests/test_auth_gateway.py::test_websocket -x` | ❌ W0 | ⬜ pending |
| 31-02-01 | 02 | 2 | NATIVEUI-01 | manifest | `kubectl apply --dry-run=client -f k8s/base/auth-gateway/` | ✅ | ⬜ pending |
| 31-03-01 | 03 | 3 | NATIVEUI-05 | build | `cd frontend && npx next build` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_auth_gateway.py` — stubs for auth flow, session management, agent resolution, WebSocket proxy
- [ ] Mock fixtures for MSAL, Cosmos, httpx in conftest

*Existing test infrastructure (conftest.py, pytest config) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full OIDC browser login flow | NATIVEUI-02 | Requires real Entra ID redirect | Visit `agent-{id}.agents.{domain}`, complete login, verify UI loads |
| WebSocket live chat in native UI | NATIVEUI-04 | Requires running OpenClaw pod | Open native UI, send chat message, verify real-time response |
| Cross-tenant access blocked | NATIVEUI-03 | Requires two real tenant sessions | Login as tenant A, access tenant B's agent URL, verify 403 |
| "Open Agent Console" button | NATIVEUI-05 | Visual verification | Open agent detail page, verify button links to correct subdomain |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
