---
phase: 24
slug: tenant-admin-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | N/A — frontend components (React/Next.js), no test framework configured |
| **Config file** | frontend/package.json |
| **Quick run command** | N/A |
| **Full suite command** | N/A |
| **Estimated runtime** | N/A |

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 24-01-01 | 01 | 1 | UI-01 | artifact | `ls frontend/src/components/layout/tenant-selector.tsx` | ✅ | ✅ green |
| 24-01-01 | 01 | 1 | UI-02 | artifact | `grep -c 'selectedTenantId' frontend/src/contexts/tenant-context.tsx` | ✅ | ✅ green |
| 24-01-01 | 01 | 1 | UI-03 | artifact | `ls frontend/src/app/dashboard/tenants/page.tsx` | ✅ | ✅ green |
| 24-02-01 | 02 | 2 | UI-04 | artifact | `grep -c 'SettingsTab' frontend/src/app/dashboard/tenants/\\[id\\]/page.tsx` | ✅ | ✅ green |
| 24-02-01 | 02 | 2 | UI-05 | artifact | `grep -c 'UsersTab' frontend/src/app/dashboard/tenants/\\[id\\]/page.tsx` | ✅ | ✅ green |
| 24-02-01 | 02 | 2 | UI-06 | artifact | `grep -c 'UsageTab' frontend/src/app/dashboard/tenants/\\[id\\]/page.tsx` | ✅ | ✅ green |
| 24-03-01 | 03 | 3 | TENANT-08 | artifact | `ls frontend/src/app/dashboard/tenants/new/page.tsx` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements (artifact-verified).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tenant selector switches context | UI-01 | Visual/interactive UI | Navigate to dashboard, verify selector appears for platform_admin, changes tenant context |
| Pages filter by selected tenant | UI-02 | Visual/interactive UI | Select tenant A, verify agents/tools show only tenant A data |
| Admin dashboard shows tenant list | UI-03 | Visual/interactive UI | Navigate to /dashboard/tenants, verify KPI tiles and sortable table |
| Settings tab saves changes | UI-04 | Visual/interactive UI | Navigate to tenant detail, edit settings, verify save |
| Users tab shows admin info | UI-05 | Visual/interactive UI | Navigate to tenant detail > Users tab, verify admin email and Entra ID link |
| Usage tab shows KPIs | UI-06 | Visual/interactive UI | Navigate to tenant detail > Usage tab, verify KPI tiles |
| Onboarding wizard creates tenant | TENANT-08 | Visual/interactive UI | Navigate to /dashboard/tenants/new, complete 5 steps, verify tenant created |

*Note: All UI requirements are artifact-verified (components exist with expected exports). Runtime verification requires running frontend + backend. UAT blocked per 24-UAT.md (all 13 tests blocked by server).*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Wave 0 covers all MISSING references
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending — artifact-verified only, visual/UAT testing blocked by deployment
