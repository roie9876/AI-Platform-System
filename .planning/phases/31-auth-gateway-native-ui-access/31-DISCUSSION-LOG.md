# Phase 31: Auth Gateway & Native UI Access - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-05
**Phase:** 31-auth-gateway-native-ui-access
**Areas discussed:** Session & authentication strategy, Agent routing & pod resolution, Wildcard Ingress & AGC behavior, Ingress architecture (platform + agents)

---

## Session & Authentication Strategy

### Session Store

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory with TTL | Zero dependencies, restarts lose sessions (re-login), fine for 2-5 tenants | ✓ |
| Redis-backed sessions | Survives restarts, shared across replicas, adds Redis operational overhead | |
| Encrypted cookie (no server store) | Encrypted JWT in cookie, no server-side state, larger cookies but stateless | |

**User's choice:** In-memory with TTL
**Notes:** Scale doesn't justify Redis. Re-login on restart is acceptable.

### Cookie Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Wildcard cookie on .agents.{domain} | Single cookie covers all agent subdomains, one login for all agents | ✓ |
| Per-subdomain cookie | Login per agent subdomain, more secure but worse UX | |

**User's choice:** Wildcard cookie on .agents.{domain}
**Notes:** UX priority — one login for all agents.

### Auth Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Server-side OIDC (ConfidentialClient) | Gateway handles full OIDC flow server-side, sets httpOnly cookie. OpenClaw UI is unaware of auth. | ✓ |
| Delegate to platform frontend | Redirect to platform frontend login, pass token back to gateway. Shares MSAL.js session. | |

**User's choice:** Server-side OIDC (ConfidentialClient)
**Notes:** OpenClaw SPA can't send Bearer tokens — must be server-side.

---

## Agent Routing & Pod Resolution

(Agent selected recommended options for all three questions)

### Resolution Method

| Option | Description | Selected |
|--------|-------------|----------|
| Cosmos DB lookup | agent_id → Cosmos query → tenant_slug + instance_name → pod DNS | ✓ |
| K8s API CR discovery | Query K8s API for OpenClawInstance CRs across namespaces, match by label | |
| Encode tenant in subdomain | Subdomain IS the K8s service name | |

**User's choice:** Cosmos DB lookup (recommended)

### Caching

| Option | Description | Selected |
|--------|-------------|----------|
| 60-second TTL cache | Cache agent_id → pod DNS, same pattern as tenant slug cache | ✓ |
| No cache | Always query Cosmos per request | |
| K8s watch + live update | Watch events for live mapping | |

**User's choice:** 60-second TTL cache (recommended)

### Error Cases

| Option | Description | Selected |
|--------|-------------|----------|
| 403/404 HTML error pages | Explicit error pages with link back to platform UI | ✓ |
| Redirect to platform UI | Redirect to platform login with error message | |

**User's choice:** 403/404 HTML error pages (recommended)

---

## Wildcard Ingress & AGC Behavior

(Recommended options presented, user agreed)

### Ingress Split

| Option | Description | Selected |
|--------|-------------|----------|
| Two separate Ingress resources | ingress.yaml (platform, hostless) + ingress-agents.yaml (wildcard, conditional) | ✓ |
| Single combined Ingress | One Ingress with both platform and agent routing | |

**User's choice:** Two separate Ingress resources (recommended)

### TLS Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| cert-manager wildcard cert | DNS-01 challenge, agents-wildcard-tls Secret, for agents Ingress only | ✓ |
| AGC-managed TLS for both | Let AGC handle TLS for agents too | |

**User's choice:** cert-manager wildcard cert for agents, AGC-managed for platform (recommended)

---

## Ingress Architecture (Platform + Agents)

### Platform Ingress

| Option | Description | Selected |
|--------|-------------|----------|
| Hostless (no host field) | AGC assigns auto-FQDN, works without domain | ✓ |
| Explicit host with AGENTS_DOMAIN | Requires domain to be set | |

**User's choice:** Hostless (recommended)

### Auth Gateway Routing

| Option | Description | Selected |
|--------|-------------|----------|
| Single wildcard Ingress → auth-gateway | All *.agents.{domain} traffic to auth-gateway, internal routing | ✓ |
| Dynamic per-agent Ingress resources | Create Ingress per agent via openclaw_service.py | |

**User's choice:** Single wildcard Ingress (recommended)

---

## Domain Strategy

### Deployment Model

| Option | Description | Selected |
|--------|-------------|----------|
| Conditional deployment (no domain now, add later) | Platform works immediately with AGC auto-FQDN. Auth gateway deployed only when AGENTS_DOMAIN is set. | ✓ |
| Buy domain now and implement end-to-end | Full native UI from day one | |

**User's choice:** Conditional deployment
**Notes:** User emphasized this is core functionality that impacts whether a real domain and cert are needed. Decision: design everything conditional, defer domain purchase.

---

## Agent's Discretion

- Session cookie encryption implementation
- OIDC callback URL pattern
- Cosmos DB repository for agent resolution
- K8s manifest specifics
- OpenClaw gateway-proxy config changes
- Error page design
- Health check implementation
- cert-manager conditional installation

## Deferred Ideas

- Redis session store (not needed at scale)
- Per-agent Ingress (rejected for single wildcard)
- NGINX alongside AGC (rejected to avoid second controller)
- OpenClaw native OIDC (future version feature)
