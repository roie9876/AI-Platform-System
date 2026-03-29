"""Azure Service Bus queue service for agent execution requests/responses.

Provides enqueue (send) and dequeue (receive + process) operations for
the KEDA scale-to-zero agent execution pattern.

Message flow:
  api-gateway  ──enqueue──→  Service Bus (agent-requests queue)
                                    │
                              KEDA watches queue depth
                              depth > 0 → scale agent-executor to 1+
                              depth = 0 for 5min → scale to 0
                                    │
                              agent-executor dequeues + executes
                                    │
                              writes response to agent-responses queue
                                    │
  api-gateway  ←──poll/ws──  reads response from agent-responses queue
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Optional

from azure.identity.aio import DefaultAzureCredential
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage

logger = logging.getLogger(__name__)

# Service Bus config — via env vars set from ConfigMap/SecretProviderClass
SERVICE_BUS_FQNS = os.getenv("SERVICE_BUS_NAMESPACE", "")  # e.g., stumsft-aiplat-prod-sb.servicebus.windows.net
SERVICE_BUS_CONN_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING", "")

REQUEST_QUEUE = "agent-requests"
RESPONSE_QUEUE = "agent-responses"


def _get_client() -> ServiceBusClient:
    """Create Service Bus client — prefer managed identity, fall back to connection string."""
    if SERVICE_BUS_CONN_STRING:
        return ServiceBusClient.from_connection_string(SERVICE_BUS_CONN_STRING)
    elif SERVICE_BUS_FQNS:
        credential = DefaultAzureCredential()
        return ServiceBusClient(fully_qualified_namespace=SERVICE_BUS_FQNS, credential=credential)
    else:
        raise RuntimeError("SERVICE_BUS_NAMESPACE or SERVICE_BUS_CONNECTION_STRING must be set")


async def enqueue_agent_request(
    agent_id: str,
    tenant_id: str,
    user_message: str,
    thread_id: Optional[str] = None,
    user_id: Optional[str] = None,
    conversation_history: Optional[list] = None,
    auth_token: Optional[str] = None,
) -> str:
    """Enqueue an agent execution request. Returns a correlation_id for polling the response."""
    correlation_id = str(uuid.uuid4())

    payload = {
        "correlation_id": correlation_id,
        "agent_id": agent_id,
        "tenant_id": tenant_id,
        "user_message": user_message,
        "thread_id": thread_id,
        "user_id": user_id,
        "conversation_history": conversation_history,
        "auth_token": auth_token,
    }

    message = ServiceBusMessage(
        body=json.dumps(payload),
        content_type="application/json",
        correlation_id=correlation_id,
        subject=agent_id,  # Used for subscription filtering if needed
        application_properties={
            "tenant_id": tenant_id,
            "agent_id": agent_id,
        },
    )

    async with _get_client() as client:
        sender = client.get_queue_sender(queue_name=REQUEST_QUEUE)
        async with sender:
            await sender.send_messages(message)
            logger.info(
                "Enqueued agent request: correlation_id=%s agent_id=%s tenant=%s",
                correlation_id, agent_id, tenant_id,
            )

    return correlation_id


async def enqueue_agent_response(
    correlation_id: str,
    tenant_id: str,
    response_content: str,
    sources: Optional[list] = None,
    error: Optional[str] = None,
) -> None:
    """Write agent execution result to the response queue."""
    payload = {
        "correlation_id": correlation_id,
        "tenant_id": tenant_id,
        "content": response_content,
        "sources": sources or [],
        "error": error,
        "done": True,
    }

    message = ServiceBusMessage(
        body=json.dumps(payload),
        content_type="application/json",
        correlation_id=correlation_id,
        application_properties={
            "tenant_id": tenant_id,
            "correlation_id": correlation_id,
        },
    )

    async with _get_client() as client:
        sender = client.get_queue_sender(queue_name=RESPONSE_QUEUE)
        async with sender:
            await sender.send_messages(message)
            logger.info("Enqueued agent response: correlation_id=%s", correlation_id)


async def poll_agent_response(
    correlation_id: str,
    timeout_seconds: float = 120,
    poll_interval: float = 0.5,
) -> dict:
    """Poll the response queue for a specific correlation_id. Returns the response payload."""
    deadline = asyncio.get_event_loop().time() + timeout_seconds

    async with _get_client() as client:
        receiver = client.get_queue_receiver(queue_name=RESPONSE_QUEUE)
        async with receiver:
            while asyncio.get_event_loop().time() < deadline:
                messages = await receiver.receive_messages(
                    max_message_count=10,
                    max_wait_time=5,
                )
                for msg in messages:
                    body = json.loads(str(msg))
                    if body.get("correlation_id") == correlation_id:
                        await receiver.complete_message(msg)
                        return body
                    # Not our message — abandon it so other consumers can get it
                    await receiver.abandon_message(msg)

                await asyncio.sleep(poll_interval)

    raise TimeoutError(f"No response for correlation_id={correlation_id} within {timeout_seconds}s")
