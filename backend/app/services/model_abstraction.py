import logging
import re
import time
from typing import Optional, List, Dict, Any, AsyncGenerator

from openai import AsyncAzureOpenAI, AsyncOpenAI

from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider

from app.services.keyvault_client import get_tenant_secret, TENANT_KV_NAME

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reasoning-model detection
# ---------------------------------------------------------------------------
# Models whose names match this pattern use the "reasoning" API contract:
#   - No temperature (or must be 1)
#   - max_completion_tokens instead of max_tokens
#   - "developer" role instead of "system"
#   - Some don't support streaming
_REASONING_MODEL_RE = re.compile(
    r"(^|[-/])(o1|o3|o4-mini|o4|gpt-5)",
    re.IGNORECASE,
)


def is_reasoning_model(model_name: str) -> bool:
    """Return True if the model uses the reasoning API contract."""
    return bool(_REASONING_MODEL_RE.search(model_name))


def _adapt_messages_for_reasoning(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convert 'system' role to 'developer' for reasoning models."""
    adapted = []
    for msg in messages:
        if msg.get("role") == "system":
            adapted.append({**msg, "role": "developer"})
        else:
            adapted.append(msg)
    return adapted


class ModelError(Exception):
    """Raised when model completion fails."""
    pass


class CircuitBreaker:
    """Simple in-process circuit breaker per endpoint."""

    FAILURE_THRESHOLD = 3
    RECOVERY_TIMEOUT = 60  # seconds

    def __init__(self) -> None:
        self._endpoints: Dict[str, Dict[str, Any]] = {}

    def _get_state(self, endpoint_id: str) -> Dict[str, Any]:
        if endpoint_id not in self._endpoints:
            self._endpoints[endpoint_id] = {
                "failures": 0,
                "last_failure": 0.0,
                "state": "closed",
            }
        return self._endpoints[endpoint_id]

    def is_available(self, endpoint_id: str) -> bool:
        state = self._get_state(endpoint_id)
        if state["state"] == "closed":
            return True
        if state["state"] == "open":
            elapsed = time.monotonic() - state["last_failure"]
            if elapsed >= self.RECOVERY_TIMEOUT:
                state["state"] = "half_open"
                return True
            return False
        # half_open — allow one probe
        return True

    def record_success(self, endpoint_id: str) -> None:
        state = self._get_state(endpoint_id)
        state["failures"] = 0
        state["state"] = "closed"

    def record_failure(self, endpoint_id: str) -> None:
        state = self._get_state(endpoint_id)
        state["failures"] += 1
        state["last_failure"] = time.monotonic()
        if state["failures"] >= self.FAILURE_THRESHOLD:
            state["state"] = "open"
        elif state["state"] == "half_open":
            state["state"] = "open"


# Module-level singleton so state persists across requests within the process.
_circuit_breaker = CircuitBreaker()

# Cache Azure credential to avoid re-creating per request.
_azure_credential: Optional[DefaultAzureCredential] = None


def _get_azure_credential() -> DefaultAzureCredential:
    global _azure_credential
    if _azure_credential is None:
        _azure_credential = DefaultAzureCredential()
    return _azure_credential


def _build_client(endpoint: dict) -> AsyncOpenAI | AsyncAzureOpenAI:
    """Construct the appropriate async OpenAI client for the endpoint."""
    provider = endpoint.get("provider_type", "")
    api_key: Optional[str] = None

    # Retrieve API key from tenant Key Vault if the endpoint uses key auth
    if endpoint.get("has_api_key") and TENANT_KV_NAME:
        tenant_id = endpoint.get("tenant_id", "")
        endpoint_id = endpoint.get("id", "")
        if tenant_id and endpoint_id:
            api_key = get_tenant_secret(tenant_id, f"ep-{endpoint_id}-apikey")

    if provider == "azure_openai":
        base_url = endpoint.get("endpoint_url")
        auth_type = endpoint.get("auth_type", "entra_id")
        if auth_type == "api_key" and api_key:
            return AsyncAzureOpenAI(
                api_key=api_key,
                azure_endpoint=base_url or "",
                api_version="2025-04-01-preview",
            )
        # Entra ID / Managed Identity auth
        credential = _get_azure_credential()
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
        return AsyncAzureOpenAI(
            azure_ad_token_provider=token_provider,
            azure_endpoint=base_url or "",
            api_version="2025-04-01-preview",
        )

    if provider == "custom":
        return AsyncOpenAI(
            api_key=api_key or "unused",
            base_url=endpoint.get("endpoint_url"),
        )

    if provider == "anthropic":
        # Anthropic has its own SDK, but we route through OpenAI-compatible
        # endpoint if configured.  For direct Anthropic API, users should
        # set provider_type=custom with the Anthropic base URL.
        return AsyncOpenAI(
            api_key=api_key or "",
            base_url=endpoint.get("endpoint_url") or "https://api.anthropic.com/v1",
        )

    # Default: OpenAI
    return AsyncOpenAI(api_key=api_key or "")


class ModelAbstractionService:
    """Direct OpenAI-SDK model abstraction with circuit breaker, fallback, and reasoning model support."""

    def __init__(self) -> None:
        self._last_usage: Dict[str, int] = {}

    def get_last_usage(self) -> Dict[str, int]:
        """Return usage from the last completion call and reset."""
        usage = self._last_usage
        self._last_usage = {}
        return usage

    async def complete(
        self,
        messages: List[Dict[str, str]],
        endpoint: dict,
        temperature: float = 0,
        max_tokens: Optional[int] = None,
        timeout: int = 30,
        stream: bool = True,
    ) -> AsyncGenerator[str, None]:
        endpoint_id = endpoint.get("id", "")

        if not _circuit_breaker.is_available(endpoint_id):
            raise ModelError(f"Circuit breaker open for endpoint {endpoint.get('name', '')}")

        model_name = endpoint.get("model_name", "")
        reasoning = is_reasoning_model(model_name)
        client = _build_client(endpoint)

        # Build kwargs
        kwargs: Dict[str, Any] = {
            "model": model_name,
            "messages": _adapt_messages_for_reasoning(messages) if reasoning else messages,
            "timeout": timeout,
            "stream": stream,
        }

        if reasoning:
            if max_tokens is not None:
                kwargs["max_completion_tokens"] = max_tokens
            # Reasoning models don't accept temperature
        else:
            kwargs["temperature"] = temperature
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens

        if stream:
            kwargs["stream_options"] = {"include_usage": True}

        try:
            response = await client.chat.completions.create(**kwargs)

            if stream:
                async for chunk in response:
                    # Capture usage from the final chunk
                    chunk_usage = getattr(chunk, "usage", None)
                    if chunk_usage:
                        self._last_usage = {
                            "prompt_tokens": getattr(chunk_usage, "prompt_tokens", 0) or 0,
                            "completion_tokens": getattr(chunk_usage, "completion_tokens", 0) or 0,
                            "total_tokens": getattr(chunk_usage, "total_tokens", 0) or 0,
                        }
                    delta = chunk.choices[0].delta if chunk.choices else None
                    content = getattr(delta, "content", None) if delta else None
                    if content:
                        yield content
            else:
                content = response.choices[0].message.content or ""
                usage = getattr(response, "usage", None)
                if usage:
                    self._last_usage = {
                        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                    }
                yield content

            _circuit_breaker.record_success(endpoint_id)
        except Exception as exc:
            _circuit_breaker.record_failure(endpoint_id)
            logger.warning(
                "Model completion failed for endpoint %s: %s",
                endpoint.get("name", ""),
                str(exc),
            )
            raise ModelError(f"Model completion failed: {exc}") from exc

    async def complete_with_fallback(
        self,
        messages: List[Dict[str, str]],
        endpoints: List[dict],
        temperature: float = 0,
        max_tokens: Optional[int] = None,
        timeout: int = 30,
        stream: bool = True,
    ) -> AsyncGenerator[str, None]:
        """Try endpoints in priority order (lower = higher priority), skip if circuit open."""
        sorted_endpoints = sorted(endpoints, key=lambda e: e.get("priority", 0))
        last_error: Optional[Exception] = None

        for endpoint in sorted_endpoints:
            endpoint_id = endpoint.get("id", "")
            if not _circuit_breaker.is_available(endpoint_id):
                logger.info("Skipping endpoint %s — circuit breaker open", endpoint.get("name", ""))
                continue

            try:
                async for token in self.complete(
                    messages, endpoint, temperature, max_tokens, timeout, stream
                ):
                    yield token
                return  # success
            except ModelError as exc:
                last_error = exc
                logger.warning(
                    "Endpoint %s failed, trying next fallback: %s",
                    endpoint.get("name", ""),
                    str(exc),
                )
                continue

        raise ModelError(
            f"All model endpoints failed. Last error: {last_error}"
        )

    async def complete_with_tools(
        self,
        messages: List[Dict[str, Any]],
        endpoints: List[dict],
        tools: Optional[list] = None,
        tool_choice: Optional[str] = None,
        temperature: float = 0,
        max_tokens: Optional[int] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Non-streaming completion that returns full response including tool_calls."""
        # Guard against None overrides from caller
        if temperature is None:
            temperature = 0
        if timeout is None:
            timeout = 60
        sorted_endpoints = sorted(endpoints, key=lambda e: e.get("priority", 0))
        last_error: Optional[Exception] = None

        for endpoint in sorted_endpoints:
            endpoint_id = endpoint.get("id", "")
            if not _circuit_breaker.is_available(endpoint_id):
                logger.info(
                    "Skipping endpoint %s — circuit breaker open",
                    endpoint.get("name", ""),
                )
                continue

            model_name = endpoint.get("model_name", "")
            reasoning = is_reasoning_model(model_name)
            client = _build_client(endpoint)

            kwargs: Dict[str, Any] = {
                "model": model_name,
                "messages": _adapt_messages_for_reasoning(messages) if reasoning else messages,
                "timeout": timeout,
                "stream": False,
            }

            if reasoning:
                if max_tokens is not None:
                    kwargs["max_completion_tokens"] = max_tokens
            else:
                kwargs["temperature"] = temperature
                if max_tokens is not None:
                    kwargs["max_tokens"] = max_tokens

            if tools:
                kwargs["tools"] = tools
            if tool_choice and not reasoning:
                # Reasoning models may not support tool_choice
                kwargs["tool_choice"] = tool_choice

            try:
                import json as _json
                logger.info(
                    "complete_with_tools: model=%s, tools_count=%d, tool_choice=%s, msg_count=%d, reasoning=%s",
                    model_name, len(tools) if tools else 0, tool_choice, len(messages), reasoning,
                )
                # Dump the first tool schema and all messages for debugging
                if tools:
                    logger.info("FIRST TOOL SCHEMA: %s", _json.dumps(tools[0], default=str))
                logger.info("MESSAGES: %s", _json.dumps(kwargs["messages"], default=str)[:2000])
                response = await client.chat.completions.create(**kwargs)
                _circuit_breaker.record_success(endpoint_id)
                message = response.choices[0].message
                logger.info(
                    "complete_with_tools result: finish_reason=%s, has_tool_calls=%s, content_len=%d",
                    response.choices[0].finish_reason,
                    bool(getattr(message, "tool_calls", None)),
                    len(message.content or ""),
                )
                if not getattr(message, "tool_calls", None):
                    logger.warning(
                        "NO TOOL CALLS — model response: %s",
                        (message.content or "")[:500],
                    )
                usage = getattr(response, "usage", None)
                usage_dict = {}
                if usage:
                    usage_dict = {
                        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                    }
                return {
                    "content": message.content,
                    "tool_calls": getattr(message, "tool_calls", None),
                    "finish_reason": response.choices[0].finish_reason,
                    "usage": usage_dict,
                }
            except Exception as exc:
                _circuit_breaker.record_failure(endpoint_id)
                last_error = exc
                logger.warning(
                    "Endpoint %s failed, trying next fallback: %s",
                    endpoint.get("name", ""),
                    str(exc),
                )
                continue

        raise ModelError(
            f"All endpoints failed: {last_error}"
        )
