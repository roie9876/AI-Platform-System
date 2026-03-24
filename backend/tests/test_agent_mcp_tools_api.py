"""Unit tests for Agent MCP Tool attach/detach/list API handlers."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.agent_mcp_tool import AgentMCPTool
from app.models.mcp_discovered_tool import MCPDiscoveredTool
from app.models.mcp_server import MCPServer
from app.api.v1.schemas import AgentMCPToolAttachRequest, AgentMCPToolResponse


def _make_mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    return db


TENANT_ID = uuid.uuid4()
AGENT_ID = uuid.uuid4()
MCP_TOOL_ID = uuid.uuid4()
SERVER_ID = uuid.uuid4()
NOW = datetime.now(timezone.utc)


def _make_agent():
    mock = MagicMock()
    mock.id = AGENT_ID
    mock.tenant_id = TENANT_ID
    return mock


def _make_mcp_tool(**overrides):
    defaults = {
        "id": MCP_TOOL_ID,
        "server_id": SERVER_ID,
        "tool_name": "test_tool",
        "description": "A test tool",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
        "is_available": True,
        "tenant_id": TENANT_ID,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(overrides)
    mock = MagicMock(spec=MCPDiscoveredTool, **defaults)
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_server(**overrides):
    defaults = {
        "id": SERVER_ID,
        "name": "Test Server",
        "url": "http://mcp.example.com",
        "tenant_id": TENANT_ID,
    }
    defaults.update(overrides)
    mock = MagicMock(spec=MCPServer, **defaults)
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_agent_mcp_tool(**overrides):
    amt_id = overrides.get("id", uuid.uuid4())
    defaults = {
        "id": amt_id,
        "agent_id": AGENT_ID,
        "mcp_tool_id": MCP_TOOL_ID,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(overrides)
    mock = MagicMock(spec=AgentMCPTool, **defaults)
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


class TestAttachMCPTool:
    @pytest.mark.asyncio
    async def test_attach_success(self):
        from app.api.v1.agent_mcp_tools import attach_mcp_tool

        db = _make_mock_db()
        agent = _make_agent()
        mcp_tool = _make_mcp_tool()
        server = _make_server()
        amt = _make_agent_mcp_tool()

        # Sequence: agent check, tool check, duplicate check, server fetch
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = agent

        tool_result = MagicMock()
        tool_result.scalar_one_or_none.return_value = mcp_tool

        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = None

        server_result = MagicMock()
        server_result.scalar_one_or_none.return_value = server

        db.execute.side_effect = [agent_result, tool_result, dup_result, server_result]
        db.refresh.side_effect = lambda x: setattr(x, 'id', amt.id) or setattr(x, 'created_at', NOW)

        body = AgentMCPToolAttachRequest(mcp_tool_id=MCP_TOOL_ID)
        result = await attach_mcp_tool(
            agent_id=AGENT_ID,
            body=body,
            request=MagicMock(),
            db=db,
            current_user=MagicMock(),
            tenant_id=str(TENANT_ID),
        )
        assert result.tool_name == "test_tool"
        assert result.server_name == "Test Server"
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_attach_agent_not_found(self):
        from fastapi import HTTPException
        from app.api.v1.agent_mcp_tools import attach_mcp_tool

        db = _make_mock_db()
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = None
        db.execute.return_value = agent_result

        body = AgentMCPToolAttachRequest(mcp_tool_id=MCP_TOOL_ID)
        with pytest.raises(HTTPException) as exc_info:
            await attach_mcp_tool(
                agent_id=AGENT_ID,
                body=body,
                request=MagicMock(),
                db=db,
                current_user=MagicMock(),
                tenant_id=str(TENANT_ID),
            )
        assert exc_info.value.status_code == 404
        assert "Agent not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_attach_tool_not_found(self):
        from fastapi import HTTPException
        from app.api.v1.agent_mcp_tools import attach_mcp_tool

        db = _make_mock_db()
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = _make_agent()
        tool_result = MagicMock()
        tool_result.scalar_one_or_none.return_value = None
        db.execute.side_effect = [agent_result, tool_result]

        body = AgentMCPToolAttachRequest(mcp_tool_id=uuid.uuid4())
        with pytest.raises(HTTPException) as exc_info:
            await attach_mcp_tool(
                agent_id=AGENT_ID,
                body=body,
                request=MagicMock(),
                db=db,
                current_user=MagicMock(),
                tenant_id=str(TENANT_ID),
            )
        assert exc_info.value.status_code == 404
        assert "MCP tool not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_attach_duplicate(self):
        from fastapi import HTTPException
        from app.api.v1.agent_mcp_tools import attach_mcp_tool

        db = _make_mock_db()
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = _make_agent()
        tool_result = MagicMock()
        tool_result.scalar_one_or_none.return_value = _make_mcp_tool()
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = _make_agent_mcp_tool()
        db.execute.side_effect = [agent_result, tool_result, dup_result]

        body = AgentMCPToolAttachRequest(mcp_tool_id=MCP_TOOL_ID)
        with pytest.raises(HTTPException) as exc_info:
            await attach_mcp_tool(
                agent_id=AGENT_ID,
                body=body,
                request=MagicMock(),
                db=db,
                current_user=MagicMock(),
                tenant_id=str(TENANT_ID),
            )
        assert exc_info.value.status_code == 409


class TestDetachMCPTool:
    @pytest.mark.asyncio
    async def test_detach_success(self):
        from app.api.v1.agent_mcp_tools import detach_mcp_tool

        db = _make_mock_db()
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = _make_agent()
        amt_result = MagicMock()
        amt_result.scalar_one_or_none.return_value = _make_agent_mcp_tool()
        db.execute.side_effect = [agent_result, amt_result]

        await detach_mcp_tool(
            agent_id=AGENT_ID,
            mcp_tool_id=MCP_TOOL_ID,
            request=MagicMock(),
            db=db,
            current_user=MagicMock(),
            tenant_id=str(TENANT_ID),
        )
        db.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_detach_not_found(self):
        from fastapi import HTTPException
        from app.api.v1.agent_mcp_tools import detach_mcp_tool

        db = _make_mock_db()
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = _make_agent()
        amt_result = MagicMock()
        amt_result.scalar_one_or_none.return_value = None
        db.execute.side_effect = [agent_result, amt_result]

        with pytest.raises(HTTPException) as exc_info:
            await detach_mcp_tool(
                agent_id=AGENT_ID,
                mcp_tool_id=MCP_TOOL_ID,
                request=MagicMock(),
                db=db,
                current_user=MagicMock(),
                tenant_id=str(TENANT_ID),
            )
        assert exc_info.value.status_code == 404


class TestListAgentMCPTools:
    @pytest.mark.asyncio
    async def test_list_returns_joined_data(self):
        from app.api.v1.agent_mcp_tools import list_agent_mcp_tools

        db = _make_mock_db()
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = _make_agent()

        amt = _make_agent_mcp_tool()
        tool = _make_mcp_tool()
        server = _make_server()
        list_result = MagicMock()
        list_result.all.return_value = [(amt, tool, server)]

        db.execute.side_effect = [agent_result, list_result]

        result = await list_agent_mcp_tools(
            agent_id=AGENT_ID,
            request=MagicMock(),
            db=db,
            current_user=MagicMock(),
            tenant_id=str(TENANT_ID),
        )
        assert len(result) == 1
        assert result[0].tool_name == "test_tool"
        assert result[0].server_name == "Test Server"
        assert result[0].is_available is True

    @pytest.mark.asyncio
    async def test_list_empty(self):
        from app.api.v1.agent_mcp_tools import list_agent_mcp_tools

        db = _make_mock_db()
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = _make_agent()
        list_result = MagicMock()
        list_result.all.return_value = []
        db.execute.side_effect = [agent_result, list_result]

        result = await list_agent_mcp_tools(
            agent_id=AGENT_ID,
            request=MagicMock(),
            db=db,
            current_user=MagicMock(),
            tenant_id=str(TENANT_ID),
        )
        assert len(result) == 0
