"""
MCP (Model Context Protocol) client.

Async JSON-RPC 2.0 client for communicating with MCP-compliant servers
over Streamable HTTP transport (POST with JSON or SSE responses).
"""

import json
import logging
from typing import Any, Dict, Optional

import httpx
from httpx_sse import aconnect_sse

from app.services.mcp_types import (
    ContentBlock,
    InitializeParams,
    InitializeResult,
    JsonRpcErrorResponse,
    JsonRpcNotification,
    JsonRpcRequest,
    JsonRpcResponse,
    ListToolsResult,
    ToolCallParams,
    ToolCallResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class MCPClientError(Exception):
    """Base error for MCP client operations."""


class MCPConnectionError(MCPClientError):
    """Connection or transport failure."""


class MCPTimeoutError(MCPClientError):
    """Request exceeded timeout."""


class MCPProtocolError(MCPClientError):
    """Invalid JSON-RPC response or MCP protocol violation."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class MCPClient:
    """Async MCP client using Streamable HTTP transport."""

    def __init__(
        self,
        server_url: str,
        *,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self._server_url = server_url
        self._timeout = timeout
        self._extra_headers = headers or {}
        self._client: Optional[httpx.AsyncClient] = None
        self._session_id: Optional[str] = None
        self._request_id: int = 0
        self._initialized: bool = False

    # -- helpers ----------------------------------------------------------

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            base_headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
            base_headers.update(self._extra_headers)
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                headers=base_headers,
            )
        return self._client

    async def _send_request(
        self, method: str, params: Optional[dict] = None
    ) -> Any:
        client = await self._ensure_client()

        request = JsonRpcRequest(
            id=self._next_id(),
            method=method,
            params=params,
        )
        payload = request.model_dump(exclude_none=True)

        headers: Dict[str, str] = {}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        try:
            response = await client.post(
                self._server_url, json=payload, headers=headers
            )
        except httpx.TimeoutException as exc:
            raise MCPTimeoutError(
                f"Timeout calling {method} on {self._server_url}"
            ) from exc
        except httpx.HTTPError as exc:
            raise MCPConnectionError(
                f"Connection error calling {method} on {self._server_url}: {exc}"
            ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise MCPConnectionError(
                f"HTTP {response.status_code} from {self._server_url} for {method}"
            )

        # Capture session id from response headers
        session_id = response.headers.get("mcp-session-id")
        if session_id:
            self._session_id = session_id

        content_type = response.headers.get("content-type", "")

        if "text/event-stream" in content_type:
            return await self._parse_sse_response(response, method)

        # Default: JSON response
        return self._parse_json_response(response, method)

    def _parse_json_response(self, response: httpx.Response, method: str) -> Any:
        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise MCPProtocolError(
                f"Invalid JSON in response for {method}"
            ) from exc

        if "error" in data:
            err = JsonRpcErrorResponse.model_validate(data)
            raise MCPProtocolError(
                f"JSON-RPC error {err.error.code}: {err.error.message}"
            )

        rpc_resp = JsonRpcResponse.model_validate(data)
        return rpc_resp.result

    async def _parse_sse_response(
        self, response: httpx.Response, method: str
    ) -> Any:
        last_data: Optional[str] = None
        event_type: Optional[str] = None
        async for line in response.aiter_lines():
            line = line.strip()
            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                last_data = line[len("data:"):].strip()
                if event_type == "message" and last_data:
                    break

        if last_data is None:
            raise MCPProtocolError(f"No SSE message event received for {method}")

        try:
            data = json.loads(last_data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise MCPProtocolError(
                f"Invalid JSON in SSE data for {method}"
            ) from exc

        if "error" in data:
            err = JsonRpcErrorResponse.model_validate(data)
            raise MCPProtocolError(
                f"JSON-RPC error {err.error.code}: {err.error.message}"
            )

        rpc_resp = JsonRpcResponse.model_validate(data)
        return rpc_resp.result

    async def _send_notification(
        self, method: str, params: Optional[dict] = None
    ) -> None:
        client = await self._ensure_client()

        notification = JsonRpcNotification(method=method, params=params)
        payload = notification.model_dump(exclude_none=True)

        headers: Dict[str, str] = {}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        try:
            await client.post(self._server_url, json=payload, headers=headers)
        except httpx.HTTPError:
            logger.warning("Failed to send notification %s", method)

    # -- public API -------------------------------------------------------

    async def connect(self) -> InitializeResult:
        """Perform the MCP initialize handshake."""
        init_params = InitializeParams()
        result = await self._send_request(
            "initialize", init_params.model_dump()
        )
        init_result = InitializeResult.model_validate(result)
        await self._send_notification("notifications/initialized")
        self._initialized = True
        logger.info(
            "Connected to MCP server %s (protocol %s)",
            init_result.serverInfo.name,
            init_result.protocolVersion,
        )
        return init_result

    async def list_tools(
        self, cursor: Optional[str] = None
    ) -> ListToolsResult:
        """Fetch available tools from the MCP server."""
        if not self._initialized:
            raise MCPClientError("Client not initialized — call connect() first")
        params: Dict[str, Any] = {}
        if cursor is not None:
            params["cursor"] = cursor
        result = await self._send_request("tools/list", params or None)
        return ListToolsResult.model_validate(result)

    async def call_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> ToolCallResult:
        """Invoke a tool on the MCP server."""
        if not self._initialized:
            raise MCPClientError("Client not initialized — call connect() first")
        call_params = ToolCallParams(name=tool_name, arguments=arguments)
        result = await self._send_request(
            "tools/call", call_params.model_dump(exclude_none=True)
        )
        return ToolCallResult.model_validate(result)

    async def disconnect(self) -> None:
        """Close the HTTP client and reset state."""
        if self._client is not None:
            await self._client.aclose()
        self._client = None
        self._session_id = None
        self._initialized = False
        logger.info("Disconnected from MCP server %s", self._server_url)

    @property
    def is_connected(self) -> bool:
        return self._initialized

    # -- context manager --------------------------------------------------

    async def __aenter__(self) -> "MCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()
