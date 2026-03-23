# Phase 3: Agent Core & Model Abstraction - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-23
**Phase:** 03-agent-core-model-abstraction
**Areas discussed:** Agent management UI layout, Chat/conversation interface, Model endpoint key storage, Agent config versioning, Streaming UX

---

## Agent Management UI Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Cards | Card-based dashboard with agent info per card | ✓ |
| Table list | Tabular layout with sortable columns | |
| Multi-step wizard (creation) | Step-by-step agent creation flow | |
| Single form (creation) | All fields on one page | ✓ (implied) |

**User's choice:** Cards
**Notes:** Quick, decisive answer. No follow-up needed.

---

## Chat / Conversation Interface

| Option | Description | Selected |
|--------|-------------|----------|
| AI Foundry style | Sidebar + chat + config panel (three-panel layout) | ✓ |
| Simple chat | Standalone chat without config panel | |
| Minimal | Chat only, config on separate page | |

**User's choice:** "Like AI Foundry" — Azure AI Foundry playground layout
**Notes:** Follow-up questions asked:
1. Config panel alongside chat vs separate page → Foundry-style (alongside) assumed from reference
2. Model endpoint selector in chat → Switchable per Foundry deployment picker pattern assumed

---

## Model Endpoint Key Storage

| Option | Description | Selected |
|--------|-------------|----------|
| Entra ID / Managed Identity (Azure OpenAI) | No keys needed for Azure endpoints | ✓ |
| API keys in Azure Key Vault (non-Azure) | Production-grade secret storage | ✓ |
| API keys encrypted in PostgreSQL | Simple, self-contained | |
| Environment variables | Simplest, not scalable | |

**User's choice:** Dual strategy — Entra ID for Azure OpenAI, Azure Key Vault for other providers
**Notes:** User initially said "entra auth?" — clarified that Entra works for Azure OpenAI but non-Azure providers still need API keys. User then explicitly chose Azure Key Vault (option B) for non-Azure key storage.

---

## Agent Config Versioning Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Agent's discretion | Agent decides implementation approach | ✓ |

**User's choice:** "You decide"
**Notes:** No discussion needed — delegated to agent.

---

## Streaming UX Details

| Option | Description | Selected |
|--------|-------------|----------|
| Agent's discretion | Agent decides rendering approach | ✓ |

**User's choice:** "You decide"
**Notes:** No discussion needed — delegated to agent.

---

## Agent's Discretion

- Config versioning implementation approach (snapshots table vs JSON diff, rollback mechanism)
- Streaming UX rendering (typing cursor, word chunks, loading states, error recovery)

## Deferred Ideas

None — discussion stayed within phase scope.
