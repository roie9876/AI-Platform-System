"""
MCP Tool Discovery Service.

Discovers tools from registered MCP servers, syncs the local catalog,
and performs health checks with reconnection logic.
"""

import logging
from typing import Dict, List, Optional
from uuid import uuid4

from app.repositories.mcp_repo import MCPServerRepository, MCPDiscoveredToolRepository
from app.services.mcp_client import MCPClient, MCPClientError

logger = logging.getLogger(__name__)

_server_repo = MCPServerRepository()
_tool_repo = MCPDiscoveredToolRepository()


class MCPDiscoveryService:
    """Discovers and syncs tools from registered MCP servers."""

    @staticmethod
    async def discover_tools_from_server(
        server: dict,
        tenant_id: str,
    ) -> list[dict]:
        """Connect to an MCP server, discover tools via tools/list, and sync local catalog."""
        headers = _build_auth_headers(server)
        client = MCPClient(server["url"], timeout=15.0, headers=headers)

        try:
            init_result = await client.connect()
            server["status"] = "connected"
            server["status_message"] = (
                f"Connected to {init_result.serverInfo.name} "
                f"v{init_result.serverInfo.version}"
            )
            await _server_repo.update(tenant_id, server["id"], server)

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
            old_tools = await _tool_repo.query(
                tenant_id,
                "SELECT * FROM c WHERE c.server_id = @sid",
                [{"name": "@sid", "value": server["id"]}],
            )
            for old in old_tools:
                await _tool_repo.delete(tenant_id, old["id"])

            discovered = []
            for tool_info in all_tools:
                tool = {
                    "id": str(uuid4()),
                    "server_id": server["id"],
                    "tool_name": tool_info.name,
                    "description": tool_info.description,
                    "input_schema": tool_info.inputSchema.model_dump(exclude_none=True) if tool_info.inputSchema else {"type": "object", "properties": {}},
                    "is_available": True,
                    "tenant_id": tenant_id,
                }
                created = await _tool_repo.create(tenant_id, tool)
                discovered.append(created)

            logger.info(
                "Discovered %d tools from MCP server %s (%s)",
                len(discovered),
                server.get("name"),
                server.get("url"),
            )
            return discovered

        except MCPClientError as e:
            server["status"] = "error"
            server["status_message"] = str(e)
            await _server_repo.update(tenant_id, server["id"], server)

            # Mark existing tools as unavailable
            existing_tools = await _tool_repo.query(
                tenant_id,
                "SELECT * FROM c WHERE c.server_id = @sid",
                [{"name": "@sid", "value": server["id"]}],
            )
            for tool in existing_tools:
                tool["is_available"] = False
                await _tool_repo.update(tenant_id, tool["id"], tool)

            logger.warning(
                "Failed to discover tools from %s: %s", server.get("name"), e
            )
            return []

        finally:
            await client.disconnect()

    @staticmethod
    async def discover_all_servers(
        tenant_id: str,
    ) -> Dict[str, int]:
        """Discover tools from all active MCP servers for a tenant."""
        servers = await _server_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND (c.is_active = true OR NOT IS_DEFINED(c.is_active))",
            [{"name": "@tid", "value": tenant_id}],
        )
        logger.info("discover_all_servers: found %d active servers for tenant %s", len(servers), tenant_id)

        summary = {}
        for server in servers:
            tools = await MCPDiscoveryService.discover_tools_from_server(
                server, tenant_id
            )
            summary[server.get("name", "")] = len(tools)

        return summary

    @staticmethod
    async def health_check_server(
        server: dict,
        tenant_id: str,
    ) -> bool:
        """Check if an MCP server is reachable and update its status."""
        headers = _build_auth_headers(server)
        client = MCPClient(server["url"], timeout=10.0, headers=headers)

        try:
            init_result = await client.connect()
            server["status"] = "connected"
            server["status_message"] = (
                f"Healthy — {init_result.serverInfo.name} "
                f"v{init_result.serverInfo.version}"
            )
            await _server_repo.update(tenant_id, server["id"], server)
            return True
        except MCPClientError as e:
            server["status"] = "error"
            server["status_message"] = str(e)
            await _server_repo.update(tenant_id, server["id"], server)
            return False
        finally:
            await client.disconnect()

    @staticmethod
    async def get_all_discovered_tools(
        tenant_id: str,
        server_id: Optional[str] = None,
    ) -> list[dict]:
        """Get all discovered tools, optionally filtered by server."""
        if server_id:
            return await _tool_repo.query(
                tenant_id,
                "SELECT * FROM c WHERE c.tenant_id = @tid AND c.server_id = @sid ORDER BY c.tool_name",
                [{"name": "@tid", "value": tenant_id}, {"name": "@sid", "value": server_id}],
            )
        return await _tool_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid ORDER BY c.tool_name",
            [{"name": "@tid", "value": tenant_id}],
        )


def _build_auth_headers(server: dict) -> Dict[str, str]:
    """Build authentication headers from MCP server configuration."""
    headers: Dict[str, str] = {}
    auth_type = server.get("auth_type")
    auth_cred = server.get("auth_credential_ref")
    if auth_type == "bearer" and auth_cred:
        headers["Authorization"] = f"Bearer {auth_cred}"
    elif auth_type == "api_key" and auth_cred:
        header_name = server.get("auth_header_name") or "X-API-Key"
        headers[header_name] = auth_cred
    elif (
        auth_type == "custom_header"
        and server.get("auth_header_name")
        and auth_cred
    ):
        headers[server["auth_header_name"]] = auth_cred
    return headers
