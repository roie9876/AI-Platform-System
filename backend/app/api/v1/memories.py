from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.dependencies import get_current_user
from app.api.v1.schemas import AgentMemoryListResponse, AgentMemoryResponse
from app.middleware.tenant import get_tenant_id
from app.repositories.agent_repo import AgentRepository
from app.repositories.thread_repo import AgentMemoryRepository

router = APIRouter()

agent_repo = AgentRepository()
memory_repo = AgentMemoryRepository()


@router.get(
    "/{agent_id}/memories",
    response_model=AgentMemoryListResponse,
)
async def list_agent_memories(
    agent_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List all memories for an agent scoped to the current user and tenant."""
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    all_memories = await memory_repo.query(
        tenant_id,
        "SELECT * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid AND c.user_id = @uid ORDER BY c.created_at DESC OFFSET 0 LIMIT 50",
        [
            {"name": "@tid", "value": tenant_id},
            {"name": "@aid", "value": agent_id},
            {"name": "@uid", "value": current_user["user_id"]},
        ],
    )

    total = await memory_repo.count(
        tenant_id,
        "c.agent_id = @aid AND c.user_id = @uid",
        [
            {"name": "@aid", "value": agent_id},
            {"name": "@uid", "value": current_user["user_id"]},
        ],
    )

    return AgentMemoryListResponse(
        memories=[
            AgentMemoryResponse(
                id=m["id"],
                agent_id=m["agent_id"],
                content=m["content"],
                memory_type=m.get("memory_type"),
                source_thread_id=m.get("source_thread_id"),
                created_at=m["created_at"],
            )
            for m in all_memories
        ],
        total=total,
    )


@router.delete(
    "/{agent_id}/memories/{memory_id}",
    status_code=204,
)
async def delete_agent_memory(
    agent_id: str,
    memory_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Delete a specific memory entry."""
    memory = await memory_repo.get(tenant_id, memory_id)
    if not memory or memory.get("agent_id") != agent_id or memory.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Memory not found")
    await memory_repo.delete(tenant_id, memory_id)


@router.delete(
    "/{agent_id}/memories",
    status_code=204,
)
async def clear_agent_memories(
    agent_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Clear all memories for an agent scoped to the current user."""
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    memories = await memory_repo.query(
        tenant_id,
        "SELECT c.id FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid AND c.user_id = @uid",
        [
            {"name": "@tid", "value": tenant_id},
            {"name": "@aid", "value": agent_id},
            {"name": "@uid", "value": current_user["user_id"]},
        ],
    )
    for m in memories:
        await memory_repo.delete(tenant_id, m["id"])
