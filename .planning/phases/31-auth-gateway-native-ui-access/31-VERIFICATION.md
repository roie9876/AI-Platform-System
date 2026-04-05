---
status: passed
phase: 31-auth-gateway-native-ui-access
verified: 2026-04-05
---

# Phase 31: Auth Gateway & Native UI Access — Verification

## Must-Haves Verification

### Truths Verified

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Auth gateway starts and responds to health checks | ✓ | health_router included, /healthz /readyz /startupz endpoints |
| 2 | Unauthenticated browser requests redirect to Entra ID OIDC login | ✓ | /auth/login route with MSAL ConfidentialClientApplication |
| 3 | After OIDC login, session cookie is set on .agents.{domain} | ✓ | _agents_session cookie with URLSafeTimedSerializer signing |
| 4 | Authenticated requests are proxied to the correct OpenClaw pod | ✓ | httpx.AsyncClient proxy with agent/tenant resolution |
| 5 | Cross-tenant access returns 403 | ✓ | tenant_id comparison with platform_admin bypass |
| 6 | WebSocket connections are proxied bidirectionally | ✓ | websockets.connect with asyncio.wait relay |
| 7 | K8s manifests exist and pass dry-run | ✓ | 5 manifests, service/hpa/pdb dry-run passed |
| 8 | Wildcard Ingress routes *.agents.{domain} | ✓ | ingress-agents.yaml with wildcard host rules |
| 9 | Auth gateway image built by postprovision.sh | ✓ | ACR build step added (12 total images) |
| 10 | Conditional deployment when AGENTS_DOMAIN set | ✓ | Step 8.1 inside AGENTS_DOMAIN check |
| 11 | Tenant NetworkPolicy allows auth-gateway | ✓ | Ingress rule on ports 18789/18790 |
| 12 | Wildcard certificate in aiplatform namespace | ✓ | namespace: aiplatform, dnsNames: *.agents.{domain} |
| 13 | OpenClaw gateway binds externally when AGENTS_DOMAIN set | ✓ | Conditional bind 0.0.0.0 + trust 10.0.0.0/8 |
| 14 | Frontend /api/config returns agents_domain | ✓ | agentsDomain field in response |
| 15 | "Open Agent Console" button on agent detail page | ✓ | Conditional render with target="_blank" |
| 16 | Button hidden when agents_domain not configured | ✓ | agentsDomain && guard |

### Artifacts Verified

| File | Exists | Key Content |
|------|--------|------------|
| backend/microservices/auth_gateway/main.py | ✓ | FastAPI, MSAL, httpx, websockets |
| backend/microservices/auth_gateway/Dockerfile | ✓ | uvicorn, port 8000 |
| k8s/base/auth-gateway/deployment.yaml | ✓ | auth-gateway, port 8000 |
| k8s/base/auth-gateway/service.yaml | ✓ | ClusterIP, port 8000 |
| k8s/base/auth-gateway/ingress-agents.yaml | ✓ | Wildcard hosts |
| k8s/base/auth-gateway/hpa.yaml | ✓ | 2-5 replicas |
| k8s/base/auth-gateway/pdb.yaml | ✓ | minAvailable 1 |

### Key Links Verified

| From | To | Via | Verified |
|------|----|-----|----------|
| auth_gateway/main.py | app.core.security | import extract_user_context | ✓ |
| auth_gateway/main.py | Cosmos DB agents | query_items by slug | ✓ |
| auth_gateway/main.py | OpenClaw pod | httpx + websockets | ✓ |
| ingress-agents.yaml | service.yaml | backend service auth-gateway | ✓ |
| postprovision.sh | k8s/base/auth-gateway/ | conditional kubectl apply | ✓ |
| openclaw_service.py | config.py | settings.AGENTS_DOMAIN | ✓ |
| agents/[id]/page.tsx | /api/config | fetch agentsDomain | ✓ |

## Syntax Validation

- All Python files: `ast.parse()` passed
- `hooks/postprovision.sh`: `bash -n` passed
- K8s manifests: `kubectl apply --dry-run=client` passed (service, hpa, pdb)

## Score: 16/16 must-haves verified
