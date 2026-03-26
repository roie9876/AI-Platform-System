---
status: testing
phase: 26-tenant-context-wiring
source: [26-01-SUMMARY.md, 26-02-SUMMARY.md]
started: "2026-03-26T15:00:00.000Z"
updated: "2026-03-26T15:00:00.000Z"
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 1
name: X-Tenant-Id Header Injection
expected: |
  1. Start the frontend: `cd frontend && npm run dev`
  2. Log in as a platform admin who can see the TenantSelector
  3. Open browser DevTools → Network tab
  4. Navigate to /dashboard/agents
  5. Find the `/api/v1/agents` request in the Network tab
  6. Check Request Headers — you should see `X-Tenant-Id: <your-selected-tenant-id>`
awaiting: user response

## Tests

### 1. X-Tenant-Id Header Injection
expected: Open DevTools Network tab, navigate to /dashboard/agents. The `/api/v1/agents` request should include an `X-Tenant-Id` header matching the currently selected tenant in the TenantSelector dropdown.
result: pass — X-Tenant-Id header present on API requests (value is Entra ID tid as no platform tenants exist yet)

### 2. Tenant Switch Refetches Core Entity Pages
expected: While on /dashboard/agents, switch to a different tenant in the TenantSelector. A new `/api/v1/agents` request fires immediately with the updated `X-Tenant-Id` header. Repeat for /dashboard/tools — switching tenants triggers a new `/api/v1/tools` request. The page content refreshes without a manual page reload.
result: blocked — No Cosmos DB available locally; cannot create platform tenants to test switching

### 3. Tenant Switch Refetches Observability Pages
expected: Navigate to /dashboard/observability. Switch tenants in the TenantSelector. A new `/api/v1/observability/dashboard` request fires with the updated `X-Tenant-Id`. Navigate to /dashboard/observability/logs — switching tenants triggers a new logs fetch with the correct tenant header.
result: blocked — No Cosmos DB available locally; cannot create platform tenants to test switching

### 4. Tenant Switch Refetches MCP Tools Pages
expected: Navigate to /dashboard/mcp-tools. Switch tenants in the TenantSelector. A new `/api/v1/mcp/tools` request fires with the updated `X-Tenant-Id`. Navigate to /dashboard/mcp-tools/servers — switching tenants triggers a new servers fetch with the correct tenant header.
result: blocked — No Cosmos DB available locally; cannot create platform tenants to test switching

### 5. No Cross-Tenant Data Leakage After Switch
expected: On /dashboard/agents with Tenant A selected, note the agents list. Switch to Tenant B. The agents list should update to show Tenant B's agents (or empty if Tenant B has none). Switching back to Tenant A restores the original list. At no point should data from both tenants appear simultaneously.
result: blocked — No Cosmos DB available locally; cannot create platform tenants to test switching

## Summary

total: 5
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 4

## Gaps

- Tests 2-5 require Cosmos DB infrastructure (AKS deployment) to create platform tenants and test tenant switching behavior
