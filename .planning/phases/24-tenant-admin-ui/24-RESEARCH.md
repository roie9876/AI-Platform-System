# Phase 24: Tenant Admin UI — Research

**Researched:** 2026-03-26
**Phase:** 24-tenant-admin-ui
**Goal:** Platform admins can manage tenants and tenant admins can manage their team through the web UI
**Requirements:** UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, TENANT-08

## Domain Analysis

### What This Phase Delivers

A set of frontend pages and components in Next.js (App Router) that consume the tenant management API (Phase 21) and observability API (Phase 23/08) to provide:

1. **Global tenant selector** — dropdown in top bar for platform admins to switch tenant context; all pages automatically filter by selected tenant
2. **Platform admin dashboard** — table/card listing all tenants with status, agent counts, user counts, resource usage
3. **Tenant onboarding wizard** — multi-step form: org name → Entra ID config → model endpoint → first agent → review & create
4. **Tenant settings page** — configure display name, allowed features, token quotas (tenant admin scope)
5. **User management page** — view users, assign roles, invite via Entra ID groups (tenant admin scope)
6. **Usage summary** — per-tenant API calls, agent executions, token consumption, cost estimates

### Existing Backend APIs Available

**Tenant API** (`/api/v1/tenants`) — from Phase 21:
- `POST /` — create tenant (name, slug, admin_email)
- `GET /` — list all tenants (optional status filter)
- `GET /{tenant_id}` — get single tenant
- `PATCH /{tenant_id}` — update tenant (name, admin_email)
- `PATCH /{tenant_id}/state` — transition lifecycle state
- `PATCH /{tenant_id}/settings` — update settings (display_name, allowed_providers, token_quota, feature_flags)
- `DELETE /{tenant_id}` — delete tenant

All tenant endpoints require `platform_admin` role.

**Observability API** (`/api/v1/observability`) — from Phase 08/23:
- `GET /dashboard` — summary stats (total executions, tokens, cost)
- `GET /tokens` — token usage breakdown by agent
- `GET /costs` — cost breakdown by model/agent
- `GET /costs/top-agents` — top agents by cost
- `GET /logs` — execution logs (filterable)

**Auth Context** — from Phase 18:
- `AuthProvider` in `contexts/auth-context.tsx` exposes `user.tenant_id` and `user.roles`
- `apiFetch()` in `lib/api.ts` automatically attaches Bearer token
- MSAL React integration with silent token refresh

### Existing Frontend Patterns

| Pattern | Location | How It Works |
|---------|----------|--------------|
| Dashboard layout | `app/dashboard/layout.tsx` | Top bar + sidebar + main content area |
| Sidebar navigation | `components/layout/foundry-sidebar.tsx` | `navItems[]` array, `Link` with active state |
| Page data fetching | Various pages | `useEffect` + `apiFetch()` + `useState` |
| CRUD pattern | `agents/`, `tools/`, `models/` | List → New → [id] detail pages |
| Card grid | `agents/page.tsx` | Grid layout with status badges |
| Form pattern | `agents/new/page.tsx`, `models/new/page.tsx` | Controlled inputs, submit handler, error state |
| Status badges | `components/ui/status-badge.tsx` | Colored badges for entity status |
| Chart components | `components/observability/` | Recharts-based chart cards, KPI tiles |
| Top bar | `dashboard/layout.tsx` | User name + Azure button + Logout |

### Frontend Tech Stack

- **Next.js 15** (App Router, `"use client"` for interactive pages)
- **React 19** with hooks (useState, useEffect, useCallback)
- **Tailwind CSS 4** for styling
- **Lucide React** for icons
- **Recharts** for charts
- **MSAL React** for auth
- **React Flow** (only for workflow builder)

No state management library (Zustand) is currently installed — all state is local via useState/useEffect. Keep this pattern.

## Technical Approach

### UI-01: Global Tenant Selector

**Approach:** Add a `<TenantSelector>` component to the dashboard layout's top bar. This component:
- Only renders for users with `platform_admin` role
- Fetches tenant list via `GET /api/v1/tenants`
- Stores selected tenant ID in React context (`TenantContext`)
- Default selection = user's own `tenant_id` from auth
- All existing pages read from TenantContext instead of auth context for data filtering

**Key Decision:** Use React Context (not URL params or Zustand) for tenant selection — matches existing pattern (AuthContext), no new dependencies.

**File Impact:** 
- New: `contexts/tenant-context.tsx`, `components/layout/tenant-selector.tsx`
- Modified: `app/dashboard/layout.tsx` (add TenantContext provider + selector in top bar)

### UI-02: Tenant-Scoped Data Filtering

**Approach:** Modify `apiFetch()` or create a wrapper that adds `X-Tenant-Id` header based on selected tenant context. Backend TenantMiddleware already reads tenant from token claims, but platform admins need to override this for cross-tenant viewing.

**Backend Consideration:** May need a small backend change — allow `X-Tenant-Id` header override for platform_admin role users. Currently, TenantMiddleware reads tenant_id from JWT claims only. **However**, for the PoC scope (2-5 tenants), the frontend can filter client-side after fetching data. The API already scopes by the user's own tenant.

**Pragmatic approach for PoC:** Platform admin pages (tenant dashboard, settings) use the `/api/v1/tenants` API which is already cross-partition. Individual resource pages (agents, tools) would need backend support for tenant override — which is a deeper change. For now, focus the global selector on tenant admin pages and tenant-aware observability.

### UI-03: Platform Admin Dashboard

**Approach:** New page at `/dashboard/tenants` showing all tenants. Uses card grid or table layout with:
- Tenant name, slug, status (with StatusBadge)
- Agent count per tenant (may need new backend endpoint or aggregate from existing data)
- Active user count (may need new backend endpoint)
- Resource usage (from observability API)

For the PoC, use available data from `GET /api/v1/tenants` for the listing. Agent counts and user counts can be shown from tenant settings/metadata or fetched separately.

### UI-04: Tenant Settings Page

**Approach:** New page at `/dashboard/tenants/[id]/settings`. Uses form pattern matching existing edit pages:
- Display name (text input)
- Allowed providers (multi-select or tag input)
- Token quota (number input)
- Feature flags (key-value editor)

Uses `PATCH /api/v1/tenants/{id}/settings` to save.

### UI-05: User Management

**Approach:** New page at `/dashboard/tenants/[id]/users`. This is more complex because the backend doesn't yet have a user listing/management API per tenant.

**Backend Gap:** Phase 21 created tenant provisioning and auto-created admin users, but there's no `GET /api/v1/tenants/{id}/users` endpoint. Options:
1. Create a simple user listing endpoint that queries Cosmos DB users container filtered by tenant_id
2. Use Entra ID Graph API to list users in the tenant's Entra group
3. Build a stub UI that shows the admin user from tenant metadata

**Pragmatic approach:** Create a simple backend endpoint to list users by tenant_id from the existing user data, and a basic role assignment UI. Invitation via Entra ID groups is informational (link to Azure portal).

### UI-06: Usage Summary

**Approach:** New page at `/dashboard/tenants/[id]/usage`. Reuses existing observability chart components:
- `KpiTiles` for headline numbers (API calls, executions, tokens, cost)  
- `ChartCard` with Recharts for time-series visualization
- Pull data from `/api/v1/observability/dashboard`, `/tokens`, `/costs`

### TENANT-08: Onboarding Wizard

**Approach:** Multi-step wizard at `/dashboard/tenants/new`. Steps:
1. **Organization** — name, slug, admin email (→ validates slug uniqueness)
2. **Entra ID** — tenant ID, group ID (informational for PoC — actual Entra setup is external)
3. **Model Endpoint** — select or register a model endpoint
4. **First Agent** — optional quick agent creation
5. **Review** — summary of all selections, create button

Uses `POST /api/v1/tenants` to create, then `POST /api/v1/model-endpoints` for model, and `POST /api/v1/agents` for first agent.

## What NOT to Build

| Feature | Reason |
|---------|--------|
| Real-time WebSocket updates | Polling is sufficient for admin dashboard (2-5 tenants) |
| Complex RBAC UI editor | Four fixed roles from Entra ID — no custom role builder needed |
| Tenant branding/theming | Out of scope per REQUIREMENTS.md |
| Audit log viewer | Deferred to UI-F03 |
| Health status indicators | Deferred to UI-F01 |

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Backend lacks tenant-scoped user listing | Create simple user endpoint in Phase 24 — minimal backend addition |
| Cross-tenant data filtering requires backend changes | Scope tenant selector to tenant admin pages only; existing observability API already supports tenant_id dimension |
| Observability data may not be tenant-partitioned in API responses | Use existing endpoints; filter client-side if needed |

## Validation Architecture

### Testable Behaviors

1. Tenant selector appears only for platform_admin role users
2. Selecting a tenant updates context and re-renders tenant-specific data
3. Tenant dashboard table displays all tenants from API
4. Onboarding wizard completes all steps and creates tenant via API
5. Settings page loads current settings and saves changes
6. Usage charts render data from observability API

### Verification Commands

```bash
# Frontend builds without errors
cd frontend && npm run build

# Backend API endpoints exist
curl -s http://localhost:8000/api/v1/tenants | python -m json.tool
curl -s http://localhost:8000/api/v1/observability/dashboard | python -m json.tool

# New pages exist
ls frontend/src/app/dashboard/tenants/page.tsx
ls frontend/src/app/dashboard/tenants/new/page.tsx
ls frontend/src/app/dashboard/tenants/\[id\]/settings/page.tsx
```

---

*Phase: 24-tenant-admin-ui*
*Research completed: 2026-03-26*
