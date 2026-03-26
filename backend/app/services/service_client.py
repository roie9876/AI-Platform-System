"""Async HTTP client for inter-service communication via K8s DNS."""

import httpx
from typing import Any, Dict, Optional

from app.core.config import settings


class ServiceClient:
    """HTTP client for inter-service communication within AKS cluster."""

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=120.0)

    async def execute_tool(
        self,
        tool_name: str,
        input_data: dict,
        input_schema: dict,
        execution_command: Optional[str],
        timeout_seconds: int,
        auth_token: str,
    ) -> dict:
        """Call tool-executor to run a tool."""
        resp = await self._client.post(
            f"{settings.TOOL_EXECUTOR_URL}/api/v1/internal/tools/execute",
            json={
                "tool_name": tool_name,
                "input_data": input_data,
                "input_schema": input_schema,
                "execution_command": execution_command,
                "timeout_seconds": timeout_seconds,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp.raise_for_status()
        return resp.json()

    async def call_mcp_tool(
        self,
        server_url: str,
        tool_name: str,
        arguments: dict,
        auth_headers: Optional[dict],
        auth_token: str,
    ) -> dict:
        """Call mcp-proxy to invoke an MCP tool."""
        resp = await self._client.post(
            f"{settings.MCP_PROXY_URL}/api/v1/internal/mcp/call-tool",
            json={
                "server_url": server_url,
                "tool_name": tool_name,
                "arguments": arguments,
                "auth_headers": auth_headers,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp.raise_for_status()
        return resp.json()

    async def execute_agent(
        self,
        agent_id: str,
        message: str,
        tenant_id: str,
        user_id: str,
        thread_id: Optional[str],
        auth_token: str,
    ) -> dict:
        """Call agent-executor to run an agent (used by workflow-engine)."""
        resp = await self._client.post(
            f"{settings.AGENT_EXECUTOR_URL}/api/v1/internal/agents/{agent_id}/execute",
            json={
                "message": message,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "thread_id": thread_id,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self._client.aclose()
