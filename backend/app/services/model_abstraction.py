import logging
import time
from typing import Optional, List, Dict, Any, AsyncGenerator

import litellm

from app.models.model_endpoint import ModelEndpoint
from app.services.secret_store import decrypt_api_key

logger = logging.getLogger(__name__)


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


def _build_litellm_params(
    endpoint: ModelEndpoint,
    messages: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout: int,
    stream: bool,
    tools: Optional[list] = None,
    tool_choice: Optional[str] = None,
) -> Dict[str, Any]:
    """Build kwargs for litellm.acompletion based on provider and auth type."""
    provider = endpoint.provider_type
    model_name = endpoint.model_name

    params: Dict[str, Any] = {
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "stream": stream,
    }

    if provider == "azure_openai":
        params["model"] = f"azure/{model_name}"
        if endpoint.endpoint_url:
            params["api_base"] = endpoint.endpoint_url
        if endpoint.auth_type == "api_key" and endpoint.api_key_encrypted:
            params["api_key"] = decrypt_api_key(endpoint.api_key_encrypted)
        # For entra_id auth, litellm can pick up AZURE_AD_TOKEN env var or
        # DefaultAzureCredential via azure-identity at runtime.
    elif provider in ("openai", "anthropic", "custom"):
        if provider == "custom":
            params["model"] = f"openai/{model_name}"
            if endpoint.endpoint_url:
                params["api_base"] = endpoint.endpoint_url
        else:
            params["model"] = f"{provider}/{model_name}"
        if endpoint.api_key_encrypted:
            params["api_key"] = decrypt_api_key(endpoint.api_key_encrypted)
    else:
        params["model"] = model_name
        if endpoint.api_key_encrypted:
            params["api_key"] = decrypt_api_key(endpoint.api_key_encrypted)

    if tools:
        params["tools"] = tools
    if tool_choice:
        params["tool_choice"] = tool_choice

    return params


class ModelAbstractionService:
    """LiteLLM-based model abstraction with circuit breaker and fallback."""

    async def complete(
        self,
        messages: List[Dict[str, str]],
        endpoint: ModelEndpoint,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: int = 30,
        stream: bool = True,
    ) -> AsyncGenerator[str, None]:
        endpoint_id = str(endpoint.id)

        if not _circuit_breaker.is_available(endpoint_id):
            raise ModelError(f"Circuit breaker open for endpoint {endpoint.name}")

        params = _build_litellm_params(
            endpoint, messages, temperature, max_tokens, timeout, stream
        )

        try:
            response = await litellm.acompletion(**params)

            if stream:
                async for chunk in response:
                    delta = chunk.choices[0].delta
                    content = getattr(delta, "content", None)
                    if content:
                        yield content
            else:
                content = response.choices[0].message.content or ""
                yield content

            _circuit_breaker.record_success(endpoint_id)
        except Exception as exc:
            _circuit_breaker.record_failure(endpoint_id)
            logger.warning(
                "Model completion failed for endpoint %s: %s",
                endpoint.name,
                str(exc),
            )
            raise ModelError(f"Model completion failed: {exc}") from exc

    async def complete_with_fallback(
        self,
        messages: List[Dict[str, str]],
        endpoints: List[ModelEndpoint],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: int = 30,
        stream: bool = True,
    ) -> AsyncGenerator[str, None]:
        """Try endpoints in priority order (lower = higher priority), skip if circuit open."""
        sorted_endpoints = sorted(endpoints, key=lambda e: e.priority)
        last_error: Optional[Exception] = None

        for endpoint in sorted_endpoints:
            endpoint_id = str(endpoint.id)
            if not _circuit_breaker.is_available(endpoint_id):
                logger.info("Skipping endpoint %s — circuit breaker open", endpoint.name)
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
                    endpoint.name,
                    str(exc),
                )
                continue

        raise ModelError(
            f"All model endpoints failed. Last error: {last_error}"
        )

    async def complete_with_tools(
        self,
        messages: List[Dict[str, Any]],
        endpoints: List[ModelEndpoint],
        tools: Optional[list] = None,
        tool_choice: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Non-streaming completion that returns full response including tool_calls.
        Returns dict with keys: content (str|None), tool_calls (list|None), finish_reason (str)."""
        sorted_endpoints = sorted(endpoints, key=lambda e: e.priority)
        last_error: Optional[Exception] = None

        for endpoint in sorted_endpoints:
            endpoint_id = str(endpoint.id)
            if not _circuit_breaker.is_available(endpoint_id):
                logger.info(
                    "Skipping endpoint %s — circuit breaker open",
                    endpoint.name,
                )
                continue

            params = _build_litellm_params(
                endpoint, messages, temperature, max_tokens, timeout,
                stream=False, tools=tools, tool_choice=tool_choice,
            )
            try:
                response = await litellm.acompletion(**params)
                _circuit_breaker.record_success(endpoint_id)
                message = response.choices[0].message
                return {
                    "content": message.content,
                    "tool_calls": getattr(message, "tool_calls", None),
                    "finish_reason": response.choices[0].finish_reason,
                }
            except Exception as exc:
                _circuit_breaker.record_failure(endpoint_id)
                last_error = exc
                logger.warning(
                    "Endpoint %s failed, trying next fallback: %s",
                    endpoint.name,
                    str(exc),
                )
                continue

        raise ModelError(
            f"All endpoints failed: {last_error}"
        )
