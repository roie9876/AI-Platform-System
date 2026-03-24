import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.agent import Agent
from app.models.thread import Thread
from app.models.workflow import Workflow, WorkflowNode, WorkflowEdge
from app.models.workflow_execution import WorkflowExecution, WorkflowNodeExecution
from app.services.agent_execution import AgentExecutionService

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Executes multi-agent workflows with sequential, parallel, autonomous, and custom DAG modes."""

    def __init__(self) -> None:
        self._agent_service = AgentExecutionService()

    async def run(
        self,
        workflow_id: UUID,
        input_data: dict,
        user_id: UUID,
        tenant_id: UUID,
        db: AsyncSession,
    ) -> WorkflowExecution:
        # Load workflow
        result = await db.execute(
            select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
        )
        workflow = result.scalar_one_or_none()
        if not workflow:
            raise ValueError("Workflow not found")

        # Load nodes and edges
        nodes_result = await db.execute(
            select(WorkflowNode)
            .where(WorkflowNode.workflow_id == workflow_id)
            .order_by(WorkflowNode.execution_order)
        )
        nodes = list(nodes_result.scalars().all())
        if not nodes:
            raise ValueError("Workflow has no nodes")

        edges_result = await db.execute(
            select(WorkflowEdge).where(WorkflowEdge.workflow_id == workflow_id)
        )
        edges = list(edges_result.scalars().all())

        # Create shared thread for cross-agent context
        thread = Thread(
            title=f"Workflow: {workflow.name}",
            agent_id=nodes[0].agent_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )
        db.add(thread)
        await db.flush()

        # Create execution record
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            status="running",
            started_at=datetime.now(timezone.utc),
            input_data=input_data,
            tenant_id=tenant_id,
            triggered_by=user_id,
            thread_id=thread.id,
        )
        db.add(execution)
        await db.flush()
        await db.commit()

        try:
            dispatch = {
                "sequential": self._execute_sequential,
                "parallel": self._execute_parallel,
                "autonomous": self._execute_autonomous,
                "custom": self._execute_custom,
            }
            handler = dispatch.get(workflow.workflow_type, self._execute_sequential)
            output = await handler(
                nodes=nodes,
                edges=edges,
                execution=execution,
                input_data=input_data,
                user_id=user_id,
                tenant_id=tenant_id,
                thread_id=thread.id,
                db=db,
            )

            execution.status = "completed"
            execution.completed_at = datetime.now(timezone.utc)
            execution.output_data = output
            await db.commit()
        except Exception as e:
            execution.status = "failed"
            execution.completed_at = datetime.now(timezone.utc)
            execution.error = str(e)
            await db.commit()
            logger.error("Workflow execution failed: %s", e, exc_info=True)

        await db.refresh(execution)
        return execution

    async def _execute_sequential(
        self,
        nodes: List[WorkflowNode],
        edges: List[WorkflowEdge],
        execution: WorkflowExecution,
        input_data: dict,
        user_id: UUID,
        tenant_id: UUID,
        thread_id: UUID,
        db: AsyncSession,
    ) -> dict:
        previous_output: Optional[dict] = None
        last_output: dict = {}

        for i, node in enumerate(nodes):
            node_exec = WorkflowNodeExecution(
                workflow_execution_id=execution.id,
                node_id=node.id,
                agent_id=node.agent_id,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            db.add(node_exec)
            await db.flush()

            # Build message
            if i == 0:
                message = input_data.get("message", "")
            else:
                # Apply output mapping from connecting edge
                edge = self._find_edge(edges, nodes[i - 1].id, node.id)
                message = self._apply_output_mapping(previous_output, edge.output_mapping if edge else None)

            node_exec.input_data = {"message": message}

            try:
                response_text = await self._execute_node(
                    node=node,
                    message=message,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    thread_id=thread_id,
                    db=db,
                )
                node_exec.status = "completed"
                node_exec.completed_at = datetime.now(timezone.utc)
                node_exec.output_data = {"response": response_text}
                previous_output = {"response": response_text}
                last_output = {"response": response_text}
                await db.commit()
            except Exception as e:
                node_exec.status = "failed"
                node_exec.completed_at = datetime.now(timezone.utc)
                node_exec.error = str(e)
                await db.commit()
                raise

        return last_output

    async def _execute_parallel(
        self,
        nodes: List[WorkflowNode],
        edges: List[WorkflowEdge],
        execution: WorkflowExecution,
        input_data: dict,
        user_id: UUID,
        tenant_id: UUID,
        thread_id: UUID,
        db: AsyncSession,
    ) -> dict:
        message = input_data.get("message", "")

        # Create node execution records
        node_execs: List[WorkflowNodeExecution] = []
        for node in nodes:
            node_exec = WorkflowNodeExecution(
                workflow_execution_id=execution.id,
                node_id=node.id,
                agent_id=node.agent_id,
                status="running",
                started_at=datetime.now(timezone.utc),
                input_data={"message": message},
            )
            db.add(node_exec)
            node_execs.append(node_exec)
        await db.flush()
        await db.commit()

        # Execute all nodes concurrently — each gets its own session
        async def run_node(node: WorkflowNode, node_exec: WorkflowNodeExecution) -> dict:
            async with async_session() as session:
                try:
                    response_text = await self._execute_node(
                        node=node,
                        message=message,
                        user_id=user_id,
                        tenant_id=tenant_id,
                        thread_id=thread_id,
                        db=session,
                    )
                    return {"node_id": str(node.id), "node_name": node.name, "response": response_text, "status": "completed"}
                except Exception as e:
                    return {"node_id": str(node.id), "node_name": node.name, "error": str(e), "status": "failed"}

        tasks = [run_node(node, node_exec) for node, node_exec in zip(nodes, node_execs)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Update node execution records
        aggregated = []
        for node_exec, result in zip(node_execs, results):
            if isinstance(result, Exception):
                node_exec.status = "failed"
                node_exec.error = str(result)
                node_exec.completed_at = datetime.now(timezone.utc)
                aggregated.append({"node_id": str(node_exec.node_id), "error": str(result), "status": "failed"})
            else:
                node_exec.status = result.get("status", "completed")
                node_exec.completed_at = datetime.now(timezone.utc)
                if result.get("status") == "completed":
                    node_exec.output_data = {"response": result.get("response", "")}
                else:
                    node_exec.error = result.get("error", "")
                aggregated.append(result)
        await db.commit()

        return {"results": aggregated}

    async def _execute_autonomous(
        self,
        nodes: List[WorkflowNode],
        edges: List[WorkflowEdge],
        execution: WorkflowExecution,
        input_data: dict,
        user_id: UUID,
        tenant_id: UUID,
        thread_id: UUID,
        db: AsyncSession,
    ) -> dict:
        # Build agent descriptions for the router
        agent_descriptions = []
        for node in nodes:
            agent_result = await db.execute(select(Agent).where(Agent.id == node.agent_id))
            agent = agent_result.scalar_one_or_none()
            if agent:
                agent_descriptions.append({
                    "node_id": str(node.id),
                    "agent_id": str(node.agent_id),
                    "name": node.name,
                    "description": agent.description or "No description",
                })

        # Find router node or use first node
        router_node = next((n for n in nodes if n.node_type == "router"), nodes[0])

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
        router_exec = WorkflowNodeExecution(
            workflow_execution_id=execution.id,
            node_id=router_node.id,
            agent_id=router_node.agent_id,
            status="running",
            started_at=datetime.now(timezone.utc),
            input_data={"message": router_prompt},
        )
        db.add(router_exec)
        await db.flush()

        try:
            router_response = await self._execute_node(
                node=router_node,
                message=router_prompt,
                user_id=user_id,
                tenant_id=tenant_id,
                thread_id=thread_id,
                db=db,
            )
            router_exec.status = "completed"
            router_exec.completed_at = datetime.now(timezone.utc)
            router_exec.output_data = {"response": router_response}
            await db.commit()
        except Exception as e:
            router_exec.status = "failed"
            router_exec.completed_at = datetime.now(timezone.utc)
            router_exec.error = str(e)
            await db.commit()
            raise

        # Parse plan from router response
        try:
            # Try to extract JSON from the response
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
                thread_id=thread_id, db=db,
            )

        # Execute each step
        node_map = {str(n.agent_id): n for n in nodes}
        results = []
        for step in steps:
            agent_id = step.get("agent_id", "")
            step_message = step.get("message", input_data.get("message", ""))
            node = node_map.get(agent_id)
            if not node:
                results.append({"agent_id": agent_id, "error": "Agent not found in workflow", "status": "skipped"})
                continue

            step_exec = WorkflowNodeExecution(
                workflow_execution_id=execution.id,
                node_id=node.id,
                agent_id=node.agent_id,
                status="running",
                started_at=datetime.now(timezone.utc),
                input_data={"message": step_message},
            )
            db.add(step_exec)
            await db.flush()

            try:
                response = await self._execute_node(
                    node=node, message=step_message,
                    user_id=user_id, tenant_id=tenant_id,
                    thread_id=thread_id, db=db,
                )
                step_exec.status = "completed"
                step_exec.completed_at = datetime.now(timezone.utc)
                step_exec.output_data = {"response": response}
                results.append({"node_name": node.name, "response": response, "status": "completed"})
                await db.commit()
            except Exception as e:
                step_exec.status = "failed"
                step_exec.completed_at = datetime.now(timezone.utc)
                step_exec.error = str(e)
                results.append({"node_name": node.name, "error": str(e), "status": "failed"})
                await db.commit()

        return {"results": results}

    async def _execute_custom(
        self,
        nodes: List[WorkflowNode],
        edges: List[WorkflowEdge],
        execution: WorkflowExecution,
        input_data: dict,
        user_id: UUID,
        tenant_id: UUID,
        thread_id: UUID,
        db: AsyncSession,
    ) -> dict:
        # Build adjacency and find root nodes (no incoming edges)
        node_map = {node.id: node for node in nodes}
        incoming: Dict[UUID, List[WorkflowEdge]] = {n.id: [] for n in nodes}
        outgoing: Dict[UUID, List[WorkflowEdge]] = {n.id: [] for n in nodes}
        for edge in edges:
            incoming[edge.target_node_id].append(edge)
            outgoing[edge.source_node_id].append(edge)

        # Topological sort using Kahn's algorithm
        in_degree = {n.id: len(incoming[n.id]) for n in nodes}
        levels: List[List[UUID]] = []
        queue = [nid for nid, deg in in_degree.items() if deg == 0]

        while queue:
            levels.append(list(queue))
            next_queue: List[UUID] = []
            for nid in queue:
                for edge in outgoing[nid]:
                    in_degree[edge.target_node_id] -= 1
                    if in_degree[edge.target_node_id] == 0:
                        next_queue.append(edge.target_node_id)
            queue = next_queue

        # Execute level by level
        node_outputs: Dict[UUID, dict] = {}
        terminal_outputs: List[dict] = []

        for level in levels:
            # Nodes at same depth run in parallel
            async def run_level_node(nid: UUID) -> None:
                node = node_map[nid]
                in_edges = incoming[nid]

                # Determine message
                if not in_edges:
                    message = input_data.get("message", "")
                else:
                    # Pick from first successful source
                    message = ""
                    for edge in in_edges:
                        source_output = node_outputs.get(edge.source_node_id)
                        if source_output is None:
                            continue

                        # Check conditional edges
                        if edge.edge_type == "conditional" and edge.condition:
                            key = edge.condition.get("key", "")
                            value = edge.condition.get("value", "")
                            if source_output.get(key) != value:
                                continue
                        elif edge.edge_type == "error":
                            # Only follow error edges if source failed
                            if source_output.get("status") != "failed":
                                continue

                        message = self._apply_output_mapping(source_output, edge.output_mapping)
                        break

                node_exec = WorkflowNodeExecution(
                    workflow_execution_id=execution.id,
                    node_id=node.id,
                    agent_id=node.agent_id,
                    status="running",
                    started_at=datetime.now(timezone.utc),
                    input_data={"message": message},
                )
                db.add(node_exec)
                await db.flush()

                try:
                    response = await self._execute_node(
                        node=node, message=message,
                        user_id=user_id, tenant_id=tenant_id,
                        thread_id=thread_id, db=db,
                    )
                    node_exec.status = "completed"
                    node_exec.completed_at = datetime.now(timezone.utc)
                    node_exec.output_data = {"response": response}
                    node_outputs[nid] = {"response": response, "status": "completed"}
                    await db.commit()
                except Exception as e:
                    node_exec.status = "failed"
                    node_exec.completed_at = datetime.now(timezone.utc)
                    node_exec.error = str(e)
                    node_outputs[nid] = {"error": str(e), "status": "failed"}
                    await db.commit()

            # Run nodes at this level
            if len(level) == 1:
                await run_level_node(level[0])
            else:
                await asyncio.gather(*(run_level_node(nid) for nid in level))

        # Collect terminal node outputs (nodes with no outgoing edges)
        for node in nodes:
            if not outgoing[node.id]:
                output = node_outputs.get(node.id, {})
                terminal_outputs.append({"node_name": node.name, **output})

        if len(terminal_outputs) == 1:
            return terminal_outputs[0]
        return {"results": terminal_outputs}

    async def _execute_node(
        self,
        node: WorkflowNode,
        message: str,
        user_id: UUID,
        tenant_id: UUID,
        thread_id: UUID,
        db: AsyncSession,
    ) -> str:
        # Load agent
        result = await db.execute(select(Agent).where(Agent.id == node.agent_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise ValueError(f"Agent {node.agent_id} not found for node {node.name}")

        # Execute and collect SSE response
        collected = []
        async for sse_line in self._agent_service.execute(
            agent=agent,
            user_message=message,
            db=db,
            thread_id=thread_id,
            user_id=user_id,
        ):
            # Parse SSE format: data: {"content": "...", "done": false}\n\n
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
        workflow: Workflow,
        nodes: List[WorkflowNode],
        db: AsyncSession,
    ) -> List[dict]:
        tools = []
        for node in nodes:
            if node.node_type != "sub_agent":
                continue
            agent_result = await db.execute(select(Agent).where(Agent.id == node.agent_id))
            agent = agent_result.scalar_one_or_none()
            if not agent:
                continue
            safe_name = node.name.replace(" ", "_").replace("-", "_").lower()
            tools.append({
                "type": "function",
                "function": {
                    "name": f"delegate_to_{safe_name}",
                    "description": f"Delegate subtask to {agent.name}: {agent.description or 'No description'}",
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
        edges: List[WorkflowEdge],
        source_id: UUID,
        target_id: UUID,
    ) -> Optional[WorkflowEdge]:
        for edge in edges:
            if edge.source_node_id == source_id and edge.target_node_id == target_id:
                return edge
        return None

    @staticmethod
    def _apply_output_mapping(source_output: Optional[dict], mapping: Optional[dict]) -> str:
        if source_output is None:
            return ""
        if mapping is None:
            return source_output.get("response", "")
        # Apply key mapping
        parts = []
        for target_key, source_key in mapping.items():
            value = source_output.get(source_key, "")
            parts.append(f"{target_key}: {value}")
        return "\n".join(parts) if parts else source_output.get("response", "")
