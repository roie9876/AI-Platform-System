"""Unit tests for MCP client."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.mcp_client import (
    MCPClient,
    MCPClientError,
    MCPConnectionError,
    MCPProtocolError,
    MCPTimeoutError,
)
from app.services.mcp_types import (
    ContentBlock,
    InitializeResult,
    ListToolsResult,
    MCPToolInfo,
    ToolCallResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jsonrpc_response(result_data, request_id=1, status_code=200):
    """Build a mock httpx.Response containing a valid JSON-RPC result."""
    body = json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result_data})
    return httpx.Response(
        status_code=status_code,
        content=body.encode(),
        headers={"content-type": "application/json"},
    )


def _make_error_response(code, message, request_id=1):
    """Build a mock httpx.Response containing a JSON-RPC error."""
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    })
    return httpx.Response(
        status_code=200,
        content=body.encode(),
        headers={"content-type": "application/json"},
    )


INIT_RESULT = {
    "protocolVersion": "2025-03-26",
    "capabilities": {"tools": {}},
    "serverInfo": {"name": "test-server", "version": "0.1.0"},
}

TOOLS_RESULT = {
    "tools": [
        {"name": "get_weather", "description": "Get weather for a city", "inputSchema": {"type": "object", "properties": {"city": {"type": "string"}}}},
        {"name": "search_web", "description": "Search the web", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}}},
    ]
}

TOOL_CALL_RESULT = {
    "content": [{"type": "text", "text": "Sunny, 25°C"}],
    "isError": False,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMCPClient:

    def test_constructor(self):
        client = MCPClient("http://example.com")
        assert client.is_connected is False
        assert client._server_url == "http://example.com"
        assert client._timeout == 30.0

    def test_constructor_custom(self):
        client = MCPClient(
            "http://example.com:8080",
            timeout=60.0,
            headers={"Authorization": "Bearer tok"},
        )
        assert client._timeout == 60.0
        assert client._extra_headers == {"Authorization": "Bearer tok"}

    @pytest.mark.asyncio
    async def test_connect_success(self):
        client = MCPClient("http://example.com")
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        # First call: initialize; second call: notifications/initialized
        mock_client.post.side_effect = [
            _make_jsonrpc_response(INIT_RESULT, request_id=1),
            httpx.Response(200, content=b"", headers={"content-type": "application/json"}),
        ]

        client._client = mock_client

        result = await client.connect()

        assert client.is_connected is True
        assert isinstance(result, InitializeResult)
        assert result.serverInfo.name == "test-server"
        assert result.protocolVersion == "2025-03-26"
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_connect_captures_session_id(self):
        client = MCPClient("http://example.com")
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        resp = _make_jsonrpc_response(INIT_RESULT, request_id=1)
        resp.headers["mcp-session-id"] = "sess-abc-123"
        mock_client.post.side_effect = [
            resp,
            httpx.Response(200, content=b"", headers={"content-type": "application/json"}),
        ]
        client._client = mock_client

        await client.connect()
        assert client._session_id == "sess-abc-123"

    @pytest.mark.asyncio
    async def test_list_tools_success(self):
        client = MCPClient("http://example.com")
        client._initialized = True
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_jsonrpc_response(TOOLS_RESULT, request_id=2)
        client._client = mock_client

        result = await client.list_tools()

        assert isinstance(result, ListToolsResult)
        assert len(result.tools) == 2
        assert result.tools[0].name == "get_weather"
        assert result.tools[1].name == "search_web"

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        client = MCPClient("http://example.com")
        client._initialized = True
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_jsonrpc_response(TOOL_CALL_RESULT, request_id=3)
        client._client = mock_client

        result = await client.call_tool("get_weather", {"city": "London"})

        assert isinstance(result, ToolCallResult)
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert result.content[0].text == "Sunny, 25°C"
        assert result.isError is False

    @pytest.mark.asyncio
    async def test_connect_server_unreachable(self):
        client = MCPClient("http://unreachable.local")
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        client._client = mock_client

        with pytest.raises(MCPConnectionError):
            await client.connect()

    @pytest.mark.asyncio
    async def test_request_timeout(self):
        client = MCPClient("http://example.com", timeout=1.0)
        client._initialized = True
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = httpx.ReadTimeout("timed out")
        client._client = mock_client

        with pytest.raises(MCPTimeoutError):
            await client.list_tools()

    @pytest.mark.asyncio
    async def test_protocol_error_jsonrpc(self):
        client = MCPClient("http://example.com")
        client._initialized = True
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_error_response(-32600, "Invalid request")
        client._client = mock_client

        with pytest.raises(MCPProtocolError, match="Invalid request"):
            await client.list_tools()

    @pytest.mark.asyncio
    async def test_list_tools_not_initialized(self):
        client = MCPClient("http://example.com")

        with pytest.raises(MCPClientError, match="not initialized"):
            await client.list_tools()

    @pytest.mark.asyncio
    async def test_call_tool_not_initialized(self):
        client = MCPClient("http://example.com")

        with pytest.raises(MCPClientError, match="not initialized"):
            await client.call_tool("anything", {})

    @pytest.mark.asyncio
    async def test_context_manager(self):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = [
            _make_jsonrpc_response(INIT_RESULT, request_id=1),
            httpx.Response(200, content=b"", headers={"content-type": "application/json"}),
        ]

        client = MCPClient("http://example.com")
        client._client = mock_client

        async with client as c:
            assert c.is_connected is True

        assert c.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect(self):
        client = MCPClient("http://example.com")
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        client._client = mock_client
        client._initialized = True
        client._session_id = "sess-123"

        await client.disconnect()

        assert client.is_connected is False
        assert client._session_id is None
        assert client._client is None
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_error_status_code(self):
        client = MCPClient("http://example.com")
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(
            status_code=500,
            content=b"Internal Server Error",
            headers={"content-type": "text/plain"},
        )
        client._client = mock_client

        with pytest.raises(MCPConnectionError, match="HTTP 500"):
            await client.connect()

    @pytest.mark.asyncio
    async def test_list_tools_with_cursor(self):
        client = MCPClient("http://example.com")
        client._initialized = True
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_jsonrpc_response(
            {"tools": [], "nextCursor": None}, request_id=2
        )
        client._client = mock_client

        result = await client.list_tools(cursor="page2")

        assert isinstance(result, ListToolsResult)
        # Verify cursor was passed in params
        call_kwargs = mock_client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["params"]["cursor"] == "page2"

    @pytest.mark.asyncio
    async def test_call_tool_error_result(self):
        """Tool call returns isError=True (tool-level error, not protocol error)."""
        client = MCPClient("http://example.com")
        client._initialized = True
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        error_result = {
            "content": [{"type": "text", "text": "City not found"}],
            "isError": True,
        }
        mock_client.post.return_value = _make_jsonrpc_response(error_result, request_id=4)
        client._client = mock_client

        result = await client.call_tool("get_weather", {"city": "Atlantis"})

        assert result.isError is True
        assert result.content[0].text == "City not found"
