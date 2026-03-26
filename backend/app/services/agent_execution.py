import json
import logging
import time
from typing import Optional, List, Dict, Any, AsyncGenerator
from uuid import uuid4

from app.repositories.agent_repo import AgentRepository
from app.repositories.tool_repo import ToolRepository, AgentToolRepository
from app.repositories.mcp_repo import MCPServerRepository, MCPDiscoveredToolRepository, AgentMCPToolRepository
from app.repositories.observability_repo import ExecutionLogRepository
from app.repositories.config_repo import ModelEndpointRepository
from app.repositories.thread_repo import ThreadRepository, ThreadMessageRepository
from app.services.model_abstraction import ModelAbstractionService, ModelError
from app.services.tool_executor import ToolExecutor, ToolExecutionError
from app.services.mcp_client import MCPClient, MCPClientError
from app.services.mcp_discovery import _build_auth_headers
from app.services.rag_service import RAGService
from app.services.memory_service import MemoryService
from app.services.platform_tools import get_adapter_by_name as get_platform_adapter

logger = logging.getLogger(__name__)

_agent_repo = AgentRepository()
_tool_repo = ToolRepository()
_agent_tool_repo = AgentToolRepository()
_mcp_server_repo = MCPServerRepository()
_mcp_tool_repo = MCPDiscoveredToolRepository()
_agent_mcp_tool_repo = AgentMCPToolRepository()
_exec_log_repo = ExecutionLogRepository()
_endpoint_repo = ModelEndpointRepository()
_thread_repo = ThreadRepository()
_message_repo = ThreadMessageRepository()


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
        agent: dict,
        user_message: str,
        tenant_id: str,
    ) -> List[Dict[str, str]]:
        """Retrieve relevant document chunks and inject as system context.
        Returns list of source descriptors for the frontend."""
        all_chunks: List[Dict[str, Any]] = []

        # 1. Local document chunks (data sources attached to agent)
        chunks = await self._rag_service.retrieve(
            query=user_message,
            agent_id=agent["id"],
            tenant_id=tenant_id,
            top_k=5,
        )
        all_chunks.extend(chunks)

        # 2. Azure AI Search indexes (knowledge connections)
        try:
            azure_chunks = await self._rag_service.retrieve_from_azure_search(
                query=user_message,
                agent_id=agent["id"],
                tenant_id=tenant_id,
                top_k=5,
            )
            all_chunks.extend(azure_chunks)
        except Exception:
            logger.warning("Azure Search retrieval failed for agent %s", agent["id"])

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

    async def _load_agent_tools(self, agent_id: str, tenant_id: str) -> List[dict]:
        """Load all tools attached to this agent."""
        links = await _agent_tool_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.agent_id = @aid",
            [{"name": "@aid", "value": agent_id}],
        )
        tools = []
        for link in links:
            tool = await _tool_repo.get(tenant_id, link["tool_id"])
            if tool:
                tools.append(tool)
        return tools

    async def _load_agent_mcp_tools(self, agent_id: str, tenant_id: str) -> List[dict]:
        """Load all MCP tools attached to this agent."""
        links = await _agent_mcp_tool_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.agent_id = @aid",
            [{"name": "@aid", "value": agent_id}],
        )
        tools = []
        for link in links:
            mt = await _mcp_tool_repo.get(tenant_id, link["mcp_tool_id"])
            if mt and mt.get("is_available"):
                tools.append(mt)
        return tools

    def _build_tool_schemas(self, tools: List[dict]) -> List[Dict[str, Any]]:
        """Convert Tool dicts to OpenAI-format tool schemas for LiteLLM."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description") or "",
                    "parameters": tool.get("input_schema") or {"type": "object", "properties": {}},
                },
            }
            for tool in tools
        ]

    def _build_mcp_tool_schemas(self, mcp_tools: List[dict]) -> List[Dict[str, Any]]:
        """Convert MCP discovered tools to OpenAI-format tool schemas."""
        schemas = []
        for mt in mcp_tools:
            params = mt.get("input_schema") or {"type": "object", "properties": {}}
            schemas.append({
                "type": "function",
                "function": {
                    "name": f"mcp__{mt['tool_name']}",
                    "description": mt.get("description") or "",
                    "parameters": params,
                },
            })
        return schemas

    async def _execute_mcp_tool(
        self,
        mcp_tool: dict,
        arguments: Dict[str, Any],
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Execute an MCP tool via tools/call on the appropriate server."""
        server = await _mcp_server_repo.get(tenant_id, mcp_tool["server_id"])
        if not server:
            return {"error": f"MCP server not found for tool {mcp_tool['tool_name']}"}

        headers = _build_auth_headers(server)
        client = MCPClient(server["url"], timeout=30.0, headers=headers)
        try:
            await client.connect()
            call_result = await client.call_tool(mcp_tool["tool_name"], arguments)
            text_parts = [
                block.text for block in call_result.content
                if block.type == "text" and block.text
            ]
            return {
                "result": "\n".join(text_parts) if text_parts else "(no text output)",
                "is_error": call_result.isError or False,
            }
        except MCPClientError as e:
            return {"error": f"MCP tool execution failed: {e}"}
        except Exception as e:
            logger.warning("Unexpected error executing MCP tool %s: %s", mcp_tool["tool_name"], e, exc_info=True)
            return {"error": f"MCP tool execution failed: {e}"}
        finally:
            await client.disconnect()

    async def execute(
        self,
        agent: dict,
        user_message: str,
        tenant_id: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        start_time = time.monotonic()

        # Load primary endpoint
        model_endpoint_id = agent.get("model_endpoint_id")
        if not model_endpoint_id:
            yield self._sse_error("Agent has no model endpoint assigned")
            return

        primary_endpoint = await _endpoint_repo.get(tenant_id, model_endpoint_id)
        if not primary_endpoint or not primary_endpoint.get("is_active"):
            yield self._sse_error("Assigned model endpoint not found or inactive")
            return

        # Load fallback endpoints (same tenant, active, different from primary)
        all_endpoints = await _endpoint_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.is_active = true AND c.id != @pid",
            [{"name": "@tid", "value": tenant_id}, {"name": "@pid", "value": model_endpoint_id}],
        )
        endpoints = [primary_endpoint] + all_endpoints

        # Build messages
        messages: List[Dict[str, Any]] = []
        system_prompt = agent.get("system_prompt")
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Inject current date/time so the model always knows today's date
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)
        date_info = f"Current date and time (UTC): {now_utc.strftime('%A, %B %d, %Y %H:%M UTC')}"
        messages.append({"role": "system", "content": date_info})

        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        # Inject RAG context from attached data sources
        rag_sources = await self._inject_rag_context(messages, agent, user_message, tenant_id)

        # Inject long-term memory context if using a thread
        if thread_id:
            try:
                memories = await self._memory_service.retrieve_relevant(
                    query=user_message,
                    agent_id=agent["id"],
                    user_id=user_id,
                    tenant_id=tenant_id,
                    model_endpoint=primary_endpoint,
                    top_k=5,
                )
                if memories:
                    memory_text = "\n\n".join(m.get("content", "") if isinstance(m, dict) else m.content for m in memories)
                    memory_msg = (
                        "Relevant memories from past interactions:\n\n"
                        f"{memory_text}"
                    )
                    insert_idx = 1 if messages and messages[0]["role"] == "system" else 0
                    while insert_idx < len(messages) and messages[insert_idx]["role"] == "system":
                        insert_idx += 1
                    messages.insert(insert_idx, {"role": "system", "content": memory_msg})
            except Exception:
                logger.warning("Memory retrieval failed for thread %s", thread_id, exc_info=True)

        # Save user message to thread if thread_id provided
        if thread_id and user_id:
            try:
                # Get next sequence number via Cosmos query
                seq_results = await _message_repo.query(
                    tenant_id,
                    "SELECT VALUE MAX(c.sequence_number) FROM c WHERE c.thread_id = @tid",
                    [{"name": "@tid", "value": thread_id}],
                )
                next_seq = (seq_results[0] if seq_results and seq_results[0] is not None else 0) + 1

                user_msg_id = str(uuid4())
                user_msg = {
                    "id": user_msg_id,
                    "thread_id": thread_id,
                    "role": "user",
                    "content": user_message,
                    "sequence_number": next_seq,
                    "tenant_id": tenant_id,
                }
                await _message_repo.create(tenant_id, user_msg)

                # Log execution event
                log_entry = {
                    "id": str(uuid4()),
                    "thread_id": thread_id,
                    "message_id": user_msg_id,
                    "event_type": "message_sent",
                    "state_snapshot": {"messages_count": len(messages)},
                    "duration_ms": 0,
                    "tenant_id": tenant_id,
                    "agent_id": agent["id"],
                }
                await _exec_log_repo.create(tenant_id, log_entry)

                # Store user message as memory for cross-thread recall
                if len(user_message) > 10:
                    try:
                        await self._memory_service.store_memory(
                            agent_id=agent["id"],
                            user_id=user_id,
                            tenant_id=tenant_id,
                            content=f"User said: {user_message}",
                            model_endpoint=None,
                            memory_type="user_input",
                            source_thread_id=thread_id,
                        )
                    except Exception:
                        logger.warning("Failed to store user memory for thread %s", thread_id, exc_info=True)
            except Exception:
                logger.warning("Failed to save user message to thread %s", thread_id, exc_info=True)

        # Update agent status to active
        agent["status"] = "active"
        await _agent_repo.update(tenant_id, agent["id"], agent)

        # Load tools attached to this agent (platform + sandbox + MCP)
        tools_list = await self._load_agent_tools(agent["id"], tenant_id)
        mcp_tools_list = await self._load_agent_mcp_tools(agent["id"], tenant_id)
        tool_schemas = self._build_tool_schemas(tools_list) if tools_list else []
        mcp_schemas = self._build_mcp_tool_schemas(mcp_tools_list) if mcp_tools_list else []
        all_schemas = tool_schemas + mcp_schemas
        tool_schemas = all_schemas if all_schemas else None
        tool_map = {t["name"]: t for t in tools_list}
        mcp_tool_map = {f"mcp__{mt['tool_name']}": mt for mt in mcp_tools_list}

        try:
            # Emit sources event so the frontend knows what knowledge was used
            if rag_sources:
                yield self._sse_sources(rag_sources)

            collected_response = ""
            tools_called: List[Dict[str, Any]] = []

            if tool_schemas:
                # Tool-calling loop
                iteration = 0
                while iteration < self.MAX_TOOL_ITERATIONS:
                    iteration += 1
                    response = await self._model_service.complete_with_tools(
                        messages=messages,
                        endpoints=endpoints,
                        tools=tool_schemas,
                        temperature=agent.get("temperature"),
                        max_tokens=agent.get("max_tokens"),
                        timeout=agent.get("timeout_seconds"),
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
                            mcp_tool = mcp_tool_map.get(tc.function.name)
                            if not tool and not mcp_tool:
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": json.dumps({"error": f"Unknown tool: {tc.function.name}"}),
                                })
                                continue
                            try:
                                args = json.loads(tc.function.arguments)
                                if mcp_tool:
                                    result = await self._execute_mcp_tool(
                                        mcp_tool, args, tenant_id
                                    )
                                elif tool.get("is_platform_tool"):
                                    adapter = get_platform_adapter(tool["name"])
                                    if adapter:
                                        result = await adapter.execute(args)
                                    else:
                                        result = {"error": f"No adapter for platform tool: {tool['name']}"}
                                else:
                                    result = await self._tool_executor.execute(
                                        tool_name=tool["name"],
                                        input_data=args,
                                        input_schema=tool.get("input_schema"),
                                        execution_command=tool.get("execution_command"),
                                        timeout_seconds=tool.get("timeout_seconds"),
                                    )
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": json.dumps(result),
                                })
                                tools_called.append({"name": tc.function.name, "status": "success"})
                            except (ToolExecutionError, MCPClientError) as e:
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": json.dumps({"error": str(e)}),
                                })
                            except Exception as e:
                                logger.warning("Unexpected error executing tool %s: %s", tc.function.name, e, exc_info=True)
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": json.dumps({"error": f"Tool execution failed: {e}"}),
                                })
                    else:
                        # No tool calls — model returned final content
                        collected_response = response["content"] or ""
                        if collected_response:
                            yield self._sse_data(collected_response, done=False)
                        usage = response.get("usage") or {}
                        input_tokens = usage.get("prompt_tokens")
                        output_tokens = usage.get("completion_tokens")
                        await self._save_assistant_response(
                            tenant_id, thread_id, user_id, agent, collected_response,
                            rag_sources, start_time, primary_endpoint,
                            input_tokens=input_tokens, output_tokens=output_tokens,
                            tools_called=tools_called,
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
                temperature=agent.get("temperature"),
                max_tokens=agent.get("max_tokens"),
                timeout=agent.get("timeout_seconds"),
                stream=True,
            ):
                collected_response += token
                yield self._sse_data(token, done=False)

            usage = self._model_service.get_last_usage()
            await self._save_assistant_response(
                tenant_id, thread_id, user_id, agent, collected_response,
                rag_sources, start_time, primary_endpoint,
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            )
            yield self._sse_data("", done=True)

        except ModelError as exc:
            agent["status"] = "error"
            await _agent_repo.update(tenant_id, agent["id"], agent)
            logger.error("Agent execution failed: %s", str(exc))
            yield self._sse_error(str(exc))
        except Exception as exc:
            agent["status"] = "error"
            await _agent_repo.update(tenant_id, agent["id"], agent)
            logger.error("Unexpected agent execution error: %s", str(exc), exc_info=True)
            yield self._sse_error("An unexpected error occurred during execution")

    async def _save_assistant_response(
        self,
        tenant_id: str,
        thread_id: Optional[str],
        user_id: Optional[str],
        agent: dict,
        content: str,
        rag_sources: List[Dict[str, str]],
        start_time: float,
        primary_endpoint: dict,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        tools_called: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Save assistant response to thread and log execution."""
        if not thread_id or not user_id:
            return
        try:
            duration_ms = int((time.monotonic() - start_time) * 1000)

            # Get next sequence number
            seq_results = await _message_repo.query(
                tenant_id,
                "SELECT VALUE MAX(c.sequence_number) FROM c WHERE c.thread_id = @tid",
                [{"name": "@tid", "value": thread_id}],
            )
            next_seq = (seq_results[0] if seq_results and seq_results[0] is not None else 0) + 1

            # Save assistant message
            metadata = {}
            if rag_sources:
                metadata["sources"] = rag_sources
            assistant_msg_id = str(uuid4())
            assistant_msg = {
                "id": assistant_msg_id,
                "thread_id": thread_id,
                "role": "assistant",
                "content": content,
                "message_metadata": metadata if metadata else None,
                "sequence_number": next_seq,
                "tenant_id": tenant_id,
            }
            await _message_repo.create(tenant_id, assistant_msg)

            # Auto-title: if thread has only 2 messages (1 user + 1 assistant), set title
            count_results = await _message_repo.query(
                tenant_id,
                "SELECT VALUE COUNT(1) FROM c WHERE c.thread_id = @tid",
                [{"name": "@tid", "value": thread_id}],
            )
            msg_count = count_results[0] if count_results else 0
            if msg_count <= 2:
                thread = await _thread_repo.get(tenant_id, thread_id)
                if thread and not thread.get("title"):
                    first_msg_results = await _message_repo.query(
                        tenant_id,
                        "SELECT * FROM c WHERE c.thread_id = @tid AND c.role = 'user' ORDER BY c.sequence_number OFFSET 0 LIMIT 1",
                        [{"name": "@tid", "value": thread_id}],
                    )
                    if first_msg_results:
                        thread["title"] = first_msg_results[0].get("content", "")[:80]
                        await _thread_repo.update(tenant_id, thread_id, thread)

            # Execution log
            state = {
                "response_length": len(content),
                "model_name": primary_endpoint.get("model_name") if primary_endpoint else None,
                "model_endpoint_id": primary_endpoint.get("id") if primary_endpoint else None,
            }
            if tools_called:
                state["tool_calls"] = tools_called

            log_entry = {
                "id": str(uuid4()),
                "thread_id": thread_id,
                "message_id": assistant_msg_id,
                "event_type": "model_response",
                "state_snapshot": state,
                "duration_ms": duration_ms,
                "token_count": {"input_tokens": input_tokens or 0, "output_tokens": output_tokens or 0},
                "tenant_id": tenant_id,
                "agent_id": agent["id"],
            }
            await _exec_log_repo.create(tenant_id, log_entry)

            # Store assistant response as long-term memory
            if len(content) > 10:
                try:
                    await self._memory_service.store_memory(
                        agent_id=agent["id"],
                        user_id=user_id,
                        tenant_id=tenant_id,
                        content=content,
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
