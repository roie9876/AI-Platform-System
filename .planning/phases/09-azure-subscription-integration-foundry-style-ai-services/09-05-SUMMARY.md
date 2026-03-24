---
phase: 09-azure-subscription-integration-foundry-style-ai-services
plan: 05
status: complete
started: 2025-03-24
completed: 2025-03-24
commits: [01ae951]
---

## Summary

Created the Foundry-style tool catalog modal and evolved the agent detail page into a split-pane config layout.

## Artifacts Created

### Task 1: Tool Catalog Modal
- **frontend/src/components/tools/catalog-tool-card.tsx** — Card with icon placeholder, name, description (line-clamp-1), dynamic badges (PreviewBadge, McpBadge, generic).
- **frontend/src/components/tools/tool-catalog-modal.tsx** — 3-tab modal (Configured/Catalog/Custom) with search + FilterBar on catalog tab, card grid for entries, CTA buttons per tab.

### Task 2: Agent Config Split-Pane
- **frontend/src/components/agent/agent-config-top-bar.tsx** — Top bar with back arrow, agent name, version dropdown, Save/Preview/More buttons, sub-nav tabs (Playground/Traces/Monitor/Evaluation).
- **frontend/src/components/agent/agent-config-layout.tsx** — 580px left panel (config) + flex-1 right panel (chat/YAML/code).
- **frontend/src/app/dashboard/agents/[id]/page.tsx** — Replaced old form-based agent edit with split-pane:
  - Left: Model selector, Instructions (textarea), Tools (with Add→catalog modal), Knowledge (KnowledgeSection), Memory (preview), Guardrails (preview)
  - Right: Chat/YAML/Code tabs with empty state chat UI

## Key Patterns
- ToolCatalogModal fetches both /api/v1/tools and /api/v1/catalog/entries on open
- CatalogToolCard dynamically renders PreviewBadge/McpBadge based on badge strings
- KnowledgeSection integrated in agent config via CollapsibleSection
- Purple (#7C3AED) accent on all active tabs, buttons, and selection rings
