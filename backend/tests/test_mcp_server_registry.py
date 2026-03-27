"""Unit tests for MCP Server Registry CRUD API handlers."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.mcp_server import MCPServer
from app.api.v1.schemas import (
    MCPServerCreateRequest,
    MCPServerUpdateRequest,
    MCPServerResponse,
    MCPServerListResponse,
)


TENANT_ID = str(uuid.uuid4())
NOW = datetime.now(timezone.utc)


def _make_server_dict(**overrides):
    defaults = {
        "id": str(uuid.uuid4()),
        "name": "Test MCP Server",
        "url": "http://mcp.example.com/sse",
        "description": "A test MCP server",
        "auth_type": "none",
        "auth_header_name": None,
        "auth_credential_ref": None,
        "is_active": True,
        "status": "unknown",
        "status_message": None,
        "tenant_id": TENANT_ID,
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
    }
    defaults.update(overrides)
    return defaults


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

    def test_list_response(self):
        server = _make_server_dict()
        resp = MCPServerResponse.model_validate(server)
        list_resp = MCPServerListResponse(servers=[resp], total=1)
        assert list_resp.total == 1
        assert len(list_resp.servers) == 1


class TestMCPServerCRUD:
    @pytest.mark.asyncio
    @patch("app.api.v1.mcp_servers.server_repo")
    async def test_list_returns_servers(self, mock_repo):
        from app.api.v1.mcp_servers import list_mcp_servers

        servers = [_make_server_dict(), _make_server_dict()]
        mock_repo.list_by_tenant = AsyncMock(return_value=servers)

        result = await list_mcp_servers(
            request=MagicMock(),
            current_user=MagicMock(),
            tenant_id=TENANT_ID,
        )
        assert result.total == 2

    @pytest.mark.asyncio
    @patch("app.api.v1.mcp_servers.server_repo")
    async def test_get_server_found(self, mock_repo):
        from app.api.v1.mcp_servers import get_mcp_server

        server = _make_server_dict()
        mock_repo.get = AsyncMock(return_value=server)

        result = await get_mcp_server(
            server_id=server["id"],
            request=MagicMock(),
            current_user=MagicMock(),
            tenant_id=TENANT_ID,
        )
        assert result["name"] == "Test MCP Server"

    @pytest.mark.asyncio
    @patch("app.api.v1.mcp_servers.server_repo")
    async def test_get_server_not_found(self, mock_repo):
        from fastapi import HTTPException
        from app.api.v1.mcp_servers import get_mcp_server

        mock_repo.get = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_mcp_server(
                server_id=str(uuid.uuid4()),
                request=MagicMock(),
                current_user=MagicMock(),
                tenant_id=TENANT_ID,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.api.v1.mcp_servers.server_repo")
    async def test_delete_server(self, mock_repo):
        from app.api.v1.mcp_servers import delete_mcp_server

        server = _make_server_dict()
        mock_repo.get = AsyncMock(return_value=server)
        mock_repo.delete = AsyncMock()

        await delete_mcp_server(
            server_id=server["id"],
            request=MagicMock(),
            current_user=MagicMock(),
            tenant_id=TENANT_ID,
        )
        mock_repo.delete.assert_called_once_with(TENANT_ID, server["id"])

    @pytest.mark.asyncio
    @patch("app.api.v1.mcp_servers.server_repo")
    async def test_delete_server_not_found(self, mock_repo):
        from fastapi import HTTPException
        from app.api.v1.mcp_servers import delete_mcp_server

        mock_repo.get = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await delete_mcp_server(
                server_id=str(uuid.uuid4()),
                request=MagicMock(),
                current_user=MagicMock(),
                tenant_id=TENANT_ID,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.api.v1.mcp_servers.server_repo")
    async def test_update_server(self, mock_repo):
        from app.api.v1.mcp_servers import update_mcp_server

        server = _make_server_dict()
        updated_server = {**server, "name": "Updated Name", "is_active": False}
        mock_repo.get = AsyncMock(return_value=server)
        mock_repo.update = AsyncMock(return_value=updated_server)

        body = MCPServerUpdateRequest(name="Updated Name", is_active=False)
        result = await update_mcp_server(
            server_id=server["id"],
            body=body,
            request=MagicMock(),
            current_user=MagicMock(),
            tenant_id=TENANT_ID,
        )
        assert result["name"] == "Updated Name"
        assert result["is_active"] is False
