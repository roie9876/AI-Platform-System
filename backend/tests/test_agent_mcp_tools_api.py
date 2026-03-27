"""Unit tests for Agent MCP Tool attach/detach/list API handlers."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.agent_mcp_tool import AgentMCPTool
from app.models.mcp_discovered_tool import MCPDiscoveredTool
from app.models.mcp_server import MCPServer
from app.api.v1.schemas import AgentMCPToolAttachRequest, AgentMCPToolResponse


TENANT_ID = str(uuid.uuid4())
AGENT_ID = str(uuid.uuid4())
MCP_TOOL_ID = str(uuid.uuid4())
SERVER_ID = str(uuid.uuid4())
NOW = datetime.now(timezone.utc)


def _make_agent():
    return {
        "id": AGENT_ID,
        "tenant_id": TENANT_ID,
        "name": "Test Agent",
    }


def _make_mcp_tool(**overrides):
    defaults = {
        "id": MCP_TOOL_ID,
        "server_id": SERVER_ID,
        "tool_name": "test_tool",
        "description": "A test tool",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
        "is_available": True,
        "tenant_id": TENANT_ID,
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_server(**overrides):
    defaults = {
        "id": SERVER_ID,
        "name": "Test Server",
        "url": "http://mcp.example.com",
        "tenant_id": TENANT_ID,
    }
    defaults.update(overrides)
    return defaults


def _make_agent_mcp_tool(**overrides):
    defaults = {
        "id": str(uuid.uuid4()),
        "agent_id": AGENT_ID,
        "mcp_tool_id": MCP_TOOL_ID,
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
        "tenant_id": TENANT_ID,
    }
    defaults.update(overrides)
    return defaults


class TestAttachMCPTool:
    @pytest.mark.asyncio
    @patch("app.api.v1.agent_mcp_tools.server_repo")
    @patch("app.api.v1.agent_mcp_tools.agent_mcp_tool_repo")
    @patch("app.api.v1.agent_mcp_tools.mcp_tool_repo")
    @patch("app.api.v1.agent_mcp_tools.agent_repo")
    async def test_attach_success(self, mock_agent_repo, mock_tool_repo, mock_amt_repo, mock_server_repo):
        from app.api.v1.agent_mcp_tools import attach_mcp_tool

        agent = _make_agent()
        mcp_tool = _make_mcp_tool()
        server = _make_server()
        amt = _make_agent_mcp_tool()

        mock_agent_repo.get = AsyncMock(return_value=agent)
        mock_tool_repo.get = AsyncMock(return_value=mcp_tool)
        mock_amt_repo.query = AsyncMock(return_value=[])  # no duplicate
        mock_amt_repo.create = AsyncMock(return_value=amt)
        mock_server_repo.get = AsyncMock(return_value=server)

        body = AgentMCPToolAttachRequest(mcp_tool_id=MCP_TOOL_ID)
        result = await attach_mcp_tool(
            agent_id=AGENT_ID,
            body=body,
            request=MagicMock(),
            current_user=MagicMock(),
            tenant_id=TENANT_ID,
        )
        assert result.tool_name == "test_tool"
        assert result.server_name == "Test Server"

    @pytest.mark.asyncio
    @patch("app.api.v1.agent_mcp_tools.agent_repo")
    async def test_attach_agent_not_found(self, mock_agent_repo):
        from fastapi import HTTPException
        from app.api.v1.agent_mcp_tools import attach_mcp_tool

        mock_agent_repo.get = AsyncMock(return_value=None)

        body = AgentMCPToolAttachRequest(mcp_tool_id=MCP_TOOL_ID)
        with pytest.raises(HTTPException) as exc_info:
            await attach_mcp_tool(
                agent_id=AGENT_ID,
                body=body,
                request=MagicMock(),
                current_user=MagicMock(),
                tenant_id=TENANT_ID,
            )
        assert exc_info.value.status_code == 404
        assert "Agent not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch("app.api.v1.agent_mcp_tools.mcp_tool_repo")
    @patch("app.api.v1.agent_mcp_tools.agent_repo")
    async def test_attach_tool_not_found(self, mock_agent_repo, mock_tool_repo):
        from fastapi import HTTPException
        from app.api.v1.agent_mcp_tools import attach_mcp_tool

        mock_agent_repo.get = AsyncMock(return_value=_make_agent())
        mock_tool_repo.get = AsyncMock(return_value=None)

        body = AgentMCPToolAttachRequest(mcp_tool_id=str(uuid.uuid4()))
        with pytest.raises(HTTPException) as exc_info:
            await attach_mcp_tool(
                agent_id=AGENT_ID,
                body=body,
                request=MagicMock(),
                current_user=MagicMock(),
                tenant_id=TENANT_ID,
            )
        assert exc_info.value.status_code == 404
        assert "MCP tool not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch("app.api.v1.agent_mcp_tools.agent_mcp_tool_repo")
    @patch("app.api.v1.agent_mcp_tools.mcp_tool_repo")
    @patch("app.api.v1.agent_mcp_tools.agent_repo")
    async def test_attach_duplicate(self, mock_agent_repo, mock_tool_repo, mock_amt_repo):
        from fastapi import HTTPException
        from app.api.v1.agent_mcp_tools import attach_mcp_tool

        mock_agent_repo.get = AsyncMock(return_value=_make_agent())
        mock_tool_repo.get = AsyncMock(return_value=_make_mcp_tool())
        mock_amt_repo.query = AsyncMock(return_value=[_make_agent_mcp_tool()])  # duplicate exists

        body = AgentMCPToolAttachRequest(mcp_tool_id=MCP_TOOL_ID)
        with pytest.raises(HTTPException) as exc_info:
            await attach_mcp_tool(
                agent_id=AGENT_ID,
                body=body,
                request=MagicMock(),
                current_user=MagicMock(),
                tenant_id=TENANT_ID,
            )
        assert exc_info.value.status_code == 409


class TestDetachMCPTool:
    @pytest.mark.asyncio
    @patch("app.api.v1.agent_mcp_tools.agent_mcp_tool_repo")
    @patch("app.api.v1.agent_mcp_tools.agent_repo")
    async def test_detach_success(self, mock_agent_repo, mock_amt_repo):
        from app.api.v1.agent_mcp_tools import detach_mcp_tool

        amt = _make_agent_mcp_tool()
        mock_agent_repo.get = AsyncMock(return_value=_make_agent())
        mock_amt_repo.query = AsyncMock(return_value=[amt])
        mock_amt_repo.delete = AsyncMock()

        await detach_mcp_tool(
            agent_id=AGENT_ID,
            mcp_tool_id=MCP_TOOL_ID,
            request=MagicMock(),
            current_user=MagicMock(),
            tenant_id=TENANT_ID,
        )
        mock_amt_repo.delete.assert_called_once_with(TENANT_ID, amt["id"])

    @pytest.mark.asyncio
    @patch("app.api.v1.agent_mcp_tools.agent_mcp_tool_repo")
    @patch("app.api.v1.agent_mcp_tools.agent_repo")
    async def test_detach_not_found(self, mock_agent_repo, mock_amt_repo):
        from fastapi import HTTPException
        from app.api.v1.agent_mcp_tools import detach_mcp_tool

        mock_agent_repo.get = AsyncMock(return_value=_make_agent())
        mock_amt_repo.query = AsyncMock(return_value=[])  # no attachment

        with pytest.raises(HTTPException) as exc_info:
            await detach_mcp_tool(
                agent_id=AGENT_ID,
                mcp_tool_id=MCP_TOOL_ID,
                request=MagicMock(),
                current_user=MagicMock(),
                tenant_id=TENANT_ID,
            )
        assert exc_info.value.status_code == 404


class TestListAgentMCPTools:
    @pytest.mark.asyncio
    @patch("app.api.v1.agent_mcp_tools.server_repo")
    @patch("app.api.v1.agent_mcp_tools.mcp_tool_repo")
    @patch("app.api.v1.agent_mcp_tools.agent_mcp_tool_repo")
    @patch("app.api.v1.agent_mcp_tools.agent_repo")
    async def test_list_returns_joined_data(self, mock_agent_repo, mock_amt_repo, mock_tool_repo, mock_server_repo):
        from app.api.v1.agent_mcp_tools import list_agent_mcp_tools

        amt = _make_agent_mcp_tool()
        tool = _make_mcp_tool()
        server = _make_server()

        mock_agent_repo.get = AsyncMock(return_value=_make_agent())
        mock_amt_repo.list_by_agent = AsyncMock(return_value=[amt])
        mock_tool_repo.get = AsyncMock(return_value=tool)
        mock_server_repo.get = AsyncMock(return_value=server)

        result = await list_agent_mcp_tools(
            agent_id=AGENT_ID,
            request=MagicMock(),
            current_user=MagicMock(),
            tenant_id=TENANT_ID,
        )
        assert len(result) == 1
        assert result[0].tool_name == "test_tool"
        assert result[0].server_name == "Test Server"
        assert result[0].is_available is True

    @pytest.mark.asyncio
    @patch("app.api.v1.agent_mcp_tools.agent_mcp_tool_repo")
    @patch("app.api.v1.agent_mcp_tools.agent_repo")
    async def test_list_empty(self, mock_agent_repo, mock_amt_repo):
        from app.api.v1.agent_mcp_tools import list_agent_mcp_tools

        mock_agent_repo.get = AsyncMock(return_value=_make_agent())
        mock_amt_repo.list_by_agent = AsyncMock(return_value=[])

        result = await list_agent_mcp_tools(
            agent_id=AGENT_ID,
            request=MagicMock(),
            current_user=MagicMock(),
            tenant_id=TENANT_ID,
        )
        assert len(result) == 0
