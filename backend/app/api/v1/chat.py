from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.agent import Agent
from app.api.v1.schemas import ChatRequest
from app.services.agent_execution import AgentExecutionService

router = APIRouter()


@router.post("/{agent_id}/chat")
async def chat_with_agent(
    agent_id: UUID,
    body: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    # Validate agent exists and belongs to tenant
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not agent.model_endpoint_id:
        raise HTTPException(
            status_code=400,
            detail="Agent has no model endpoint assigned. Assign a model endpoint before chatting.",
        )

    # Build conversation history from ChatMessage objects
    conversation_history = None
    if body.conversation_history:
        conversation_history = [
            {"role": m.role, "content": m.content}
            for m in body.conversation_history
        ]

    execution_service = AgentExecutionService()

    async def event_generator():
        async for event in execution_service.execute(
            agent=agent,
            user_message=body.message,
            db=db,
            conversation_history=conversation_history,
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
