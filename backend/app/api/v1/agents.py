from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.agent import Agent
from app.models.agent_config_version import AgentConfigVersion
from app.api.v1.schemas import (
    AgentCreateRequest,
    AgentUpdateRequest,
    AgentResponse,
    AgentListResponse,
    AgentConfigVersionResponse,
)

router = APIRouter()


def _build_config_snapshot(agent: Agent) -> dict:
    return {
        "system_prompt": agent.system_prompt,
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "timeout_seconds": agent.timeout_seconds,
        "model_endpoint_id": str(agent.model_endpoint_id) if agent.model_endpoint_id else None,
    }


@router.post("/", response_model=AgentResponse, status_code=201)
async def create_agent(
    body: AgentCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = Agent(
        name=body.name,
        description=body.description,
        system_prompt=body.system_prompt,
        model_endpoint_id=body.model_endpoint_id,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        timeout_seconds=body.timeout_seconds,
        tenant_id=tenant_id,
        current_config_version=1,
    )
    db.add(agent)
    await db.flush()

    config_version = AgentConfigVersion(
        agent_id=agent.id,
        version_number=1,
        config_snapshot=_build_config_snapshot(agent),
        change_description="Initial configuration",
        tenant_id=tenant_id,
    )
    db.add(config_version)
    await db.flush()
    await db.refresh(agent)
    return agent


@router.get("/", response_model=AgentListResponse)
async def list_agents(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Agent).where(Agent.tenant_id == tenant_id).order_by(Agent.created_at.desc())
    )
    agents = list(result.scalars().all())
    return AgentListResponse(agents=agents, total=len(agents))


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    body: AgentUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    for field, value in update_data.items():
        setattr(agent, field, value)

    agent.current_config_version += 1
    await db.flush()

    config_version = AgentConfigVersion(
        agent_id=agent.id,
        version_number=agent.current_config_version,
        config_snapshot=_build_config_snapshot(agent),
        change_description=f"Updated: {', '.join(update_data.keys())}",
        tenant_id=tenant_id,
    )
    db.add(config_version)
    await db.flush()
    await db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.flush()


@router.get("/{agent_id}/versions", response_model=list[AgentConfigVersionResponse])
async def list_agent_versions(
    agent_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await db.execute(
        select(AgentConfigVersion)
        .where(AgentConfigVersion.agent_id == agent_id, AgentConfigVersion.tenant_id == tenant_id)
        .order_by(AgentConfigVersion.version_number.desc())
    )
    return list(result.scalars().all())


@router.post("/{agent_id}/rollback/{version_number}", response_model=AgentResponse)
async def rollback_agent(
    agent_id: UUID,
    version_number: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await db.execute(
        select(AgentConfigVersion).where(
            AgentConfigVersion.agent_id == agent_id,
            AgentConfigVersion.version_number == version_number,
            AgentConfigVersion.tenant_id == tenant_id,
        )
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    snapshot = version.config_snapshot
    agent.system_prompt = snapshot.get("system_prompt")
    agent.temperature = snapshot.get("temperature", 0.7)
    agent.max_tokens = snapshot.get("max_tokens", 1024)
    agent.timeout_seconds = snapshot.get("timeout_seconds", 30)
    endpoint_id = snapshot.get("model_endpoint_id")
    agent.model_endpoint_id = UUID(endpoint_id) if endpoint_id else None

    agent.current_config_version += 1
    await db.flush()

    rollback_version = AgentConfigVersion(
        agent_id=agent.id,
        version_number=agent.current_config_version,
        config_snapshot=_build_config_snapshot(agent),
        change_description=f"Rollback to version {version_number}",
        tenant_id=tenant_id,
    )
    db.add(rollback_version)
    await db.flush()
    await db.refresh(agent)
    return agent
