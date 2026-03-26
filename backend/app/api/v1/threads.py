from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.api.v1.schemas import (
    ThreadCreateRequest,
    ThreadListResponse,
    ThreadMessageResponse,
    ThreadMessagesResponse,
    ThreadResponse,
    ThreadUpdateRequest,
)
from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.models.agent import Agent
from app.models.thread import Thread
from app.models.thread_message import ThreadMessage

router = APIRouter()


@router.post("", response_model=ThreadResponse, status_code=201)
async def create_thread(
    body: ThreadCreateRequest,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    # Validate agent exists and belongs to tenant
    result = await db.execute(
        select(Agent).where(
            Agent.id == body.agent_id,
            Agent.tenant_id == tenant_id,
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    thread = Thread(
        title=body.title,
        agent_id=body.agent_id,
        user_id=current_user["user_id"],
        tenant_id=tenant_id,
    )
    db.add(thread)
    await db.commit()
    await db.refresh(thread)

    return ThreadResponse(
        id=thread.id,
        title=thread.title,
        agent_id=thread.agent_id,
        user_id=thread.user_id,
        tenant_id=thread.tenant_id,
        is_active=thread.is_active,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        message_count=0,
        last_message_preview=None,
    )


@router.get("", response_model=ThreadListResponse)
async def list_threads(
    agent_id: UUID,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    # Base query: user's threads for this agent in this tenant
    base_filter = [
        Thread.agent_id == agent_id,
        Thread.user_id == current_user["user_id"],
        Thread.tenant_id == tenant_id,
        Thread.is_active == True,  # noqa: E712
    ]

    # Count
    count_result = await db.execute(
        select(func.count(Thread.id)).where(*base_filter)
    )
    total = count_result.scalar() or 0

    # Fetch threads ordered by most recent
    result = await db.execute(
        select(Thread).where(*base_filter).order_by(desc(Thread.updated_at))
    )
    threads = result.scalars().all()

    # Enrich with message_count and last_message_preview
    thread_responses = []
    for thread in threads:
        # Message count
        msg_count_result = await db.execute(
            select(func.count(ThreadMessage.id)).where(
                ThreadMessage.thread_id == thread.id
            )
        )
        message_count = msg_count_result.scalar() or 0

        # Last message preview (last assistant message)
        last_msg_result = await db.execute(
            select(ThreadMessage.content)
            .where(
                ThreadMessage.thread_id == thread.id,
                ThreadMessage.role == "assistant",
            )
            .order_by(desc(ThreadMessage.sequence_number))
            .limit(1)
        )
        last_msg = last_msg_result.scalar_one_or_none()
        preview = last_msg[:100] if last_msg else None

        thread_responses.append(
            ThreadResponse(
                id=thread.id,
                title=thread.title,
                agent_id=thread.agent_id,
                user_id=thread.user_id,
                tenant_id=thread.tenant_id,
                is_active=thread.is_active,
                created_at=thread.created_at,
                updated_at=thread.updated_at,
                message_count=message_count,
                last_message_preview=preview,
            )
        )

    return ThreadListResponse(threads=thread_responses, total=total)


@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: UUID,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thread).where(
            Thread.id == thread_id,
            Thread.user_id == current_user["user_id"],
            Thread.tenant_id == tenant_id,
        )
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Message count
    msg_count_result = await db.execute(
        select(func.count(ThreadMessage.id)).where(
            ThreadMessage.thread_id == thread.id
        )
    )
    message_count = msg_count_result.scalar() or 0

    return ThreadResponse(
        id=thread.id,
        title=thread.title,
        agent_id=thread.agent_id,
        user_id=thread.user_id,
        tenant_id=thread.tenant_id,
        is_active=thread.is_active,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        message_count=message_count,
        last_message_preview=None,
    )


@router.get("/{thread_id}/messages", response_model=ThreadMessagesResponse)
async def get_thread_messages(
    thread_id: UUID,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    # Validate thread ownership
    thread_result = await db.execute(
        select(Thread).where(
            Thread.id == thread_id,
            Thread.user_id == current_user["user_id"],
            Thread.tenant_id == tenant_id,
        )
    )
    thread = thread_result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Fetch messages
    result = await db.execute(
        select(ThreadMessage)
        .where(ThreadMessage.thread_id == thread_id)
        .order_by(ThreadMessage.sequence_number)
    )
    messages = result.scalars().all()

    return ThreadMessagesResponse(
        messages=[
            ThreadMessageResponse(
                id=msg.id,
                thread_id=msg.thread_id,
                role=msg.role,
                content=msg.content,
                message_metadata=msg.message_metadata,
                sequence_number=msg.sequence_number,
                created_at=msg.created_at,
            )
            for msg in messages
        ],
        total=len(messages),
    )


@router.patch("/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: UUID,
    body: ThreadUpdateRequest,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thread).where(
            Thread.id == thread_id,
            Thread.user_id == current_user["user_id"],
            Thread.tenant_id == tenant_id,
        )
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    thread.title = body.title
    await db.commit()
    await db.refresh(thread)

    return ThreadResponse(
        id=thread.id,
        title=thread.title,
        agent_id=thread.agent_id,
        user_id=thread.user_id,
        tenant_id=thread.tenant_id,
        is_active=thread.is_active,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        message_count=0,
        last_message_preview=None,
    )


@router.delete("/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: UUID,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thread).where(
            Thread.id == thread_id,
            Thread.user_id == current_user["user_id"],
            Thread.tenant_id == tenant_id,
        )
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    await db.delete(thread)
    await db.commit()


@router.delete("", status_code=204)
async def delete_all_threads(
    agent_id: UUID,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thread).where(
            Thread.agent_id == agent_id,
            Thread.user_id == current_user["user_id"],
            Thread.tenant_id == tenant_id,
        )
    )
    threads = result.scalars().all()
    for thread in threads:
        await db.delete(thread)
    await db.commit()
