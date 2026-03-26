import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.repositories.workflow_repo import (
    WorkflowRepository,
    WorkflowNodeRepository,
    WorkflowEdgeRepository,
    WorkflowExecutionRepository,
    WorkflowNodeExecutionRepository,
)
from app.repositories.agent_repo import AgentRepository
from app.repositories.thread_repo import ThreadRepository
from app.services.agent_execution import AgentExecutionService

logger = logging.getLogger(__name__)

_workflow_repo = WorkflowRepository()
_node_repo = WorkflowNodeRepository()
_edge_repo = WorkflowEdgeRepository()
_exec_repo = WorkflowExecutionRepository()
_node_exec_repo = WorkflowNodeExecutionRepository()
_agent_repo = AgentRepository()
_thread_repo = ThreadRepository()


class WorkflowEngine:
    """Executes multi-agent workflows with sequential, parallel, autonomous, and custom DAG modes."""

    def __init__(self) -> None:
        self._agent_service = AgentExecutionService()

    async def run(
        self,
        workflow_id: str,
        input_data: dict,
        user_id: str,
        tenant_id: str,
    ) -> dict:
        # Load workflow
        workflow = await _workflow_repo.get(tenant_id, workflow_id)
        if not workflow:
            raise ValueError("Workflow not found")

        # Load nodes and edges
        all_nodes = await _node_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.workflow_id = @wid ORDER BY c.execution_order",
            [{"name": "@wid", "value": workflow_id}],
        )
        if not all_nodes:
            raise ValueError("Workflow has no nodes")

        all_edges = await _edge_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.workflow_id = @wid",
            [{"name": "@wid", "value": workflow_id}],
        )

        # Create shared thread for cross-agent context
        thread_id = str(uuid4())
        thread = {
            "id": thread_id,
            "title": f"Workflow: {workflow['name']}",
            "agent_id": all_nodes[0]["agent_id"],
            "user_id": user_id,
            "tenant_id": tenant_id,
        }
        await _thread_repo.create(tenant_id, thread)

        # Create execution record
        exec_id = str(uuid4())
        execution = {
            "id": exec_id,
            "workflow_id": workflow_id,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "input_data": input_data,
            "tenant_id": tenant_id,
            "triggered_by": user_id,
            "thread_id": thread_id,
        }
        await _exec_repo.create(tenant_id, execution)

        try:
            dispatch = {
                "sequential": self._execute_sequential,
                "parallel": self._execute_parallel,
                "autonomous": self._execute_autonomous,
                "custom": self._execute_custom,
            }
            handler = dispatch.get(workflow.get("workflow_type", "sequential"), self._execute_sequential)
            output = await handler(
                nodes=all_nodes,
                edges=all_edges,
                execution=execution,
                input_data=input_data,
                user_id=user_id,
                tenant_id=tenant_id,
                thread_id=thread_id,
            )

            execution["status"] = "completed"
            execution["completed_at"] = datetime.now(timezone.utc).isoformat()
            execution["output_data"] = output
            await _exec_repo.update(tenant_id, exec_id, execution)
        except Exception as e:
            execution["status"] = "failed"
            execution["completed_at"] = datetime.now(timezone.utc).isoformat()
            execution["error"] = str(e)
            await _exec_repo.update(tenant_id, exec_id, execution)
            logger.error("Workflow execution failed: %s", e, exc_info=True)

        return await _exec_repo.get(tenant_id, exec_id)

    async def _execute_sequential(
        self,
        nodes: List[dict],
        edges: List[dict],
        execution: dict,
        input_data: dict,
        user_id: str,
        tenant_id: str,
        thread_id: str,
    ) -> dict:
        previous_output: Optional[dict] = None
        last_output: dict = {}

        for i, node in enumerate(nodes):
            node_exec_id = str(uuid4())
            node_exec = {
                "id": node_exec_id,
                "workflow_execution_id": execution["id"],
                "node_id": node["id"],
                "agent_id": node["agent_id"],
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "tenant_id": tenant_id,
            }
            await _node_exec_repo.create(tenant_id, node_exec)

            # Build message
            if i == 0:
                message = input_data.get("message", "")
            else:
                # Apply output mapping from connecting edge
                edge = self._find_edge(edges, nodes[i - 1]["id"], node["id"])
                message = self._apply_output_mapping(previous_output, edge.get("output_mapping") if edge else None)

            node_exec["input_data"] = {"message": message}

            try:
                response_text = await self._execute_node(
                    node=node,
                    message=message,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    thread_id=thread_id,
                )
                node_exec["status"] = "completed"
                node_exec["completed_at"] = datetime.now(timezone.utc).isoformat()
                node_exec["output_data"] = {"response": response_text}
                previous_output = {"response": response_text}
                last_output = {"response": response_text}
                await _node_exec_repo.update(tenant_id, node_exec_id, node_exec)
            except Exception as e:
                node_exec["status"] = "failed"
                node_exec["completed_at"] = datetime.now(timezone.utc).isoformat()
                node_exec["error"] = str(e)
                await _node_exec_repo.update(tenant_id, node_exec_id, node_exec)
                raise

        return last_output

    async def _execute_parallel(
        self,
        nodes: List[dict],
        edges: List[dict],
        execution: dict,
        input_data: dict,
        user_id: str,
        tenant_id: str,
        thread_id: str,
    ) -> dict:
        message = input_data.get("message", "")

        # Create node execution records
        node_exec_ids: List[str] = []
        for node in nodes:
            ne_id = str(uuid4())
            node_exec = {
                "id": ne_id,
                "workflow_execution_id": execution["id"],
                "node_id": node["id"],
                "agent_id": node["agent_id"],
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "input_data": {"message": message},
                "tenant_id": tenant_id,
            }
            await _node_exec_repo.create(tenant_id, node_exec)
            node_exec_ids.append(ne_id)

        # Execute all nodes concurrently — repos are stateless singletons
        async def run_node(node: dict) -> dict:
            try:
                response_text = await self._execute_node(
                    node=node,
                    message=message,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    thread_id=thread_id,
                )
                return {"node_id": node["id"], "node_name": node.get("name", ""), "response": response_text, "status": "completed"}
            except Exception as e:
                return {"node_id": node["id"], "node_name": node.get("name", ""), "error": str(e), "status": "failed"}

        tasks = [run_node(node) for node in nodes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Update node execution records
        aggregated = []
        for ne_id, result in zip(node_exec_ids, results):
            ne = await _node_exec_repo.get(tenant_id, ne_id)
            if not ne:
                continue
            if isinstance(result, Exception):
                ne["status"] = "failed"
                ne["error"] = str(result)
                ne["completed_at"] = datetime.now(timezone.utc).isoformat()
                aggregated.append({"node_id": ne["node_id"], "error": str(result), "status": "failed"})
            else:
                ne["status"] = result.get("status", "completed")
                ne["completed_at"] = datetime.now(timezone.utc).isoformat()
                if result.get("status") == "completed":
                    ne["output_data"] = {"response": result.get("response", "")}
                else:
                    ne["error"] = result.get("error", "")
                aggregated.append(result)
            await _node_exec_repo.update(tenant_id, ne_id, ne)

        return {"results": aggregated}

    async def _execute_autonomous(
        self,
        nodes: List[dict],
        edges: List[dict],
        execution: dict,
        input_data: dict,
        user_id: str,
        tenant_id: str,
        thread_id: str,
    ) -> dict:
        # Build agent descriptions for the router
        agent_descriptions = []
        for node in nodes:
            agent = await _agent_repo.get(tenant_id, node["agent_id"])
            if agent:
                agent_descriptions.append({
                    "node_id": node["id"],
                    "agent_id": node["agent_id"],
                    "name": node.get("name", ""),
                    "description": agent.get("description") or "No description",
                })

        # Find router node or use first node
        router_node = next((n for n in nodes if n.get("node_type") == "router"), nodes[0])

        router_prompt = (
            f"You are a workflow orchestrator. Given the user's request, decide which agents to call and in what order.\n\n"
            f"Available agents:\n"
        )
        for desc in agent_descriptions:
            router_prompt += f"- {desc['name']} (agent_id: {desc['agent_id']}): {desc['description']}\n"
        router_prompt += (
            f"\nUser request: {input_data.get('message', '')}\n\n"
            f"Respond with ONLY a JSON object: {{\"steps\": [{{\"agent_id\": \"...\", \"message\": \"...\"}}]}}\n"
            f"Choose the agents and craft specific messages for each."
        )

        # Execute router to get plan
        router_exec_id = str(uuid4())
        router_exec = {
            "id": router_exec_id,
            "workflow_execution_id": execution["id"],
            "node_id": router_node["id"],
            "agent_id": router_node["agent_id"],
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "input_data": {"message": router_prompt},
            "tenant_id": tenant_id,
        }
        await _node_exec_repo.create(tenant_id, router_exec)

        try:
            router_response = await self._execute_node(
                node=router_node,
                message=router_prompt,
                user_id=user_id,
                tenant_id=tenant_id,
                thread_id=thread_id,
            )
            router_exec["status"] = "completed"
            router_exec["completed_at"] = datetime.now(timezone.utc).isoformat()
            router_exec["output_data"] = {"response": router_response}
            await _node_exec_repo.update(tenant_id, router_exec_id, router_exec)
        except Exception as e:
            router_exec["status"] = "failed"
            router_exec["completed_at"] = datetime.now(timezone.utc).isoformat()
            router_exec["error"] = str(e)
            await _node_exec_repo.update(tenant_id, router_exec_id, router_exec)
            raise

        # Parse plan from router response
        try:
            json_start = router_response.find("{")
            json_end = router_response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                plan = json.loads(router_response[json_start:json_end])
            else:
                raise ValueError("No JSON found in router response")
            steps = plan.get("steps", [])
        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse autonomous plan, falling back to sequential")
            return await self._execute_sequential(
                nodes=nodes, edges=edges, execution=execution,
                input_data=input_data, user_id=user_id, tenant_id=tenant_id,
                thread_id=thread_id,
            )

        # Execute each step
        node_map = {n["agent_id"]: n for n in nodes}
        results = []
        for step in steps:
            agent_id = step.get("agent_id", "")
            step_message = step.get("message", input_data.get("message", ""))
            node = node_map.get(agent_id)
            if not node:
                results.append({"agent_id": agent_id, "error": "Agent not found in workflow", "status": "skipped"})
                continue

            step_exec_id = str(uuid4())
            step_exec = {
                "id": step_exec_id,
                "workflow_execution_id": execution["id"],
                "node_id": node["id"],
                "agent_id": node["agent_id"],
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "input_data": {"message": step_message},
                "tenant_id": tenant_id,
            }
            await _node_exec_repo.create(tenant_id, step_exec)

            try:
                response = await self._execute_node(
                    node=node, message=step_message,
                    user_id=user_id, tenant_id=tenant_id,
                    thread_id=thread_id,
                )
                step_exec["status"] = "completed"
                step_exec["completed_at"] = datetime.now(timezone.utc).isoformat()
                step_exec["output_data"] = {"response": response}
                results.append({"node_name": node.get("name", ""), "response": response, "status": "completed"})
                await _node_exec_repo.update(tenant_id, step_exec_id, step_exec)
            except Exception as e:
                step_exec["status"] = "failed"
                step_exec["completed_at"] = datetime.now(timezone.utc).isoformat()
                step_exec["error"] = str(e)
                results.append({"node_name": node.get("name", ""), "error": str(e), "status": "failed"})
                await _node_exec_repo.update(tenant_id, step_exec_id, step_exec)

        return {"results": results}

    async def _execute_custom(
        self,
        nodes: List[dict],
        edges: List[dict],
        execution: dict,
        input_data: dict,
        user_id: str,
        tenant_id: str,
        thread_id: str,
    ) -> dict:
        # Build adjacency and find root nodes (no incoming edges)
        node_map = {node["id"]: node for node in nodes}
        incoming: Dict[str, List[dict]] = {n["id"]: [] for n in nodes}
        outgoing: Dict[str, List[dict]] = {n["id"]: [] for n in nodes}
        for edge in edges:
            incoming[edge["target_node_id"]].append(edge)
            outgoing[edge["source_node_id"]].append(edge)

        # Topological sort using Kahn's algorithm
        in_degree = {n["id"]: len(incoming[n["id"]]) for n in nodes}
        levels: List[List[str]] = []
        queue = [nid for nid, deg in in_degree.items() if deg == 0]

        while queue:
            levels.append(list(queue))
            next_queue: List[str] = []
            for nid in queue:
                for edge in outgoing[nid]:
                    in_degree[edge["target_node_id"]] -= 1
                    if in_degree[edge["target_node_id"]] == 0:
                        next_queue.append(edge["target_node_id"])
            queue = next_queue

        # Execute level by level
        node_outputs: Dict[str, dict] = {}
        terminal_outputs: List[dict] = []

        for level in levels:
            async def run_level_node(nid: str) -> None:
                node = node_map[nid]
                in_edges = incoming[nid]

                # Determine message
                if not in_edges:
                    message = input_data.get("message", "")
                else:
                    message = ""
                    for edge in in_edges:
                        source_output = node_outputs.get(edge["source_node_id"])
                        if source_output is None:
                            continue
                        if edge.get("edge_type") == "conditional" and edge.get("condition"):
                            key = edge["condition"].get("key", "")
                            value = edge["condition"].get("value", "")
                            if source_output.get(key) != value:
                                continue
                        elif edge.get("edge_type") == "error":
                            if source_output.get("status") != "failed":
                                continue
                        message = self._apply_output_mapping(source_output, edge.get("output_mapping"))
                        break

                ne_id = str(uuid4())
                node_exec = {
                    "id": ne_id,
                    "workflow_execution_id": execution["id"],
                    "node_id": node["id"],
                    "agent_id": node["agent_id"],
                    "status": "running",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "input_data": {"message": message},
                    "tenant_id": tenant_id,
                }
                await _node_exec_repo.create(tenant_id, node_exec)

                try:
                    response = await self._execute_node(
                        node=node, message=message,
                        user_id=user_id, tenant_id=tenant_id,
                        thread_id=thread_id,
                    )
                    node_exec["status"] = "completed"
                    node_exec["completed_at"] = datetime.now(timezone.utc).isoformat()
                    node_exec["output_data"] = {"response": response}
                    node_outputs[nid] = {"response": response, "status": "completed"}
                    await _node_exec_repo.update(tenant_id, ne_id, node_exec)
                except Exception as e:
                    node_exec["status"] = "failed"
                    node_exec["completed_at"] = datetime.now(timezone.utc).isoformat()
                    node_exec["error"] = str(e)
                    node_outputs[nid] = {"error": str(e), "status": "failed"}
                    await _node_exec_repo.update(tenant_id, ne_id, node_exec)

            if len(level) == 1:
                await run_level_node(level[0])
            else:
                await asyncio.gather(*(run_level_node(nid) for nid in level))

        # Collect terminal node outputs (nodes with no outgoing edges)
        for node in nodes:
            if not outgoing[node["id"]]:
                output = node_outputs.get(node["id"], {})
                terminal_outputs.append({"node_name": node.get("name", ""), **output})

        if len(terminal_outputs) == 1:
            return terminal_outputs[0]
        return {"results": terminal_outputs}

    async def _execute_node(
        self,
        node: dict,
        message: str,
        user_id: str,
        tenant_id: str,
        thread_id: str,
    ) -> str:
        # Load agent
        agent = await _agent_repo.get(tenant_id, node["agent_id"])
        if not agent:
            raise ValueError(f"Agent {node['agent_id']} not found for node {node.get('name', '')}")

        # Execute and collect SSE response
        collected = []
        async for sse_line in self._agent_service.execute(
            agent=agent,
            user_message=message,
            tenant_id=tenant_id,
            thread_id=thread_id,
            user_id=user_id,
        ):
            if sse_line.startswith("data: "):
                try:
                    payload = json.loads(sse_line[6:].strip())
                    if payload.get("error"):
                        raise ValueError(f"Agent error: {payload['error']}")
                    content = payload.get("content", "")
                    if content and not payload.get("done"):
                        collected.append(content)
                except json.JSONDecodeError:
                    continue

        return "".join(collected)

    async def register_sub_agent_tools(
        self,
        workflow: dict,
        nodes: List[dict],
        tenant_id: str,
    ) -> List[dict]:
        tools = []
        for node in nodes:
            if node.get("node_type") != "sub_agent":
                continue
            agent = await _agent_repo.get(tenant_id, node["agent_id"])
            if not agent:
                continue
            safe_name = node.get("name", "").replace(" ", "_").replace("-", "_").lower()
            tools.append({
                "type": "function",
                "function": {
                    "name": f"delegate_to_{safe_name}",
                    "description": f"Delegate subtask to {agent.get('name', '')}: {agent.get('description') or 'No description'}",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "The message/task to send to this agent",
                            }
                        },
                        "required": ["message"],
                    },
                },
            })
        return tools

    @staticmethod
    def _find_edge(
        edges: List[dict],
        source_id: str,
        target_id: str,
    ) -> Optional[dict]:
        for edge in edges:
            if edge.get("source_node_id") == source_id and edge.get("target_node_id") == target_id:
                return edge
        return None

    @staticmethod
    def _apply_output_mapping(source_output: Optional[dict], mapping: Optional[dict]) -> str:
        if source_output is None:
            return ""
        if mapping is None:
            return source_output.get("response", "")
        parts = []
        for target_key, source_key in mapping.items():
            value = source_output.get(source_key, "")
            parts.append(f"{target_key}: {value}")
        return "\n".join(parts) if parts else source_output.get("response", "")
