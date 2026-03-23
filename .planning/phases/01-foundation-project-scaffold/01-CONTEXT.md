# Phase 1: Foundation & Project Scaffold - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the foundational project structure, database schema, authentication system, and API skeleton that all subsequent phases build on. Specifically: FastAPI backend with OpenAPI docs, Next.js frontend scaffold, PostgreSQL base schema (tenants, users), JWT authentication (login, refresh, protected routes), and multi-tenant middleware that auto-filters queries by tenant_id.

This phase does NOT include agent CRUD, model abstraction, tools, RAG, or any feature-level functionality — those belong in Phases 3+.

</domain>

<decisions>
## Implementation Decisions

### Project Structure
- **D-01:** Monorepo with `backend/` and `frontend/` top-level directories. Single repository keeps PoC simple — one clone, one PR per feature, shared CI.
- **D-02:** Shared types via OpenAPI auto-generated client. FastAPI produces the OpenAPI spec, frontend consumes it via code generation (e.g., `openapi-typescript-codegen` or similar). No shared TypeScript/Python types package at PoC scale.

### Database & ORM Layer
- **D-03:** SQLAlchemy 2.0 with async support (`asyncpg` driver) as the ORM. Battle-tested, handles complex queries needed in later phases (orchestration joins, memory lookups). SQLModel rejected — too immature for complex query patterns.
- **D-04:** Alembic for database migrations. Standard migration tool for SQLAlchemy, no reason to deviate.
- **D-05:** App-level tenant filtering via middleware, not PostgreSQL Row-Level Security (RLS). Simpler to debug, sufficient for PoC, easier to demo. Middleware injects `tenant_id` from JWT claims and auto-filters all queries.
- **D-06:** UUID primary keys for all tables (using `uuid7` for sortable IDs). Base schema includes `tenants` and `users` tables with `tenant_id` foreign key on users. All tables include `created_at` and `updated_at` timestamps.

### Authentication
- **D-07:** PyJWT for JWT token handling. Lightweight, well-maintained, sufficient for the platform's needs.
- **D-08:** Tokens stored in httpOnly cookies (not localStorage or Authorization headers). Prevents XSS attacks on token theft. CSRF protection via SameSite=Lax + origin checking.
- **D-09:** Email/password authentication for Phase 1. Microsoft Entra ID integration deferred to Phase 7 (Policy Engine & Governance) where RBAC is implemented. This keeps Phase 1 focused on the skeleton.
- **D-10:** Password hashing via passlib with bcrypt backend. Industry standard, no reason to deviate.
- **D-11:** Access token expiry: 30 minutes. Refresh token expiry: 7 days. Refresh tokens stored in database for revocation capability.

### API Conventions
- **D-12:** All API routes prefixed with `/api/v1/`. Clean versioning, industry standard, allows future API versions without breaking changes.
- **D-13:** Structured error responses: `{"detail": "Human-readable message", "code": "MACHINE_READABLE_CODE"}`. Consistent format across all endpoints.
- **D-14:** Cursor-based pagination using `cursor` and `limit` query parameters. Scales better than offset-based for real-time agent data in later phases.
- **D-15:** CORS configured for `localhost:3000` (Next.js dev server) with `credentials: true` for cookie-based auth. Production origins configurable via environment variable.

### Agent's Discretion
User delegated all Phase 1 technical decisions. All decisions above (D-01 through D-15) were made by the agent based on project context, industry best practices, and downstream phase requirements. User's guidance: "I'll let you decide as someone who sees the big picture."

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Context
- `.planning/PROJECT.md` — Core value, constraints, key decisions (framework, RAG, AI Services)
- `.planning/REQUIREMENTS.md` — All 45 v1 requirements with phase mapping
- `.planning/ROADMAP.md` — 8-phase roadmap with success criteria and dependency graph

### Research
- `.planning/research/STACK.md` — Technology stack decisions (Python/FastAPI, Next.js, PostgreSQL, custom execution loop)
- `.planning/research/ARCHITECTURE.md` — Control plane / runtime plane architecture pattern
- `.planning/research/FEATURES.md` — Feature categories and breakdown

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code outside `.planning/`

### Established Patterns
- None yet — this phase establishes the foundational patterns

### Integration Points
- FastAPI backend serves OpenAPI spec consumed by Next.js frontend
- PostgreSQL accessed via SQLAlchemy async sessions
- JWT cookies flow between frontend and backend on every request
- Multi-tenant middleware sits between all routes and the database layer

</code_context>

<specifics>
## Specific Ideas

- Three-tier deliverable approach (HLD → MSFT Arch → PoC) — the code here is the PoC foundation
- Platform is designed for manager presentation — clean, well-structured code that demonstrates architectural thinking
- Model-agnostic from day one — the abstraction layer comes in Phase 3, but the base schema should not assume any specific model provider
- Microsoft-first product mapping — PostgreSQL maps to Azure Database for PostgreSQL Flexible Server

</specifics>

<deferred>
## Deferred Ideas

- **Trace viewer UI requirement** — discussed in earlier conversation as a gap in observability requirements. Not yet added to REQUIREMENTS.md. Belongs in Phase 8 scope.
- **Entra ID integration** — deferred to Phase 7 where RBAC and governance are implemented. Phase 1 uses email/password.

</deferred>

---

*Phase: 01-foundation-project-scaffold*
*Context gathered: 2026-03-23*
