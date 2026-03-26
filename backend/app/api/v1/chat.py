from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.models.agent import Agent
from app.models.thread import Thread
from app.models.thread_message import ThreadMessage
from app.api.v1.schemas import ChatRequest
from app.services.agent_execution import AgentExecutionService

router = APIRouter()


@router.post("/{agent_id}/chat")
async def chat_with_agent(
    agent_id: UUID,
    body: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
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

    # If thread_id provided, load history from DB instead of client-sent history
    conversation_history = None
    if body.thread_id:
        # Validate thread ownership
        thread_result = await db.execute(
            select(Thread).where(
                Thread.id == body.thread_id,
                Thread.user_id == current_user["user_id"],
                Thread.tenant_id == tenant_id,
            )
        )
        thread = thread_result.scalar_one_or_none()
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        # Load messages from thread as conversation history
        msg_result = await db.execute(
            select(ThreadMessage)
            .where(ThreadMessage.thread_id == body.thread_id)
            .order_by(ThreadMessage.sequence_number)
        )
        messages = msg_result.scalars().all()
        conversation_history = [
            {"role": m.role, "content": m.content} for m in messages
        ]
    elif body.conversation_history:
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
            thread_id=body.thread_id,
            user_id=current_user["user_id"],
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
