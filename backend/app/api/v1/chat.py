from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from typing import Optional

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.agent_repo import AgentRepository
from app.repositories.thread_repo import ThreadRepository, ThreadMessageRepository
from app.api.v1.schemas import ChatRequest
from app.services.agent_execution import AgentExecutionService
from app.services.document_parser import DocumentParser

router = APIRouter()

agent_repo = AgentRepository()
thread_repo = ThreadRepository()
message_repo = ThreadMessageRepository()
document_parser = DocumentParser()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {"pdf", "txt", "md", "docx"}


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


@router.post("/{agent_id}/chat/upload")
async def chat_with_file(
    agent_id: str,
    request: Request,
    message: str = Form(...),
    thread_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Chat with an agent and attach a file for inline context."""
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not agent.get("model_endpoint_id"):
        raise HTTPException(
            status_code=400,
            detail="Agent has no model endpoint assigned.",
        )

    # Validate file extension
    filename = file.filename or "unknown.txt"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read and validate file size
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB.",
        )

    # Parse file content to text
    try:
        file_text = document_parser.parse_bytes(file_content, filename)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to parse file content.")

    # Truncate to ~30k chars to stay within model context limits
    max_chars = 30_000
    if len(file_text) > max_chars:
        file_text = file_text[:max_chars] + "\n\n[... file truncated ...]"

    # Build conversation history
    conversation_history = None
    if thread_id:
        thread = await thread_repo.get(tenant_id, thread_id)
        if not thread or thread.get("user_id") != current_user["user_id"]:
            raise HTTPException(status_code=404, detail="Thread not found")
        messages = await message_repo.list_by_thread(tenant_id, thread_id)
        conversation_history = [
            {"role": m["role"], "content": m["content"]} for m in messages
        ]

    # Inject file content as a system message before the user's question
    file_context_msg = {
        "role": "system",
        "content": (
            f"The user has attached a file named '{filename}'. "
            f"Here is the full text content of the file:\n\n{file_text}"
        ),
    }

    if conversation_history is None:
        conversation_history = []
    conversation_history.append(file_context_msg)

    execution_service = AgentExecutionService()

    async def event_generator():
        async for event in execution_service.execute(
            agent=agent,
            user_message=message,
            conversation_history=conversation_history,
            thread_id=thread_id,
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
