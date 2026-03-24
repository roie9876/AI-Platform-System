"""Unit tests for MCP Server Registry CRUD API handlers."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.mcp_server import MCPServer
from app.api.v1.schemas import (
    MCPServerCreateRequest,
    MCPServerUpdateRequest,
    MCPServerResponse,
    MCPServerListResponse,
)


def _make_mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    return db


def _make_mcp_server(**overrides):
    from datetime import datetime, timezone

    defaults = {
        "id": uuid.uuid4(),
        "name": "Test MCP Server",
        "url": "http://mcp.example.com/sse",
        "description": "A test MCP server",
        "auth_type": "none",
        "auth_header_name": None,
        "auth_credential_ref": None,
        "is_active": True,
        "status": "unknown",
        "status_message": None,
        "tenant_id": uuid.uuid4(),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    mock = MagicMock(spec=MCPServer, **defaults)
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


TENANT_ID = uuid.uuid4()


class TestMCPServerModel:
    def test_model_importable(self):
        assert MCPServer.__tablename__ == "mcp_servers"

    def test_model_has_required_columns(self):
        column_names = [c.name for c in MCPServer.__table__.columns]
        for col in ["id", "name", "url", "auth_type", "status", "tenant_id"]:
            assert col in column_names


class TestMCPServerSchemas:
    def test_create_request_valid(self):
        req = MCPServerCreateRequest(
            name="My Server",
            url="http://localhost:3000/mcp",
        )
        assert req.name == "My Server"
        assert req.auth_type == "none"

    def test_create_request_with_auth(self):
        req = MCPServerCreateRequest(
            name="Authed Server",
            url="https://mcp.example.com",
            auth_type="bearer",
            auth_credential_ref="secret-ref-123",
        )
        assert req.auth_type == "bearer"

    def test_update_request_partial(self):
        req = MCPServerUpdateRequest(name="New Name")
        dumped = req.model_dump(exclude_unset=True)
        assert dumped == {"name": "New Name"}

    def test_response_from_attributes(self):
        server = _make_mcp_server(tenant_id=TENANT_ID)
        resp = MCPServerResponse.model_validate(server, from_attributes=True)
        assert resp.name == "Test MCP Server"
        assert resp.status == "unknown"

    def test_list_response(self):
        server = _make_mcp_server(tenant_id=TENANT_ID)
        resp = MCPServerResponse.model_validate(server, from_attributes=True)
        list_resp = MCPServerListResponse(servers=[resp], total=1)
        assert list_resp.total == 1
        assert len(list_resp.servers) == 1


class TestMCPServerCRUD:
    @pytest.mark.asyncio
    async def test_list_returns_servers(self):
        from app.api.v1.mcp_servers import list_mcp_servers

        db = _make_mock_db()
        servers = [_make_mcp_server(tenant_id=TENANT_ID), _make_mcp_server(tenant_id=TENANT_ID)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = servers
        db.execute.return_value = mock_result

        with patch("app.api.v1.mcp_servers.get_db", return_value=db), \
             patch("app.api.v1.mcp_servers.get_current_user", return_value=MagicMock()), \
             patch("app.api.v1.mcp_servers.get_tenant_id", return_value=str(TENANT_ID)):
            result = await list_mcp_servers(
                request=MagicMock(),
                db=db,
                current_user=MagicMock(),
                tenant_id=str(TENANT_ID),
            )
        assert result.total == 2

    @pytest.mark.asyncio
    async def test_get_server_found(self):
        from app.api.v1.mcp_servers import get_mcp_server

        db = _make_mock_db()
        server = _make_mcp_server(tenant_id=TENANT_ID)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = server
        db.execute.return_value = mock_result

        result = await get_mcp_server(
            server_id=server.id,
            request=MagicMock(),
            db=db,
            current_user=MagicMock(),
            tenant_id=str(TENANT_ID),
        )
        assert result.name == "Test MCP Server"

    @pytest.mark.asyncio
    async def test_get_server_not_found(self):
        from fastapi import HTTPException
        from app.api.v1.mcp_servers import get_mcp_server

        db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_mcp_server(
                server_id=uuid.uuid4(),
                request=MagicMock(),
                db=db,
                current_user=MagicMock(),
                tenant_id=str(TENANT_ID),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_server(self):
        from app.api.v1.mcp_servers import delete_mcp_server

        db = _make_mock_db()
        server = _make_mcp_server(tenant_id=TENANT_ID)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = server
        db.execute.return_value = mock_result

        await delete_mcp_server(
            server_id=server.id,
            request=MagicMock(),
            db=db,
            current_user=MagicMock(),
            tenant_id=str(TENANT_ID),
        )
        db.delete.assert_called_once_with(server)

    @pytest.mark.asyncio
    async def test_delete_server_not_found(self):
        from fastapi import HTTPException
        from app.api.v1.mcp_servers import delete_mcp_server

        db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_mcp_server(
                server_id=uuid.uuid4(),
                request=MagicMock(),
                db=db,
                current_user=MagicMock(),
                tenant_id=str(TENANT_ID),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_server(self):
        from app.api.v1.mcp_servers import update_mcp_server

        db = _make_mock_db()
        server = _make_mcp_server(tenant_id=TENANT_ID)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = server
        db.execute.return_value = mock_result

        body = MCPServerUpdateRequest(name="Updated Name", is_active=False)
        result = await update_mcp_server(
            server_id=server.id,
            body=body,
            request=MagicMock(),
            db=db,
            current_user=MagicMock(),
            tenant_id=str(TENANT_ID),
        )
        assert server.name == "Updated Name"
        assert server.is_active is False
