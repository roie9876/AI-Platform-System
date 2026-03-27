"""Unit tests for MCP Tool Discovery Service."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

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

TENANT_ID = str(uuid.uuid4())


def _make_server(**overrides):
    defaults = {
        "id": str(uuid.uuid4()),
        "name": "Test Server",
        "url": "http://mcp.example.com/sse",
        "auth_type": "none",
        "auth_header_name": None,
        "auth_credential_ref": None,
        "is_active": True,
        "status": "unknown",
        "status_message": None,
        "tenant_id": TENANT_ID,
    }
    defaults.update(overrides)
    return defaults


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
    @patch("app.services.mcp_discovery._tool_repo")
    @patch("app.services.mcp_discovery._server_repo")
    async def test_discovers_tools_successfully(self, mock_server_repo, mock_tool_repo, MockClient):
        mock_client_instance = AsyncMock()
        mock_client_instance.connect.return_value = _make_init_result()
        mock_client_instance.list_tools.return_value = _make_tools_result(
            ["get_weather", "search_web"]
        )
        MockClient.return_value = mock_client_instance

        mock_server_repo.update = AsyncMock()
        mock_tool_repo.query = AsyncMock(return_value=[])
        mock_tool_repo.delete = AsyncMock()
        mock_tool_repo.create = AsyncMock(side_effect=lambda tid, data: data)

        server = _make_server()
        tools = await MCPDiscoveryService.discover_tools_from_server(server, TENANT_ID)

        assert len(tools) == 2
        assert server["status"] == "connected"
        mock_client_instance.connect.assert_called_once()
        mock_client_instance.list_tools.assert_called_once()
        mock_client_instance.disconnect.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.mcp_discovery.MCPClient")
    @patch("app.services.mcp_discovery._tool_repo")
    @patch("app.services.mcp_discovery._server_repo")
    async def test_handles_connection_failure(self, mock_server_repo, mock_tool_repo, MockClient):
        mock_client_instance = AsyncMock()
        mock_client_instance.connect.side_effect = MCPConnectionError("refused")
        MockClient.return_value = mock_client_instance

        mock_server_repo.update = AsyncMock()
        mock_tool_repo.query = AsyncMock(return_value=[])
        mock_tool_repo.update = AsyncMock()

        server = _make_server()
        tools = await MCPDiscoveryService.discover_tools_from_server(server, TENANT_ID)

        assert tools == []
        assert server["status"] == "error"
        assert "refused" in server["status_message"]
        mock_client_instance.disconnect.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.mcp_discovery.MCPClient")
    @patch("app.services.mcp_discovery._tool_repo")
    @patch("app.services.mcp_discovery._server_repo")
    async def test_marks_existing_tools_unavailable_on_failure(self, mock_server_repo, mock_tool_repo, MockClient):
        mock_client_instance = AsyncMock()
        mock_client_instance.connect.side_effect = MCPConnectionError("timeout")
        MockClient.return_value = mock_client_instance

        existing_tool = {"id": "t1", "server_id": "s1", "is_available": True, "tenant_id": TENANT_ID}
        mock_server_repo.update = AsyncMock()
        mock_tool_repo.query = AsyncMock(return_value=[existing_tool])
        mock_tool_repo.update = AsyncMock()

        server = _make_server()
        await MCPDiscoveryService.discover_tools_from_server(server, TENANT_ID)

        # The service sets is_available = False and calls update
        assert existing_tool["is_available"] is False
        mock_tool_repo.update.assert_called_once()


class TestHealthCheckServer:
    @pytest.mark.asyncio
    @patch("app.services.mcp_discovery.MCPClient")
    @patch("app.services.mcp_discovery._server_repo")
    async def test_healthy_server(self, mock_server_repo, MockClient):
        mock_client_instance = AsyncMock()
        mock_client_instance.connect.return_value = _make_init_result()
        MockClient.return_value = mock_client_instance
        mock_server_repo.update = AsyncMock()

        server = _make_server()
        result = await MCPDiscoveryService.health_check_server(server, TENANT_ID)

        assert result is True
        assert server["status"] == "connected"
        assert "Healthy" in server["status_message"]

    @pytest.mark.asyncio
    @patch("app.services.mcp_discovery.MCPClient")
    @patch("app.services.mcp_discovery._server_repo")
    async def test_unhealthy_server(self, mock_server_repo, MockClient):
        mock_client_instance = AsyncMock()
        mock_client_instance.connect.side_effect = MCPConnectionError("refused")
        MockClient.return_value = mock_client_instance
        mock_server_repo.update = AsyncMock()

        server = _make_server()
        result = await MCPDiscoveryService.health_check_server(server, TENANT_ID)

        assert result is False
        assert server["status"] == "error"


class TestGetAllDiscoveredTools:
    @pytest.mark.asyncio
    @patch("app.services.mcp_discovery._tool_repo")
    async def test_returns_tools(self, mock_tool_repo):
        mock_tools = [{"id": "1", "tool_name": "a"}, {"id": "2", "tool_name": "b"}]
        mock_tool_repo.query = AsyncMock(return_value=mock_tools)

        tools = await MCPDiscoveryService.get_all_discovered_tools(TENANT_ID)
        assert len(tools) == 2

    @pytest.mark.asyncio
    @patch("app.services.mcp_discovery._tool_repo")
    async def test_filter_by_server(self, mock_tool_repo):
        mock_tool_repo.query = AsyncMock(return_value=[])

        server_id = str(uuid.uuid4())
        tools = await MCPDiscoveryService.get_all_discovered_tools(TENANT_ID, server_id=server_id)
        assert tools == []
        mock_tool_repo.query.assert_called_once()


class TestMCPDiscoveredToolModel:
    def test_model_importable(self):
        assert MCPDiscoveredTool.__tablename__ == "mcp_discovered_tools"

    def test_model_has_required_columns(self):
        column_names = [c.name for c in MCPDiscoveredTool.__table__.columns]
        for col in ["id", "server_id", "tool_name", "is_available", "tenant_id"]:
            assert col in column_names
