from fastapi import APIRouter, Depends, HTTPException, Request

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.agent_repo import AgentRepository
from app.repositories.mcp_repo import MCPServerRepository, MCPDiscoveredToolRepository, AgentMCPToolRepository
from app.api.v1.schemas import (
    AgentMCPToolAttachRequest,
    AgentMCPToolResponse,
)

router = APIRouter()

agent_repo = AgentRepository()
mcp_tool_repo = MCPDiscoveredToolRepository()
agent_mcp_tool_repo = AgentMCPToolRepository()
server_repo = MCPServerRepository()


@router.post(
    "/{agent_id}/mcp-tools", response_model=AgentMCPToolResponse, status_code=201
)
async def attach_mcp_tool(
    agent_id: str,
    body: AgentMCPToolAttachRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    mcp_tool = await mcp_tool_repo.get(tenant_id, str(body.mcp_tool_id))
    if not mcp_tool:
        raise HTTPException(status_code=404, detail="MCP tool not found")

    # Check for existing attachment
    existing = await agent_mcp_tool_repo.query(
        tenant_id,
        "SELECT * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid AND c.mcp_tool_id = @mtid",
        [
            {"name": "@tid", "value": tenant_id},
            {"name": "@aid", "value": agent_id},
            {"name": "@mtid", "value": str(body.mcp_tool_id)},
        ],
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="MCP tool already attached to agent"
        )

    attachment_data = {
        "agent_id": agent_id,
        "mcp_tool_id": str(body.mcp_tool_id),
    }
    agent_mcp_tool = await agent_mcp_tool_repo.create(tenant_id, attachment_data)

    server = await server_repo.get(tenant_id, mcp_tool.get("server_id", ""))

    return AgentMCPToolResponse(
        id=agent_mcp_tool["id"],
        agent_id=agent_mcp_tool["agent_id"],
        mcp_tool_id=agent_mcp_tool["mcp_tool_id"],
        tool_name=mcp_tool.get("tool_name", ""),
        description=mcp_tool.get("description"),
        server_id=mcp_tool.get("server_id"),
        server_name=server["name"] if server else "Unknown",
        is_available=mcp_tool.get("is_available", True),
        created_at=agent_mcp_tool["created_at"],
    )


@router.delete("/{agent_id}/mcp-tools/{mcp_tool_id}", status_code=204)
async def detach_mcp_tool(
    agent_id: str,
    mcp_tool_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    existing = await agent_mcp_tool_repo.query(
        tenant_id,
        "SELECT * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid AND c.mcp_tool_id = @mtid",
        [
            {"name": "@tid", "value": tenant_id},
            {"name": "@aid", "value": agent_id},
            {"name": "@mtid", "value": mcp_tool_id},
        ],
    )
    if not existing:
        raise HTTPException(
            status_code=404, detail="MCP tool not attached to agent"
        )
    await agent_mcp_tool_repo.delete(tenant_id, existing[0]["id"])


@router.get(
    "/{agent_id}/mcp-tools", response_model=list[AgentMCPToolResponse]
)
async def list_agent_mcp_tools(
    agent_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    attachments = await agent_mcp_tool_repo.list_by_agent(tenant_id, agent_id)

    results = []
    for amt in attachments:
        tool = await mcp_tool_repo.get(tenant_id, amt.get("mcp_tool_id", ""))
        server = await server_repo.get(tenant_id, tool.get("server_id", "")) if tool else None
        results.append(
            AgentMCPToolResponse(
                id=amt["id"],
                agent_id=amt["agent_id"],
                mcp_tool_id=amt["mcp_tool_id"],
                tool_name=tool.get("tool_name", "") if tool else "",
                description=tool.get("description") if tool else None,
                server_id=tool.get("server_id") if tool else None,
                server_name=server["name"] if server else "Unknown",
                is_available=tool.get("is_available", True) if tool else False,
                created_at=amt["created_at"],
            )
        )

    return results
