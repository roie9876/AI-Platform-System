from fastapi import APIRouter, Depends, HTTPException, Request

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.agent_repo import AgentRepository
from app.repositories.tool_repo import ToolRepository, AgentToolRepository
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

tool_repo = ToolRepository()
agent_tool_repo = AgentToolRepository()
agent_repo = AgentRepository()


@router.post("", response_model=ToolResponse, status_code=201)
async def create_tool(
    body: ToolCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tool_data = {
        "name": body.name,
        "description": body.description,
        "input_schema": body.input_schema,
        "output_schema": body.output_schema,
        "docker_image": body.docker_image,
        "execution_command": body.execution_command,
        "timeout_seconds": body.timeout_seconds,
        "is_platform_tool": False,
    }
    tool = await tool_repo.create(tenant_id, tool_data)
    return tool


@router.get("", response_model=ToolListResponse)
async def list_tools(
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tools = await tool_repo.list_by_tenant(tenant_id)
    return ToolListResponse(tools=tools, total=len(tools))


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tool = await tool_repo.get(tenant_id, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: str,
    body: ToolUpdateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tool = await tool_repo.get(tenant_id, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if tool.get("is_platform_tool"):
        raise HTTPException(status_code=403, detail="Cannot modify platform tools")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    for field, value in update_data.items():
        tool[field] = value

    etag = tool.get("_etag")
    tool = await tool_repo.update(tenant_id, tool_id, tool, etag=etag)
    return tool


@router.delete("/{tool_id}", status_code=204)
async def delete_tool(
    tool_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    tool = await tool_repo.get(tenant_id, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if tool.get("is_platform_tool"):
        raise HTTPException(status_code=403, detail="Cannot delete platform tools")
    await tool_repo.delete(tenant_id, tool_id)


# --- Agent-Tool attachment endpoints ---


@agent_tools_router.post("/{agent_id}/tools", response_model=AgentToolResponse, status_code=201)
async def attach_tool(
    agent_id: str,
    body: AgentToolAttachRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    tool = await tool_repo.get(tenant_id, str(body.tool_id))
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    existing = await agent_tool_repo.get_by_agent_and_tool(tenant_id, agent_id, str(body.tool_id))
    if existing:
        raise HTTPException(status_code=409, detail="Tool already attached to agent")

    agent_tool_data = {"agent_id": agent_id, "tool_id": str(body.tool_id)}
    agent_tool = await agent_tool_repo.create(tenant_id, agent_tool_data)
    return agent_tool


@agent_tools_router.delete("/{agent_id}/tools/{tool_id}", status_code=204)
async def detach_tool(
    agent_id: str,
    tool_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    existing = await agent_tool_repo.get_by_agent_and_tool(tenant_id, agent_id, tool_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Tool not attached to agent")
    await agent_tool_repo.delete(tenant_id, existing["id"])


@agent_tools_router.get("/{agent_id}/tools", response_model=list[AgentToolResponse])
async def list_agent_tools(
    agent_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return await agent_tool_repo.list_by_agent(tenant_id, agent_id)
