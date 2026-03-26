---
phase: 24
slug: tenant-admin-ui
status: draft
shadcn_initialized: false
preset: none
created: 2026-03-26
---

# Phase 24 — UI Design Contract

> Visual and interaction contract for the Tenant Admin UI. Generated from existing codebase patterns analysis.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (raw Tailwind CSS) |
| Preset | not applicable |
| Component library | none (custom components) |
| Icon library | lucide-react |
| Font | system default (Tailwind sans stack) |

**Rationale:** Phase 24 continues the existing pattern established across phases 01-16. No component library is installed; all UI uses Tailwind utility classes directly. Adding shadcn/ui mid-milestone would create inconsistency.

---

## Spacing Scale

Declared values (must be multiples of 4):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Icon gaps (`gap-1`), inline padding |
| sm | 8px | Compact element spacing (`gap-2`, `p-2`) |
| md | 16px | Default element spacing (`gap-4`, `p-4`) |
| lg | 24px | Section padding (`p-6`) |
| xl | 32px | Layout gaps (`p-8`, page padding) |
| 2xl | 48px | Major section breaks (`py-12`) |
| 3xl | 64px | Page-level spacing (unused) |

Exceptions: none — matches existing codebase usage in `agents/page.tsx` (`p-8`, `mb-6`, `gap-6`)

---

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Body | 14px (`text-sm`) | 400 (normal) | 1.5 (default) |
| Label | 12px (`text-xs`) | 500 (`font-medium`) | 1.5 |
| Heading | 24px (`text-2xl`) | 700 (`font-bold`) | 1.25 |
| Display | 30px (`text-3xl`) | 700 (`font-bold`) | 1.25 |

**Heading pattern (from agents/page.tsx):** `<h1 className="text-2xl font-bold text-gray-900">`
**KPI display (from kpi-tiles.tsx):** `<div className="text-3xl font-bold text-gray-900">`
**Section heading (from chart-card.tsx):** `<h3 className="text-sm font-semibold text-gray-700">`

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `#F9FAFB` (gray-50) | Page background (`bg-gray-50`) |
| Secondary (30%) | `#FFFFFF` (white) | Cards, sidebar, top bar (`bg-white`) |
| Accent (10%) | `#7C3AED` (violet-600) | Active sidebar item, loading spinners |
| Destructive | `#DC2626` (red-600) | Delete buttons, error badges |

**Additional status colors (established in codebase):**

| Status | Background | Text | Usage |
|--------|-----------|------|-------|
| Active / Connected | `bg-green-100` / `bg-emerald-600` | `text-green-800` | Active tenants, healthy status |
| Warning / Degraded | `bg-amber-100` / `bg-amber-600` | `text-amber-800` | Suspended tenants |
| Error | `bg-red-100` / `bg-red-600` | `text-red-800` | Deactivated/errored tenants |
| Inactive | `bg-gray-100` / `bg-gray-400` | `text-gray-800` | Provisioning/deleted/unknown |

**Tenant lifecycle status mapping:**

| Tenant Status | Badge BG | Badge Text | Dot Color |
|---------------|----------|-----------|-----------|
| provisioning | `bg-blue-100` | `text-blue-800` | `bg-blue-500` |
| active | `bg-green-100` | `text-green-800` | `bg-emerald-600` |
| suspended | `bg-amber-100` | `text-amber-800` | `bg-amber-600` |
| deactivated | `bg-red-100` | `text-red-800` | `bg-red-600` |
| deleted | `bg-gray-100` | `text-gray-800` | `bg-gray-400` |

Accent reserved for: active sidebar nav item border-left, loading spinner, primary CTA focus ring

**CTA button colors (established):**

| Role | Classes |
|------|---------|
| Primary CTA | `bg-blue-600 text-white hover:bg-blue-700` |
| Destructive CTA | `bg-red-600 text-white hover:bg-red-700` |
| Secondary/ghost | `border border-gray-200 text-gray-600 hover:bg-gray-50` |

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA (create tenant) | "Create Tenant" |
| Primary CTA (save settings) | "Save Settings" |
| Empty state heading (tenant list) | "No tenants yet" |
| Empty state body (tenant list) | "Create your first tenant to start onboarding teams. → Create Tenant" |
| Empty state heading (users) | "No users found" |
| Empty state body (users) | "Users are managed through Microsoft Entra ID groups." |
| Error state (API) | "{Error message from API}" (pass through backend detail) |
| Destructive confirmation (delete) | "Delete tenant \"{name}\"? This will deactivate all resources and cannot be undone." |
| Destructive confirmation (deactivate) | "Deactivate tenant \"{name}\"? All API access will be blocked." |
| Wizard step labels | "Organization → Entra ID → Model Endpoint → First Agent → Review" |
| Wizard complete CTA | "Create & Provision" |
| Tenant selector label | "Tenant:" (inline with dropdown) |

---

## Page Layouts

### Tenant Dashboard (`/dashboard/tenants`)
```
┌──────────────────────────────────────────────────────────┐
│ p-8                                                       │
│ ┌─ Header ─────────────────────────────────┐             │
│ │ "Tenants" (text-2xl font-bold)   [Create Tenant] btn  │
│ └───────────────────────────────────────────┘             │
│                                                           │
│ ┌─ KPI Row ───────────────────────────────────┐          │
│ │ [Total] [Active] [Suspended] [Provisioning] │          │
│ │  KpiTile  KpiTile  KpiTile    KpiTile       │          │
│ └─────────────────────────────────────────────┘          │
│                                                           │
│ ┌─ Table ─────────────────────────────────────────────┐  │
│ │ Name | Slug | Status | Agents | Users | Created     │  │
│ │ ───────────────────────────────────────────────────  │  │
│ │ row → click navigates to /dashboard/tenants/[id]    │  │
│ └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**Layout rules:**
- Page padding: `p-8` (matches agents page)
- Header: flex with justify-between, heading left + CTA right
- KPI row: `grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6`
- Table: `rounded-lg border border-gray-200 bg-white shadow-sm`
- Rows: `hover:bg-gray-50 cursor-pointer` with `border-b border-gray-100`

### Tenant Detail / Settings (`/dashboard/tenants/[id]`)
```
┌──────────────────────────────────────────────────────────┐
│ p-8                                                       │
│ ┌─ Header ─────────────────────────────────┐             │
│ │ ← Back   "Tenant: {name}" + StatusBadge  │             │
│ └───────────────────────────────────────────┘             │
│                                                           │
│ ┌─ Tab Navigation ────────────────────────────┐          │
│ │ [Settings] [Users] [Usage]                  │          │
│ └─────────────────────────────────────────────┘          │
│                                                           │
│ ┌─ Content Area ──────────────────────────────┐          │
│ │ (renders based on active tab)               │          │
│ └─────────────────────────────────────────────┘          │
└──────────────────────────────────────────────────────────┘
```

**Tab pattern:**
- Tabs: `border-b border-gray-200` with `text-sm font-medium`
- Active tab: `border-b-2 border-blue-600 text-blue-600`
- Inactive tab: `text-gray-500 hover:text-gray-700`

### Onboarding Wizard (`/dashboard/tenants/new`)
```
┌──────────────────────────────────────────────────────────┐
│ p-8 max-w-2xl mx-auto                                    │
│ ┌─ Header ─────────────────────────────────┐             │
│ │ "New Tenant" (text-2xl font-bold)         │             │
│ └───────────────────────────────────────────┘             │
│                                                           │
│ ┌─ Step Indicator ─────────────────────────────────────┐ │
│ │ (1)──(2)──(3)──(4)──(5)                              │ │
│ │  Org  Entra Model Agent Review                       │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                           │
│ ┌─ Step Content (bg-white rounded-lg border p-6) ────┐  │
│ │ Form fields for current step                        │  │
│ └─────────────────────────────────────────────────────┘  │
│                                                           │
│ ┌─ Navigation ─────────────────────────────────────────┐ │
│ │                              [Back]  [Next / Create] │ │
│ └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

**Step indicator:**
- Circles: `h-8 w-8 rounded-full flex items-center justify-center text-sm font-medium`
- Completed: `bg-blue-600 text-white`
- Current: `border-2 border-blue-600 text-blue-600`
- Upcoming: `bg-gray-200 text-gray-500`
- Connector lines: `h-0.5 bg-gray-200` → `bg-blue-600` when completed

### Tenant Selector (in top bar)
```
┌─ Top Bar ──────────────────────────────────────────────┐
│     [Tenant: ▾ dropdown]   [Azure]  {name}  [Logout]  │
└────────────────────────────────────────────────────────┘
```

- Only visible when user has `platform_admin` role
- Dropdown: `border border-gray-200 rounded-md px-3 py-1.5 text-sm`
- Position: left side of top bar actions, before Azure button
- Width: `min-w-[200px]` to accommodate tenant names

### Usage Tab
```
┌─ Usage Content ──────────────────────────────────────────┐
│ ┌─ KPI Row ───────────────────────────────────┐          │
│ │ [API Calls] [Executions] [Tokens] [Cost]    │          │
│ └─────────────────────────────────────────────┘          │
│                                                           │
│ ┌─ Charts ─────────────────────────────────────────────┐ │
│ │  ChartCard: "API Calls (30d)"                        │ │
│ │  ChartCard: "Token Usage (30d)"                      │ │
│ └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

- Reuses `KpiTile` and `ChartCard` from `components/observability/`
- Chart grid: `grid grid-cols-1 lg:grid-cols-2 gap-6`

---

## Component Patterns

### Card Pattern (existing — reuse)
```tsx
className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow"
```

### Form Input Pattern (existing — reuse)
```tsx
<label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
<input className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500" />
```

### Error Alert Pattern (existing — reuse)
```tsx
<div className="rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</div>
```

### Loading State Pattern (existing — reuse)
```tsx
<p className="text-gray-500">Loading...</p>
```

### Tenant Status Badge (new — extends StatusBadge pattern)
```tsx
const tenantStatusConfig = {
  provisioning: { bg: "bg-blue-100", text: "text-blue-800", dot: "bg-blue-500" },
  active: { bg: "bg-green-100", text: "text-green-800", dot: "bg-emerald-600" },
  suspended: { bg: "bg-amber-100", text: "text-amber-800", dot: "bg-amber-600" },
  deactivated: { bg: "bg-red-100", text: "text-red-800", dot: "bg-red-600" },
  deleted: { bg: "bg-gray-100", text: "text-gray-800", dot: "bg-gray-400" },
};
```

---

## Interaction Patterns

| Interaction | Pattern |
|-------------|---------|
| Navigation from list | Row click → navigate to detail page |
| Delete action | Trash icon in row → `confirm()` dialog → API call |
| Form submission | Button click → loading state → success redirect or error alert |
| Wizard navigation | Back/Next buttons → state-driven step transitions |
| Tenant selector | Dropdown `<select>` → updates TenantContext → re-fetches data |
| Tab switching | Client-side tab state → conditionally renders content |
| Settings save | Form change → enable Save button → PATCH API → success feedback |

---

## Responsive Breakpoints

| Breakpoint | Layout |
|------------|--------|
| Mobile (< 768px) | Single column, stacked KPIs and cards |
| Tablet (md: 768px) | 2-column KPI grid |
| Desktop (lg: 1024px) | 4-column KPI grid, 2-column chart grid, 3-column agent grid |

Matches existing responsive pattern: `grid-cols-1 md:grid-cols-2 lg:grid-cols-3` (agents) / `lg:grid-cols-4` (KPIs).

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| No registries | None | not applicable |

**Note:** This phase uses no shadcn, no third-party component registries. All components are custom Tailwind-only.

---

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS — All CTAs, empty states, error states, and confirmations specified with exact copy
- [x] Dimension 2 Visuals: PASS — Page layouts with ASCII wireframes, component patterns with exact Tailwind classes
- [x] Dimension 3 Color: PASS — 60/30/10 split specified, all status colors mapped, accent usage restricted
- [x] Dimension 4 Typography: PASS — All four roles defined with exact Tailwind classes and source references
- [x] Dimension 5 Spacing: PASS — Token scale matches established codebase, page padding verified against source
- [x] Dimension 6 Registry Safety: PASS — No registries used, all custom components

**Approval:** approved 2026-03-26
