"""LLM Token Proxy — transparent proxy between OpenClaw pods and Azure OpenAI.

Captures token usage from streaming and non-streaming responses,
logs every request to Cosmos DB with tenant/agent attribution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from azure.identity.aio import WorkloadIdentityCredential, DefaultAzureCredential
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.telemetry import init_telemetry
from app.core.logging_config import configure_logging
from app.health import health_router
from app.repositories.cosmos_client import close_cosmos_client
from app.repositories.token_log_repository import TokenLogRepository

logger = logging.getLogger(__name__)

# Azure OpenAI uses the Cognitive Services scope for Entra ID auth
_AZURE_OPENAI_SCOPE = "https://cognitiveservices.azure.com/.default"
_azure_credential = None
_cached_token = None
_token_expires_on = 0


def _get_azure_credential():
    global _azure_credential
    if _azure_credential is None:
        # Use the managed identity client ID from the service account annotation,
        # NOT the Entra app client ID that may be in AZURE_CLIENT_ID env var
        managed_identity_client_id = os.getenv("AZURE_WORKLOAD_CLIENT_ID")
        try:
            if managed_identity_client_id:
                logger.info("Using WorkloadIdentityCredential with managed identity %s", managed_identity_client_id)
                _azure_credential = WorkloadIdentityCredential(client_id=managed_identity_client_id)
            else:
                _azure_credential = WorkloadIdentityCredential()
        except Exception:
            _azure_credential = DefaultAzureCredential(managed_identity_client_id=managed_identity_client_id)
    return _azure_credential


async def _get_azure_openai_token() -> str:
    """Get a valid Azure AD token for Azure OpenAI, with caching."""
    global _cached_token, _token_expires_on
    now = time.time()
    if _cached_token and _token_expires_on > now + 60:
        return _cached_token
    cred = _get_azure_credential()
    token = await cred.get_token(_AZURE_OPENAI_SCOPE)
    _cached_token = token.token
    _token_expires_on = token.expires_on
    logger.info("Acquired new Azure AD token for Azure OpenAI (expires in %ds)", int(_token_expires_on - now))
    return _cached_token

AZURE_OPENAI_BASE = os.getenv(
    "AZURE_OPENAI_BASE", "https://ai-platform-system.openai.azure.com"
)

token_log_repo = TokenLogRepository()
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
            follow_redirects=True,
        )
    return _http_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(service_name="llm-proxy")
    init_telemetry(service_name="llm-proxy")
    logger.info("LLM Token Proxy starting — upstream: %s", AZURE_OPENAI_BASE)
    yield
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
    global _azure_credential
    if _azure_credential is not None:
        await _azure_credential.close()
        _azure_credential = None
    await close_cosmos_client()


app = FastAPI(title="AI Platform - LLM Token Proxy", version="0.1.0", lifespan=lifespan)
app.include_router(health_router)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------


def _detect_api_type(path: str) -> str:
    """Determine API type from the request path."""
    if "chat/completions" in path:
        return "chat-completions"
    if "responses" in path:
        return "responses"
    return "other"


def _extract_model(body: dict, response_data: dict | None = None) -> str:
    """Extract model name from request body or response."""
    if body.get("model"):
        return body["model"]
    if response_data and response_data.get("model"):
        return response_data["model"]
    return "unknown"


async def _log_usage(
    tenant_id: str,
    agent_id: str,
    usage: dict | None,
    model: str,
    api_type: str,
    is_stream: bool,
    latency_ms: float,
    status_code: int,
    request_id: str | None = None,
) -> None:
    """Log token usage to Cosmos DB. Best-effort — never fails the response."""
    try:
        log_doc = {
            "id": str(uuid4()),
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model or "unknown",
            "api": api_type,
            "stream": is_stream,
            "prompt_tokens": usage.get("prompt_tokens", 0) if usage else 0,
            "completion_tokens": usage.get("completion_tokens", 0) if usage else 0,
            "total_tokens": usage.get("total_tokens", 0) if usage else 0,
            "reasoning_tokens": (
                (usage.get("completion_tokens_details") or {}).get(
                    "reasoning_tokens", 0
                )
                if usage
                else 0
            ),
            "cached_tokens": (
                (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
                if usage
                else 0
            ),
            "latency_ms": round(latency_ms, 1),
            "status": status_code,
            "request_id": request_id,
        }
        await token_log_repo.log_usage(tenant_id, log_doc)
        logger.debug(
            "Logged %d tokens for tenant=%s agent=%s",
            log_doc["total_tokens"],
            tenant_id,
            agent_id,
        )
    except Exception:
        logger.exception("Failed to log token usage (non-fatal)")


# ---------------------------------------------------------------------------
#  Non-streaming handler
# ---------------------------------------------------------------------------


async def _handle_non_streaming(
    url: str,
    headers: dict,
    body: dict,
    tenant_id: str,
    agent_id: str,
    start_time: float,
    api_type: str,
) -> JSONResponse:
    """Proxy a non-streaming request and log token usage."""
    client = _get_http_client()
    response = await client.post(url, content=json.dumps(body), headers=headers)

    latency_ms = (time.monotonic() - start_time) * 1000
    response_data = None
    usage = None

    if response.headers.get("content-type", "").startswith("application/json"):
        try:
            response_data = response.json()
            usage = response_data.get("usage")
        except (json.JSONDecodeError, ValueError):
            pass

    model = _extract_model(body, response_data)
    request_id = response_data.get("id") if response_data else None

    asyncio.create_task(
        _log_usage(
            tenant_id, agent_id, usage, model, api_type,
            False, latency_ms, response.status_code, request_id,
        )
    )

    return JSONResponse(
        content=response_data if response_data is not None else response.text,
        status_code=response.status_code,
        headers={
            k: v
            for k, v in response.headers.items()
            if k.lower() not in ("content-length", "transfer-encoding", "content-encoding")
        },
    )


# ---------------------------------------------------------------------------
#  Streaming handler
# ---------------------------------------------------------------------------


async def _handle_streaming(
    url: str,
    headers: dict,
    body: dict,
    tenant_id: str,
    agent_id: str,
    start_time: float,
    api_type: str,
) -> StreamingResponse:
    """Proxy a streaming request, capture usage from final chunk."""
    client = _get_http_client()
    model = _extract_model(body)
    usage_data: dict | None = None
    request_id: str | None = None
    status_code = 200

    async def generate():
        nonlocal usage_data, request_id, status_code
        try:
            async with client.stream(
                "POST", url, content=json.dumps(body), headers=headers
            ) as response:
                status_code = response.status_code

                if response.status_code >= 400:
                    error_body = await response.aread()
                    yield error_body.decode("utf-8", errors="replace")
                    return

                async for line in response.aiter_lines():
                    if not line:
                        yield "\n"
                        continue

                    # Parse SSE data lines for usage extraction
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            data = json.loads(line[6:])
                            if data.get("usage"):
                                usage_data = data["usage"]
                            if data.get("id") and not request_id:
                                request_id = data["id"]
                        except (json.JSONDecodeError, ValueError):
                            pass

                    yield line + "\n"

        except httpx.HTTPError as exc:
            logger.error("Upstream error during streaming: %s", exc)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

        # Log usage after stream completes
        latency_ms = (time.monotonic() - start_time) * 1000
        asyncio.create_task(
            _log_usage(
                tenant_id, agent_id, usage_data, model, api_type,
                True, latency_ms, status_code, request_id,
            )
        )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
#  Proxy routes
# ---------------------------------------------------------------------------


@app.post("/proxy/{tenant_id}/{agent_id}/{path:path}")
async def proxy_post(request: Request, tenant_id: str, agent_id: str, path: str):
    """Main proxy endpoint — forwards POST requests to Azure OpenAI."""
    # Read and parse request body
    raw_body = await request.body()
    try:
        body = json.loads(raw_body) if raw_body else {}
    except (json.JSONDecodeError, ValueError):
        body = {}

    is_streaming = body.get("stream", False)
    api_type = _detect_api_type(path)

    # Inject stream_options.include_usage for streaming requests
    if is_streaming:
        body.setdefault("stream_options", {})
        body["stream_options"]["include_usage"] = True

    # Build upstream URL preserving query string (api-version, etc.)
    upstream_url = f"{AZURE_OPENAI_BASE}/{path}"
    if request.query_params:
        upstream_url += f"?{request.query_params}"

    # Forward headers — replace API key with Azure AD Bearer token
    forward_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "transfer-encoding", "api-key", "authorization")
    }
    forward_headers["content-type"] = "application/json"

    # Use managed identity to authenticate with Azure OpenAI
    try:
        ad_token = await _get_azure_openai_token()
        forward_headers["Authorization"] = f"Bearer {ad_token}"
    except Exception:
        logger.exception("Failed to acquire Azure AD token — falling back to api-key header")
        api_key = request.headers.get("api-key")
        if api_key:
            forward_headers["api-key"] = api_key

    start_time = time.monotonic()

    if is_streaming:
        return await _handle_streaming(
            upstream_url, forward_headers, body,
            tenant_id, agent_id, start_time, api_type,
        )
    else:
        return await _handle_non_streaming(
            upstream_url, forward_headers, body,
            tenant_id, agent_id, start_time, api_type,
        )


@app.api_route(
    "/proxy/{tenant_id}/{agent_id}/{path:path}",
    methods=["GET", "PUT", "DELETE", "PATCH"],
)
async def proxy_passthrough(
    request: Request, tenant_id: str, agent_id: str, path: str
):
    """Passthrough for non-POST requests — forward without token extraction."""
    client = _get_http_client()

    upstream_url = f"{AZURE_OPENAI_BASE}/{path}"
    if request.query_params:
        upstream_url += f"?{request.query_params}"

    forward_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "transfer-encoding", "api-key", "authorization")
    }

    # Use managed identity to authenticate with Azure OpenAI
    try:
        ad_token = await _get_azure_openai_token()
        forward_headers["Authorization"] = f"Bearer {ad_token}"
    except Exception:
        logger.exception("Failed to acquire Azure AD token for passthrough")
        api_key = request.headers.get("api-key")
        if api_key:
            forward_headers["api-key"] = api_key

    raw_body = await request.body()

    response = await client.request(
        method=request.method,
        url=upstream_url,
        headers=forward_headers,
        content=raw_body if raw_body else None,
    )

    return JSONResponse(
        content=response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
        status_code=response.status_code,
    )
