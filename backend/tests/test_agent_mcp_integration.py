"""Unit tests for MCP integration in Agent Execution Service."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.agent_mcp_tool import AgentMCPTool
from app.models.mcp_discovered_tool import MCPDiscoveredTool
from app.services.agent_execution import AgentExecutionService
from app.services.mcp_client import MCPClientError
from app.services.mcp_types import ContentBlock, ToolCallResult

TENANT_ID = str(uuid.uuid4())


def _make_mcp_tool(**overrides):
    defaults = {
        "id": str(uuid.uuid4()),
        "server_id": str(uuid.uuid4()),
        "tool_name": "get_weather",
        "description": "Get weather for a city",
        "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}},
        "is_available": True,
        "tenant_id": TENANT_ID,
    }
    defaults.update(overrides)
    return defaults


class TestBuildMCPToolSchemas:
    def test_builds_schemas_with_mcp_prefix(self):
        service = AgentExecutionService()
        mcp_tools = [
            _make_mcp_tool(tool_name="get_weather", description="Weather tool"),
            _make_mcp_tool(tool_name="search_web", description="Search tool"),
        ]
        schemas = service._build_mcp_tool_schemas(mcp_tools)

        assert len(schemas) == 2
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "mcp__get_weather"
        assert schemas[0]["function"]["description"] == "Weather tool"
        assert schemas[1]["function"]["name"] == "mcp__search_web"

    def test_empty_list(self):
        service = AgentExecutionService()
        schemas = service._build_mcp_tool_schemas([])
        assert schemas == []

    def test_default_schema_when_none(self):
        service = AgentExecutionService()
        tool = _make_mcp_tool(input_schema=None)
        schemas = service._build_mcp_tool_schemas([tool])
        assert schemas[0]["function"]["parameters"] == {
            "type": "object",
            "properties": {},
        }


class TestExecuteMCPTool:
    @pytest.mark.asyncio
    @patch("app.services.agent_execution.MCPClient")
    @patch("app.services.agent_execution._mcp_server_repo")
    async def test_successful_execution(self, mock_server_repo, MockClient):
        mock_client = AsyncMock()
        mock_client.connect.return_value = MagicMock()
        mock_client.call_tool.return_value = ToolCallResult(
            content=[ContentBlock(type="text", text="Sunny, 25°C")],
            isError=False,
        )
        MockClient.return_value = mock_client

        server = {
            "id": str(uuid.uuid4()),
            "url": "http://mcp.example.com",
            "auth_type": "none",
            "auth_credential_ref": None,
            "auth_header_name": None,
        }
        mock_server_repo.get = AsyncMock(return_value=server)

        service = AgentExecutionService()
        mcp_tool = _make_mcp_tool()

        result = await service._execute_mcp_tool(
            mcp_tool, {"city": "London"}, TENANT_ID
        )

        assert result["result"] == "Sunny, 25°C"
        assert result["is_error"] is False
        mock_client.connect.assert_called_once()
        mock_client.call_tool.assert_called_once_with("get_weather", {"city": "London"})
        mock_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.agent_execution.MCPClient")
    @patch("app.services.agent_execution._mcp_server_repo")
    async def test_execution_failure(self, mock_server_repo, MockClient):
        mock_client = AsyncMock()
        mock_client.connect.side_effect = MCPClientError("Connection refused")
        MockClient.return_value = mock_client

        server = {
            "id": str(uuid.uuid4()),
            "url": "http://mcp.example.com",
            "auth_type": "none",
            "auth_credential_ref": None,
            "auth_header_name": None,
        }
        mock_server_repo.get = AsyncMock(return_value=server)

        service = AgentExecutionService()
        mcp_tool = _make_mcp_tool()

        result = await service._execute_mcp_tool(mcp_tool, {}, TENANT_ID)

        assert "error" in result
        assert "Connection refused" in result["error"]
        mock_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.agent_execution._mcp_server_repo")
    async def test_server_not_found(self, mock_server_repo):
        mock_server_repo.get = AsyncMock(return_value=None)

        service = AgentExecutionService()
        mcp_tool = _make_mcp_tool()

        result = await service._execute_mcp_tool(mcp_tool, {}, TENANT_ID)

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    @patch("app.services.agent_execution.MCPClient")
    @patch("app.services.agent_execution._mcp_server_repo")
    async def test_tool_level_error(self, mock_server_repo, MockClient):
        mock_client = AsyncMock()
        mock_client.connect.return_value = MagicMock()
        mock_client.call_tool.return_value = ToolCallResult(
            content=[ContentBlock(type="text", text="City not found")],
            isError=True,
        )
        MockClient.return_value = mock_client

        server = {
            "id": str(uuid.uuid4()),
            "url": "http://mcp.example.com",
            "auth_type": "none",
            "auth_credential_ref": None,
            "auth_header_name": None,
        }
        mock_server_repo.get = AsyncMock(return_value=server)

        service = AgentExecutionService()
        mcp_tool = _make_mcp_tool()

        result = await service._execute_mcp_tool(mcp_tool, {"city": "Atlantis"}, TENANT_ID)

        assert result["is_error"] is True
        assert result["result"] == "City not found"


class TestLoadAgentMCPTools:
    @pytest.mark.asyncio
    @patch("app.services.agent_execution._mcp_tool_repo")
    @patch("app.services.agent_execution._agent_mcp_tool_repo")
    async def test_returns_available_tools(self, mock_amt_repo, mock_tool_repo):
        links = [
            {"agent_id": "a1", "mcp_tool_id": "t1"},
            {"agent_id": "a1", "mcp_tool_id": "t2"},
        ]
        mock_amt_repo.query = AsyncMock(return_value=links)

        tools = [
            _make_mcp_tool(tool_name="get_weather"),
            _make_mcp_tool(tool_name="search"),
        ]
        mock_tool_repo.get = AsyncMock(side_effect=tools)

        service = AgentExecutionService()
        result = await service._load_agent_mcp_tools("a1", TENANT_ID)
        assert len(result) == 2


class TestAgentMCPToolModel:
    def test_model_importable(self):
        assert AgentMCPTool.__tablename__ == "agent_mcp_tools"

    def test_model_has_columns(self):
        col_names = [c.name for c in AgentMCPTool.__table__.columns]
        assert "agent_id" in col_names
        assert "mcp_tool_id" in col_names
