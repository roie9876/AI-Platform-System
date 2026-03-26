from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.dependencies import get_current_user
from app.api.v1.schemas import (
    ThreadCreateRequest,
    ThreadListResponse,
    ThreadMessageResponse,
    ThreadMessagesResponse,
    ThreadResponse,
    ThreadUpdateRequest,
)
from app.middleware.tenant import get_tenant_id
from app.repositories.agent_repo import AgentRepository
from app.repositories.thread_repo import ThreadRepository, ThreadMessageRepository

router = APIRouter()

agent_repo = AgentRepository()
thread_repo = ThreadRepository()
message_repo = ThreadMessageRepository()


@router.post("", response_model=ThreadResponse, status_code=201)
async def create_thread(
    body: ThreadCreateRequest,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, str(body.agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    thread_data = {
        "title": body.title,
        "agent_id": str(body.agent_id),
        "user_id": current_user["user_id"],
        "is_active": True,
    }
    thread = await thread_repo.create(tenant_id, thread_data)

    return ThreadResponse(
        id=thread["id"],
        title=thread["title"],
        agent_id=thread["agent_id"],
        user_id=thread["user_id"],
        tenant_id=thread["tenant_id"],
        is_active=thread["is_active"],
        created_at=thread["created_at"],
        updated_at=thread["updated_at"],
        message_count=0,
        last_message_preview=None,
    )


@router.get("", response_model=ThreadListResponse)
async def list_threads(
    agent_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    all_threads = await thread_repo.list_by_agent(tenant_id, agent_id)
    threads = [
        t for t in all_threads
        if t.get("user_id") == current_user["user_id"] and t.get("is_active", True)
    ]

    thread_responses = []
    for thread in threads:
        message_count = await message_repo.count_by_thread(tenant_id, thread["id"])

        messages = await message_repo.list_by_thread(tenant_id, thread["id"])
        assistant_msgs = [m for m in reversed(messages) if m.get("role") == "assistant"]
        preview = assistant_msgs[0]["content"][:100] if assistant_msgs else None

        thread_responses.append(
            ThreadResponse(
                id=thread["id"],
                title=thread["title"],
                agent_id=thread["agent_id"],
                user_id=thread["user_id"],
                tenant_id=thread["tenant_id"],
                is_active=thread.get("is_active", True),
                created_at=thread["created_at"],
                updated_at=thread["updated_at"],
                message_count=message_count,
                last_message_preview=preview,
            )
        )

    return ThreadListResponse(threads=thread_responses, total=len(thread_responses))


@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    thread = await thread_repo.get(tenant_id, thread_id)
    if not thread or thread.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Thread not found")

    message_count = await message_repo.count_by_thread(tenant_id, thread["id"])

    return ThreadResponse(
        id=thread["id"],
        title=thread["title"],
        agent_id=thread["agent_id"],
        user_id=thread["user_id"],
        tenant_id=thread["tenant_id"],
        is_active=thread.get("is_active", True),
        created_at=thread["created_at"],
        updated_at=thread["updated_at"],
        message_count=message_count,
        last_message_preview=None,
    )


@router.get("/{thread_id}/messages", response_model=ThreadMessagesResponse)
async def get_thread_messages(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    thread = await thread_repo.get(tenant_id, thread_id)
    if not thread or thread.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Thread not found")

    messages = await message_repo.list_by_thread(tenant_id, thread_id)

    return ThreadMessagesResponse(
        messages=[
            ThreadMessageResponse(
                id=msg["id"],
                thread_id=msg["thread_id"],
                role=msg["role"],
                content=msg["content"],
                message_metadata=msg.get("message_metadata"),
                sequence_number=msg.get("sequence_number", 0),
                created_at=msg["created_at"],
            )
            for msg in messages
        ],
        total=len(messages),
    )


@router.patch("/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: str,
    body: ThreadUpdateRequest,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    thread = await thread_repo.get(tenant_id, thread_id)
    if not thread or thread.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Thread not found")

    thread["title"] = body.title
    etag = thread.get("_etag")
    thread = await thread_repo.update(tenant_id, thread_id, thread, etag=etag)

    return ThreadResponse(
        id=thread["id"],
        title=thread["title"],
        agent_id=thread["agent_id"],
        user_id=thread["user_id"],
        tenant_id=thread["tenant_id"],
        is_active=thread.get("is_active", True),
        created_at=thread["created_at"],
        updated_at=thread["updated_at"],
        message_count=0,
        last_message_preview=None,
    )


@router.delete("/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    thread = await thread_repo.get(tenant_id, thread_id)
    if not thread or thread.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Thread not found")

    await thread_repo.delete(tenant_id, thread_id)


@router.delete("", status_code=204)
async def delete_all_threads(
    agent_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    all_threads = await thread_repo.list_by_agent(tenant_id, agent_id)
    for thread in all_threads:
        if thread.get("user_id") == current_user["user_id"]:
            await thread_repo.delete(tenant_id, thread["id"])
