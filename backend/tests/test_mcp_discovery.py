"""Unit tests for MCP Tool Discovery Service."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.mcp_server import MCPServer
from app.models.mcp_discovered_tool import MCPDiscoveredTool
from app.services.mcp_discovery import MCPDiscoveryService, _build_auth_headers
from app.services.mcp_client import MCPClientError, MCPConnectionError
from app.services.mcp_types import (
    InitializeResult,
    ListToolsResult,
    MCPToolInfo,
    MCPToolInputSchema,
    ServerCapabilities,
    ServerInfo,
)


def _make_server(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "name": "Test Server",
        "url": "http://mcp.example.com/sse",
        "auth_type": "none",
        "auth_header_name": None,
        "auth_credential_ref": None,
        "is_active": True,
        "status": "unknown",
        "status_message": None,
        "tenant_id": uuid.uuid4(),
    }
    defaults.update(overrides)
    mock = MagicMock(spec=MCPServer, **defaults)
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_init_result():
    return InitializeResult(
        protocolVersion="2025-03-26",
        capabilities=ServerCapabilities(tools={}),
        serverInfo=ServerInfo(name="test-server", version="1.0.0"),
    )


def _make_tools_result(names):
    tools = [
        MCPToolInfo(
            name=n,
            description=f"Tool {n}",
            inputSchema=MCPToolInputSchema(type="object"),
        )
        for n in names
    ]
    return ListToolsResult(tools=tools, nextCursor=None)


class TestBuildAuthHeaders:
    def test_no_auth(self):
        server = _make_server(auth_type="none")
        assert _build_auth_headers(server) == {}

    def test_bearer_auth(self):
        server = _make_server(auth_type="bearer", auth_credential_ref="tok-123")
        headers = _build_auth_headers(server)
        assert headers == {"Authorization": "Bearer tok-123"}

    def test_api_key_default_header(self):
        server = _make_server(auth_type="api_key", auth_credential_ref="key-abc")
        headers = _build_auth_headers(server)
        assert headers == {"X-API-Key": "key-abc"}

    def test_api_key_custom_header(self):
        server = _make_server(
            auth_type="api_key",
            auth_header_name="X-Custom",
            auth_credential_ref="key-xyz",
        )
        headers = _build_auth_headers(server)
        assert headers == {"X-Custom": "key-xyz"}

    def test_custom_header(self):
        server = _make_server(
            auth_type="custom_header",
            auth_header_name="X-Secret",
            auth_credential_ref="secret-val",
        )
        headers = _build_auth_headers(server)
        assert headers == {"X-Secret": "secret-val"}


class TestDiscoverToolsFromServer:
    @pytest.mark.asyncio
    @patch("app.services.mcp_discovery.MCPClient")
    async def test_discovers_tools_successfully(self, MockClient):
        mock_client_instance = AsyncMock()
        mock_client_instance.connect.return_value = _make_init_result()
        mock_client_instance.list_tools.return_value = _make_tools_result(
            ["get_weather", "search_web"]
        )
        MockClient.return_value = mock_client_instance

        db = AsyncMock()
        db.execute.return_value = MagicMock()  # for delete
        server = _make_server()

        tools = await MCPDiscoveryService.discover_tools_from_server(db, server)

        assert len(tools) == 2
        assert server.status == "connected"
        mock_client_instance.connect.assert_called_once()
        mock_client_instance.list_tools.assert_called_once()
        mock_client_instance.disconnect.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.mcp_discovery.MCPClient")
    async def test_handles_connection_failure(self, MockClient):
        mock_client_instance = AsyncMock()
        mock_client_instance.connect.side_effect = MCPConnectionError("refused")
        MockClient.return_value = mock_client_instance

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result
        server = _make_server()

        tools = await MCPDiscoveryService.discover_tools_from_server(db, server)

        assert tools == []
        assert server.status == "error"
        assert "refused" in server.status_message
        mock_client_instance.disconnect.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.mcp_discovery.MCPClient")
    async def test_marks_existing_tools_unavailable_on_failure(self, MockClient):
        mock_client_instance = AsyncMock()
        mock_client_instance.connect.side_effect = MCPConnectionError("timeout")
        MockClient.return_value = mock_client_instance

        existing_tool = MagicMock()
        existing_tool.is_available = True

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_tool]
        db.execute.return_value = mock_result
        server = _make_server()

        await MCPDiscoveryService.discover_tools_from_server(db, server)

        assert existing_tool.is_available is False


class TestHealthCheckServer:
    @pytest.mark.asyncio
    @patch("app.services.mcp_discovery.MCPClient")
    async def test_healthy_server(self, MockClient):
        mock_client_instance = AsyncMock()
        mock_client_instance.connect.return_value = _make_init_result()
        MockClient.return_value = mock_client_instance

        db = AsyncMock()
        server = _make_server()

        result = await MCPDiscoveryService.health_check_server(db, server)

        assert result is True
        assert server.status == "connected"
        assert "Healthy" in server.status_message

    @pytest.mark.asyncio
    @patch("app.services.mcp_discovery.MCPClient")
    async def test_unhealthy_server(self, MockClient):
        mock_client_instance = AsyncMock()
        mock_client_instance.connect.side_effect = MCPConnectionError("refused")
        MockClient.return_value = mock_client_instance

        db = AsyncMock()
        server = _make_server()

        result = await MCPDiscoveryService.health_check_server(db, server)

        assert result is False
        assert server.status == "error"


class TestGetAllDiscoveredTools:
    @pytest.mark.asyncio
    async def test_returns_tools(self):
        db = AsyncMock()
        mock_tools = [MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_tools
        db.execute.return_value = mock_result

        tools = await MCPDiscoveryService.get_all_discovered_tools(
            db, tenant_id=uuid.uuid4()
        )
        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_filter_by_server(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        server_id = uuid.uuid4()
        tools = await MCPDiscoveryService.get_all_discovered_tools(
            db, tenant_id=uuid.uuid4(), server_id=server_id
        )
        assert tools == []
        db.execute.assert_called_once()


class TestMCPDiscoveredToolModel:
    def test_model_importable(self):
        assert MCPDiscoveredTool.__tablename__ == "mcp_discovered_tools"

    def test_model_has_required_columns(self):
        column_names = [c.name for c in MCPDiscoveredTool.__table__.columns]
        for col in ["id", "server_id", "tool_name", "is_available", "tenant_id"]:
            assert col in column_names
