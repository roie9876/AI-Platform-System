import json
import logging
import time
from typing import Optional, List, Dict, Any, AsyncGenerator
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.execution_log import ExecutionLog
from app.models.model_endpoint import ModelEndpoint
from app.models.thread import Thread
from app.models.thread_message import ThreadMessage
from app.models.tool import Tool, AgentTool
from app.services.model_abstraction import ModelAbstractionService, ModelError
from app.services.tool_executor import ToolExecutor, ToolExecutionError
from app.services.rag_service import RAGService
from app.services.memory_service import MemoryService
from app.services.platform_tools import get_adapter_by_name as get_platform_adapter

logger = logging.getLogger(__name__)


class AgentExecutionService:
    """Executes agent conversations against model endpoints with SSE formatting."""

    MAX_TOOL_ITERATIONS = 10

    def __init__(self) -> None:
        self._model_service = ModelAbstractionService()
        self._tool_executor = ToolExecutor()
        self._rag_service = RAGService()
        self._memory_service = MemoryService()

    async def _inject_rag_context(
        self,
        messages: List[Dict[str, Any]],
        agent: Agent,
        user_message: str,
        db: AsyncSession,
    ) -> List[Dict[str, str]]:
        """Retrieve relevant document chunks and inject as system context.
        Returns list of source descriptors for the frontend."""
        all_chunks: List[Dict[str, Any]] = []

        # 1. Local document chunks (data sources attached to agent)
        chunks = await self._rag_service.retrieve(
            query=user_message,
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
            db=db,
            top_k=5,
        )
        all_chunks.extend(chunks)

        # 2. Azure AI Search indexes (knowledge connections)
        try:
            azure_chunks = await self._rag_service.retrieve_from_azure_search(
                query=user_message,
                agent_id=agent.id,
                tenant_id=agent.tenant_id,
                db=db,
                top_k=5,
            )
            all_chunks.extend(azure_chunks)
        except Exception:
            logger.warning("Azure Search retrieval failed for agent %s", agent.id)

        if not all_chunks:
            return []

        context_text = "\n\n---\n\n".join(c["content"] for c in all_chunks if c.get("content"))
        if not context_text:
            return []

        rag_system_msg = (
            "The following context from attached documents and knowledge bases "
            "may be relevant to the user's question. Use it if helpful:\n\n"
            f"{context_text}"
        )

        # Insert RAG context after system prompt, before conversation
        insert_idx = 1 if messages and messages[0]["role"] == "system" else 0
        messages.insert(insert_idx, {"role": "system", "content": rag_system_msg})

        # Build source descriptors for the frontend
        sources: List[Dict[str, str]] = []
        seen = set()
        for chunk in all_chunks:
            if chunk.get("source") == "azure_search":
                key = f"azure_search:{chunk.get('index', '')}"
                if key not in seen:
                    seen.add(key)
                    sources.append({"type": "azure_search", "index": chunk.get("index", "")})
            elif chunk.get("document_id"):
                key = f"document:{chunk['document_id']}"
                if key not in seen:
                    seen.add(key)
                    meta = chunk.get("metadata") or {}
                    sources.append({"type": "document", "name": meta.get("filename") or meta.get("url") or "local document"})
        return sources

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
        thread_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
    ) -> AsyncGenerator[str, None]:
        start_time = time.monotonic()

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
        rag_sources = await self._inject_rag_context(messages, agent, user_message, db)

        # Inject long-term memory context if using a thread
        if thread_id:
            try:
                memories = await self._memory_service.retrieve_relevant(
                    query=user_message,
                    agent_id=agent.id,
                    user_id=user_id,
                    tenant_id=agent.tenant_id,
                    db=db,
                    model_endpoint=primary_endpoint,
                    top_k=5,
                )
                if memories:
                    memory_text = "\n\n".join(m.content for m in memories)
                    memory_msg = (
                        "Relevant memories from past interactions:\n\n"
                        f"{memory_text}"
                    )
                    # Insert after RAG context, before conversation
                    insert_idx = 1 if messages and messages[0]["role"] == "system" else 0
                    # Skip past any existing system messages (original + RAG)
                    while insert_idx < len(messages) and messages[insert_idx]["role"] == "system":
                        insert_idx += 1
                    messages.insert(insert_idx, {"role": "system", "content": memory_msg})
            except Exception:
                logger.warning("Memory retrieval failed for thread %s", thread_id, exc_info=True)

        # Save user message to thread if thread_id provided
        if thread_id and user_id:
            try:
                seq_result = await db.execute(
                    select(func.coalesce(func.max(ThreadMessage.sequence_number), 0))
                    .where(ThreadMessage.thread_id == thread_id)
                )
                next_seq = (seq_result.scalar() or 0) + 1
                user_msg = ThreadMessage(
                    thread_id=thread_id,
                    role="user",
                    content=user_message,
                    sequence_number=next_seq,
                )
                db.add(user_msg)
                await db.commit()

                # Log execution event
                log_entry = ExecutionLog(
                    thread_id=thread_id,
                    message_id=user_msg.id,
                    event_type="message_sent",
                    state_snapshot={"messages_count": len(messages)},
                    duration_ms=0,
                )
                db.add(log_entry)
                await db.commit()

                # Store user message as memory for cross-thread recall
                if len(user_message) > 10:
                    try:
                        await self._memory_service.store_memory(
                            agent_id=agent.id,
                            user_id=user_id,
                            tenant_id=agent.tenant_id,
                            content=f"User said: {user_message}",
                            db=db,
                            model_endpoint=None,
                            memory_type="user_input",
                            source_thread_id=thread_id,
                        )
                    except Exception:
                        logger.warning("Failed to store user memory for thread %s", thread_id, exc_info=True)
            except Exception:
                logger.warning("Failed to save user message to thread %s", thread_id, exc_info=True)

        # Update agent status to active
        agent.status = "active"
        await db.commit()

        # Load tools attached to this agent
        tools_list = await self._load_agent_tools(agent.id, db)
        tool_schemas = self._build_tool_schemas(tools_list) if tools_list else None
        tool_map = {t.name: t for t in tools_list}

        try:
            # Emit sources event so the frontend knows what knowledge was used
            if rag_sources:
                yield self._sse_sources(rag_sources)

            collected_response = ""

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
                                if tool.is_platform_tool:
                                    # Execute via platform adapter (direct call)
                                    adapter = get_platform_adapter(tool.name)
                                    if adapter:
                                        result = await adapter.execute(args)
                                    else:
                                        result = {"error": f"No adapter for platform tool: {tool.name}"}
                                else:
                                    # Execute via subprocess sandbox
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
                        collected_response = response["content"] or ""
                        if collected_response:
                            yield self._sse_data(collected_response, done=False)
                        # Extract token usage from response
                        usage = response.get("usage") or {}
                        input_tokens = usage.get("prompt_tokens")
                        output_tokens = usage.get("completion_tokens")
                        await self._save_assistant_response(
                            db, thread_id, user_id, agent, collected_response,
                            rag_sources, start_time, primary_endpoint,
                            input_tokens=input_tokens, output_tokens=output_tokens,
                        )
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
                collected_response += token
                yield self._sse_data(token, done=False)

            await self._save_assistant_response(
                db, thread_id, user_id, agent, collected_response,
                rag_sources, start_time, primary_endpoint,
            )
            yield self._sse_data("", done=True)

        except ModelError as exc:
            agent.status = "error"
            await db.commit()
            logger.error("Agent execution failed: %s", str(exc))
            yield self._sse_error(str(exc))

    async def _save_assistant_response(
        self,
        db: AsyncSession,
        thread_id: Optional[UUID],
        user_id: Optional[UUID],
        agent: Agent,
        content: str,
        rag_sources: List[Dict[str, str]],
        start_time: float,
        primary_endpoint: ModelEndpoint,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
    ) -> None:
        """Save assistant response to thread and log execution."""
        if not thread_id or not user_id:
            return
        try:
            duration_ms = int((time.monotonic() - start_time) * 1000)

            # Get next sequence number
            seq_result = await db.execute(
                select(func.coalesce(func.max(ThreadMessage.sequence_number), 0))
                .where(ThreadMessage.thread_id == thread_id)
            )
            next_seq = (seq_result.scalar() or 0) + 1

            # Save assistant message
            metadata = {}
            if rag_sources:
                metadata["sources"] = rag_sources
            assistant_msg = ThreadMessage(
                thread_id=thread_id,
                role="assistant",
                content=content,
                message_metadata=metadata if metadata else None,
                sequence_number=next_seq,
            )
            db.add(assistant_msg)
            await db.commit()

            # Auto-title: if thread has only 2 messages (1 user + 1 assistant), set title
            msg_count_result = await db.execute(
                select(func.count(ThreadMessage.id))
                .where(ThreadMessage.thread_id == thread_id)
            )
            msg_count = msg_count_result.scalar() or 0
            if msg_count <= 2:
                thread_result = await db.execute(
                    select(Thread).where(Thread.id == thread_id)
                )
                thread = thread_result.scalar_one_or_none()
                if thread and not thread.title:
                    # Get first user message for title
                    first_msg_result = await db.execute(
                        select(ThreadMessage.content)
                        .where(
                            ThreadMessage.thread_id == thread_id,
                            ThreadMessage.role == "user",
                        )
                        .order_by(ThreadMessage.sequence_number)
                        .limit(1)
                    )
                    first_msg = first_msg_result.scalar_one_or_none()
                    if first_msg:
                        thread.title = first_msg[:80]
                        await db.commit()

            # Execution log
            log_entry = ExecutionLog(
                thread_id=thread_id,
                message_id=assistant_msg.id,
                event_type="model_response",
                state_snapshot={
                    "response_length": len(content),
                    "model_name": primary_endpoint.model_name if primary_endpoint else None,
                    "model_endpoint_id": str(primary_endpoint.id) if primary_endpoint else None,
                },
                duration_ms=duration_ms,
                token_count={"input_tokens": input_tokens or 0, "output_tokens": output_tokens or 0},
            )
            db.add(log_entry)
            await db.commit()

            # Store assistant response as long-term memory
            if len(content) > 10:
                try:
                    await self._memory_service.store_memory(
                        agent_id=agent.id,
                        user_id=user_id,
                        tenant_id=agent.tenant_id,
                        content=content,
                        db=db,
                        model_endpoint=None,
                        memory_type="knowledge",
                        source_thread_id=thread_id,
                    )
                except Exception:
                    logger.warning("Failed to store memory for thread %s", thread_id, exc_info=True)
        except Exception:
            logger.warning("Failed to save assistant response to thread %s", thread_id, exc_info=True)

    @staticmethod
    def _sse_data(content: str, done: bool) -> str:
        return f"data: {json.dumps({'content': content, 'done': done})}\n\n"

    @staticmethod
    def _sse_sources(sources: List[Dict[str, str]]) -> str:
        return f"data: {json.dumps({'sources': sources})}\n\n"

    @staticmethod
    def _sse_error(message: str) -> str:
        return f"data: {json.dumps({'error': message, 'done': True})}\n\n"
