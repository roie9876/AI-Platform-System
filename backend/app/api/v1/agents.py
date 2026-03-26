from fastapi import APIRouter, Depends, HTTPException, Request

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.agent_repo import AgentRepository, AgentConfigVersionRepository
from app.api.v1.schemas import (
    AgentCreateRequest,
    AgentUpdateRequest,
    AgentResponse,
    AgentListResponse,
    AgentConfigVersionResponse,
)

router = APIRouter()

agent_repo = AgentRepository()
config_version_repo = AgentConfigVersionRepository()


def _build_config_snapshot(agent: dict) -> dict:
    return {
        "system_prompt": agent.get("system_prompt"),
        "temperature": agent.get("temperature"),
        "max_tokens": agent.get("max_tokens"),
        "timeout_seconds": agent.get("timeout_seconds"),
        "model_endpoint_id": agent.get("model_endpoint_id"),
    }


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    body: AgentCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent_data = {
        "name": body.name,
        "description": body.description,
        "system_prompt": body.system_prompt,
        "model_endpoint_id": str(body.model_endpoint_id) if body.model_endpoint_id else None,
        "temperature": body.temperature,
        "max_tokens": body.max_tokens,
        "timeout_seconds": body.timeout_seconds,
        "current_config_version": 1,
        "status": "active" if body.model_endpoint_id else "inactive",
    }
    agent = await agent_repo.create(tenant_id, agent_data)

    config_data = {
        "agent_id": agent["id"],
        "version_number": 1,
        "config_snapshot": _build_config_snapshot(agent),
        "change_description": "Initial configuration",
    }
    await config_version_repo.create(tenant_id, config_data)
    return agent


@router.get("", response_model=AgentListResponse)
async def list_agents(
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agents = await agent_repo.list_by_tenant(tenant_id)
    return AgentListResponse(agents=agents, total=len(agents))


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    body: AgentUpdateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    for field, value in update_data.items():
        if field == "model_endpoint_id" and value is not None:
            agent[field] = str(value)
        else:
            agent[field] = value

    if "model_endpoint_id" in update_data:
        agent["status"] = "active" if update_data["model_endpoint_id"] else "inactive"

    agent["current_config_version"] = agent.get("current_config_version", 1) + 1
    etag = agent.get("_etag")
    agent = await agent_repo.update(tenant_id, agent_id, agent, etag=etag)

    config_data = {
        "agent_id": agent["id"],
        "version_number": agent["current_config_version"],
        "config_snapshot": _build_config_snapshot(agent),
        "change_description": f"Updated: {', '.join(update_data.keys())}",
    }
    await config_version_repo.create(tenant_id, config_data)
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    versions = await config_version_repo.list_by_agent(tenant_id, agent_id)
    for v in versions:
        await config_version_repo.delete(tenant_id, v["id"])

    await agent_repo.delete(tenant_id, agent_id)


@router.get("/{agent_id}/versions", response_model=list[AgentConfigVersionResponse])
async def list_agent_versions(
    agent_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return await config_version_repo.list_by_agent(tenant_id, agent_id)


@router.post("/{agent_id}/rollback/{version_number}", response_model=AgentResponse)
async def rollback_agent(
    agent_id: str,
    version_number: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    versions = await config_version_repo.list_by_agent(tenant_id, agent_id)
    version = next((v for v in versions if v.get("version_number") == version_number), None)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    snapshot = version["config_snapshot"]
    agent["system_prompt"] = snapshot.get("system_prompt")
    agent["temperature"] = snapshot.get("temperature", 0.7)
    agent["max_tokens"] = snapshot.get("max_tokens", 1024)
    agent["timeout_seconds"] = snapshot.get("timeout_seconds", 30)
    agent["model_endpoint_id"] = snapshot.get("model_endpoint_id")
    agent["current_config_version"] = agent.get("current_config_version", 1) + 1

    etag = agent.get("_etag")
    agent = await agent_repo.update(tenant_id, agent_id, agent, etag=etag)

    rollback_config = {
        "agent_id": agent["id"],
        "version_number": agent["current_config_version"],
        "config_snapshot": _build_config_snapshot(agent),
        "change_description": f"Rollback to version {version_number}",
    }
    await config_version_repo.create(tenant_id, rollback_config)
    return agent
