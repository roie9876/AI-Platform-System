# Phase 1: Foundation & Project Scaffold - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-23
**Phase:** 01-foundation-project-scaffold
**Areas discussed:** Project Structure, Database & ORM, Authentication, API Conventions

---

## Project Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Monorepo (`backend/` + `frontend/`) | Single repo, simple for PoC, one PR per feature | ✓ |
| Separate repos | Independent deploy cycles, more CI complexity | |
| Nx/Turborepo monorepo | Workspace tooling overhead, overkill for PoC | |

**User's choice:** Delegated to agent — "I'll let you decide as someone who sees the big picture"
**Notes:** Monorepo chosen for PoC simplicity. Shared types via OpenAPI codegen, not a shared package.

---

## Database & ORM Layer

| Option | Description | Selected |
|--------|-------------|----------|
| SQLAlchemy 2.0 async + Alembic | Battle-tested, complex query support, async native | ✓ |
| SQLModel + Alembic | Pydantic integration, but immature for complex queries | |
| Tortoise ORM | Django-inspired async ORM, smaller ecosystem | |

**Tenant isolation strategy:**

| Option | Description | Selected |
|--------|-------------|----------|
| App-level filtering (middleware) | Simpler to debug, sufficient for PoC | ✓ |
| PostgreSQL RLS | Database-enforced, more secure but harder to debug | |
| Schema-per-tenant | Full isolation, but migration complexity at scale | |

**User's choice:** Delegated to agent
**Notes:** SQLAlchemy 2.0 selected for async support and maturity. App-level filtering chosen over RLS for debuggability in a PoC context.

---

## Authentication

| Option | Description | Selected |
|--------|-------------|----------|
| PyJWT + httpOnly cookies | Lightweight, XSS-safe, simple | ✓ |
| python-jose + httpOnly cookies | More features (JWS, JWE), heavier | |
| authlib + httpOnly cookies | Full OAuth2 toolkit, overkill for Phase 1 | |

**Token storage:**

| Option | Description | Selected |
|--------|-------------|----------|
| httpOnly cookies | XSS protection, automatic on requests | ✓ |
| localStorage + Authorization header | Vulnerable to XSS, manual header management | |

**Identity provider:**

| Option | Description | Selected |
|--------|-------------|----------|
| Email/password (Phase 1) | Simple, gets auth skeleton working | ✓ |
| Entra ID from the start | Full enterprise auth, but too much scope for Phase 1 | |

**User's choice:** Delegated to agent
**Notes:** PyJWT + httpOnly cookies for simplicity and security. Entra ID deferred to Phase 7. Access 30min / Refresh 7 days.

---

## API Conventions

| Option | Description | Selected |
|--------|-------------|----------|
| `/api/v1/` prefix | Clean versioning, industry standard | ✓ |
| No version prefix | Simpler URLs, harder to version later | |

**Pagination:**

| Option | Description | Selected |
|--------|-------------|----------|
| Cursor-based | Scales for real-time data, consistent ordering | ✓ |
| Offset-based | Simpler, but breaks with concurrent writes | |

**User's choice:** Delegated to agent
**Notes:** Structured error format `{detail, code}`. CORS for localhost:3000 with credentials.

---

## Agent's Discretion

All four areas (Project Structure, Database & ORM, Authentication, API Conventions) were delegated to the agent by the user. User stated they lack technical depth for these decisions and trust the agent's big-picture view.

## Deferred Ideas

- Trace viewer UI requirement — identified gap, not yet added to REQUIREMENTS.md
- Entra ID integration — belongs in Phase 7 with RBAC
