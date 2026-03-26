from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.api.v1.schemas import AgentMemoryListResponse, AgentMemoryResponse
from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.models.agent import Agent
from app.models.agent_memory import AgentMemory

router = APIRouter()


@router.get(
    "/{agent_id}/memories",
    response_model=AgentMemoryListResponse,
)
async def list_agent_memories(
    agent_id: UUID,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """List all memories for an agent scoped to the current user and tenant."""
    # Validate agent exists and belongs to tenant
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Agent not found")

    count_result = await db.execute(
        select(func.count()).where(
            AgentMemory.agent_id == agent_id,
            AgentMemory.user_id == current_user["user_id"],
            AgentMemory.tenant_id == tenant_id,
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(AgentMemory)
        .where(
            AgentMemory.agent_id == agent_id,
            AgentMemory.user_id == current_user["user_id"],
            AgentMemory.tenant_id == tenant_id,
        )
        .order_by(AgentMemory.created_at.desc())
        .limit(50)
    )
    memories = result.scalars().all()

    return AgentMemoryListResponse(
        memories=[
            AgentMemoryResponse(
                id=m.id,
                agent_id=m.agent_id,
                content=m.content,
                memory_type=m.memory_type,
                source_thread_id=m.source_thread_id,
                created_at=m.created_at,
            )
            for m in memories
        ],
        total=total,
    )


@router.delete(
    "/{agent_id}/memories/{memory_id}",
    status_code=204,
)
async def delete_agent_memory(
    agent_id: UUID,
    memory_id: UUID,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific memory entry."""
    result = await db.execute(
        select(AgentMemory).where(
            AgentMemory.id == memory_id,
            AgentMemory.agent_id == agent_id,
            AgentMemory.user_id == current_user["user_id"],
            AgentMemory.tenant_id == tenant_id,
        )
    )
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    await db.execute(
        delete(AgentMemory).where(AgentMemory.id == memory_id)
    )
    await db.commit()


@router.delete(
    "/{agent_id}/memories",
    status_code=204,
)
async def clear_agent_memories(
    agent_id: UUID,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Clear all memories for an agent scoped to the current user."""
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Agent not found")

    await db.execute(
        delete(AgentMemory).where(
            AgentMemory.agent_id == agent_id,
            AgentMemory.user_id == current_user["user_id"],
            AgentMemory.tenant_id == tenant_id,
        )
    )
    await db.commit()
