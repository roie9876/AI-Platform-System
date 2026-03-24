# Phase 9: Azure Subscription Integration & Foundry-Style AI Services - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-24
**Phase:** 09-azure-subscription-integration-foundry-style-ai-services
**Areas discussed:** Subscription Authentication, Resource Discovery, Connection Management, Tool Catalog & Knowledge UX, UI Visual Design

---

## Subscription Authentication Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Service principal registration | Tenant registers app registration + client secret | |
| OAuth consent flow (Entra ID) | Admin authenticates via web portal using Azure Portal credentials | ✓ |
| Managed Identity | Platform uses its own managed identity | |

**User's choice:** OAuth consent flow — admin logs in with same credentials as Azure portal. Backend uses admin's token to call ARM APIs.
**Notes:** Multi-subscription support required — admin can select more than one subscription. No service principal or client secret management needed.

---

## Resource Discovery UX

| Option | Description | Selected |
|--------|-------------|----------|
| Show all resources across types | Discover everything in subscription | |
| Type-filtered discovery | User picks resource type, discover matching resources | ✓ |
| Region-grouped view | Group by Azure region | |

**User's choice:** Type-filtered — user selects the type of resource they want to connect (e.g., AI Search), platform discovers all matching resources across connected subscriptions.
**Notes:** Resources shown with name + region badge matching Foundry dropdown pattern.

---

## Connection Management

**User's choice:** "You decide" — agent's discretion
**Notes:** Downstream planner decides connection model, health checks, and UI integration.

---

## Tool Catalog & Knowledge UX

| Option | Description | Selected |
|--------|-------------|----------|
| Foundry 3-tab pattern | Configured / Catalog / Custom tabs in modal | ✓ |
| Flat tool list | Simple list of all available tools | |
| Category-grouped page | Full page with tool categories | |

**User's choice:** Mirror Foundry's exact 3-tab pattern. User provided 10 screenshots of Foundry portal as visual reference.
**Notes:**
- Knowledge as separate section (sidebar + agent config collapsible) matching Foundry IQ
- AI Search resource picker dropdown → auth type selector → Connect → browse indexes
- Initial connectors: AI Search, Cosmos DB, PostgreSQL
- Knowledge connects to existing Phase 4 RAG pipeline

---

## UI Visual Design

| Option | Description | Selected |
|--------|-------------|----------|
| Match Foundry look & feel | Purple accent, white backgrounds, same card/badge styling | ✓ |
| Keep existing platform style | Continue with current dashboard design | |
| Custom design system | Create our own distinct visual identity | |

**User's choice:** Match Foundry's visual design — purple accent color, clean white layout, card styling, region badges, collapsible sections, table layouts.
**Notes:** User explicitly requested "make the UI color look and feel the same" as Foundry. Agent config page should mirror Foundry's split-pane playground layout. Sidebar should include all Foundry nav items (unbuilt features show as disabled with "Preview" badge).

---

## Agent's Discretion

- ARM API pagination and caching strategy
- OAuth token refresh and storage mechanism
- Tool catalog data storage approach (hardcoded vs database)
- Connection model structure and health check strategy

## Deferred Ideas

- Workflows, Fine-tune, Data, Evaluations, Guardrails pages (Phases 5-8)
- Memory section in agent config (Phase 5)
- Additional catalog connectors beyond AI Search, Cosmos DB, PostgreSQL (v2)
- "Ask AI" search bar and suggestion chips (v2)
- Voice mode toggle (v2)
