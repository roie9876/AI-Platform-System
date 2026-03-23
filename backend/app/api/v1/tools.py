from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.agent import Agent
from app.models.tool import Tool, AgentTool
from app.api.v1.schemas import (
    ToolCreateRequest,
    ToolUpdateRequest,
    ToolResponse,
    ToolListResponse,
    AgentToolAttachRequest,
    AgentToolResponse,
)

router = APIRouter()
agent_tools_router = APIRouter()


@router.post("/", response_model=ToolResponse, status_code=201)
async def create_tool(
    body: ToolCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tool = Tool(
        name=body.name,
        description=body.description,
        input_schema=body.input_schema,
        output_schema=body.output_schema,
        docker_image=body.docker_image,
        execution_command=body.execution_command,
        timeout_seconds=body.timeout_seconds,
        is_platform_tool=False,
        tenant_id=tenant_id,
    )
    db.add(tool)
    await db.flush()
    await db.refresh(tool)
    return tool


@router.get("/", response_model=ToolListResponse)
async def list_tools(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Tool)
        .where(or_(Tool.tenant_id == tenant_id, Tool.is_platform_tool == True))
        .order_by(Tool.created_at.desc())
    )
    tools = list(result.scalars().all())
    return ToolListResponse(tools=tools, total=len(tools))


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Tool).where(
            Tool.id == tool_id,
            or_(Tool.tenant_id == tenant_id, Tool.is_platform_tool == True),
        )
    )
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: UUID,
    body: ToolUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Tool).where(Tool.id == tool_id, Tool.tenant_id == tenant_id)
    )
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if tool.is_platform_tool:
        raise HTTPException(status_code=403, detail="Cannot modify platform tools")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    for field, value in update_data.items():
        setattr(tool, field, value)

    await db.flush()
    await db.refresh(tool)
    return tool


@router.delete("/{tool_id}", status_code=204)
async def delete_tool(
    tool_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Tool).where(Tool.id == tool_id, Tool.tenant_id == tenant_id)
    )
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if tool.is_platform_tool:
        raise HTTPException(status_code=403, detail="Cannot delete platform tools")
    await db.delete(tool)
    await db.flush()


# --- Agent-Tool attachment endpoints ---


@agent_tools_router.post("/{agent_id}/tools", response_model=AgentToolResponse, status_code=201)
async def attach_tool(
    agent_id: UUID,
    body: AgentToolAttachRequest,
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

    # Verify tool exists and is accessible
    result = await db.execute(
        select(Tool).where(
            Tool.id == body.tool_id,
            or_(Tool.tenant_id == tenant_id, Tool.is_platform_tool == True),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Tool not found")

    # Check for existing attachment
    result = await db.execute(
        select(AgentTool).where(
            AgentTool.agent_id == agent_id, AgentTool.tool_id == body.tool_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Tool already attached to agent")

    agent_tool = AgentTool(agent_id=agent_id, tool_id=body.tool_id)
    db.add(agent_tool)
    await db.flush()
    await db.refresh(agent_tool)
    return agent_tool


@agent_tools_router.delete("/{agent_id}/tools/{tool_id}", status_code=204)
async def detach_tool(
    agent_id: UUID,
    tool_id: UUID,
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
        select(AgentTool).where(
            AgentTool.agent_id == agent_id, AgentTool.tool_id == tool_id
        )
    )
    agent_tool = result.scalar_one_or_none()
    if not agent_tool:
        raise HTTPException(status_code=404, detail="Tool not attached to agent")
    await db.delete(agent_tool)
    await db.flush()


@agent_tools_router.get("/{agent_id}/tools", response_model=list[AgentToolResponse])
async def list_agent_tools(
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

    result = await db.execute(
        select(AgentTool).where(AgentTool.agent_id == agent_id)
    )
    return list(result.scalars().all())
