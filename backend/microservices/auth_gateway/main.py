"""Auth Gateway — OIDC authentication + reverse proxy for OpenClaw native UIs.

Handles browser-based OIDC login via Entra ID, session management with signed
cookies, agent-to-pod resolution from Cosmos DB, and transparent HTTP/WebSocket
proxying to per-tenant OpenClaw pods.

Two routing modes (auto-selected):
  1. Subdomain: agent-{slug}.agents.{domain} — when AGENTS_DOMAIN is set.
  2. Path:      {base}/agents/{slug}/...      — when AGENTS_DOMAIN is empty but
     PLATFORM_BASE_URL (or AGC FQDN from configmap) is available.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from urllib.parse import quote, urlencode

import httpx
import msal
import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.security import extract_user_context
from app.core.telemetry import init_telemetry
from app.health import health_router
from app.repositories.cosmos_client import close_cosmos_client, get_cosmos_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AGENTS_DOMAIN = os.getenv("AGENTS_DOMAIN", "")
PLATFORM_BASE_URL = os.getenv("PLATFORM_BASE_URL", "").rstrip("/")
SESSION_TTL = int(os.getenv("SESSION_TTL", "3600"))
AGENT_CACHE_TTL = int(os.getenv("AGENT_CACHE_TTL", "60"))
COOKIE_SECRET = os.getenv("COOKIE_SECRET", secrets.token_urlsafe(32))
COOKIE_NAME = "_agents_session"

# Routing mode: subdomain (AGENTS_DOMAIN set) or path (fallback to PLATFORM_BASE_URL)
ROUTE_MODE = "subdomain" if AGENTS_DOMAIN else "path"

_signer = URLSafeTimedSerializer(COOKIE_SECRET)

# ---------------------------------------------------------------------------
# Cookie-embedded sessions (no server-side state — survives multi-pod)
# ---------------------------------------------------------------------------


def create_signed_cookie(user_context: dict) -> str:
    """Sign user_context into a tamper-proof cookie value."""
    return _signer.dumps(user_context)


def load_signed_cookie(cookie_value: str) -> dict | None:
    """Verify signature + TTL and return user_context, or None."""
    try:
        return _signer.loads(cookie_value, max_age=SESSION_TTL)
    except BadSignature:
        return None


# ---------------------------------------------------------------------------
# Agent + Tenant resolution caches
# ---------------------------------------------------------------------------
_agent_cache: dict[str, tuple[dict, float]] = {}
_tenant_cache: dict[str, tuple[str, float]] = {}


async def resolve_agent(agent_slug: str) -> dict | None:
    """Resolve agent by slug from Cosmos DB with TTL cache."""
    now = time.time()
    cached = _agent_cache.get(agent_slug)
    if cached and cached[1] > now:
        return cached[0]

    client = await get_cosmos_client()
    if client is None:
        return None

    db = client.get_database_client(settings.COSMOS_DATABASE)
    container = db.get_container_client("agents")

    items = []
    async for item in container.query_items(
        query="SELECT * FROM c WHERE c.slug = @slug OR c.id = @slug",
        parameters=[{"name": "@slug", "value": agent_slug}],
    ):
        items.append(item)
    if not items:
        return None

    agent_doc = items[0]
    _agent_cache[agent_slug] = (agent_doc, now + AGENT_CACHE_TTL)
    return agent_doc


async def resolve_tenant_slug(tenant_id: str) -> str | None:
    """Resolve tenant_id → tenant slug from Cosmos DB with TTL cache."""
    now = time.time()
    cached = _tenant_cache.get(tenant_id)
    if cached and cached[1] > now:
        return cached[0]

    client = await get_cosmos_client()
    if client is None:
        return None

    db = client.get_database_client(settings.COSMOS_DATABASE)
    container = db.get_container_client("tenants")

    items = []
    async for item in container.query_items(
        query="SELECT c.slug FROM c WHERE c.id = @tid",
        parameters=[{"name": "@tid", "value": tenant_id}],
    ):
        items.append(item)
    if not items:
        return None

    slug = items[0].get("slug", "")
    _tenant_cache[tenant_id] = (slug, now + AGENT_CACHE_TTL)
    return slug


# ---------------------------------------------------------------------------
# MSAL + HTTP client globals
# ---------------------------------------------------------------------------
_msal_app: msal.ConfidentialClientApplication | None = None
_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _msal_app, _http_client

    configure_logging(service_name="auth-gateway")
    init_telemetry(service_name="auth-gateway")

    if not AGENTS_DOMAIN:
        logger.warning(
            "AGENTS_DOMAIN not set — running in path-based mode (PLATFORM_BASE_URL=%s)",
            PLATFORM_BASE_URL,
        )

    entra_client_id = settings.ENTRA_APP_CLIENT_ID or settings.AZURE_CLIENT_ID
    entra_client_secret = settings.ENTRA_CLIENT_SECRET

    _msal_app = msal.ConfidentialClientApplication(
        client_id=entra_client_id,
        client_credential=entra_client_secret,
        authority=f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}",
    )

    _http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=10.0),
        follow_redirects=True,
    )

    logger.info(
        "Auth gateway started — domain=%s, client_id=%s",
        AGENTS_DOMAIN,
        entra_client_id,
    )
    yield

    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
    await close_cosmos_client()


app = FastAPI(
    title="AI Platform - Auth Gateway",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(health_router)


# ---------------------------------------------------------------------------
# Helpers — build base URL for OIDC redirects and cookie domain
# ---------------------------------------------------------------------------

def _base_url() -> str:
    """Return the external base URL for OIDC redirects."""
    if AGENTS_DOMAIN:
        return f"https://agents.{AGENTS_DOMAIN}"
    return PLATFORM_BASE_URL  # e.g. https://arh2b5...alb.azure.com


def _cookie_domain() -> str | None:
    """Cookie domain — scoped to agents subdomain tree or None (host-only)."""
    if AGENTS_DOMAIN:
        return f".agents.{AGENTS_DOMAIN}"
    return None  # host-only cookie on the AGC FQDN


def _set_session_cookie(response, signed_value: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=signed_value,
        domain=_cookie_domain(),
        path="/agents/" if ROUTE_MODE == "path" else "/",
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=SESSION_TTL,
    )


def _delete_session_cookie(response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        domain=_cookie_domain(),
        path="/agents/" if ROUTE_MODE == "path" else "/",
    )


# ---------------------------------------------------------------------------
# Host parsing helpers
# ---------------------------------------------------------------------------

def _parse_agent_slug(host: str) -> str | None:
    """Extract agent slug from agent-{slug}.agents.{domain} hostname.

    Returns None if the host is the base agents.{domain} or doesn't match.
    """
    if not AGENTS_DOMAIN:
        return None

    agents_suffix = f".agents.{AGENTS_DOMAIN}"
    base_host = f"agents.{AGENTS_DOMAIN}"

    # Strip port if present
    hostname = host.split(":")[0]

    if hostname == base_host:
        return None  # base domain, no agent slug

    if hostname.endswith(agents_suffix):
        prefix = hostname[: -len(agents_suffix)]
        if prefix.startswith("agent-"):
            return prefix[len("agent-"):]
    return None


def _is_agents_domain(host: str) -> bool:
    """Check if host belongs to the agents domain at all."""
    if not AGENTS_DOMAIN:
        return False
    hostname = host.split(":")[0]
    agents_suffix = f"agents.{AGENTS_DOMAIN}"
    return hostname == agents_suffix or hostname.endswith(f".{agents_suffix}")


# ---------------------------------------------------------------------------
# Error pages
# ---------------------------------------------------------------------------

def _error_page(status: int, title: str, message: str) -> HTMLResponse:
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; display: flex;
         justify-content: center; align-items: center; min-height: 100vh; margin: 0;
         background: #f9fafb; color: #111827; }}
  .card {{ background: white; border-radius: 12px; padding: 2rem 3rem;
           box-shadow: 0 1px 3px rgba(0,0,0,.1); text-align: center; max-width: 420px; }}
  h1 {{ font-size: 1.5rem; margin-bottom: .5rem; }}
  p {{ color: #6b7280; line-height: 1.6; }}
  a {{ color: #7C3AED; text-decoration: none; }}
</style></head>
<body><div class="card">
  <h1>{title}</h1>
  <p>{message}</p>
</div></body></html>"""
    return HTMLResponse(content=html, status_code=status)


# ---------------------------------------------------------------------------
# localStorage namespace injection — isolates per-agent console sessions
# + UI branding — shows agent name instead of "OpenClaw" in the sidebar
# ---------------------------------------------------------------------------

_LS_NAMESPACE_SCRIPT = """<script>(function(){
var s=window.location.pathname.split('/');if(s[1]!=='agents'||!s[2])return;
var slug=s[2],p='__oc_'+slug+'_',ls=window.localStorage;
var _set=Storage.prototype.setItem,_rem=Storage.prototype.removeItem,_get=Storage.prototype.getItem;
var old=_get.call(ls,'__oc_active_slug__');
if(old&&old!==slug){var op='__oc_'+old+'_',sv=[];
for(var i=0;i<ls.length;i++){var k=ls.key(i);if(k&&k.indexOf('openclaw')===0&&k.indexOf('__oc_')!==0)sv.push(k)}
for(i=0;i<sv.length;i++)_set.call(ls,op+sv[i],_get.call(ls,sv[i]))}
var cl=[];for(var i=0;i<ls.length;i++){var k=ls.key(i);if(k&&k.indexOf('openclaw')===0&&k.indexOf('__oc_')!==0)cl.push(k)}
for(i=0;i<cl.length;i++)_rem.call(ls,cl[i]);
var rs=[];for(var i=0;i<ls.length;i++){var k=ls.key(i);if(k&&k.indexOf(p)===0)rs.push(k)}
for(i=0;i<rs.length;i++)_set.call(ls,rs[i].substring(p.length),_get.call(ls,rs[i]));
_set.call(ls,'__oc_active_slug__',slug);
Storage.prototype.setItem=function(k,v){_set.call(this,k,v);
if(this===ls&&typeof k==='string'&&k.indexOf('openclaw')===0)try{_set.call(this,p+k,v)}catch(e){}};
Storage.prototype.removeItem=function(k){_rem.call(this,k);
if(this===ls&&typeof k==='string'&&k.indexOf('openclaw')===0)try{_rem.call(this,p+k)}catch(e){}};
})();</script>"""

def _inject_localstorage_namespace(content: bytes, agent_slug: str, agent_name: str = "", nonce: str = "") -> bytes:
    """Inject localStorage-namespacing script into HTML <head>."""
    html = content.decode("utf-8", errors="replace")
    # Replace page title with agent name
    if agent_name:
        html = html.replace("<title>OpenClaw Control</title>", f"<title>{agent_name} — Control</title>")
    script = _LS_NAMESPACE_SCRIPT
    if nonce:
        script = script.replace('<script>', f'<script nonce="{nonce}">')
    for tag in ("<head>", "<HEAD>"):
        if tag in html:
            html = html.replace(tag, tag + script, 1)
            return html.encode("utf-8")
    return (script + html).encode("utf-8")


def _patch_js_branding(content: bytes, agent_name: str) -> bytes:
    """Replace OpenClaw branding strings in JS bundle with agent name."""
    text = content.decode("utf-8", errors="replace")
    # Sidebar brand title: <span class="sidebar-brand__title">OpenClaw</span>
    text = text.replace('>OpenClaw</span>', f'>{agent_name}</span>')
    # Image alt attributes
    text = text.replace('alt="OpenClaw"', f'alt="{agent_name}"')
    return text.encode("utf-8")


# ---------------------------------------------------------------------------
# OIDC routes — path-based mode (/agents/auth/*)
# ---------------------------------------------------------------------------

@app.get("/agents/auth/login")
async def path_auth_login(request: Request):
    """Initiate OIDC login (path-based mode)."""
    return_to = str(request.query_params.get("return_to", ""))
    redirect_uri = f"{_base_url()}/agents/auth/callback"
    auth_url = _msal_app.get_authorization_request_url(
        scopes=[],
        redirect_uri=redirect_uri,
        state=json.dumps({"return_to": return_to}),
    )
    return RedirectResponse(url=auth_url)


@app.get("/agents/auth/callback")
async def path_auth_callback(request: Request):
    """Handle OIDC callback (path-based mode)."""
    code = request.query_params.get("code")
    state_raw = request.query_params.get("state", "{}")
    error = request.query_params.get("error")

    if error:
        return _error_page(401, "Authentication Failed", request.query_params.get("error_description", error))
    if not code:
        return _error_page(400, "Bad Request", "Missing authorization code.")

    redirect_uri = f"{_base_url()}/agents/auth/callback"
    result = _msal_app.acquire_token_by_authorization_code(
        code=code,
        scopes=[],
        redirect_uri=redirect_uri,
    )

    if "error" in result:
        logger.error("OIDC token exchange failed: %s", result.get("error_description"))
        return _error_page(401, "Authentication Failed", result.get("error_description", "Token exchange failed."))

    claims = result.get("id_token_claims", {})
    user_context = extract_user_context(claims)
    signed = create_signed_cookie(user_context)

    try:
        state = json.loads(state_raw)
    except (json.JSONDecodeError, TypeError):
        state = {}
    return_to = state.get("return_to", f"{_base_url()}/agents/")

    response = RedirectResponse(url=return_to)
    _set_session_cookie(response, signed)
    return response


@app.get("/agents/auth/logout")
async def path_auth_logout(request: Request):
    """Clear session (path-based mode)."""

    entra_client_id = settings.ENTRA_APP_CLIENT_ID or settings.AZURE_CLIENT_ID
    logout_url = (
        f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={quote(f'{_base_url()}/agents/')}"
    )
    response = RedirectResponse(url=logout_url)
    _delete_session_cookie(response)
    return response


# ---------------------------------------------------------------------------
# HTTP proxy — path-based mode (/agents/{slug}/{path})
# ---------------------------------------------------------------------------

@app.api_route(
    "/agents/{agent_slug}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def path_proxy_http(request: Request, agent_slug: str, path: str = ""):
    """Path-based HTTP proxy — authenticates and forwards to OpenClaw pod."""
    user_context = _get_user_from_cookie(request)
    if user_context is None:
        # Build return URL from _base_url() — request.url has http:// behind TLS-terminating AGC
        current_url = f"{_base_url()}{request.url.path}"
        if request.url.query:
            current_url = f"{current_url}?{request.url.query}"
        login_url = f"{_base_url()}/agents/auth/login?return_to={quote(current_url)}"
        return RedirectResponse(url=login_url)

    agent = await resolve_agent(agent_slug)
    if agent is None:
        return _error_page(404, "Agent Not Found", f"No agent with slug '{agent_slug}' was found.")

    agent_tenant_id = agent.get("tenant_id", "")
    user_tenant_id = user_context.get("tenant_id", "")
    user_roles = user_context.get("roles", [])
    if agent_tenant_id != user_tenant_id and "platform_admin" not in user_roles:
        return _error_page(403, "Access Denied", "This agent belongs to another tenant.")

    tenant_slug = await resolve_tenant_slug(agent_tenant_id)
    if tenant_slug is None:
        return _error_page(500, "Internal Error", "Could not resolve tenant.")

    instance_name = agent.get("openclaw_instance_name", "")
    if not instance_name:
        instance_name = f"oc-openclaw-agent-{agent.get('id', agent_slug)[:8]}"
    pod_url = f"http://{instance_name}.tenant-{tenant_slug}.svc.cluster.local:18789"

    target_url = f"{pod_url}/{path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    body = await request.body()
    headers = dict(request.headers)
    for hop_header in ("host", "connection", "keep-alive", "transfer-encoding", "upgrade"):
        headers.pop(hop_header, None)
    client_ip = request.client.host if request.client else "unknown"
    headers["x-forwarded-for"] = client_ip
    headers["x-real-ip"] = client_ip
    headers["x-forwarded-proto"] = "https"

    try:
        resp = await _http_client.request(method=request.method, url=target_url, headers=headers, content=body)
        resp_headers = dict(resp.headers)
        for h in ("connection", "keep-alive", "transfer-encoding", "content-encoding", "content-length"):
            resp_headers.pop(h, None)
        content = resp.content
        content_type = resp_headers.get("content-type", "")
        agent_name = agent.get("name", "")
        if "text/html" in content_type:
            nonce = secrets.token_urlsafe(16)
            content = _inject_localstorage_namespace(content, agent_slug, agent_name, nonce=nonce)
            # Allow our injected inline script via CSP nonce + fix blob:/worker for file uploads
            csp = resp_headers.get("content-security-policy", "")
            if csp:
                if "script-src" in csp:
                    csp = csp.replace("script-src ", f"script-src 'nonce-{nonce}' ")
                if "connect-src" in csp and "blob:" not in csp:
                    csp = csp.replace("connect-src ", "connect-src blob: ")
                if "worker-src" not in csp:
                    csp += "; worker-src 'self' blob:"
                resp_headers["content-security-policy"] = csp
        elif agent_name and "javascript" in content_type:
            content = _patch_js_branding(content, agent_name)
            # Prevent browser from caching JS across agents (branding is per-agent)
            resp_headers["cache-control"] = "no-cache, no-store, must-revalidate"
            resp_headers["vary"] = "Cookie"
        return HTMLResponse(content=content, status_code=resp.status_code, headers=resp_headers)
    except httpx.ConnectError:
        return _error_page(502, "Agent Unavailable", "The agent pod is not reachable. It may be starting up.")
    except httpx.TimeoutException:
        return _error_page(504, "Gateway Timeout", "The agent pod did not respond in time.")


# ---------------------------------------------------------------------------
# WebSocket proxy — path-based mode (/agents/{slug}/{path})
# ---------------------------------------------------------------------------

@app.websocket("/agents/{agent_slug}")
@app.websocket("/agents/{agent_slug}/{path:path}")
async def path_proxy_websocket(websocket: WebSocket, agent_slug: str, path: str = ""):
    """Path-based WebSocket proxy to OpenClaw pod."""
    logger.info("WS upgrade for agent=%s path=%s cookies=%s", agent_slug, path, dict(websocket.cookies))
    user_context = _get_user_from_ws_cookie(websocket)
    if user_context is None:
        logger.warning("WS auth failed — no valid session cookie")
        await websocket.close(code=1008, reason="Authentication required")
        return

    agent = await resolve_agent(agent_slug)
    if agent is None:
        await websocket.close(code=1008, reason="Agent not found")
        return

    agent_tenant_id = agent.get("tenant_id", "")
    user_tenant_id = user_context.get("tenant_id", "")
    user_roles = user_context.get("roles", [])
    if agent_tenant_id != user_tenant_id and "platform_admin" not in user_roles:
        await websocket.close(code=1008, reason="Access denied")
        return

    tenant_slug = await resolve_tenant_slug(agent_tenant_id)
    if tenant_slug is None:
        await websocket.close(code=1011, reason="Tenant resolution failed")
        return

    instance_name = agent.get("openclaw_instance_name", "")
    if not instance_name:
        instance_name = f"oc-openclaw-agent-{agent.get('id', agent_slug)[:8]}"
    pod_ws_url = f"ws://{instance_name}.tenant-{tenant_slug}.svc.cluster.local:18789/{path}"
    logger.info("WS proxy: slug=%s name=%s → instance=%s url=%s", agent_slug, agent.get("name"), instance_name, pod_ws_url)

    # Forward Origin so OpenClaw controlUi allows the connection
    extra_headers = {}
    origin = websocket.headers.get("origin")
    if origin:
        extra_headers["Origin"] = origin

    await websocket.accept()
    try:
        async with websockets.connect(
            pod_ws_url,
            additional_headers=extra_headers,
            max_size=25 * 1024 * 1024,  # 25 MB — match OpenClaw's MAX_PAYLOAD_BYTES
        ) as pod_ws:
            async def client_to_pod():
                try:
                    while True:
                        msg = await websocket.receive()
                        if "text" in msg:
                            await pod_ws.send(msg["text"])
                        elif "bytes" in msg:
                            await pod_ws.send(msg["bytes"])
                except WebSocketDisconnect:
                    pass

            async def pod_to_client():
                try:
                    async for message in pod_ws:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except websockets.exceptions.ConnectionClosed:
                    pass

            done, pending = await asyncio.wait(
                [asyncio.ensure_future(client_to_pod()), asyncio.ensure_future(pod_to_client())],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except (websockets.exceptions.WebSocketException, OSError) as exc:
        logger.warning("WebSocket proxy error for agent %s: %s", agent_slug, exc)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# OIDC routes — subdomain mode (agents.{domain}/auth/*)
# ---------------------------------------------------------------------------

@app.get("/auth/login")
async def auth_login(request: Request):
    """Initiate OIDC authorization code flow (subdomain mode)."""
    return_to = str(request.query_params.get("return_to", ""))
    redirect_uri = f"{_base_url()}/auth/callback"
    auth_url = _msal_app.get_authorization_request_url(
        scopes=[],
        redirect_uri=redirect_uri,
        state=json.dumps({"return_to": return_to}),
    )
    return RedirectResponse(url=auth_url)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    """Handle OIDC callback — exchange code for tokens, create session."""
    code = request.query_params.get("code")
    state_raw = request.query_params.get("state", "{}")
    error = request.query_params.get("error")

    if error:
        error_desc = request.query_params.get("error_description", error)
        return _error_page(401, "Authentication Failed", error_desc)

    if not code:
        return _error_page(400, "Bad Request", "Missing authorization code.")

    redirect_uri = f"{_base_url()}/auth/callback"
    result = _msal_app.acquire_token_by_authorization_code(
        code=code,
        scopes=[],
        redirect_uri=redirect_uri,
    )

    if "error" in result:
        logger.error("OIDC token exchange failed: %s", result.get("error_description"))
        return _error_page(401, "Authentication Failed", result.get("error_description", "Token exchange failed."))

    claims = result.get("id_token_claims", {})
    user_context = extract_user_context(claims)
    signed = create_signed_cookie(user_context)

    try:
        state = json.loads(state_raw)
    except (json.JSONDecodeError, TypeError):
        state = {}
    return_to = state.get("return_to", f"{_base_url()}/")

    response = RedirectResponse(url=return_to)
    _set_session_cookie(response, signed)
    return response


@app.get("/auth/logout")
async def auth_logout(request: Request):
    """Clear session and redirect to Entra ID logout."""

    entra_client_id = settings.ENTRA_APP_CLIENT_ID or settings.AZURE_CLIENT_ID
    logout_url = (
        f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={quote(f'{_base_url()}/')}"
    )
    response = RedirectResponse(url=logout_url)
    _delete_session_cookie(response)
    return response


# ---------------------------------------------------------------------------
# Session extraction helper
# ---------------------------------------------------------------------------

def _get_user_from_cookie(request: Request) -> dict | None:
    """Extract user context from signed session cookie."""
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        return None
    return load_signed_cookie(cookie)


def _get_user_from_ws_cookie(websocket: WebSocket) -> dict | None:
    """Extract user context from signed session cookie on WebSocket."""
    cookie = websocket.cookies.get(COOKIE_NAME)
    if not cookie:
        return None
    return load_signed_cookie(cookie)


# ---------------------------------------------------------------------------
# HTTP proxy catch-all
# ---------------------------------------------------------------------------

@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy_http(request: Request, path: str):
    """Catch-all HTTP proxy — authenticates and forwards to OpenClaw pod."""
    host = request.headers.get("host", "")

    # Only serve auth routes on the base agents domain
    if not _parse_agent_slug(host):
        if _is_agents_domain(host):
            return _error_page(404, "Not Found", "Please use an agent-specific subdomain.")
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    agent_slug = _parse_agent_slug(host)

    # Authenticate
    user_context = _get_user_from_cookie(request)
    if user_context is None:
        # Build return URL from _base_url() — request.url has http:// behind TLS-terminating AGC
        current_url = f"{_base_url()}{request.url.path}"
        if request.url.query:
            current_url = f"{current_url}?{request.url.query}"
        login_url = f"{_base_url()}/auth/login?return_to={quote(current_url)}"
        return RedirectResponse(url=login_url)

    # Resolve agent
    agent = await resolve_agent(agent_slug)
    if agent is None:
        return _error_page(404, "Agent Not Found", f"No agent with slug '{agent_slug}' was found.")

    # Tenant access check
    agent_tenant_id = agent.get("tenant_id", "")
    user_tenant_id = user_context.get("tenant_id", "")
    user_roles = user_context.get("roles", [])

    if agent_tenant_id != user_tenant_id and "platform_admin" not in user_roles:
        return _error_page(
            403,
            "Access Denied",
            "This agent belongs to another tenant. You do not have permission to access it.",
        )

    # Resolve tenant slug for pod URL
    tenant_slug = await resolve_tenant_slug(agent_tenant_id)
    if tenant_slug is None:
        return _error_page(500, "Internal Error", "Could not resolve tenant.")

    # Build pod URL
    instance_name = agent.get("openclaw_instance_name", "")
    if not instance_name:
        instance_name = f"oc-openclaw-agent-{agent.get('id', agent_slug)[:8]}"
    pod_url = f"http://{instance_name}.tenant-{tenant_slug}.svc.cluster.local:18789"

    # Forward the request
    target_url = f"{pod_url}/{path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    body = await request.body()

    # Build forwarded headers — strip hop-by-hop headers
    headers = dict(request.headers)
    for hop_header in ("host", "connection", "keep-alive", "transfer-encoding", "upgrade"):
        headers.pop(hop_header, None)

    client_ip = request.client.host if request.client else "unknown"
    headers["x-forwarded-for"] = client_ip
    headers["x-real-ip"] = client_ip
    headers["x-forwarded-proto"] = "https"
    headers["x-forwarded-host"] = host

    try:
        resp = await _http_client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
        )
        # Forward response headers, excluding hop-by-hop
        resp_headers = dict(resp.headers)
        for hop_header in ("connection", "keep-alive", "transfer-encoding", "content-encoding", "content-length"):
            resp_headers.pop(hop_header, None)

        return HTMLResponse(
            content=resp.content,
            status_code=resp.status_code,
            headers=resp_headers,
        )
    except httpx.ConnectError:
        return _error_page(502, "Agent Unavailable", "The agent pod is not reachable. It may be starting up.")
    except httpx.TimeoutException:
        return _error_page(504, "Gateway Timeout", "The agent pod did not respond in time.")


# ---------------------------------------------------------------------------
# WebSocket proxy catch-all
# ---------------------------------------------------------------------------

@app.websocket("/{path:path}")
async def proxy_websocket(websocket: WebSocket, path: str):
    """WebSocket proxy — authenticates and relays bidirectionally to OpenClaw pod."""
    host = websocket.headers.get("host", "")
    agent_slug = _parse_agent_slug(host)

    if not agent_slug:
        await websocket.close(code=1008, reason="Invalid host")
        return

    # Authenticate via cookie
    user_context = _get_user_from_ws_cookie(websocket)
    if user_context is None:
        await websocket.close(code=1008, reason="Authentication required")
        return

    # Resolve agent
    agent = await resolve_agent(agent_slug)
    if agent is None:
        await websocket.close(code=1008, reason="Agent not found")
        return

    # Tenant access check
    agent_tenant_id = agent.get("tenant_id", "")
    user_tenant_id = user_context.get("tenant_id", "")
    user_roles = user_context.get("roles", [])

    if agent_tenant_id != user_tenant_id and "platform_admin" not in user_roles:
        await websocket.close(code=1008, reason="Access denied")
        return

    # Resolve tenant slug
    tenant_slug = await resolve_tenant_slug(agent_tenant_id)
    if tenant_slug is None:
        await websocket.close(code=1011, reason="Tenant resolution failed")
        return

    # Build pod WebSocket URL
    instance_name = agent.get("openclaw_instance_name", "")
    if not instance_name:
        instance_name = f"oc-openclaw-agent-{agent.get('id', agent_slug)[:8]}"
    pod_ws_url = f"ws://{instance_name}.tenant-{tenant_slug}.svc.cluster.local:18789/{path}"

    await websocket.accept()

    try:
        async with websockets.connect(pod_ws_url) as pod_ws:

            async def client_to_pod():
                try:
                    while True:
                        msg = await websocket.receive()
                        if "text" in msg:
                            await pod_ws.send(msg["text"])
                        elif "bytes" in msg:
                            await pod_ws.send(msg["bytes"])
                except WebSocketDisconnect:
                    pass

            async def pod_to_client():
                try:
                    async for message in pod_ws:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except websockets.exceptions.ConnectionClosed:
                    pass

            done, pending = await asyncio.wait(
                [
                    asyncio.ensure_future(client_to_pod()),
                    asyncio.ensure_future(pod_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

    except (websockets.exceptions.WebSocketException, OSError) as exc:
        logger.warning("WebSocket proxy error for agent %s: %s", agent_slug, exc)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
