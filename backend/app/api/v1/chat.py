from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.agent_repo import AgentRepository
from app.repositories.thread_repo import ThreadRepository, ThreadMessageRepository
from app.api.v1.schemas import ChatRequest
from app.services.agent_execution import AgentExecutionService

router = APIRouter()

agent_repo = AgentRepository()
thread_repo = ThreadRepository()
message_repo = ThreadMessageRepository()


@router.post("/{agent_id}/chat")
async def chat_with_agent(
    agent_id: str,
    body: ChatRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not agent.get("model_endpoint_id"):
        raise HTTPException(
            status_code=400,
            detail="Agent has no model endpoint assigned. Assign a model endpoint before chatting.",
        )

    conversation_history = None
    if body.thread_id:
        thread = await thread_repo.get(tenant_id, str(body.thread_id))
        if not thread or thread.get("user_id") != current_user["user_id"]:
            raise HTTPException(status_code=404, detail="Thread not found")

        messages = await message_repo.list_by_thread(tenant_id, str(body.thread_id))
        conversation_history = [
            {"role": m["role"], "content": m["content"]} for m in messages
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
            conversation_history=conversation_history,
            thread_id=str(body.thread_id) if body.thread_id else None,
            user_id=current_user["user_id"],
            tenant_id=tenant_id,
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
