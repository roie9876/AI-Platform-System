from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.v1.dependencies import get_current_user
from app.api.v1.schemas import PlatformToolListResponse, PlatformToolToggleRequest
from app.middleware.tenant import get_tenant_id
from app.repositories.agent_repo import AgentRepository
from app.repositories.tool_repo import ToolRepository, AgentToolRepository
from app.services.platform_tools import (
    PLATFORM_ADAPTERS,
    get_adapter_by_name,
    register_platform_tools,
)

router = APIRouter()
agent_repo = AgentRepository()
tool_repo = ToolRepository()
agent_tool_repo = AgentToolRepository()


@router.get("/", response_model=PlatformToolListResponse)
async def list_platform_tools(
    request: Request,
    agent_id: str = Query(default=None),
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List all available platform AI services/tools.
    If agent_id is provided, includes enabled/disabled status for that agent."""
    await register_platform_tools(tenant_id)

    platform_tools = await tool_repo.query(
        tenant_id,
        "SELECT * FROM c WHERE c.is_platform_tool = true",
        [],
    )

    enabled_tool_ids = set()
    if agent_id:
        agent_tools = await agent_tool_repo.list_by_agent(tenant_id, agent_id)
        enabled_tool_ids = {at["tool_id"] for at in agent_tools}

    tools_response = []
    for tool in platform_tools:
        adapter = get_adapter_by_name(tool["name"])
        tools_response.append({
            "id": tool["id"],
            "name": tool["name"],
            "description": tool.get("description"),
            "input_schema": tool.get("input_schema"),
            "service_name": adapter.service_name() if adapter else tool["name"],
            "is_enabled": tool["id"] in enabled_tool_ids,
        })

    return {"tools": tools_response, "total": len(tools_response)}


@router.post("/toggle")
async def toggle_platform_tool(
    body: PlatformToolToggleRequest,
    request: Request,
    agent_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Enable or disable a platform tool for an agent."""
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    tool = await tool_repo.get(tenant_id, body.tool_id)
    if not tool or not tool.get("is_platform_tool"):
        raise HTTPException(status_code=404, detail="Platform tool not found")

    if body.enabled:
        existing = await agent_tool_repo.get_by_agent_and_tool(tenant_id, agent_id, body.tool_id)
        if not existing:
            from uuid import uuid4
            await agent_tool_repo.create(tenant_id, {
                "id": str(uuid4()),
                "agent_id": agent_id,
                "tool_id": body.tool_id,
                "tenant_id": tenant_id,
            })
        return {"status": "enabled", "tool_id": body.tool_id, "agent_id": agent_id}
    else:
        existing = await agent_tool_repo.get_by_agent_and_tool(tenant_id, agent_id, body.tool_id)
        if existing:
            await agent_tool_repo.delete(tenant_id, existing["id"])
        return {"status": "disabled", "tool_id": body.tool_id, "agent_id": agent_id}
