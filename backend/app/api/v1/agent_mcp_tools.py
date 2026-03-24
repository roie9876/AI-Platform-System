from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.agent import Agent
from app.models.agent_mcp_tool import AgentMCPTool
from app.models.mcp_discovered_tool import MCPDiscoveredTool
from app.models.mcp_server import MCPServer
from app.api.v1.schemas import (
    AgentMCPToolAttachRequest,
    AgentMCPToolResponse,
)

router = APIRouter()


@router.post(
    "/{agent_id}/mcp-tools", response_model=AgentMCPToolResponse, status_code=201
)
async def attach_mcp_tool(
    agent_id: UUID,
    body: AgentMCPToolAttachRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    # Verify agent belongs to tenant
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Agent not found")

    # Verify MCP tool exists and belongs to tenant
    result = await db.execute(
        select(MCPDiscoveredTool).where(
            MCPDiscoveredTool.id == body.mcp_tool_id,
            MCPDiscoveredTool.tenant_id == tenant_id,
        )
    )
    mcp_tool = result.scalar_one_or_none()
    if not mcp_tool:
        raise HTTPException(status_code=404, detail="MCP tool not found")

    # Check for existing attachment
    result = await db.execute(
        select(AgentMCPTool).where(
            AgentMCPTool.agent_id == agent_id,
            AgentMCPTool.mcp_tool_id == body.mcp_tool_id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail="MCP tool already attached to agent"
        )

    agent_mcp_tool = AgentMCPTool(
        agent_id=agent_id, mcp_tool_id=body.mcp_tool_id
    )
    db.add(agent_mcp_tool)
    await db.flush()
    await db.refresh(agent_mcp_tool)

    # Fetch server name for response
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == mcp_tool.server_id)
    )
    server = result.scalar_one_or_none()

    return AgentMCPToolResponse(
        id=agent_mcp_tool.id,
        agent_id=agent_mcp_tool.agent_id,
        mcp_tool_id=agent_mcp_tool.mcp_tool_id,
        tool_name=mcp_tool.tool_name,
        description=mcp_tool.description,
        server_id=mcp_tool.server_id,
        server_name=server.name if server else "Unknown",
        is_available=mcp_tool.is_available,
        created_at=agent_mcp_tool.created_at,
    )


@router.delete("/{agent_id}/mcp-tools/{mcp_tool_id}", status_code=204)
async def detach_mcp_tool(
    agent_id: UUID,
    mcp_tool_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    # Verify agent belongs to tenant
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await db.execute(
        select(AgentMCPTool).where(
            AgentMCPTool.agent_id == agent_id,
            AgentMCPTool.mcp_tool_id == mcp_tool_id,
        )
    )
    agent_mcp_tool = result.scalar_one_or_none()
    if not agent_mcp_tool:
        raise HTTPException(
            status_code=404, detail="MCP tool not attached to agent"
        )
    await db.delete(agent_mcp_tool)
    await db.flush()


@router.get(
    "/{agent_id}/mcp-tools", response_model=list[AgentMCPToolResponse]
)
async def list_agent_mcp_tools(
    agent_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    # Verify agent belongs to tenant
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Agent not found")

    # Join AgentMCPTool → MCPDiscoveredTool → MCPServer
    result = await db.execute(
        select(AgentMCPTool, MCPDiscoveredTool, MCPServer)
        .join(
            MCPDiscoveredTool,
            AgentMCPTool.mcp_tool_id == MCPDiscoveredTool.id,
        )
        .join(MCPServer, MCPDiscoveredTool.server_id == MCPServer.id)
        .where(AgentMCPTool.agent_id == agent_id)
        .order_by(MCPDiscoveredTool.tool_name)
    )
    rows = result.all()

    return [
        AgentMCPToolResponse(
            id=amt.id,
            agent_id=amt.agent_id,
            mcp_tool_id=amt.mcp_tool_id,
            tool_name=tool.tool_name,
            description=tool.description,
            server_id=tool.server_id,
            server_name=server.name,
            is_available=tool.is_available,
            created_at=amt.created_at,
        )
        for amt, tool, server in rows
    ]
