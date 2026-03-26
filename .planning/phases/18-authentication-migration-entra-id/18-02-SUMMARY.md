---
phase: 18-authentication-migration-entra-id
plan: 02
subsystem: auth
tags: [msal, entra-id, oidc, react, frontend]

requires:
  - phase: 18-authentication-migration-entra-id
    provides: Backend Entra ID token validation (Plan 01)

provides:
  - MSAL React auth flow with Entra ID OIDC
  - Bearer token attached to all API calls
  - Auth context with user from token claims
  - Login page with "Sign in with Microsoft" SSO button

affects: [19-data-layer-migration, 24-tenant-admin-ui]

tech-stack:
  added: []
  patterns: [MSAL React provider, acquireTokenSilent, Bearer Authorization header]

key-files:
  created:
    - frontend/src/components/providers.tsx
    - frontend/.env.example
  modified:
    - frontend/src/lib/msal.ts
    - frontend/src/lib/api.ts
    - frontend/src/contexts/auth-context.tsx
    - frontend/src/app/login/page.tsx
    - frontend/src/app/register/page.tsx
    - frontend/src/components/protected-route.tsx
    - frontend/src/app/layout.tsx
    - frontend/src/app/dashboard/agents/[id]/page.tsx
    - frontend/src/app/dashboard/agents/[id]/chat/page.tsx

key-decisions:
  - "loginScopes uses api:// custom scope for platform, not Azure management API"
  - "Auth context derives user from MSAL idTokenClaims, no /me API call needed"
  - "MsalProvider wraps AuthProvider via Providers client component"
  - "Streaming chat endpoints get Bearer token via acquireTokenSilent inline"

patterns-established:
  - "Bearer token pattern: apiFetch calls acquireTokenSilent before every fetch"
  - "MSAL provider hierarchy: MsalProvider > AuthProvider > App"
  - "SSO login: single button redirects to Entra ID, no email/password form"

requirements-completed: [AUTH-01, AUTH-05]

duration: 10min
completed: 2026-03-26
---

# Phase 18 Plan 02: Frontend MSAL Auth Migration

**Replaced custom email/password login with MSAL React Entra ID OIDC flow — all API calls now attach Bearer tokens via acquireTokenSilent.**

## What Was Built

1. **MSAL config** (`msal.ts`): Removed Azure CLI fallback, platform-specific `api://` scopes for access_as_user.

2. **API layer** (`api.ts`): `apiFetch` calls `acquireTokenSilent` before every request, adds `Authorization: Bearer {token}`. Removed `credentials: "include"`. Falls back to `acquireTokenRedirect` on `InteractionRequiredAuthError`.

3. **Auth context** (`auth-context.tsx`): Uses `useMsal` + `useIsAuthenticated` hooks. User derived from `idTokenClaims` (oid, preferred_username, name, tid, roles). `login()` calls `loginRedirect`, `logout()` calls `logoutRedirect`. No more email/password params.

4. **Login page**: "Sign in with Microsoft" button only. No email/password form.

5. **Register page**: Redirect to login with message about organization-managed registration.

6. **Layout**: `Providers` wrapper (`MsalProvider > AuthProvider > App`) replaces direct `AuthProvider`.

7. **Streaming endpoints**: Two chat pages updated from `credentials: "include"` to inline `acquireTokenSilent` + Bearer header.

## Verification

- `npx tsc --noEmit` passes with no errors
- No `credentials: "include"` remaining in API calls
- No email/password inputs in login page

## Self-Check: PASSED
