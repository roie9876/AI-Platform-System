import json
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.model_endpoint import ModelEndpoint
from app.models.tool import Tool, AgentTool
from app.services.model_abstraction import ModelAbstractionService, ModelError
from app.services.tool_executor import ToolExecutor, ToolExecutionError
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)


class AgentExecutionService:
    """Executes agent conversations against model endpoints with SSE formatting."""

    MAX_TOOL_ITERATIONS = 10

    def __init__(self) -> None:
        self._model_service = ModelAbstractionService()
        self._tool_executor = ToolExecutor()
        self._rag_service = RAGService()

    async def _inject_rag_context(
        self,
        messages: List[Dict[str, Any]],
        agent: Agent,
        user_message: str,
        db: AsyncSession,
    ) -> None:
        """Retrieve relevant document chunks and inject as system context."""
        chunks = await self._rag_service.retrieve(
            query=user_message,
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
            db=db,
            top_k=5,
        )
        if not chunks:
            return

        context_text = "\n\n---\n\n".join(c["content"] for c in chunks)
        rag_system_msg = (
            "The following context from attached documents may be relevant "
            "to the user's question. Use it if helpful:\n\n"
            f"{context_text}"
        )

        # Insert RAG context after system prompt, before conversation
        insert_idx = 1 if messages and messages[0]["role"] == "system" else 0
        messages.insert(insert_idx, {"role": "system", "content": rag_system_msg})

    async def _load_agent_tools(self, agent_id, db: AsyncSession) -> List[Tool]:
        """Load all tools attached to this agent."""
        result = await db.execute(
            select(Tool)
            .join(AgentTool, AgentTool.tool_id == Tool.id)
            .where(AgentTool.agent_id == agent_id)
        )
        return list(result.scalars().all())

    def _build_tool_schemas(self, tools: List[Tool]) -> List[Dict[str, Any]]:
        """Convert Tool models to OpenAI-format tool schemas for LiteLLM."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema,
                },
            }
            for tool in tools
        ]

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
        messages: List[Dict[str, Any]] = []
        if agent.system_prompt:
            messages.append({"role": "system", "content": agent.system_prompt})
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        # Inject RAG context from attached data sources
        await self._inject_rag_context(messages, agent, user_message, db)

        # Update agent status to active
        agent.status = "active"
        await db.commit()

        # Load tools attached to this agent
        tools_list = await self._load_agent_tools(agent.id, db)
        tool_schemas = self._build_tool_schemas(tools_list) if tools_list else None
        tool_map = {t.name: t for t in tools_list}

        try:
            if tool_schemas:
                # Tool-calling loop
                iteration = 0
                while iteration < self.MAX_TOOL_ITERATIONS:
                    iteration += 1
                    response = await self._model_service.complete_with_tools(
                        messages=messages,
                        endpoints=endpoints,
                        tools=tool_schemas,
                        temperature=agent.temperature,
                        max_tokens=agent.max_tokens,
                        timeout=agent.timeout_seconds,
                    )

                    if response["tool_calls"]:
                        # Append assistant message with tool_calls
                        messages.append({
                            "role": "assistant",
                            "content": response["content"],
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments,
                                    },
                                }
                                for tc in response["tool_calls"]
                            ],
                        })

                        for tc in response["tool_calls"]:
                            tool = tool_map.get(tc.function.name)
                            if not tool:
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": json.dumps({"error": f"Unknown tool: {tc.function.name}"}),
                                })
                                continue
                            try:
                                args = json.loads(tc.function.arguments)
                                result = await self._tool_executor.execute(
                                    tool_name=tool.name,
                                    input_data=args,
                                    input_schema=tool.input_schema,
                                    execution_command=tool.execution_command,
                                    timeout_seconds=tool.timeout_seconds,
                                )
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": json.dumps(result),
                                })
                            except ToolExecutionError as e:
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": json.dumps({"error": str(e)}),
                                })
                    else:
                        # No tool calls — model returned final content
                        if response["content"]:
                            yield self._sse_data(response["content"], done=False)
                        yield self._sse_data("", done=True)
                        return

                # Max iterations reached
                yield self._sse_error("Tool calling loop exceeded maximum iterations")
                return

            # No tools — use existing streaming path
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
