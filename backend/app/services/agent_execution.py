import json
import logging
from typing import Optional, List, Dict, AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.model_endpoint import ModelEndpoint
from app.services.model_abstraction import ModelAbstractionService, ModelError

logger = logging.getLogger(__name__)


class AgentExecutionService:
    """Executes agent conversations against model endpoints with SSE formatting."""

    def __init__(self) -> None:
        self._model_service = ModelAbstractionService()

    async def execute(
        self,
        agent: Agent,
        user_message: str,
        db: AsyncSession,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[str, None]:
        # Load primary endpoint
        if not agent.model_endpoint_id:
            yield self._sse_error("Agent has no model endpoint assigned")
            return

        result = await db.execute(
            select(ModelEndpoint).where(
                ModelEndpoint.id == agent.model_endpoint_id,
                ModelEndpoint.is_active == True,
            )
        )
        primary_endpoint = result.scalar_one_or_none()

        if not primary_endpoint:
            yield self._sse_error("Assigned model endpoint not found or inactive")
            return

        # Load fallback endpoints (same tenant, active, different from primary, sorted by priority)
        result = await db.execute(
            select(ModelEndpoint).where(
                ModelEndpoint.tenant_id == agent.tenant_id,
                ModelEndpoint.is_active == True,
                ModelEndpoint.id != agent.model_endpoint_id,
            )
        )
        fallback_endpoints = list(result.scalars().all())

        endpoints = [primary_endpoint] + fallback_endpoints

        # Build messages
        messages: List[Dict[str, str]] = []
        if agent.system_prompt:
            messages.append({"role": "system", "content": agent.system_prompt})
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        # Update agent status to active
        agent.status = "active"
        await db.commit()

        try:
            async for token in self._model_service.complete_with_fallback(
                messages=messages,
                endpoints=endpoints,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
                timeout=agent.timeout_seconds,
                stream=True,
            ):
                yield self._sse_data(token, done=False)

            yield self._sse_data("", done=True)

        except ModelError as exc:
            agent.status = "error"
            await db.commit()
            logger.error("Agent execution failed: %s", str(exc))
            yield self._sse_error(str(exc))

    @staticmethod
    def _sse_data(content: str, done: bool) -> str:
        return f"data: {json.dumps({'content': content, 'done': done})}\n\n"

    @staticmethod
    def _sse_error(message: str) -> str:
        return f"data: {json.dumps({'error': message, 'done': True})}\n\n"
