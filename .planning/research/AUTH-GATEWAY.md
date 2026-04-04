# Authentication Gateway for OpenClaw Native UI Access

**Project:** AI Agent Platform v4.0 — Architecture Pivot  
**Researched:** 2026-04-04  
**Overall Confidence:** HIGH (uses existing Entra ID auth patterns + well-documented K8s ingress patterns)

---

## Executive Summary

The platform needs to expose OpenClaw's native web UI (port 18789 inside pods) to authenticated users at `agent-{id}.agents.{domain}`. The current stack uses Azure Application Gateway for Containers (AGC) as the ingress controller, MSAL.js for Entra ID authentication in the browser, and python-jose JWKS validation on the backend. OpenClaw runs with `auth.mode: none` — it has no built-in auth.

**Recommended approach:** A custom auth gateway service (Python/FastAPI) deployed in the `aiplatform` namespace, fronted by a wildcard Ingress on AGC. The auth gateway handles the OIDC login flow for browser sessions, validates Bearer tokens, resolves agent → tenant → pod mapping, and proxies HTTP + WebSocket to the correct OpenClaw pod. This approach reuses the platform's existing Entra ID token validation code, avoids introducing a new ingress controller, and gives full control over tenant-to-pod routing.

---

## 1. OAuth2 Proxy

### What It Is
[oauth2-proxy](https://oauth2-proxy.github.io/oauth2-proxy/) is a reverse proxy that provides authentication via OIDC providers. It sits in front of an upstream and handles the entire login flow.

### Entra ID + OIDC Support
**Verdict: Works, but limited for this use case.**

oauth2-proxy supports Azure AD/Entra ID via the `oidc` provider:

```yaml
# oauth2-proxy deployment args
args:
  - --provider=oidc
  - --oidc-issuer-url=https://login.microsoftonline.com/{TENANT_ID}/v2.0
  - --client-id={ENTRA_APP_CLIENT_ID}
  - --client-secret={ENTRA_APP_CLIENT_SECRET}
  - --email-domain=*
  - --scope=openid email profile
  - --cookie-secret={RANDOM_32_BYTES}
  - --cookie-secure=true
  - --pass-access-token=true
  - --set-xauthrequest=true
  - --upstream=http://localhost:18789  # static upstream
```

### WebSocket Support
oauth2-proxy passes WebSocket upgrade requests through since v7.0+. The initial HTTP upgrade request is authenticated; subsequent WebSocket frames pass through without re-auth. **This works correctly.**

### Dynamic Upstream Routing — BLOCKER
oauth2-proxy is designed for **static upstreams**. The `--upstream` flag targets a single backend. It cannot:
- Route to different upstream pods based on the hostname (e.g., `agent-abc.agents.example.com` → `oc-agent-abc.tenant-eng.svc:18789`)
- Perform a Cosmos DB lookup to resolve agent ID → tenant namespace → pod service name
- Inject tenant context headers dynamically

You would need either:
1. **One oauth2-proxy instance per agent** — operationally disastrous
2. **oauth2-proxy as auth-only** (with `--set-xauthrequest`) in front of NGINX Ingress with `auth-url` — adds complexity, two hops

### Verdict
**Not recommended as the primary solution.** oauth2-proxy excels at protecting static upstream services (dashboards, admin UIs). For dynamic multi-tenant routing to per-agent pods, it adds complexity without solving the core routing problem.

---

## 2. NGINX Ingress `auth_request`

### How It Works
NGINX Ingress Controller supports an `auth-url` annotation. On every request, NGINX sends a subrequest to the configured auth URL. If the auth service returns 200, the request is proxied to the backend. If 401/403, the user is redirected to login.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: openclaw-wildcard
  annotations:
    nginx.ingress.kubernetes.io/auth-url: "http://auth-gateway.aiplatform.svc:8000/auth/verify"
    nginx.ingress.kubernetes.io/auth-response-headers: "X-Tenant-Id,X-Agent-Id,X-User-Id"
    nginx.ingress.kubernetes.io/auth-signin: "https://$host/auth/login?rd=$escaped_request_uri"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    nginx.ingress.kubernetes.io/upstream-hash-by: "$host"
spec:
  ingressClassName: nginx  # NOT azure-alb-external
  tls:
    - hosts:
        - "*.agents.example.com"
      secretName: agents-wildcard-tls
  rules:
    - host: "*.agents.example.com"
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: auth-gateway  # The auth gateway then handles routing
                port:
                  number: 8000
```

### WebSocket + auth_request
The `auth_request` subrequest fires **only on the initial HTTP upgrade request**, not on subsequent WebSocket frames. This is the correct behavior:
1. Browser sends `Connection: Upgrade, Upgrade: websocket`
2. NGINX sends subrequest to auth-url
3. Auth service validates token, returns 200 + headers
4. NGINX proxies the WebSocket upgrade to backend
5. WebSocket frames flow directly — no auth check per frame

**This works correctly for OpenClaw's WebSocket UI.**

### Caching
NGINX Ingress supports `auth-cache-duration` to avoid hammering the auth service:
```yaml
nginx.ingress.kubernetes.io/auth-cache-duration: "200 10m"  # Cache 200 responses for 10 min
```
For WebSocket connections, caching matters less since the auth check happens once per connection.

### Critical Issue: AGC vs NGINX
**The platform currently uses AGC (`azure-alb-external`), not NGINX Ingress.** AGC does NOT support `auth-url` annotations. Options:
1. **Add NGINX Ingress Controller alongside AGC** — use `ingressClassName: nginx` for agent subdomains, keep `azure-alb-external` for the platform. This works but means operating two ingress controllers.
2. **Replace AGC with NGINX Ingress** — risky mid-milestone; affects entire platform routing.

### Routing Challenge
Even with NGINX `auth-url`, the backend service is static in the Ingress spec. The dynamic agent → pod routing still needs a component that receives the request after auth and proxies to the correct pod. The auth gateway fills this role regardless.

### Verdict
**auth-url is useful if you add NGINX Ingress alongside AGC**, but it doesn't eliminate the need for a custom routing component. It adds the auth check at the edge (before WebSocket upgrade reaches the gateway), which is a defense-in-depth benefit. However, it also means operating a second ingress controller.

---

## 3. Traefik ForwardAuth

### How It Works
Traefik's ForwardAuth middleware sends the request to an external auth service before proxying. Conceptually identical to NGINX `auth-url`.

```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: entra-auth
spec:
  forwardAuth:
    address: http://auth-gateway.aiplatform.svc:8000/auth/verify
    trustForwardHeader: true
    authResponseHeaders:
      - X-Tenant-Id
      - X-Agent-Id
      - X-User-Id
```

### WebSocket Handling
Traefik handles WebSocket correctly with ForwardAuth — the auth check runs on the upgrade request only. Traefik has native WebSocket support and doesn't require special annotations.

### Not Relevant for Current Stack
**The platform uses AGC, not Traefik.** Migrating to Traefik solely for ForwardAuth is not justified. The same auth-before-proxy pattern can be achieved with a custom gateway or by adding NGINX Ingress.

### Verdict
**Not recommended.** Same capability as NGINX auth-url but requires replacing the entire ingress stack. Only relevant if the platform were already on Traefik.

---

## 4. Custom Auth Gateway (RECOMMENDED)

### Architecture

```
Browser → agent-abc.agents.example.com
         │
         ▼
    ┌─────────────┐
    │  AGC (TLS,  │   Wildcard Ingress: *.agents.example.com
    │  wildcard)  │   ingressClassName: azure-alb-external
    └──────┬──────┘
           │
           ▼
    ┌──────────────────┐
    │  Auth Gateway    │   Deployment in aiplatform namespace
    │  (FastAPI)       │   Single service, all agent traffic
    │                  │
    │  1. Cookie/Token │   Check session cookie OR Bearer token
    │  2. OIDC login   │   If no session → redirect to Entra ID
    │  3. Resolve pod  │   agent-{id} → tenant-{slug} → pod DNS
    │  4. Proxy req    │   HTTP + WebSocket to pod:18789
    └──────┬───────────┘
           │ Cross-namespace
           ▼
    ┌──────────────────┐
    │  OpenClaw Pod    │   oc-{name}.tenant-{slug}.svc.cluster.local:18789
    │  (tenant-{slug}) │   auth.mode: none
    └──────────────────┘
```

### Why FastAPI (Python)
- **Reuse existing security module**: `app.core.security.validate_entra_token()` already handles JWKS caching, audience validation, issuer validation (v1 + v2), role extraction
- **Reuse tenant resolution**: `app.middleware.tenant._resolve_tenant_id()` already resolves slug → UUID
- **Same language**: no new runtime, same Docker base image pattern, same team expertise
- **MSAL Python**: `msal` library handles the server-side OIDC flow (authorization code + PKCE)

### Key Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| `msal` | 1.35+ | Server-side OIDC authorization code flow with Entra ID |
| `python-jose[cryptography]` | 3.3+ | JWT validation (already in use) |
| `httpx` | 0.27+ | HTTP proxying to OpenClaw pods |
| `websockets` or `wsproto` | latest | WebSocket proxying |
| `uvicorn` | 0.30+ | ASGI server |

### OIDC Login Flow (Browser Session)

OpenClaw's UI is a browser SPA — it doesn't send Bearer tokens. The auth gateway must handle the OIDC flow itself:

```python
from msal import ConfidentialClientApplication

app_config = {
    "client_id": ENTRA_APP_CLIENT_ID,
    "client_credential": ENTRA_APP_CLIENT_SECRET,  # or certificate
    "authority": f"https://login.microsoftonline.com/{TENANT_ID}",
}
msal_app = ConfidentialClientApplication(**app_config)

# 1. Browser hits agent-abc.agents.example.com (no session cookie)
# 2. Auth gateway redirects to:
auth_url = msal_app.get_authorization_request_url(
    scopes=[f"api://{ENTRA_APP_CLIENT_ID}/access_as_user"],
    redirect_uri=f"https://{request_host}/auth/callback",
    state={"original_url": request.url.path},
)
# 3. User authenticates at Entra ID
# 4. Entra ID redirects to /auth/callback with authorization code
# 5. Auth gateway exchanges code for tokens:
result = msal_app.acquire_token_by_authorization_code(
    code=request.query_params["code"],
    scopes=[f"api://{ENTRA_APP_CLIENT_ID}/access_as_user"],
    redirect_uri=f"https://{request_host}/auth/callback",
)
# 6. Auth gateway sets encrypted session cookie
# 7. Redirect to original URL — now authenticated
```

**Session cookie vs Bearer token:**
- OpenClaw's UI won't attach Bearer tokens (it doesn't know about our auth)
- The auth gateway must use **httpOnly cookies** for the OpenClaw UI session
- Cookie domain: `.agents.example.com` (wildcard, covers all agent subdomains)
- Cookie content: encrypted session ID → server-side session store (Redis or in-memory with TTL)
- This is different from the platform's MSAL.js Bearer token flow, but uses the same Entra ID app registration

### WebSocket Proxying

```python
import asyncio
import httpx
from fastapi import WebSocket

async def proxy_websocket(ws_client: WebSocket, target_url: str):
    """Bidirectional WebSocket proxy."""
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", target_url, headers={
            "Connection": "Upgrade",
            "Upgrade": "websocket",
        }) as upstream:
            # In practice, use a native WebSocket client library:
            pass

# Better approach using `websockets` library:
import websockets

async def proxy_websocket(client_ws: WebSocket, pod_url: str):
    await client_ws.accept()
    async with websockets.connect(pod_url) as pod_ws:
        async def client_to_pod():
            async for msg in client_ws.iter_text():
                await pod_ws.send(msg)
        async def pod_to_client():
            async for msg in pod_ws:
                await client_ws.send_text(msg)
        # Run both directions concurrently
        await asyncio.gather(
            client_to_pod(),
            pod_to_client(),
        )
```

### Agent Resolution

```python
from app.repositories.cosmos_client import get_cosmos_client

# Cache agent → pod mapping (short TTL since agents rarely move)
_agent_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 300  # 5 minutes

async def resolve_agent_pod(agent_id: str) -> str:
    """Resolve agent-{id} hostname to OpenClaw pod service URL."""
    # 1. Look up agent in Cosmos DB
    agent = await agent_repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    
    # 2. Get tenant slug from tenant_id
    tenant = await tenant_repo.get_tenant(agent["tenant_id"])
    slug = tenant["slug"]
    
    # 3. Construct pod DNS name
    # OpenClaw pods: oc-{cr-name}.tenant-{slug}.svc.cluster.local:18789
    oc_name = agent.get("openclaw_instance_name", f"openclaw-agent-{agent_id[:8]}")
    return f"http://oc-{oc_name}-0.tenant-{slug}.svc.cluster.local:18789"
```

### Tenant Access Validation

```python
async def verify_tenant_access(user_claims: dict, agent: dict) -> bool:
    """Ensure authenticated user can access this agent's tenant."""
    user_tenant_id = user_claims.get("tenant_id")
    agent_tenant_id = agent["tenant_id"]
    
    # Platform admins can access all tenants
    if "Platform.Admin" in user_claims.get("roles", []):
        return True
    
    # Regular users can only access their own tenant's agents
    return user_tenant_id == agent_tenant_id
```

### Deployment Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-gateway
  namespace: aiplatform
spec:
  replicas: 2
  selector:
    matchLabels:
      app: auth-gateway
  template:
    metadata:
      labels:
        app: auth-gateway
    spec:
      serviceAccountName: aiplatform-sa
      containers:
        - name: auth-gateway
          image: stumsftaiplatformprodacr.azurecr.io/aiplatform-auth-gateway:latest
          ports:
            - containerPort: 8000
          env:
            - name: ENTRA_APP_CLIENT_ID
              valueFrom:
                secretKeyRef:
                  name: auth-gateway-secrets
                  key: client-id
            - name: AZURE_TENANT_ID
              valueFrom:
                configMapKeyRef:
                  name: aiplatform-config
                  key: AZURE_TENANT_ID
            - name: COSMOS_ENDPOINT
              valueFrom:
                configMapKeyRef:
                  name: aiplatform-config
                  key: COSMOS_ENDPOINT
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
---
apiVersion: v1
kind: Service
metadata:
  name: auth-gateway
  namespace: aiplatform
spec:
  selector:
    app: auth-gateway
  ports:
    - port: 8000
      targetPort: 8000
```

### Wildcard Ingress for AGC

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: agents-wildcard-ingress
  namespace: aiplatform
  annotations:
    alb.networking.azure.io/alb-id: "${AGC_RESOURCE_ID}"
spec:
  ingressClassName: azure-alb-external
  tls:
    - hosts:
        - "*.agents.example.com"
      secretName: agents-wildcard-tls
  rules:
    - host: "*.agents.example.com"
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: auth-gateway
                port:
                  number: 8000
```

### NetworkPolicy Update

The tenant namespace NetworkPolicy must allow ingress from the auth-gateway pods in `aiplatform`:

```yaml
# ADD to k8s/overlays/tenant-template/network-policy.yaml
ingress:
  # Existing: Allow from ALB Controller
  - from:
      - namespaceSelector:
          matchLabels:
            app.kubernetes.io/name: alb-controller
  # NEW: Allow from auth-gateway in aiplatform namespace
  - from:
      - namespaceSelector:
          matchLabels:
            kubernetes.io/metadata.name: aiplatform
        podSelector:
          matchLabels:
            app: auth-gateway
    ports:
      - protocol: TCP
        port: 18789  # OpenClaw web UI port
  # Existing: Allow from same namespace
  - from:
      - podSelector: {}
```

### Verdict
**Recommended approach.** Reuses existing Entra ID validation code, works with AGC (no new ingress controller), gives full control over routing, handles both OIDC browser flow and Bearer token auth.

---

## 5. Tenant-to-Pod Routing

### Routing Flow

```
agent-abc.agents.example.com
  │
  ├── DNS: *.agents.example.com → AGC public IP (A record or CNAME)
  │
  ├── AGC: TLS terminate, match *.agents.example.com → auth-gateway:8000
  │
  ├── Auth Gateway: extract "abc" from Host header
  │   ├── Cosmos lookup: agent "abc" → tenant_id → tenant slug "eng"
  │   ├── Validate: user's tenant matches agent's tenant
  │   └── Proxy to: oc-openclaw-agent-abc.tenant-eng.svc.cluster.local:18789
  │
  └── OpenClaw Pod: receives request as if from localhost
```

### DNS Setup (Bicep)

```bicep
// In infra/modules/dns.bicep — add wildcard record
resource agentsWildcard 'Microsoft.Network/dnsZones/A@2023-07-01-preview' = {
  parent: dnsZone
  name: '*.agents'
  properties: {
    TTL: 300
    ARecords: [
      { ipv4Address: agcPublicIp }
    ]
  }
}
```

### Wildcard TLS Certificate

Options for `*.agents.example.com`:
1. **cert-manager + Let's Encrypt** — automated renewal, DNS-01 challenge (required for wildcard), uses Azure DNS zone for validation
2. **Azure Key Vault certificate** — manually provisioned or via App Service Certificate, synced to K8s via CSI driver
3. **AGC-managed TLS** — if AGC supports managed certs for the wildcard domain

**Recommended: cert-manager with DNS-01 challenge.** Already standard for K8s wildcard certs.

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: agents-wildcard-tls
  namespace: aiplatform
spec:
  secretName: agents-wildcard-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - "*.agents.example.com"
```

### Subdomain Routing vs Path-Based vs Header-Based

| Approach | Subdomain | Path-based | Header-based |
|----------|-----------|------------|--------------|
| URL pattern | `agent-{id}.agents.example.com` | `agents.example.com/agent/{id}/*` | `agents.example.com` + `X-Agent-Id` header |
| OpenClaw SPA routing | Works (root `/`) | **Breaks** (SPA expects root path) | Works (root `/`) |
| Cookie isolation | Natural (per-subdomain) | Shared (same domain) | Shared |
| CORS | Isolated per agent | Shared | Shared |
| DNS/TLS | Wildcard cert | Single cert | Single cert |
| Ingress rules | One wildcard rule | One rule + rewrite | One rule |

**Recommendation: Subdomain routing.** OpenClaw's UI is a SPA that assumes it's served from `/`. Path-based routing would require URL rewriting that breaks internal SPA routing. Subdomain routing is zero-rewrite and gives natural cookie/CORS isolation between agents.

---

## 6. Session Persistence

### WebSocket Stickiness
**Not a concern.** Each OpenClaw agent runs as a **single pod** (StatefulSet with replicas: 1). There is no pool of pods to sticky-session across. Once the auth gateway resolves the agent to its pod, the WebSocket connection goes to the only pod running that agent.

### Auth Session Persistence
The auth gateway needs to maintain session state (to avoid re-authenticating on every request):

| Approach | Pros | Cons |
|----------|------|------|
| **Encrypted cookie** | Stateless, no external store | Cookie size limit (~4KB), token data fits |
| **Server-side session (Redis)** | Full control, can revoke | Adds Redis dependency |
| **Server-side session (in-memory)** | Simple | Lost on pod restart, doesn't work with multiple replicas |

**Recommended: Encrypted cookie (Fernet or AES-GCM).** Store the essential claims (user_id, tenant_id, email, roles, expiry) in an encrypted httpOnly cookie. No external store needed. Token refresh handled by re-redirecting to Entra ID when cookie expires.

```python
from cryptography.fernet import Fernet

# Cookie encryption
COOKIE_KEY = Fernet.generate_key()  # From K8s Secret in production
fernet = Fernet(COOKIE_KEY)

def create_session_cookie(claims: dict) -> str:
    """Encrypt user claims into a session cookie value."""
    payload = json.dumps({
        "user_id": claims["oid"],
        "tenant_id": claims.get("tid"),
        "email": claims.get("preferred_username"),
        "roles": claims.get("roles", []),
        "exp": int(time.time()) + 3600,  # 1 hour
    }).encode()
    return fernet.encrypt(payload).decode()

def validate_session_cookie(cookie_value: str) -> dict | None:
    """Decrypt and validate session cookie."""
    try:
        payload = json.loads(fernet.decrypt(cookie_value.encode()))
        if payload["exp"] < time.time():
            return None  # Expired
        return payload
    except Exception:
        return None
```

### WebSocket Connection Lifecycle
1. Browser loads OpenClaw UI page — auth gateway validates cookie, proxies HTML
2. OpenClaw JS opens WebSocket to same host — auth gateway validates cookie on upgrade request
3. WebSocket connection established — frames flow bidirectionally without re-auth
4. Connection drops → browser reconnects → cookie re-validated on new upgrade request

**Cookie is validated once per WebSocket connection**, not per message. This is efficient and correct.

---

## 7. Architecture Recommendation

### Recommended Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| **Ingress** | AGC with wildcard Ingress | Already deployed, supports WebSocket, no new infra |
| **Auth Gateway** | FastAPI (Python) | Reuses existing Entra ID validation, same language as backend |
| **OIDC Flow** | `msal` ConfidentialClientApplication | Server-side auth code flow for browser sessions |
| **Token Validation** | Existing `validate_entra_token()` | Already validates JWKS, audience, issuer |
| **WebSocket Proxy** | `websockets` library | Mature, async-native, bidirectional proxy |
| **HTTP Proxy** | `httpx` with streaming | Already in use across the backend |
| **Session** | Encrypted cookie (Fernet) | Stateless, no Redis needed |
| **TLS** | cert-manager + Let's Encrypt (DNS-01) | Standard wildcard cert solution for K8s |
| **Routing** | Subdomain-based | No SPA rewriting, natural isolation |

### What NOT to Do

| Anti-pattern | Why |
|-------------|-----|
| Deploy NGINX Ingress alongside AGC | Two ingress controllers = operational overhead, duplicate TLS management |
| Use oauth2-proxy for dynamic routing | Designed for static upstreams, can't resolve agent → pod dynamically |
| Use Traefik ForwardAuth | Would require replacing AGC entirely |
| Use path-based routing (`/agent/{id}/...`) | Breaks OpenClaw SPA routing, requires URL rewriting |
| Store sessions in Redis | Over-engineering for 2-5 tenants; encrypted cookies are sufficient |
| Re-validate Entra ID tokens at OpenClaw pod | OpenClaw has no auth — the gateway IS the auth boundary |

### Request Flow Summary

```
1. User navigates to agent-abc.agents.example.com
2. DNS resolves *.agents.example.com → AGC public IP
3. AGC terminates TLS, matches wildcard Ingress → auth-gateway:8000
4. Auth gateway checks session cookie:
   a. No cookie → redirect to Entra ID OIDC login → callback → set cookie → redirect back
   b. Valid cookie → extract user claims
5. Auth gateway extracts "abc" from Host header
6. Auth gateway queries Cosmos: agent "abc" → tenant_id → tenant slug "eng"
7. Auth gateway validates: user's tenant == agent's tenant (or user is platform admin)
8. Auth gateway proxies request to oc-openclaw-agent-abc-0.tenant-eng.svc.cluster.local:18789
9. For WebSocket: auth gateway establishes bidirectional proxy on upgrade
10. OpenClaw serves its native UI — user configures agent, chats, manages channels
```

---

## 8. Implementation Complexity Assessment

| Component | Complexity | LOC Estimate | Notes |
|-----------|-----------|--------------|-------|
| Auth gateway service | Medium | ~400 | OIDC flow + token validation + proxy |
| WebSocket proxy | Medium | ~100 | Bidirectional async proxy |
| Agent resolution | Low | ~50 | Cosmos lookup + DNS construction |
| Wildcard Ingress | Low | ~30 | AGC manifest, DNS record |
| NetworkPolicy update | Low | ~10 | Allow auth-gateway → tenant pods |
| cert-manager setup | Low | ~30 | Certificate + ClusterIssuer |
| Tenant access validation | Low | ~30 | Claims → tenant match |
| Frontend "Open Console" link | Low | ~20 | Link to agent-{id}.agents.domain |

**Total estimated service code: ~600 LOC Python** — a small, focused microservice.

---

## 9. Open Questions / Risks

| Question | Risk | Mitigation |
|----------|------|------------|
| AGC WebSocket timeout limits | Medium | AGC default idle timeout is 30s for WebSocket; may need annotation to increase |
| OpenClaw UI assets (fonts, images) | Low | All served from same origin (subdomain), should work |
| OpenClaw CSRF protection | Low | OpenClaw has no CSRF since auth.mode=none; gateway handles CSRF via cookie |
| Cookie domain security | Medium | Set `SameSite=Lax`, `Secure`, `HttpOnly`; wildcard domain `.agents.example.com` |
| Multiple AGC wildcard Ingresses | Low | AGC supports multiple Ingress resources; test wildcard + existing platform Ingress |
| auth-gateway pod scaling | Low | 2 replicas sufficient; encrypted cookies = stateless = horizontally scalable |
| Entra ID app registration | Low | May need a second app registration or additional redirect URIs for `*.agents.example.com/auth/callback` |

### Entra ID App Registration Note
The callback URL `https://*.agents.example.com/auth/callback` is NOT valid in Entra ID (wildcards not supported in redirect URIs). Options:
1. **Single callback URL**: `https://auth.agents.example.com/auth/callback` — dedicated auth subdomain, redirect to original agent subdomain after login
2. **Dynamic redirect URIs**: Register each agent's callback URL on deploy — operationally complex
3. **Shared callback + state parameter**: Auth gateway at a known URL handles all callbacks, uses `state` parameter to redirect to the correct agent subdomain

**Recommendation: Option 1** — single auth subdomain. Simple, secure, one redirect URI in Entra ID.

---

## 10. Sources

| Source | Type | Confidence |
|--------|------|------------|
| Platform codebase (`security.py`, `tenant.py`, `msal.ts`) | Direct | HIGH |
| `docs/v2-architecture-pivot.md` | Direct | HIGH |
| `docs/TODO.md` #10 | Direct | HIGH |
| `k8s/base/ingress.yaml` (AGC config) | Direct | HIGH |
| `k8s/overlays/tenant-template/network-policy.yaml` | Direct | HIGH |
| oauth2-proxy docs (WebSocket support) | Training data | MEDIUM |
| NGINX Ingress auth-url behavior | Training data | HIGH |
| AGC wildcard Ingress support | Training data | MEDIUM |
| Entra ID redirect URI constraints | Training data | HIGH |
| cert-manager DNS-01 wildcards | Training data | HIGH |
