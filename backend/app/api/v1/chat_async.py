"""Async chat endpoint — enqueues agent execution to Service Bus for KEDA scale-to-zero.

Flow:
  1. POST /agents/{agent_id}/chat/async → enqueue to Service Bus → return 202 + correlation_id
  2. GET /agents/executions/{correlation_id} → poll Cosmos DB for result
  3. Agent-executor dequeues, executes, writes result to Cosmos DB execution_results container

This runs alongside the existing SSE-based chat endpoint.  Use async mode when
agent-executor pods may be scaled to zero (KEDA), or for long-running executions.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.agent_repo import AgentRepository
from app.repositories.thread_repo import ThreadRepository, ThreadMessageRepository
from app.api.v1.schemas import ChatRequest

import logging

logger = logging.getLogger(__name__)

router = APIRouter()

agent_repo = AgentRepository()
thread_repo = ThreadRepository()
message_repo = ThreadMessageRepository()


@router.post("/{agent_id}/chat/async")
async def chat_with_agent_async(
    agent_id: str,
    body: ChatRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Enqueue agent chat request for async processing. Returns correlation_id to poll for result."""
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not agent.get("model_endpoint_id"):
        raise HTTPException(
            status_code=400,
            detail="Agent has no model endpoint assigned.",
        )

    # Build conversation history (same logic as sync chat)
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

    # Enqueue to Service Bus
    from app.services.queue_service import enqueue_agent_request

    auth_header = request.headers.get("Authorization", "")
    auth_token = auth_header[7:] if auth_header.startswith("Bearer ") else None

    correlation_id = await enqueue_agent_request(
        agent_id=agent_id,
        tenant_id=tenant_id,
        user_message=body.message,
        thread_id=str(body.thread_id) if body.thread_id else None,
        user_id=current_user["user_id"],
        conversation_history=conversation_history,
        auth_token=auth_token,
    )

    return JSONResponse(
        status_code=202,
        content={
            "correlation_id": correlation_id,
            "status": "queued",
            "poll_url": f"/api/v1/agents/executions/{correlation_id}",
        },
    )


@router.get("/executions/{correlation_id}")
async def get_execution_result(
    correlation_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Poll for async agent execution result."""
    from app.repositories.execution_repo import ExecutionResultRepository

    repo = ExecutionResultRepository()
    result = await repo.get(tenant_id, correlation_id)

    if not result:
        return JSONResponse(
            status_code=200,
            content={
                "correlation_id": correlation_id,
                "status": "processing",
                "content": None,
            },
        )

    if result.get("error"):
        return JSONResponse(
            status_code=200,
            content={
                "correlation_id": correlation_id,
                "status": "failed",
                "error": result["error"],
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "correlation_id": correlation_id,
            "status": "completed",
            "content": result.get("content", ""),
            "sources": result.get("sources", []),
        },
    )
