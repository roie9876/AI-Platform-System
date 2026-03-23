---
phase: 01-foundation-project-scaffold
plan: 03
subsystem: frontend-auth
tags: [react, nextjs, auth-context, protected-routes, tailwind]

requires:
  - phase: 01-01
    provides: Next.js scaffold, apiFetch utility
  - phase: 01-02
    provides: Auth API endpoints (register, login, logout, me)
provides:
  - AuthProvider context managing user state via cookie-based JWT
  - Login and Register pages calling backend auth API
  - ProtectedRoute component redirecting unauthenticated users
  - Dashboard page displaying current user info
  - Auth-aware landing page with conditional redirect
affects: [all-frontend-features, agent-management-ui, dashboard-extensions]

tech-stack:
  added: []
  patterns: [react-context-auth, client-components-use-client, protected-route-pattern]

key-files:
  created:
    - frontend/src/contexts/auth-context.tsx
    - frontend/src/components/protected-route.tsx
    - frontend/src/app/login/page.tsx
    - frontend/src/app/register/page.tsx
    - frontend/src/app/dashboard/page.tsx
  modified:
    - frontend/src/app/layout.tsx
    - frontend/src/app/page.tsx
    - backend/app/api/v1/auth.py
    - backend/app/core/security.py
    - backend/app/models/base.py
    - backend/app/models/refresh_token.py
    - backend/requirements.txt
    - backend/alembic/env.py
    - backend/alembic/versions/001_initial_schema.py
---

## What was done

Created the frontend auth layer and fixed several Docker runtime issues discovered during e2e verification.

### Frontend Auth Layer
- **AuthProvider** (`auth-context.tsx`): React context with `user` state, `loading` flag, `login()`, `register()`, `logout()` functions. Calls backend `/api/v1/auth/*` endpoints via `apiFetch`. Checks auth status on mount via `/auth/me`.
- **ProtectedRoute** (`protected-route.tsx`): Wraps pages that require auth. Redirects to `/login` if `user` is null after loading completes.
- **Login page**: Email/password form, calls `auth.login()`, redirects to `/dashboard` on success.
- **Register page**: Email/fullName/password/tenantSlug form, calls `auth.register()`, redirects to `/login` on success.
- **Dashboard page**: Wrapped in `ProtectedRoute`, shows `user.full_name`, `user.email`, `user.tenant_id`, logout button.
- **Landing page**: Made auth-aware — redirects to `/dashboard` if already logged in.
- **Layout**: Wraps children in `<AuthProvider>`.

### Runtime Fixes (discovered during e2e)
- **uuid7 → uuid4**: Docker runs Python 3.12 (not 3.14), so `uuid.uuid7()` doesn't exist. Changed to `uuid.uuid4()`.
- **passlib → bcrypt**: passlib has a known incompatibility with newer bcrypt versions. Replaced with direct `bcrypt` library.
- **email-validator**: Added missing dependency required by Pydantic's `EmailStr`.
- **Alembic env.py**: Updated to read `DATABASE_URL` from environment variable (for Docker `db` hostname) with fallback to `alembic.ini`.
- **Refresh token column**: Changed from `String(255)` to `Text` — JWTs exceed 255 characters.
- **Auto-create tenant**: Register endpoint now auto-creates tenant if slug doesn't exist, instead of returning 404.

## Decisions made
- Used plain Tailwind CSS classes instead of shadcn/ui (CLI requires interactive prompts).
- Auto-create tenants on registration for self-service onboarding flow.
- Used `uuid4` universally (Docker Python 3.12 compatibility).
- Replaced passlib with direct bcrypt for reliability.

## Verification
- `npm run build` passes with all 5 routes compiling
- `curl` register → login → /me flow works end-to-end
- User confirmed registration and login work from browser
