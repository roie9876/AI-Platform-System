"""Unit tests for MCP integration in Agent Execution Service."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.agent_mcp_tool import AgentMCPTool
from app.models.mcp_discovered_tool import MCPDiscoveredTool
from app.services.agent_execution import AgentExecutionService
from app.services.mcp_client import MCPClientError
from app.services.mcp_types import ContentBlock, ToolCallResult


def _make_mcp_tool(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "server_id": uuid.uuid4(),
        "tool_name": "get_weather",
        "description": "Get weather for a city",
        "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}},
        "is_available": True,
        "tenant_id": uuid.uuid4(),
    }
    defaults.update(overrides)
    mock = MagicMock(spec=MCPDiscoveredTool, **defaults)
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


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
    async def test_successful_execution(self, MockClient):
        mock_client = AsyncMock()
        mock_client.connect.return_value = MagicMock()
        mock_client.call_tool.return_value = ToolCallResult(
            content=[ContentBlock(type="text", text="Sunny, 25°C")],
            isError=False,
        )
        MockClient.return_value = mock_client

        service = AgentExecutionService()
        mcp_tool = _make_mcp_tool()

        db = AsyncMock()
        server_mock = MagicMock()
        server_mock.url = "http://mcp.example.com"
        server_mock.auth_type = "none"
        server_mock.auth_credential_ref = None
        server_mock.auth_header_name = None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = server_mock
        db.execute.return_value = mock_result

        result = await service._execute_mcp_tool(
            mcp_tool, {"city": "London"}, db
        )

        assert result["result"] == "Sunny, 25°C"
        assert result["is_error"] is False
        mock_client.connect.assert_called_once()
        mock_client.call_tool.assert_called_once_with("get_weather", {"city": "London"})
        mock_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.agent_execution.MCPClient")
    async def test_execution_failure(self, MockClient):
        mock_client = AsyncMock()
        mock_client.connect.side_effect = MCPClientError("Connection refused")
        MockClient.return_value = mock_client

        service = AgentExecutionService()
        mcp_tool = _make_mcp_tool()

        db = AsyncMock()
        server_mock = MagicMock()
        server_mock.url = "http://mcp.example.com"
        server_mock.auth_type = "none"
        server_mock.auth_credential_ref = None
        server_mock.auth_header_name = None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = server_mock
        db.execute.return_value = mock_result

        result = await service._execute_mcp_tool(mcp_tool, {}, db)

        assert "error" in result
        assert "Connection refused" in result["error"]
        mock_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_server_not_found(self):
        service = AgentExecutionService()
        mcp_tool = _make_mcp_tool()

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        result = await service._execute_mcp_tool(mcp_tool, {}, db)

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    @patch("app.services.agent_execution.MCPClient")
    async def test_tool_level_error(self, MockClient):
        mock_client = AsyncMock()
        mock_client.connect.return_value = MagicMock()
        mock_client.call_tool.return_value = ToolCallResult(
            content=[ContentBlock(type="text", text="City not found")],
            isError=True,
        )
        MockClient.return_value = mock_client

        service = AgentExecutionService()
        mcp_tool = _make_mcp_tool()

        db = AsyncMock()
        server_mock = MagicMock()
        server_mock.url = "http://mcp.example.com"
        server_mock.auth_type = "none"
        server_mock.auth_credential_ref = None
        server_mock.auth_header_name = None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = server_mock
        db.execute.return_value = mock_result

        result = await service._execute_mcp_tool(mcp_tool, {"city": "Atlantis"}, db)

        assert result["is_error"] is True
        assert result["result"] == "City not found"


class TestLoadAgentMCPTools:
    @pytest.mark.asyncio
    async def test_returns_available_tools(self):
        service = AgentExecutionService()
        db = AsyncMock()

        tools = [_make_mcp_tool(), _make_mcp_tool(tool_name="search")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = tools
        db.execute.return_value = mock_result

        result = await service._load_agent_mcp_tools(uuid.uuid4(), db)
        assert len(result) == 2


class TestAgentMCPToolModel:
    def test_model_importable(self):
        assert AgentMCPTool.__tablename__ == "agent_mcp_tools"

    def test_model_has_columns(self):
        col_names = [c.name for c in AgentMCPTool.__table__.columns]
        assert "agent_id" in col_names
        assert "mcp_tool_id" in col_names
