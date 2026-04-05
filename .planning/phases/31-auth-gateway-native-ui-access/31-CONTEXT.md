# Phase 31: Auth Gateway & Native UI Access - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Build and deploy a FastAPI auth gateway that provides authenticated access to OpenClaw's native web UI via subdomain routing. Users access any agent's full UI at `agent-{id}.agents.{domain}`, authenticated via Entra ID OIDC, scoped to their tenant. The auth gateway handles the OIDC login flow (server-side), session management, agent-to-pod resolution, and HTTP + WebSocket proxying to OpenClaw pods. All Phase 31 resources are **conditionally deployed** — only when `AGENTS_DOMAIN` is set in the azd environment. Without a domain, the platform works with AGC auto-FQDN and platform UI only.

</domain>

<decisions>
## Implementation Decisions

### Domain Strategy & Conditional Deployment
- **D-01:** Phase 31 resources are entirely conditional on `AGENTS_DOMAIN` being set. Without it: no auth-gateway Deployment, no wildcard Ingress, no cert-manager resources. The Docker image is always built (in ACR), but K8s resources are only applied when the domain is configured.
- **D-02:** `postprovision.sh` handles the conditional logic: if `AGENTS_DOMAIN` is set → deploy auth-gateway manifests, cert-manager ClusterIssuer, wildcard Certificate, and agents Ingress. If not → skip all Phase 31 K8s resources.
- **D-03:** Domain can be added later without redeploying: `azd env set AGENTS_DOMAIN myagents.com` → `azd up` → auth gateway and wildcard Ingress get created.
- **D-04:** Three domain options (from Phase 28 D-05): default (AGC auto-FQDN, no native UI), buy via Azure (`BUY_DOMAIN=true`), or bring-your-own (`AGENTS_DOMAIN` only with manual NS delegation).

### Session & Authentication Strategy
- **D-05:** Server-side OIDC using `msal` ConfidentialClientApplication. The auth gateway handles the full authorization code + PKCE flow — OpenClaw UI has no knowledge of auth. Uses the same Entra ID app registration as the platform.
- **D-06:** In-memory session store with TTL. Sessions are Python dicts keyed by session ID, garbage-collected on expiry. Restarts lose sessions (users re-login). Acceptable for 2-5 tenants. No Redis dependency.
- **D-07:** Wildcard httpOnly cookie on `.agents.{domain}`. Single login covers all agent subdomains — accessing `agent-abc.agents.example.com` and then `agent-def.agents.example.com` uses the same session cookie. Cookie is Secure, SameSite=Lax, encrypted/signed.
- **D-08:** Token refresh handled server-side. MSAL ConfidentialClient caches refresh tokens in memory. Gateway refreshes access tokens silently when they expire. If refresh fails (revoked, expired), user gets redirected to OIDC login again.
- **D-09:** Entra ID app registration reuse. The auth gateway uses the **same client ID** as the platform backend (AZURE_CLIENT_ID). A new client secret is stored in Key Vault for the ConfidentialClient flow. No new app registration needed.

### Agent Routing & Pod Resolution
- **D-10:** Cosmos DB lookup for agent resolution. Subdomain `agent-{id}` → query `agents` container by agent slug/ID → get `tenant_id` → resolve `tenant_slug` → construct DNS: `oc-{instance_name}.tenant-{slug}.svc.cluster.local:18789`.
- **D-11:** 60-second TTL cache for agent-to-pod mappings. Same pattern as tenant slug cache in `tenant.py`. Cache is per-process (in-memory dict with TTL). On cache miss, query Cosmos DB.
- **D-12:** 403/404 HTML error pages for access failures. "Agent not found" (404) or "Access denied — this agent belongs to another tenant" (403). Pages include a link back to the platform UI. No redirects to platform login.
- **D-13:** Tenant-scoping enforcement. After resolving the agent from Cosmos, compare agent's `tenant_id` against the authenticated user's `tenant_id` from the session. Mismatch → 403. Deleted/suspended agents → 404.

### Wildcard Ingress & AGC Behavior
- **D-14:** Two separate Ingress resources: `ingress.yaml` (platform, hostless, AGC auto-FQDN) and `ingress-agents.yaml` (wildcard `*.agents.{domain}`, conditional). Both use `ingressClassName: azure-alb-external` — single AGC, no second ingress controller.
- **D-15:** Platform Ingress is hostless — no `host:` field, no `tls:` section. AGC assigns an auto-generated FQDN. This unblocks `azd up` without any domain configuration.
- **D-16:** Agents Ingress uses explicit wildcard host: `*.agents.{domain}`. TLS terminated by AGC using a wildcard cert from cert-manager (`agents-wildcard-tls` Secret). cert-manager DNS-01 challenge validates domain ownership via Azure DNS zone.
- **D-17:** Auth gateway is the sole backend for the agents Ingress. All `*.agents.{domain}` traffic → `auth-gateway.aiplatform.svc:8000`. The gateway handles routing internally (no per-agent Ingress resources).

### Ingress Architecture (Platform + Agents)
- **D-18:** Platform Ingress (`ingress.yaml`) remains path-based with existing routes: `/api/v1/*` → microservices, `/` → frontend. No `host:` field — AGC assigns FQDN.
- **D-19:** Agents Ingress (`ingress-agents.yaml`) is a template in `k8s/base/auth-gateway/`. `postprovision.sh` renders it with `${AGENTS_DOMAIN}` substitution and applies it only when the variable is set.
- **D-20:** No dynamic per-agent Ingress creation. A single wildcard Ingress covers all agents. The auth gateway does the per-agent routing internally via Cosmos DB lookup.
- **D-21:** WebSocket proxy through AGC works natively — AGC supports WebSocket upgrade without special annotations. The auth gateway proxies both HTTP and WebSocket to OpenClaw pods.

### Frontend Integration
- **D-22:** "Open Agent Console" button on agent detail page, conditionally rendered. Platform API exposes `agents_domain` via the `/api/config` endpoint (or similar). If present, frontend renders the button linking to `https://agent-{slug}.agents.{domain}`. If absent, button is hidden.
- **D-23:** Button opens in a new tab (`target="_blank"`). No iframe embedding — OpenClaw SPA expects full page control.

### Auth Gateway Service Architecture
- **D-24:** FastAPI service in `aiplatform` namespace. Same patterns as token-proxy and mcp-platform-tools: Dockerfile, Deployment, Service, HPA (2-5 replicas), PDB, health probes.
- **D-25:** Reuse `app.core.security.validate_entra_token()` for Bearer token validation (API callers). Server-side OIDC flow (MSAL ConfidentialClient) for browser sessions.
- **D-26:** `httpx.AsyncClient` for HTTP proxying (connection pooling, 120s timeout). `websockets` library for WebSocket proxying — bidirectional frame relay between browser and OpenClaw pod.
- **D-27:** Proxy preserves all headers and request bodies. The gateway adds `X-Forwarded-For`, `X-Real-IP`, and `X-Forwarded-Proto` headers. OpenClaw gateway-proxy needs `trustedProxies` widened to trust the auth gateway's pod CIDR.

### Agent's Discretion
- Session cookie encryption implementation (Fernet, itsdangerous, or similar)
- OIDC callback URL pattern (`/auth/callback` on each agent subdomain vs single auth subdomain)
- Cosmos DB repository pattern for agent resolution (new repository or extend existing)
- K8s manifest specifics (resource limits, probe paths, environment variables)
- OpenClaw gateway-proxy config changes for `trustedProxies` and `allowedOrigins`
- Error page HTML/CSS design
- Health check implementation (`/healthz`, `/readyz`)
- App Insights telemetry integration
- How `install-cluster-deps.sh` conditionally installs cert-manager

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Auth & Security
- `backend/app/core/security.py` — JWKS caching, token validation (v1+v2 issuers), role extraction. Reuse for Bearer token validation.
- `backend/app/middleware/tenant.py` — Tenant middleware with slug cache, status checks. Reference for cache pattern and tenant resolution.
- `backend/app/api/v1/dependencies.py` — Auth dependency injection (`get_current_user`, `require_role`).
- `frontend/src/lib/msal.ts` — MSAL config, login scopes. Reference for Entra ID app registration details.
- `frontend/src/contexts/auth-context.tsx` — Frontend auth context. Reference for how the platform handles auth.
- `frontend/src/lib/api.ts` — Token acquisition, `X-Tenant-Id` header injection.

### Proxy & Microservice Patterns
- `backend/microservices/llm_proxy/main.py` — httpx-based transparent proxy, streaming support. Reference implementation for auth gateway proxy.
- `backend/microservices/api_gateway/main.py` — FastAPI lifespan, middleware stack order, router pattern. Template for auth gateway service structure.

### OpenClaw Integration
- `backend/app/services/openclaw_service.py` — `get_pod_url()` (line ~370), WebSocket connection to gateway (line ~288-360), CR management. Critical for understanding pod resolution and WebSocket protocol.
- `k8s/base/openclaw/openclawinstance.yaml` — OpenClaw CR template. Reference for gateway-proxy port (18789/18790) and config structure.

### K8s / Ingress
- `k8s/base/ingress.yaml` — Current platform Ingress (needs hostless fix). Reference for AGC annotations.
- `k8s/base/kustomization.yaml` — Resource list for kubectl apply.
- `k8s/base/token-proxy/` — Deployment, Service, HPA pattern to replicate for auth-gateway.

### Infrastructure
- `hooks/postprovision.sh` — Post-provision hook. Will need conditional logic for AGENTS_DOMAIN.
- `scripts/install-cluster-deps.sh` — Cluster deps installer. Will need conditional cert-manager installation.
- `infra/modules/agc.bicep` — AGC Traffic Controller. Reference for AGC capabilities.
- `backend/app/core/config.py` — Environment configuration (AZURE_TENANT_ID, AZURE_CLIENT_ID, etc.).

### Research
- `.planning/research/AUTH-GATEWAY.md` — Evaluated oauth2-proxy, NGINX auth_request, Traefik ForwardAuth, custom FastAPI gateway. Custom gateway recommended.
- `.planning/research/OPENCLAW-MCP-NATIVE-UI.md` — OpenClaw pod topology (4 containers), gateway-proxy port, WebSocket protocol, auth config.

### Requirements
- `.planning/REQUIREMENTS.md` §Native UI Access — NATIVEUI-01 through NATIVEUI-05

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `security.py` JWKS validation pipeline — handles v1/v2 issuers, audience mismatch, role mapping. Direct reuse for Bearer token path.
- `tenant.py` slug-to-UUID cache with 60s TTL — exact pattern for agent-to-pod cache.
- `llm_proxy/main.py` httpx.AsyncClient proxy with connection pooling — template for HTTP proxying.
- `openclaw_service.py` WebSocket frame-by-frame protocol — reference for WebSocket proxy implementation.
- Token-proxy K8s manifests (Deployment, Service, HPA, PDB, probes) — copy and adapt for auth-gateway.

### Established Patterns
- FastAPI lifespan context manager for startup/shutdown (Cosmos client, telemetry).
- CORSMiddleware + TenantMiddleware + TelemetryMiddleware stack ordering.
- CSI SecretProviderClass for Key Vault secrets → environment variables.
- `requirements.txt` with pinned versions, `Dockerfile` multi-stage builds.

### Integration Points
- Frontend agent detail page (`frontend/src/app/dashboard/agents/[id]/page.tsx` ~line 920) — add "Open Agent Console" button.
- Platform API `/api/config` endpoint — add `agents_domain` field for conditional frontend rendering.
- `postprovision.sh` — add conditional deployment block for auth-gateway + agents Ingress.
- `install-cluster-deps.sh` — conditional cert-manager installation (already partially designed in D-07 Phase 28).
- `k8s/base/kustomization.yaml` — auth-gateway resources added conditionally (not in static kustomization).

</code_context>

<specifics>
## Specific Ideas

- Auth gateway callback URL should use a single fixed path on each agent subdomain (e.g., `https://agent-{id}.agents.{domain}/auth/callback`) rather than a separate auth subdomain — simpler, fewer DNS records.
- OpenClaw gateway-proxy config likely needs `bind: "0.0.0.0"` and widened `trustedProxies` for the auth gateway to proxy correctly. This is a CR config change applied via `openclaw_service.py`.
- The `agents_domain` config value should come from the backend's environment, not hardcoded — so the frontend can conditionally render the button without a rebuild.

</specifics>

<deferred>
## Deferred Ideas

- **Redis session store** — not needed at current scale (2-5 tenants). Revisit if session persistence across restarts becomes a problem.
- **Per-agent Ingress with dynamic creation** — rejected in favor of single wildcard Ingress. Revisit only if AGC wildcard behavior proves problematic.
- **NGINX Ingress alongside AGC** — rejected to avoid operating two ingress controllers. Only reconsider if AGC can't handle wildcard + hostless simultaneously.
- **OpenClaw auth integration** — OpenClaw has `auth.mode` settings but we bypass them entirely. If OpenClaw adds native OIDC support in a future version, the auth gateway could be simplified.

</deferred>

---

*Phase: 31-auth-gateway-native-ui-access*
*Context gathered: 2026-04-05*
