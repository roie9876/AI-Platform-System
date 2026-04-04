import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
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
from app.core.config import settings
from app.services.service_client import ServiceClient

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
        self._rag_service = RAGService()
        self._memory_service = MemoryService()

        # In microservice mode, use HTTP calls; in monolith mode, use direct imports
        if settings.SERVICE_NAME == "agent-executor":
            self._service_client = ServiceClient()
            self._tool_executor = None
        else:
            self._service_client = None
            self._tool_executor = ToolExecutor()

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
        """Convert Tool dicts to OpenAI-format tool schemas."""
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
            params = dict(mt.get("input_schema") or {})
            # Ensure OpenAI-compatible schema: type must be object,
            # properties must be a dict, required must be a list (or absent).
            params.setdefault("type", "object")
            params.setdefault("properties", {})
            if params.get("properties") is None:
                params["properties"] = {}
            if "required" in params and params["required"] is None:
                del params["required"]
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
        auth_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute an MCP tool via tools/call on the appropriate server."""
        server = await _mcp_server_repo.get(tenant_id, mcp_tool["server_id"])
        if not server:
            return {"error": f"MCP server not found for tool {mcp_tool['tool_name']}"}

        # In microservice mode, use HTTP call to mcp-proxy
        if self._service_client and auth_token:
            try:
                headers = _build_auth_headers(server)
                result_data = await self._service_client.call_mcp_tool(
                    server_url=server["url"],
                    tool_name=mcp_tool["tool_name"],
                    arguments=arguments,
                    auth_headers=headers,
                    auth_token=auth_token,
                )
                return result_data
            except Exception as e:
                return {"error": f"MCP tool execution failed: {e}"}

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
        auth_token: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        start_time = time.monotonic()

        # OpenClaw agents — route through the gateway's /v1/chat/completions
        if agent.get("agent_type") == "openclaw":
            async for event in self._execute_openclaw(
                agent, user_message, tenant_id,
                conversation_history, thread_id, user_id, start_time,
            ):
                yield event
            return

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
        system_prompt = agent.get("system_prompt") or ""
        if not system_prompt.strip():
            system_prompt = "You are a helpful assistant."
        # Always append tool-use directive so the model calls tools proactively
        system_prompt += (
            "\n\nIMPORTANT: You have access to external tools. "
            "When the user asks a question that your tools can help answer, "
            "you MUST call the appropriate tool immediately instead of asking "
            "the user for clarification. Be proactive — use your tools first, "
            "then summarize the results for the user."
        )
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
                        "Relevant memories from past interactions (for context only "
                        "— always use your tools to fetch live data rather than "
                        "relying on these memories):\n\n"
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
        logger.info(
            "Agent %s: loaded %d platform tools, %d MCP tools",
            agent.get("name"), len(tools_list), len(mcp_tools_list),
        )
        tool_schemas = self._build_tool_schemas(tools_list) if tools_list else []
        mcp_schemas = self._build_mcp_tool_schemas(mcp_tools_list) if mcp_tools_list else []
        all_schemas = tool_schemas + mcp_schemas
        tool_schemas = all_schemas if all_schemas else None
        if tool_schemas:
            logger.info(
                "Agent %s: sending %d tool schemas to LLM: %s",
                agent.get("name"), len(all_schemas),
                [s["function"]["name"] for s in all_schemas],
            )
        else:
            logger.warning("Agent %s: NO tools loaded — running without tools", agent.get("name"))
        tool_map = {t["name"]: t for t in tools_list}
        mcp_tool_map = {f"mcp__{mt['tool_name']}": mt for mt in mcp_tools_list}

        try:
            # Emit sources event so the frontend knows what knowledge was used
            if rag_sources:
                yield self._sse_sources(rag_sources)

            collected_response = ""
            tools_called: List[Dict[str, Any]] = []

            # Record RAG retrieval as synthetic tool calls for trace visibility
            if rag_sources:
                for src in rag_sources:
                    if src.get("type") == "azure_search":
                        tools_called.append({
                            "name": "azure_ai_search",
                            "status": "success",
                            "index": src.get("index", ""),
                        })
                    elif src.get("type") == "document":
                        tools_called.append({
                            "name": "document_retrieval",
                            "status": "success",
                            "document": src.get("name", ""),
                        })

            if tool_schemas:
                # Tool-calling loop
                iteration = 0
                while iteration < self.MAX_TOOL_ITERATIONS:
                    iteration += 1
                    response = await self._model_service.complete_with_tools(
                        messages=messages,
                        endpoints=endpoints,
                        tools=tool_schemas,
                        tool_choice="auto",
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
                                # Emit tool_call event so the frontend can show execution UI
                                yield self._sse_tool_call(tc.function.name, args)
                                if mcp_tool:
                                    result = await self._execute_mcp_tool(
                                        mcp_tool, args, tenant_id,
                                        auth_token=auth_token,
                                    )
                                elif tool.get("is_platform_tool"):
                                    adapter = get_platform_adapter(tool["name"])
                                    if adapter:
                                        result = await adapter.execute(args)
                                    else:
                                        result = {"error": f"No adapter for platform tool: {tool['name']}"}
                                elif self._service_client and auth_token:
                                    result = await self._service_client.execute_tool(
                                        tool_name=tool["name"],
                                        input_data=args,
                                        input_schema=tool.get("input_schema") or {},
                                        execution_command=tool.get("execution_command"),
                                        timeout_seconds=tool.get("timeout_seconds") or 30,
                                        auth_token=auth_token,
                                    )
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
                                # Emit tool_result event so the frontend can show output
                                yield self._sse_tool_result(tc.function.name, result, "success")
                            except (ToolExecutionError, MCPClientError) as e:
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": json.dumps({"error": str(e)}),
                                })
                                yield self._sse_tool_result(tc.function.name, {"error": str(e)}, "error")
                            except Exception as e:
                                logger.warning("Unexpected error executing tool %s: %s", tc.function.name, e, exc_info=True)
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": json.dumps({"error": f"Tool execution failed: {e}"}),
                                })
                                yield self._sse_tool_result(tc.function.name, {"error": f"Tool execution failed: {e}"}, "error")
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
                tools_called=tools_called,
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

    @asynccontextmanager
    async def _openclaw_ws_session(self, gateway_url: str, instance_name: str = "", tenant_slug: str = ""):
        """Open authenticated WS to OpenClaw gateway and fetch cross-session context.

        Yields a tuple (context_string, ws_connection) where ws_connection
        can be reused for chat.send to route completions via WS instead of
        HTTP.  The WS is kept alive until the context-manager exits.
        """
        context = ""
        ws = None

        try:
            import websockets  # type: ignore
        except ImportError:
            yield ""
            return

        ws_url = gateway_url.replace("http://", "ws://", 1) + "/"
        origin = gateway_url

        # Read the gateway token from K8s secret for Bearer auth
        gw_token = ""
        if instance_name:
            try:
                from app.services.openclaw_service import _get_k8s_clients
                core_v1, _ = _get_k8s_clients()
                namespace = f"tenant-{tenant_slug}" if tenant_slug else "tenant-eng"
                secret_name = f"{instance_name}-gateway-token"
                loop = asyncio.get_event_loop()
                secret = await loop.run_in_executor(
                    None,
                    lambda: core_v1.read_namespaced_secret(secret_name, namespace),
                )
                import base64
                gw_token = base64.b64decode(secret.data.get("token", "")).decode()
            except Exception as tok_exc:
                logger.error("Could not read gateway token for %s: %s", instance_name, tok_exc, exc_info=True)

        extra_headers = {"Origin": origin}
        if gw_token:
            extra_headers["Authorization"] = f"Bearer {gw_token}"

        async def _ws_req(ws_conn, method: str, params: dict, timeout: int = 5) -> dict:
            """Send a WS JSON-RPC request and return the response, skipping events."""
            rid = str(uuid4())
            await ws_conn.send(json.dumps({"type": "req", "id": rid, "method": method, "params": params}))
            for _ in range(20):
                raw = await asyncio.wait_for(ws_conn.recv(), timeout=timeout)
                msg = json.loads(raw)
                if msg.get("type") == "event":
                    continue
                if msg.get("id") == rid or msg.get("type") == "res":
                    return msg
            return {"ok": False}

        # Open WS and build context — errors are non-fatal
        try:
            ws = await websockets.connect(
                ws_url,
                additional_headers=extra_headers,
                open_timeout=5,
                close_timeout=3,
            )
            # 1. Challenge + connect handshake
            await asyncio.wait_for(ws.recv(), timeout=3)
            resp = await _ws_req(ws, "connect", {
                "minProtocol": 3,
                "maxProtocol": 3,
                "client": {
                    "id": "openclaw-control-ui",
                    "version": "control-ui",
                    "platform": "linux",
                    "mode": "webchat",
                    "instanceId": f"aiplatform-ctx-{uuid4().hex[:8]}",
                },
                "role": "operator",
                "scopes": ["operator.admin", "operator.read"],
                "caps": [],
                "userAgent": "aiplatform-proxy/1.0",
                "locale": "en-US",
            })
            if not resp.get("ok"):
                raise RuntimeError("connect handshake failed")

            # 2. Fetch session list
            list_resp = await _ws_req(ws, "sessions.list", {})
            sessions: list = list_resp.get("payload", {}).get("sessions", []) if list_resp.get("ok") else []

            other_sessions = [s for s in sessions if s.get("key") not in ("main", "agent:main:main")]

            if other_sessions:
                # 3. Build context from session metadata
                context_parts: list[str] = []
                for session in other_sessions[:5]:
                    skey = session.get("key", "")
                    channel = session.get("channel") or "unknown"
                    kind = session.get("kind", "")
                    label = channel
                    if "whatsapp" in skey:
                        label = "WhatsApp"
                    elif "telegram" in skey:
                        label = "Telegram"
                    elif "discord" in skey:
                        label = "Discord"
                    # Include the human-readable group name if available
                    display_name = (
                        session.get("subject")
                        or session.get("displayName")
                        or session.get("name")
                        or ""
                    )
                    if display_name and kind == "group":
                        context_parts.append(
                            f'- Active {label} group "{display_name}" (session: {skey})'
                        )
                    else:
                        context_parts.append(
                            f"- Active {label} session (type={kind}): {skey}"
                        )

                # 4. Fetch actual message content from each channel session
                def _extract_messages(msgs, limit=10):
                    lines = []
                    for m in msgs[-limit:]:
                        role = m.get("role", "?")
                        sender = m.get("senderName") or m.get("sender") or role
                        contents = m.get("content", [])
                        if isinstance(contents, str):
                            text = contents[:300]
                        elif isinstance(contents, list):
                            text = " ".join(
                                c.get("text", "")[:300]
                                for c in contents
                                if isinstance(c, dict) and c.get("type") == "text"
                            )
                        else:
                            text = ""
                        if text.strip():
                            lines.append(f"  [{sender}]: {text.strip()}")
                    return lines

                channel_messages: dict[str, list[str]] = {}
                for session in other_sessions[:5]:
                    skey = session.get("key", "")
                    label = context_parts[other_sessions.index(session)].split(":")[0].strip("- ")
                    try:
                        sess_resp = await _ws_req(
                            ws, "sessions.get",
                            {"sessionKey": skey, "limit": 10},
                            timeout=5,
                        )
                        if sess_resp.get("ok"):
                            msgs = sess_resp.get("payload", {}).get("messages", [])
                            lines = _extract_messages(msgs)
                            if lines:
                                channel_messages[label + " (" + skey + ")"] = lines
                    except Exception:
                        pass

                # 5. Also fetch main session recent messages
                main_ctx_lines: list[str] = []
                try:
                    main_resp = await _ws_req(ws, "sessions.get", {"sessionKey": "agent:main:main", "limit": 5}, timeout=5)
                    if main_resp.get("ok"):
                        msgs = main_resp.get("payload", {}).get("messages", [])
                        main_ctx_lines = _extract_messages(msgs, limit=5)
                except Exception:
                    pass

                context = (
                    "You are connected to an OpenClaw agent with active sessions "
                    "on multiple channels. Below are the actual recent messages "
                    "from each channel — you can read and reference them directly.\n\n"
                    "Active channel sessions:\n"
                    + "\n".join(context_parts)
                )

                for ch_label, msg_lines in channel_messages.items():
                    context += (
                        f"\n\nRecent messages from {ch_label}:\n"
                        + "\n".join(msg_lines)
                    )

                if main_ctx_lines:
                    context += (
                        "\n\nRecent webchat (main session) messages:\n"
                        + "\n".join(main_ctx_lines)
                    )

            logger.debug("OpenClaw WS session opened, context len=%d", len(context))

        except Exception as exc:
            logger.error("Failed to set up OpenClaw WS session: %s", exc, exc_info=True)

        # Yield context + ws for chat.send routing
        try:
            yield context, ws
        finally:
            if ws:
                try:
                    await ws.close()
                except Exception:
                    pass

    async def _execute_openclaw(
        self,
        agent: dict,
        user_message: str,
        tenant_id: str,
        conversation_history: Optional[List[Dict[str, str]]],
        thread_id: Optional[str],
        user_id: Optional[str],
        start_time: float,
    ) -> AsyncGenerator[str, None]:
        """Route chat through OpenClaw gateway via WS chat.send."""

        gateway_url = agent.get("openclaw_gateway_url")
        instance_name = agent.get("openclaw_instance_name", "")
        logger.info("OpenClaw execute: gateway_url=%s instance_name=%s", gateway_url, instance_name)

        if not gateway_url:
            yield self._sse_error(
                "OpenClaw gateway not configured. Please delete and recreate the agent."
            )
            return

        # Build messages — send only the new user message.
        # OpenClaw maintains its own session history; we use x-openclaw-session-key
        # to route into the shared session so Playground and Telegram share context.
        messages: List[Dict[str, Any]] = []

        # Inject platform long-term memory as a system message
        if thread_id:
            try:
                memories = await self._memory_service.retrieve_relevant(
                    query=user_message,
                    agent_id=agent["id"],
                    user_id=user_id,
                    tenant_id=tenant_id,
                    model_endpoint=None,
                    top_k=5,
                )
                if memories:
                    memory_text = "\n\n".join(
                        m.get("content", "") if isinstance(m, dict) else m.content
                        for m in memories
                    )
                    messages.append({
                        "role": "system",
                        "content": (
                            "Relevant memories from past interactions (for context only "
                            "— always use your tools to fetch live data rather than "
                            "relying on these memories):\n\n"
                            f"{memory_text}"
                        ),
                    })
            except Exception:
                logger.warning("Memory retrieval failed for openclaw thread %s", thread_id, exc_info=True)

        # Inject cross-session context (WhatsApp, Telegram, etc.)
        # The WS connection is kept alive during the completion so the
        # gateway sees a "paired" device and the agent's built-in
        # sessions tools can connect successfully.
        tenant_slug = ""
        if gateway_url and ".tenant-" in gateway_url:
            tenant_slug = gateway_url.split(".tenant-")[1].split(".")[0]

        async with self._openclaw_ws_session(
            gateway_url, instance_name=instance_name, tenant_slug=tenant_slug
        ) as (session_ctx, ws_conn):
            if session_ctx:
                messages.append({
                    "role": "system",
                    "content": session_ctx,
                })

            # Inject configured WhatsApp group name mapping so the agent
            # knows the human-readable names (especially Hebrew) of its groups.
            openclaw_cfg = agent.get("openclaw_config") or {}
            wa_cfg = openclaw_cfg.get("whatsapp") or {}
            wa_rules: list = wa_cfg.get("whatsapp_group_rules") or []
            named_groups = [
                r for r in wa_rules
                if r.get("group_name") and r.get("policy") != "blocked"
            ]
            if named_groups:
                group_lines = []
                for r in named_groups:
                    jid_note = f" (JID: {r['group_jid']})" if r.get("group_jid") else " (pending resolution)"
                    line = f'- "{r["group_name"]}"{jid_note}'
                    if r.get("instructions"):
                        line += f' — Instructions: {r["instructions"]}'
                    group_lines.append(line)
                messages.append({
                    "role": "system",
                    "content": (
                        "Configured WhatsApp groups for this agent:\n"
                        + "\n".join(group_lines)
                        + "\n\nWhen the user refers to a group by name, use "
                        "the corresponding session key to send messages."
                    ),
                })

            messages.append({"role": "user", "content": user_message})

            # Inject RAG context from attached data sources & Azure AI Search
            rag_sources = await self._inject_rag_context(messages, agent, user_message, tenant_id)

            # Save user message to thread
            if thread_id and user_id:
                try:
                    seq_results = await _message_repo.query(
                        tenant_id,
                        "SELECT VALUE MAX(c.sequence_number) FROM c WHERE c.thread_id = @tid",
                        [{"name": "@tid", "value": thread_id}],
                    )
                    next_seq = (seq_results[0] if seq_results and seq_results[0] is not None else 0) + 1
                    user_msg_id = str(uuid4())
                    await _message_repo.create(tenant_id, {
                        "id": user_msg_id,
                        "thread_id": thread_id,
                        "role": "user",
                        "content": user_message,
                        "sequence_number": next_seq,
                        "tenant_id": tenant_id,
                    })
                except Exception:
                    logger.warning("Failed to save user message to thread %s", thread_id, exc_info=True)

            # Route via WS chat.send instead of HTTP POST to bypass
            # gateway auth/scope issues with the HTTP endpoint.
            if not ws_conn:
                yield self._sse_error(
                    "WebSocket connection to OpenClaw not established"
                )
                return

            # Build enriched message: prepend system context (memory, RAG,
            # session ctx) so the OpenClaw agent sees it in the user message.
            system_parts: list[str] = []
            for m in messages:
                if m["role"] == "system" and m.get("content"):
                    system_parts.append(m["content"])

            enriched_message = user_message
            if system_parts:
                enriched_message = (
                    "<platform_context>\n"
                    + "\n\n".join(system_parts)
                    + "\n</platform_context>\n\n"
                    + user_message
                )

            run_id = f"platform-{uuid4().hex[:12]}"
            req_id = str(uuid4())
            collected_response = ""

            try:
                await ws_conn.send(json.dumps({
                    "type": "req",
                    "id": req_id,
                    "method": "chat.send",
                    "params": {
                        "message": enriched_message,
                        "sessionKey": "agent:main:main",
                        "idempotencyKey": run_id,
                    },
                }))

                # Wait for chat.send confirmation
                confirmed = False
                for _ in range(20):
                    raw = await asyncio.wait_for(ws_conn.recv(), timeout=10)
                    msg = json.loads(raw)
                    if msg.get("id") == req_id:
                        if not msg.get("ok"):
                            err = msg.get("error", {})
                            yield self._sse_error(
                                f"chat.send failed: {err.get('message', 'unknown error')}"
                            )
                            return
                        run_id = msg.get("payload", {}).get("runId", run_id)
                        confirmed = True
                        break
                    # Skip events (health, tick, etc.)

                if not confirmed:
                    yield self._sse_error("chat.send did not confirm")
                    return

                # Emit sources so the frontend knows what knowledge was used
                if rag_sources:
                    yield self._sse_sources(rag_sources)

                # Listen for streaming events from the agent
                while True:
                    raw = await asyncio.wait_for(ws_conn.recv(), timeout=120)
                    msg = json.loads(raw)

                    if msg.get("type") != "event":
                        continue

                    event_name = msg.get("event", "")
                    payload = msg.get("payload", {})

                    # Only process events for our runId
                    if payload.get("runId") != run_id:
                        continue

                    if event_name == "agent":
                        stream = payload.get("stream", "")
                        data = payload.get("data", {})

                        if stream == "assistant":
                            delta = data.get("delta", "")
                            if delta:
                                collected_response += delta
                                yield self._sse_data(delta, done=False)

                        elif stream == "lifecycle" and data.get("phase") == "end":
                            break

                    elif event_name == "chat" and payload.get("state") == "final":
                        # Extract full text from final message if we missed deltas
                        if not collected_response:
                            final_msg = payload.get("message", {})
                            for part in (final_msg.get("content") or []):
                                if isinstance(part, dict) and part.get("type") == "text":
                                    collected_response += part.get("text", "")
                            if collected_response:
                                yield self._sse_data(collected_response, done=False)
                        break

            except asyncio.TimeoutError:
                if not collected_response:
                    yield self._sse_error("OpenClaw response timed out")
                    return
            except Exception as exc:
                if "ConnectionClosed" in type(exc).__name__:
                    logger.error("OpenClaw WS closed during streaming: %s", exc)
                    if not collected_response:
                        yield self._sse_error("OpenClaw connection lost during response")
                        return
                else:
                    logger.error("OpenClaw WS execution error: %s", exc, exc_info=True)
                    if not collected_response:
                        yield self._sse_error("OpenClaw execution failed")
                        return

            # Estimate tokens (~4 chars/token)
            input_text = enriched_message
            est_input = len(input_text) // 4 + 1
            est_output = len(collected_response) // 4 + 1

            # Save assistant response to thread
            if thread_id and user_id:
                primary_endpoint = None
                model_endpoint_id = agent.get("model_endpoint_id")
                if model_endpoint_id:
                    primary_endpoint = await _endpoint_repo.get(tenant_id, model_endpoint_id)
                await self._save_assistant_response(
                    tenant_id, thread_id, user_id, agent, collected_response,
                    rag_sources, start_time, primary_endpoint or {},
                    input_tokens=est_input, output_tokens=est_output,
                )

            # Store to platform memory for cross-thread recall
            if thread_id and user_id and collected_response:
                try:
                    if len(user_message) > 10:
                        await self._memory_service.store_memory(
                            agent_id=agent["id"],
                            user_id=user_id,
                            tenant_id=tenant_id,
                            content=f"User said: {user_message}",
                            model_endpoint=None,
                            memory_type="user_input",
                            source_thread_id=thread_id,
                        )
                    if len(collected_response) > 10:
                        await self._memory_service.store_memory(
                            agent_id=agent["id"],
                            user_id=user_id,
                            tenant_id=tenant_id,
                            content=f"Assistant replied: {collected_response[:500]}",
                            model_endpoint=None,
                            memory_type="assistant_response",
                            source_thread_id=thread_id,
                        )
                except Exception:
                    logger.warning("Failed to store openclaw memory for thread %s", thread_id, exc_info=True)

            yield self._sse_data("", done=True)

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

            # Store assistant response as long-term memory only when tool
            # calls were made — conversational responses (e.g. "I can't find…")
            # poison future interactions if stored as memories.
            if len(content) > 10 and tools_called:
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
    def _sse_tool_call(tool_name: str, arguments: dict) -> str:
        return f"data: {json.dumps({'tool_call': {'name': tool_name, 'arguments': arguments}})}\n\n"

    @staticmethod
    def _sse_tool_result(tool_name: str, result: dict, status: str = "success") -> str:
        return f"data: {json.dumps({'tool_result': {'name': tool_name, 'result': result, 'status': status}})}\n\n"

    @staticmethod
    def _sse_error(message: str) -> str:
        return f"data: {json.dumps({'error': message, 'done': True})}\n\n"
