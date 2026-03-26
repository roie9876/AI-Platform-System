---
status: partial
phase: 24-tenant-admin-ui
source: [24-01-SUMMARY.md, 24-02-SUMMARY.md, 24-03-SUMMARY.md]
started: "2026-03-26T15:00:00.000Z"
updated: "2026-03-26T15:30:00.000Z"
---

## Current Test

[testing complete — all tests blocked, no live environment]

## Tests

### 1. Tenants navigation link in sidebar
expected: The sidebar shows a "Tenants" navigation item with a Building2 icon. Clicking it navigates to the tenants dashboard page.
result: blocked
blocked_by: server
reason: "No pods deployed to AKS yet — backend APIs not running"

### 2. Tenant selector in header (platform admin)
expected: As a platform_admin user, a tenant selector dropdown appears in the dashboard header bar. Selecting a different tenant changes the active tenant context across all pages.
result: blocked
blocked_by: server
reason: "No pods deployed to AKS yet — backend APIs not running"

### 3. Tenant selector hidden for non-admins
expected: As a non-admin user (Member or Viewer role), no tenant selector dropdown appears in the header — it is completely hidden, not just disabled.
result: blocked
blocked_by: server
reason: "No pods deployed to AKS yet — Entra ID auth not available"

### 4. Tenants dashboard page with KPI tiles
expected: Navigating to /dashboard/tenants shows KPI tiles (total tenants, active tenants, etc.) at the top, followed by a sortable table listing all tenants with their name, status, and key metrics.
result: blocked
blocked_by: server
reason: "No pods deployed to AKS yet — tenant API not available"

### 5. Tenant status badges
expected: Each tenant in the table displays a colored status badge reflecting its lifecycle state: provisioning, active, suspended, deactivated, or deleted — each with a distinct color.
result: blocked
blocked_by: server
reason: "No pods deployed to AKS yet — no tenant data to display"

### 6. Tenant detail page with tabs
expected: Clicking a tenant row navigates to /dashboard/tenants/[id] showing the tenant detail page with three tabs: Settings, Users, and Usage. The active tab is highlighted with a blue bottom border.
result: blocked
blocked_by: server
reason: "No pods deployed to AKS yet — tenant detail API not available"

### 7. Settings tab — edit tenant configuration
expected: The Settings tab shows a form with display_name, token_quota, and allowed_providers fields. Submitting the form saves changes via PATCH to /api/v1/tenants/{id}/settings.
result: blocked
blocked_by: server
reason: "No pods deployed to AKS yet — settings API not available"

### 8. Users tab — view users and Entra ID link
expected: The Users tab shows the tenant admin email and a link/info box pointing to Azure Portal Entra ID for group management.
result: blocked
blocked_by: server
reason: "No pods deployed to AKS yet — users API not available"

### 9. Usage tab — per-tenant metrics
expected: The Usage tab displays KPI tiles showing API calls, agent executions, token consumption, and cost estimates. Chart cards show time-series placeholders for usage trends.
result: blocked
blocked_by: server
reason: "No pods deployed to AKS yet — metrics API not available"

### 10. Onboarding wizard — step navigation
expected: Navigating to /dashboard/tenants/new shows a 5-step wizard with a step indicator (connected progress circles). Steps are: Organization, Entra ID, Model Endpoint, First Agent, Review.
result: blocked
blocked_by: server
reason: "No pods deployed to AKS yet — cannot test wizard flow"

### 11. Onboarding wizard — Organization step
expected: Step 1 asks for organization name and auto-generates a slug from it. The slug can be manually overridden. Clicking Next advances to Step 2.
result: blocked
blocked_by: server
reason: "No pods deployed to AKS yet — cannot test wizard flow"

### 12. Onboarding wizard — optional steps with Skip
expected: Steps 2-4 (Entra ID, Model Endpoint, First Agent) show a "Skip" button when no fields are filled, changing to "Next" when fields have values. Skipping advances without requiring input.
result: blocked
blocked_by: server
reason: "No pods deployed to AKS yet — cannot test wizard flow"

### 13. Onboarding wizard — Review and submit
expected: Step 5 (Review) shows a summary of all entered data. Submitting triggers sequential API calls: create tenant → create model endpoint (if provided) → create agent (if provided). Success navigates back to the tenants list.
result: blocked
blocked_by: server
reason: "No pods deployed to AKS yet — cannot test submission"

## Summary

total: 13
passed: 0
issues: 0
pending: 0
skipped: 0
blocked: 13

## Gaps

[none — all tests blocked by missing infrastructure, not code issues]
