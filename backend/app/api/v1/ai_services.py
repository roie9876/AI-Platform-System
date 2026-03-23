from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.api.v1.schemas import PlatformToolListResponse, PlatformToolToggleRequest
from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.models.agent import Agent
from app.models.tool import AgentTool, Tool
from app.models.user import User
from app.services.platform_tools import (
    PLATFORM_ADAPTERS,
    get_adapter_by_name,
    register_platform_tools,
)

router = APIRouter()


@router.get("/", response_model=PlatformToolListResponse)
async def list_platform_tools(
    request: Request,
    agent_id: UUID = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List all available platform AI services/tools.
    If agent_id is provided, includes enabled/disabled status for that agent."""
    await register_platform_tools(db)

    result = await db.execute(
        select(Tool).where(Tool.is_platform_tool == True)
    )
    platform_tools = list(result.scalars().all())

    enabled_tool_ids = set()
    if agent_id:
        at_result = await db.execute(
            select(AgentTool.tool_id).where(AgentTool.agent_id == agent_id)
        )
        enabled_tool_ids = {row[0] for row in at_result.fetchall()}

    tools_response = []
    for tool in platform_tools:
        adapter = get_adapter_by_name(tool.name)
        tools_response.append({
            "id": tool.id,
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "service_name": adapter.service_name() if adapter else tool.name,
            "is_enabled": tool.id in enabled_tool_ids,
        })

    return {"tools": tools_response, "total": len(tools_response)}


@router.post("/toggle")
async def toggle_platform_tool(
    body: PlatformToolToggleRequest,
    request: Request,
    agent_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Enable or disable a platform tool for an agent."""
    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    tool_result = await db.execute(
        select(Tool).where(Tool.id == body.tool_id, Tool.is_platform_tool == True)
    )
    tool = tool_result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Platform tool not found")

    if body.enabled:
        existing = await db.execute(
            select(AgentTool).where(
                AgentTool.agent_id == agent_id, AgentTool.tool_id == body.tool_id
            )
        )
        if not existing.scalar_one_or_none():
            db.add(AgentTool(agent_id=agent_id, tool_id=body.tool_id))
            await db.commit()
        return {"status": "enabled", "tool_id": str(body.tool_id), "agent_id": str(agent_id)}
    else:
        existing = await db.execute(
            select(AgentTool).where(
                AgentTool.agent_id == agent_id, AgentTool.tool_id == body.tool_id
            )
        )
        record = existing.scalar_one_or_none()
        if record:
            await db.delete(record)
            await db.commit()
        return {"status": "disabled", "tool_id": str(body.tool_id), "agent_id": str(agent_id)}
