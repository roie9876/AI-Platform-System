"""Queue consumer for agent-executor — dequeues from Service Bus, executes agents, writes results.

This runs as a background asyncio task during the agent-executor lifespan.
When KEDA scales the pod from 0→1 because a message arrived in the queue,
this consumer picks it up and processes it.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

from azure.identity.aio import DefaultAzureCredential, WorkloadIdentityCredential
from azure.servicebus.aio import ServiceBusClient

logger = logging.getLogger(__name__)

SERVICE_BUS_FQNS = os.getenv("SERVICE_BUS_NAMESPACE", "")
SERVICE_BUS_CONN_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING", "")
REQUEST_QUEUE = "agent-requests"

# Sentinel for graceful shutdown
_shutdown_event: asyncio.Event | None = None


def _get_credential():
    """Use WorkloadIdentityCredential with the managed-identity client ID.

    AZURE_CLIENT_ID is the Entra SPA app (no federated credentials).
    AZURE_WORKLOAD_CLIENT_ID is the managed identity that *has* federation.
    """
    workload_client_id = os.getenv("AZURE_WORKLOAD_CLIENT_ID")
    token_file = os.getenv("AZURE_FEDERATED_TOKEN_FILE")
    if workload_client_id and token_file:
        return WorkloadIdentityCredential(
            client_id=workload_client_id,
            tenant_id=os.getenv("AZURE_TENANT_ID", ""),
            token_file_path=token_file,
        )
    return DefaultAzureCredential()


def _get_client() -> ServiceBusClient:
    if SERVICE_BUS_CONN_STRING:
        return ServiceBusClient.from_connection_string(SERVICE_BUS_CONN_STRING)
    elif SERVICE_BUS_FQNS:
        credential = _get_credential()
        return ServiceBusClient(fully_qualified_namespace=SERVICE_BUS_FQNS, credential=credential)
    else:
        raise RuntimeError("SERVICE_BUS_NAMESPACE or SERVICE_BUS_CONNECTION_STRING must be set")


async def _process_message(payload: dict) -> None:
    """Execute agent for a queued request and save result to Cosmos DB."""
    from app.repositories.agent_repo import AgentRepository
    from app.repositories.execution_repo import ExecutionResultRepository
    from app.services.agent_execution import AgentExecutionService

    correlation_id = payload["correlation_id"]
    agent_id = payload["agent_id"]
    tenant_id = payload["tenant_id"]

    logger.info("Processing queued agent request: correlation_id=%s agent_id=%s", correlation_id, agent_id)

    result_repo = ExecutionResultRepository()
    agent_repo = AgentRepository()

    # Save initial "processing" status
    await result_repo.create(tenant_id, {
        "id": correlation_id,
        "correlation_id": correlation_id,
        "agent_id": agent_id,
        "status": "processing",
        "content": None,
        "sources": [],
        "error": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
    })

    try:
        agent = await agent_repo.get(tenant_id, agent_id)
        if not agent:
            await result_repo.update(tenant_id, correlation_id, {
                "status": "failed",
                "error": f"Agent {agent_id} not found",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
            return

        # Execute agent — collect SSE output into a single response
        service = AgentExecutionService()
        collected_content = []
        sources = []

        async for sse_line in service.execute(
            agent=agent,
            user_message=payload["user_message"],
            tenant_id=tenant_id,
            conversation_history=payload.get("conversation_history"),
            thread_id=payload.get("thread_id"),
            user_id=payload.get("user_id"),
            auth_token=payload.get("auth_token"),
        ):
            if sse_line.startswith("data: "):
                try:
                    data = json.loads(sse_line[6:].strip())
                    if "content" in data and data["content"]:
                        collected_content.append(data["content"])
                    if "sources" in data:
                        sources = data["sources"]
                except json.JSONDecodeError:
                    pass

        full_content = "".join(collected_content)

        # Save completed result
        await result_repo.update(tenant_id, correlation_id, {
            "status": "completed",
            "content": full_content,
            "sources": sources,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })

        logger.info("Completed queued agent request: correlation_id=%s (%d chars)", correlation_id, len(full_content))

    except Exception as e:
        logger.exception("Failed queued agent request: correlation_id=%s", correlation_id)
        try:
            await result_repo.update(tenant_id, correlation_id, {
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            logger.exception("Failed to write error result for correlation_id=%s", correlation_id)


async def start_queue_consumer() -> None:
    """Main consumer loop — runs until shutdown_event is set."""
    global _shutdown_event
    _shutdown_event = asyncio.Event()

    if not (SERVICE_BUS_FQNS or SERVICE_BUS_CONN_STRING):
        logger.info("Service Bus not configured — queue consumer disabled (HTTP-only mode)")
        return

    logger.info("Starting queue consumer for queue=%s", REQUEST_QUEUE)

    while not _shutdown_event.is_set():
        try:
            async with _get_client() as client:
                receiver = client.get_queue_receiver(queue_name=REQUEST_QUEUE)
                async with receiver:
                    while not _shutdown_event.is_set():
                        messages = await receiver.receive_messages(
                            max_message_count=1,
                            max_wait_time=10,
                        )
                        for msg in messages:
                            try:
                                payload = json.loads(str(msg))
                                await _process_message(payload)
                                await receiver.complete_message(msg)
                            except Exception:
                                logger.exception("Error processing queue message, will retry")
                                await receiver.abandon_message(msg)

        except asyncio.CancelledError:
            logger.info("Queue consumer cancelled — shutting down")
            return
        except Exception:
            logger.exception("Queue consumer connection error — reconnecting in 5s")
            await asyncio.sleep(5)


async def stop_queue_consumer() -> None:
    """Signal the consumer to stop."""
    global _shutdown_event
    if _shutdown_event:
        _shutdown_event.set()
