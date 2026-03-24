"""
MCP Tool Discovery Service.

Discovers tools from registered MCP servers, syncs the local catalog,
and performs health checks with reconnection logic.
"""

import logging
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_server import MCPServer
from app.models.mcp_discovered_tool import MCPDiscoveredTool
from app.services.mcp_client import MCPClient, MCPClientError

logger = logging.getLogger(__name__)


class MCPDiscoveryService:
    """Discovers and syncs tools from registered MCP servers."""

    @staticmethod
    async def discover_tools_from_server(
        db: AsyncSession,
        server: MCPServer,
    ) -> List[MCPDiscoveredTool]:
        """Connect to an MCP server, discover tools via tools/list, and sync local catalog."""
        headers = _build_auth_headers(server)
        client = MCPClient(server.url, timeout=15.0, headers=headers)

        try:
            init_result = await client.connect()
            server.status = "connected"
            server.status_message = (
                f"Connected to {init_result.serverInfo.name} "
                f"v{init_result.serverInfo.version}"
            )

            # Fetch all tools (handle pagination)
            all_tools = []
            cursor = None
            while True:
                result = await client.list_tools(cursor=cursor)
                all_tools.extend(result.tools)
                if result.nextCursor:
                    cursor = result.nextCursor
                else:
                    break

            # Sync: remove old tools for this server, insert new ones
            await db.execute(
                delete(MCPDiscoveredTool).where(
                    MCPDiscoveredTool.server_id == server.id
                )
            )

            discovered = []
            for tool_info in all_tools:
                tool = MCPDiscoveredTool(
                    server_id=server.id,
                    tool_name=tool_info.name,
                    description=tool_info.description,
                    input_schema=tool_info.inputSchema.model_dump() if tool_info.inputSchema else None,
                    is_available=True,
                    tenant_id=server.tenant_id,
                )
                db.add(tool)
                discovered.append(tool)

            await db.flush()
            logger.info(
                "Discovered %d tools from MCP server %s (%s)",
                len(discovered),
                server.name,
                server.url,
            )
            return discovered

        except MCPClientError as e:
            server.status = "error"
            server.status_message = str(e)

            # Mark existing tools as unavailable
            result = await db.execute(
                select(MCPDiscoveredTool).where(
                    MCPDiscoveredTool.server_id == server.id
                )
            )
            for tool in result.scalars().all():
                tool.is_available = False

            await db.flush()
            logger.warning(
                "Failed to discover tools from %s: %s", server.name, e
            )
            return []

        finally:
            await client.disconnect()

    @staticmethod
    async def discover_all_servers(
        db: AsyncSession,
        tenant_id: UUID,
    ) -> Dict[str, int]:
        """Discover tools from all active MCP servers for a tenant."""
        result = await db.execute(
            select(MCPServer).where(
                MCPServer.tenant_id == tenant_id,
                MCPServer.is_active == True,
            )
        )
        servers = list(result.scalars().all())

        summary = {}
        for server in servers:
            tools = await MCPDiscoveryService.discover_tools_from_server(
                db, server
            )
            summary[server.name] = len(tools)

        return summary

    @staticmethod
    async def health_check_server(
        db: AsyncSession,
        server: MCPServer,
    ) -> bool:
        """Check if an MCP server is reachable and update its status."""
        headers = _build_auth_headers(server)
        client = MCPClient(server.url, timeout=10.0, headers=headers)

        try:
            init_result = await client.connect()
            server.status = "connected"
            server.status_message = (
                f"Healthy — {init_result.serverInfo.name} "
                f"v{init_result.serverInfo.version}"
            )
            await db.flush()
            return True
        except MCPClientError as e:
            server.status = "error"
            server.status_message = str(e)
            await db.flush()
            return False
        finally:
            await client.disconnect()

    @staticmethod
    async def get_all_discovered_tools(
        db: AsyncSession,
        tenant_id: UUID,
        server_id: Optional[UUID] = None,
    ) -> List[MCPDiscoveredTool]:
        """Get all discovered tools, optionally filtered by server."""
        query = select(MCPDiscoveredTool).where(
            MCPDiscoveredTool.tenant_id == tenant_id
        )
        if server_id:
            query = query.where(MCPDiscoveredTool.server_id == server_id)
        query = query.order_by(MCPDiscoveredTool.tool_name)

        result = await db.execute(query)
        return list(result.scalars().all())


def _build_auth_headers(server: MCPServer) -> Dict[str, str]:
    """Build authentication headers from MCP server configuration."""
    headers: Dict[str, str] = {}
    if server.auth_type == "bearer" and server.auth_credential_ref:
        headers["Authorization"] = f"Bearer {server.auth_credential_ref}"
    elif server.auth_type == "api_key" and server.auth_credential_ref:
        header_name = server.auth_header_name or "X-API-Key"
        headers[header_name] = server.auth_credential_ref
    elif (
        server.auth_type == "custom_header"
        and server.auth_header_name
        and server.auth_credential_ref
    ):
        headers[server.auth_header_name] = server.auth_credential_ref
    return headers
