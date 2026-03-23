from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.agent import Agent
from app.models.data_source import DataSource, AgentDataSource
from app.services.secret_store import encrypt_api_key
from app.api.v1.schemas import (
    DataSourceCreateRequest,
    DataSourceUpdateRequest,
    DataSourceResponse,
    DataSourceListResponse,
    AgentDataSourceAttachRequest,
    AgentDataSourceResponse,
)

router = APIRouter()
agent_data_sources_router = APIRouter()


@router.post("/", response_model=DataSourceResponse, status_code=201)
async def create_data_source(
    body: DataSourceCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    if body.source_type not in ("file", "url"):
        raise HTTPException(status_code=400, detail="source_type must be 'file' or 'url'")

    credentials_encrypted = None
    if body.credentials:
        credentials_encrypted = encrypt_api_key(body.credentials)

    data_source = DataSource(
        name=body.name,
        description=body.description,
        source_type=body.source_type,
        config=body.config,
        credentials_encrypted=credentials_encrypted,
        tenant_id=tenant_id,
    )
    db.add(data_source)
    await db.flush()
    await db.refresh(data_source)
    return data_source


@router.get("/", response_model=DataSourceListResponse)
async def list_data_sources(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(DataSource)
        .where(DataSource.tenant_id == tenant_id)
        .order_by(DataSource.created_at.desc())
    )
    data_sources = list(result.scalars().all())
    return DataSourceListResponse(data_sources=data_sources, total=len(data_sources))


@router.get("/{data_source_id}", response_model=DataSourceResponse)
async def get_data_source(
    data_source_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(DataSource).where(
            DataSource.id == data_source_id, DataSource.tenant_id == tenant_id
        )
    )
    data_source = result.scalar_one_or_none()
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")
    return data_source


@router.put("/{data_source_id}", response_model=DataSourceResponse)
async def update_data_source(
    data_source_id: UUID,
    body: DataSourceUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(DataSource).where(
            DataSource.id == data_source_id, DataSource.tenant_id == tenant_id
        )
    )
    data_source = result.scalar_one_or_none()
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    for field, value in update_data.items():
        setattr(data_source, field, value)

    await db.flush()
    await db.refresh(data_source)
    return data_source


@router.delete("/{data_source_id}", status_code=204)
async def delete_data_source(
    data_source_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(DataSource).where(
            DataSource.id == data_source_id, DataSource.tenant_id == tenant_id
        )
    )
    data_source = result.scalar_one_or_none()
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")
    await db.delete(data_source)
    await db.flush()


# --- Agent-DataSource attachment endpoints ---


@agent_data_sources_router.post(
    "/{agent_id}/data-sources", response_model=AgentDataSourceResponse, status_code=201
)
async def attach_data_source(
    agent_id: UUID,
    body: AgentDataSourceAttachRequest,
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

    # Verify data source belongs to tenant
    result = await db.execute(
        select(DataSource).where(
            DataSource.id == body.data_source_id, DataSource.tenant_id == tenant_id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Data source not found")

    # Check for existing attachment
    result = await db.execute(
        select(AgentDataSource).where(
            AgentDataSource.agent_id == agent_id,
            AgentDataSource.data_source_id == body.data_source_id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Data source already attached to agent")

    agent_ds = AgentDataSource(agent_id=agent_id, data_source_id=body.data_source_id)
    db.add(agent_ds)
    await db.flush()
    await db.refresh(agent_ds)
    return agent_ds


@agent_data_sources_router.delete("/{agent_id}/data-sources/{data_source_id}", status_code=204)
async def detach_data_source(
    agent_id: UUID,
    data_source_id: UUID,
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
        select(AgentDataSource).where(
            AgentDataSource.agent_id == agent_id,
            AgentDataSource.data_source_id == data_source_id,
        )
    )
    agent_ds = result.scalar_one_or_none()
    if not agent_ds:
        raise HTTPException(status_code=404, detail="Data source not attached to agent")
    await db.delete(agent_ds)
    await db.flush()


@agent_data_sources_router.get(
    "/{agent_id}/data-sources", response_model=list[AgentDataSourceResponse]
)
async def list_agent_data_sources(
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
        select(AgentDataSource).where(AgentDataSource.agent_id == agent_id)
    )
    return list(result.scalars().all())
