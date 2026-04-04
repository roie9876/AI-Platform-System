# Research: OpenClaw MCP Integration Patterns & Native UI Exposure

**Project:** AI Agent Platform v4.0 — Architecture Pivot
**Researched:** 2026-04-04
**Overall Confidence:** HIGH (based on codebase analysis + production deployment evidence)

---

## 1. OpenClaw MCP Server Configuration

### How OpenClaw Consumes MCP Servers

**Confidence:** HIGH — verified from production code in `openclaw_service.py`

OpenClaw consumes MCP servers via its `config.raw` CR spec under `agents.defaults.mcpServers`. The format is a dictionary keyed by server name, with each entry containing a `url` field pointing to an SSE/StreamableHTTP MCP endpoint.

**CR Configuration Format:**
```yaml
apiVersion: openclaw.rocks/v1alpha1
kind: OpenClawInstance
metadata:
  name: my-agent
spec:
  config:
    raw:
      agents:
        defaults:
          mcpServers:
            cosmos-memory:
              url: "http://mcp-cosmos-memory.aiplatform.svc:8000/sse"
            azure-search:
              url: "http://mcp-azure-search.aiplatform.svc:8000/sse"
            platform-context:
              url: "http://mcp-platform-context.aiplatform.svc:8000/sse"
```

**Current Platform Implementation** (from `openclaw_service.py:1190-1193`):
```python
# MCP servers
mcp_servers: dict = {}
for url in openclaw_config.get("mcp_server_urls", []):
    name = url.rstrip("/").split("/")[-1].split(".")[0].replace("mcp-", "")
    mcp_servers[name] = {"url": url}
```

Then injected at line 1275:
```python
if mcp_servers:
    raw_config["agents"]["defaults"]["mcpServers"] = mcp_servers
```

**Key Finding:** MCP server URLs are injected into the CR at deploy time. The name is auto-derived from the URL path. Each MCP server entry is a simple `{url: string}` object — no auth headers, no additional config required for in-cluster services.

### Dynamic vs Deploy-Time Injection

**Confidence:** HIGH — verified from `_replace_cr()` and `update_agent()` in the codebase

MCP servers are configured in the CR spec and applied via the OpenClaw Operator. Two injection paths exist:

1. **Deploy-time** — `_build_cr()` → `_apply_simple()` or `_apply_resources()`: MCP servers included in initial CR creation
2. **Post-deploy update** — `update_agent()` → `_build_cr()` → `_replace_cr()`: Full CR replacement with updated MCP servers

**Critical finding:** `_replace_cr()` does a **full replace** (not merge patch). It fetches the existing CR's `resourceVersion`, bumps a timestamp annotation (`aiplatform.io/last-deployed`), and calls `replace_namespaced_custom_object()`. The OpenClaw Operator reconciles the diff and applies changes.

**What happens on CR update:**
- The Operator detects the change and reconciles
- OpenClaw reads the new `config.raw` and applies it
- **Pod is NOT restarted** if only config changes — the Operator updates the ConfigMap/config file and OpenClaw watches for changes
- However, certain changes (image, storage, env vars) DO trigger a pod restart via StatefulSet rollout

**Implication for v4.0:** Platform MCP servers CAN be injected after initial deployment by patching the CR. This is already the pattern used by `update_agent()`. No pod restart needed for config-only changes. MCP server URLs can be added/removed dynamically.

---

## 2. OpenClaw Native UI Architecture

### Web UI Overview

**Confidence:** HIGH — verified from production pod topology and gateway config

OpenClaw's web UI runs as part of the main OpenClaw process inside the pod. The pod has 4 containers:

| Container | Port | Purpose |
|-----------|------|---------|
| `openclaw` | internal | Core agent runtime (ReAct loop, channels, memory) |
| `wa-bridge` | internal | WhatsApp Baileys protocol bridge |
| `gateway-proxy` | 18790 (targetPort) → 18789 (service) | HTTP/WebSocket gateway for UI + API |
| `chromium` | internal | Headless browser sidecar for web browsing |

The `gateway-proxy` container serves:
- **Web UI** — SPA on root `/` (port 18789 via Service, 18790 on container)
- **WebSocket** — JSON-RPC protocol on `ws://host:18789/` (same port, protocol upgrade)
- **OpenAI-compatible API** — `POST /v1/chat/completions` (when `chatCompletions.enabled: true`)

### WebSocket Protocol

**Confidence:** HIGH — verified from `openclaw_service.py:305-350`

The WebSocket handshake follows a custom JSON-RPC protocol:

1. **Client connects** to `ws://host:18789/`
2. **Server sends** `connect.challenge` event
3. **Client sends** `connect` method with params:
   ```json
   {
     "type": "req",
     "id": "uuid",
     "method": "connect",
     "params": {
       "minProtocol": 3,
       "maxProtocol": 3,
       "client": {
         "id": "openclaw-control-ui",
         "version": "control-ui",
         "platform": "linux",
         "mode": "webchat",
         "instanceId": "aiplatform-{name}"
       },
       "role": "operator"
     }
   }
   ```
4. **Server sends** `connect.result` with session info
5. Bidirectional JSON-RPC messaging begins

**WebSocket requirements for the UI:**
- Full duplex WebSocket (not SSE)
- `Origin` header must match the gateway host
- No auth token required when `auth.mode: none` (current config)
- WebSocket upgrade must be supported through the reverse proxy chain

### Authentication Configuration

**Confidence:** HIGH — verified from gateway config in `openclaw_service.py:1254-1268`

Current production config:
```python
raw_config["gateway"] = {
    "auth": {"mode": "none"},
    "bind": "loopback",
    "controlUi": {"allowedOrigins": ["*"]},
    "trustedProxies": ["127.0.0.0/8"],
    "http": {
        "endpoints": {
            "chatCompletions": {"enabled": True},
        }
    },
}
```

**Key findings:**
- `auth.mode: none` — no authentication at the OpenClaw level (platform handles auth)
- `bind: loopback` — gateway only listens on 127.0.0.1 (pod-internal)
- `controlUi.allowedOrigins: ["*"]` — CORS allowed from all origins
- `trustedProxies: ["127.0.0.0/8"]` — only trusts loopback proxies

**For v4.0 native UI exposure**, the gateway config must change:
```python
raw_config["gateway"] = {
    "auth": {"mode": "none"},
    "bind": "0.0.0.0",        # <-- Must listen on all interfaces
    "controlUi": {
        "allowedOrigins": [
            "https://*.agents.stumsft.com",
            "https://aiplatform.stumsft.com",
        ],
    },
    "trustedProxies": ["10.0.0.0/8"],  # <-- Trust cluster CIDR
    "http": {
        "endpoints": {
            "chatCompletions": {"enabled": True},
        }
    },
}
```

### URL Paths Served

| Path | Content | Protocol |
|------|---------|----------|
| `/` | SPA web UI (HTML/JS/CSS) | HTTP |
| `/` | JSON-RPC control protocol | WebSocket (upgrade) |
| `/v1/chat/completions` | OpenAI-compatible API | HTTP POST |
| `/readyz` | Readiness probe | HTTP GET |

The UI is a single-page application — all routes are served from `/` with client-side routing. **This means subdomain routing is strongly preferred** over path-based routing, because path rewriting would break the SPA's asset URLs and client-side router.

---

## 3. Reverse Proxy Patterns for WebSocket UIs on Kubernetes

### Current Ingress Controller: Application Gateway for Containers (AGC)

**Confidence:** HIGH — verified from `k8s/base/ingress.yaml` and `infra/modules/agc.bicep`

The platform currently uses **Azure Application Gateway for Containers (AGC)** with the ALB Controller (`ingressClassName: azure-alb-external`). This is NOT NGINX Ingress Controller.

**AGC WebSocket Support:**
- AGC supports WebSocket upgrade natively
- WebSocket connections are proxied through the managed Application Gateway
- No special annotations needed — WebSocket upgrade is automatic on HTTP/1.1 upgrade requests
- Session affinity available via `alb.networking.azure.io/session-affinity` annotation

### Pattern Analysis: Auth Proxy for WebSocket UI on AGC

| Pattern | WebSocket Support | Auth Integration | AGC Compatible | Complexity |
|---------|-------------------|------------------|----------------|------------|
| AGC + OAuth2 Proxy sidecar | ✅ | Entra ID OIDC | ✅ | Medium |
| AGC + custom auth middleware | ✅ | Entra ID JWT | ✅ | Low |
| NGINX Ingress + auth_request | ✅ | Entra ID subrequest | ❌ (requires NGINX IC) | Medium |
| Traefik + ForwardAuth | ✅ | Entra ID subrequest | ❌ (requires Traefik) | Medium |
| Emissary/Ambassador | ✅ | External filter | ❌ (requires Emissary) | High |

### Recommended Pattern: AGC + Auth Gateway Pod

**Confidence:** HIGH — this aligns with existing architecture

Since the platform already uses AGC, the simplest pattern is:

```
Browser → AGC (wildcard Ingress) → auth-gateway pod → OpenClaw pod
```

**Auth gateway** is a lightweight reverse proxy (deployed per-tenant or shared) that:
1. Intercepts all requests to `*.agents.stumsft.com`
2. Validates Entra ID JWT token (from cookie or Authorization header)
3. Checks tenant RBAC (user can access this agent?)
4. Proxies HTTP + WebSocket to the target OpenClaw pod
5. Strips auth headers before forwarding (OpenClaw has `auth.mode: none`)

**Why not OAuth2 Proxy?** OAuth2 Proxy works well for simple HTTP but has known issues with WebSocket connections for long-lived sessions. A custom auth gateway gives full control over WebSocket upgrade handling and can be built on the existing FastAPI stack the team already knows.

**Implementation options for the auth gateway:**
1. **FastAPI + websockets** — Python, familiar stack, but may have performance concerns for long-lived WebSocket proxying
2. **Go reverse proxy** — `net/http/httputil.ReverseProxy` + `gorilla/websocket`, better for persistent connections
3. **Caddy** — automatic TLS, built-in reverse proxy, WebSocket-transparent, configurable via API

**Recommended: Caddy as auth-gateway container.** Caddy natively handles WebSocket proxying transparently (no special config), supports custom auth middleware via HTTP subrequests, and can be configured per-tenant via API. Deploy as a DaemonSet or per-namespace pod.

**Alternative: Extend the existing api-gateway.** Add a `/agents/{id}/console/*` route that does auth + WebSocket proxy inline. Simplest but couples auth concerns with the API gateway.

### WebSocket Proxy Considerations

| Concern | Solution |
|---------|----------|
| Connection timeout | AGC default 30s idle → set `alb.networking.azure.io/connection-idle-timeout` to 3600 |
| Buffering | Disable response buffering for WebSocket streams |
| Max payload | Default 4MB → increase if agents send large tool outputs |
| Protocol upgrade | AGC handles HTTP/1.1 → WebSocket upgrade natively |
| Multiple hops (AGC → auth → OpenClaw) | Each proxy must forward `Upgrade: websocket` and `Connection: Upgrade` headers |

---

## 4. Wildcard Ingress on AKS with AGC

### Current Setup

**Confidence:** HIGH — verified from Bicep and K8s manifests

- **Ingress Controller:** Application Gateway for Containers (AGC) via ALB Controller
- **Ingress Class:** `azure-alb-external`
- **Current host:** Single FQDN (AGC-generated hostname)
- **TLS:** `agc-tls-secret` (single-host cert)
- **DNS:** No custom DNS zone in Bicep — currently using AGC-generated FQDN

### Wildcard DNS + TLS on AGC

**Option A: Azure DNS Zone + cert-manager (Recommended)**

```
*.agents.stumsft.com  →  CNAME → AGC frontend IP/FQDN
```

1. **Azure DNS Zone** — `agents.stumsft.com` zone in Azure DNS
2. **Wildcard A/CNAME record** — `*.agents.stumsft.com` → AGC frontend IP
3. **cert-manager** with Let's Encrypt — DNS-01 challenge for wildcard cert
4. **Certificate** stored as K8s Secret `agents-wildcard-tls`

```yaml
# cert-manager ClusterIssuer for Let's Encrypt + Azure DNS
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v2.api.letsencrypt.org/directory
    email: platform@stumsft.com
    privateKeySecretRef:
      name: letsencrypt-account-key
    solvers:
      - dns01:
          azureDNS:
            subscriptionID: ${SUBSCRIPTION_ID}
            resourceGroupName: ${RG_NAME}
            hostedZoneName: agents.stumsft.com
            environment: AzurePublicCloud
            managedIdentity:
              clientID: ${WORKLOAD_CLIENT_ID}
---
# Wildcard Certificate
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: agents-wildcard-cert
  namespace: aiplatform
spec:
  secretName: agents-wildcard-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - "*.agents.stumsft.com"
    - "agents.stumsft.com"
```

**Option B: Azure Key Vault Certificate (Manual/Azure-Managed)**

Upload a wildcard cert to Key Vault, mount via CSI. Less automation but no cert-manager dependency.

### Ingress Strategy: One Wildcard Ingress vs Per-Agent Ingress

**Comparison:**

| Approach | Pros | Cons |
|----------|------|------|
| **Single wildcard Ingress** | Simple, one manifest, no dynamic creation | Must handle routing in the backend, all agents share config, harder per-agent TLS settings |
| **Per-agent Ingress** | Precise routing, independent lifecycle, can be in tenant namespace | Dynamic creation needed, more K8s objects, AGC reconciliation per Ingress |

**Recommended: Single wildcard Ingress + auth-gateway routing**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: agents-wildcard-ingress
  namespace: aiplatform
  annotations:
    alb.networking.azure.io/alb-id: "${AGC_RESOURCE_ID}"
    alb.networking.azure.io/alb-frontend: "agents-frontend"
spec:
  ingressClassName: azure-alb-external
  tls:
    - hosts:
        - "*.agents.stumsft.com"
      secretName: agents-wildcard-tls
  rules:
    - host: "*.agents.stumsft.com"
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: agents-auth-gateway
                port:
                  number: 8080
```

The `agents-auth-gateway` service receives all requests, extracts the agent ID from the hostname (`agent-{id}.agents.stumsft.com`), validates auth, resolves the target OpenClaw pod, and proxies the request.

**Why single Ingress:** AGC/ALB Controller has rate limits on Ingress reconciliation. Creating/deleting Ingress resources per agent adds latency and complexity. A single wildcard Ingress with a smart auth-gateway is simpler and more predictable.

### AGC-Specific Considerations

- **ALB Frontend:** AGC requires a named frontend. The wildcard Ingress needs its own frontend separate from the main platform Ingress. Use `alb.networking.azure.io/alb-frontend: "agents-frontend"` annotation.
- **Cross-namespace routing:** The auth-gateway needs to proxy to OpenClaw pods in `tenant-{slug}` namespaces. This works because it's the gateway pod itself making the HTTP call (not requiring cross-namespace Service references in Ingress).
- **NetworkPolicy update:** The tenant `network-policy.yaml` currently allows ingress from `alb-controller` namespace and same-namespace pods only. Must add ingress from `aiplatform` namespace (where auth-gateway runs) on port 18789.

```yaml
# Addition to tenant NetworkPolicy
ingress:
  # Allow from auth-gateway in aiplatform namespace
  - from:
      - namespaceSelector:
          matchLabels:
            kubernetes.io/metadata.name: aiplatform
        podSelector:
          matchLabels:
            app.kubernetes.io/name: agents-auth-gateway
    ports:
      - protocol: TCP
        port: 18789
```

---

## 5. MCP Server Lifecycle: Hot-Injection vs Pod Restart

### Can MCP Servers Be Added to a Running Instance?

**Confidence:** HIGH — verified from operator behavior and codebase

**Answer: YES, with caveats.**

The lifecycle flow:

1. Platform patches the `OpenClawInstance` CR with new `mcpServers` entries
2. OpenClaw Operator detects the CR change
3. Operator updates the ConfigMap that holds the agent's `config.raw`
4. OpenClaw watches its config file for changes and hot-reloads

**What happens in practice:**
- **Config-only changes** (mcpServers, system prompt, channel settings): OpenClaw hot-reloads without pod restart. The Operator updates the ConfigMap, OpenClaw's file watcher picks it up, and the new MCP servers become available.
- **Structural changes** (new env vars, image change, storage): Operator triggers a StatefulSet rollout → pod restart.

**Evidence from codebase:** The `update_agent()` method in `openclaw_service.py` calls `_replace_cr()` which does a full CR replace. The annotation `aiplatform.io/last-deployed` is bumped to force operator reconciliation. This is the same pattern used today for config updates and does NOT trigger a pod restart for config-only changes.

### MCP Server Hot-Injection API Flow

```
Platform API                 K8s API              OpenClaw Operator        OpenClaw Runtime
    │                           │                       │                       │
    │  PATCH CR (add MCP srv)   │                       │                       │
    ├──────────────────────────►│                       │                       │
    │                           │  Watch event          │                       │
    │                           ├──────────────────────►│                       │
    │                           │                       │  Update ConfigMap     │
    │                           │                       ├──────────────────────►│
    │                           │                       │                       │  Hot-reload config
    │                           │                       │                       │  Connect to new MCP
    │                           │                       │                       │  ✅ Tools available
```

### Implications for v4.0

1. **Platform MCP servers can be pre-injected** at deploy time — add their URLs to the CR when creating the OpenClawInstance
2. **Additional MCP servers can be added later** — patch the CR, operator reconciles, OpenClaw hot-reloads
3. **Users can also add MCP servers via OpenClaw's native UI** — these are stored in OpenClaw's local config on the PVC, separate from the CR
4. **Conflict risk:** If both the platform CR and the user's UI-added config both define MCP servers, the resulting config is a merge. The CR-defined servers are always present; UI-added servers are additive. No conflict as long as names don't collide.

### MCP Server URL Requirements

- Must be reachable from the OpenClaw pod (in-cluster Service URLs work)
- Must use SSE transport (OpenClaw connects as MCP client via SSE)
- Must respond to MCP protocol negotiation (list_tools, call_tool)
- No auth needed for in-cluster services (protected by NetworkPolicy)

---

## 6. Synthesis: Implications for v4.0 Phases

### Phase Dependencies and Ordering

Based on this research, the recommended phase ordering is:

1. **Infrastructure Foundation** — Wildcard DNS, cert-manager, wildcard certificate, auth-gateway skeleton
2. **Token Proxy** — LLM counting proxy (independent, no dependency on UI exposure)
3. **Platform MCP Servers** — Build `mcp-cosmos-memory`, `mcp-azure-search`, `mcp-platform-context`; auto-inject URLs in CR
4. **Expose Native UI** — Update gateway bind, NetworkPolicy, deploy auth-gateway, create wildcard Ingress
5. **Dual-mode** — Both UIs working simultaneously
6. **Simplify** — Deprecate redundant platform UI pages

### Critical Configuration Changes for Native UI Exposure

| Config | Current Value | Required Value | Where |
|--------|---------------|----------------|-------|
| `gateway.bind` | `loopback` | `0.0.0.0` | CR `config.raw` |
| `gateway.controlUi.allowedOrigins` | `["*"]` | `["https://*.agents.stumsft.com"]` | CR `config.raw` |
| `gateway.trustedProxies` | `["127.0.0.0/8"]` | `["10.0.0.0/8"]` | CR `config.raw` |
| NetworkPolicy ingress | ALB + same-namespace | + aiplatform namespace on 18789 | tenant network-policy.yaml |
| Service port | 18789 (ClusterIP) | 18789 (ClusterIP, no change) | — |

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| WebSocket timeout through AGC | Medium | Set idle timeout to 3600s via annotation |
| Auth bypass if gateway misconfigured | High | Auth-gateway is single entry point; OpenClaw has `auth.mode: none` by design, security depends entirely on auth-gateway |
| MCP server name collision (platform vs user-added) | Low | Use `platform-` prefix for platform MCP server names |
| Config merge conflicts (CR vs UI-added) | Low | CR defines infrastructure MCP servers; UI defines user-added ones; OpenClaw merges both |
| AGC frontend limit | Low | AGC supports multiple frontends; use dedicated `agents-frontend` |

---

## Sources

- `backend/app/services/openclaw_service.py` — CR builder, gateway config, MCP injection, WebSocket protocol
- `k8s/base/openclaw/openclawinstance.yaml` — Production CR example
- `k8s/base/ingress.yaml` — Current AGC Ingress config
- `k8s/overlays/tenant-template/network-policy.yaml` — Tenant NetworkPolicy
- `infra/modules/agc.bicep` — Application Gateway for Containers setup
- `docs/TODO.md` — TODO items 10, 11, 12 with original architecture notes
- `docs/v2-architecture-pivot.md` — Full architecture pivot document
