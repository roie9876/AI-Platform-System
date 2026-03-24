from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.agent import Agent
from app.models.workflow import Workflow, WorkflowNode, WorkflowEdge
from app.models.workflow_execution import WorkflowExecution, WorkflowNodeExecution
from app.api.v1.schemas import (
    WorkflowCreateRequest,
    WorkflowUpdateRequest,
    WorkflowResponse,
    WorkflowDetailResponse,
    WorkflowListResponse,
    WorkflowNodeCreateRequest,
    WorkflowNodeResponse,
    WorkflowEdgeCreateRequest,
    WorkflowEdgeResponse,
    WorkflowExecutionResponse,
    WorkflowExecutionListResponse,
    WorkflowExecutionDetailResponse,
    WorkflowNodeExecutionResponse,
    WorkflowExecuteRequest,
)

router = APIRouter()


@router.post("/", response_model=WorkflowDetailResponse, status_code=201)
async def create_workflow(
    body: WorkflowCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    workflow = Workflow(
        name=body.name,
        description=body.description,
        workflow_type=body.workflow_type,
        tenant_id=tenant_id,
        created_by=current_user.id,
    )
    db.add(workflow)
    await db.flush()

    created_nodes = []
    node_id_map: dict[str, UUID] = {}

    if body.nodes:
        for i, node_req in enumerate(body.nodes):
            # Validate agent exists in tenant
            agent_result = await db.execute(
                select(Agent).where(Agent.id == node_req.agent_id, Agent.tenant_id == tenant_id)
            )
            if not agent_result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail=f"Agent {node_req.agent_id} not found in tenant")

            node = WorkflowNode(
                workflow_id=workflow.id,
                agent_id=node_req.agent_id,
                name=node_req.name,
                node_type=node_req.node_type,
                position_x=node_req.position_x,
                position_y=node_req.position_y,
                config=node_req.config.model_dump() if node_req.config else None,
                execution_order=node_req.execution_order if node_req.execution_order else i,
            )
            db.add(node)
            await db.flush()
            created_nodes.append(node)
            node_id_map[str(node_req.agent_id) + str(i)] = node.id

    created_edges = []
    if body.edges and body.nodes:
        for edge_req in body.edges:
            edge = WorkflowEdge(
                workflow_id=workflow.id,
                source_node_id=edge_req.source_node_id,
                target_node_id=edge_req.target_node_id,
                edge_type=edge_req.edge_type,
                condition=edge_req.condition,
                output_mapping=edge_req.output_mapping,
            )
            db.add(edge)
            await db.flush()
            created_edges.append(edge)

    await db.refresh(workflow)
    return WorkflowDetailResponse(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        workflow_type=workflow.workflow_type,
        is_active=workflow.is_active,
        tenant_id=workflow.tenant_id,
        created_by=workflow.created_by,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        nodes=[WorkflowNodeResponse.model_validate(n) for n in created_nodes],
        edges=[WorkflowEdgeResponse.model_validate(e) for e in created_edges],
    )


@router.get("/", response_model=WorkflowListResponse)
async def list_workflows(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Workflow).where(Workflow.tenant_id == tenant_id).order_by(Workflow.created_at.desc())
    )
    workflows = list(result.scalars().all())
    return WorkflowListResponse(workflows=workflows, total=len(workflows))


@router.get("/{workflow_id}", response_model=WorkflowDetailResponse)
async def get_workflow(
    workflow_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    nodes_result = await db.execute(
        select(WorkflowNode)
        .where(WorkflowNode.workflow_id == workflow_id)
        .order_by(WorkflowNode.execution_order)
    )
    nodes = list(nodes_result.scalars().all())

    edges_result = await db.execute(
        select(WorkflowEdge).where(WorkflowEdge.workflow_id == workflow_id)
    )
    edges = list(edges_result.scalars().all())

    return WorkflowDetailResponse(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        workflow_type=workflow.workflow_type,
        is_active=workflow.is_active,
        tenant_id=workflow.tenant_id,
        created_by=workflow.created_by,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        nodes=[WorkflowNodeResponse.model_validate(n) for n in nodes],
        edges=[WorkflowEdgeResponse.model_validate(e) for e in edges],
    )


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    body: WorkflowUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    for field, value in update_data.items():
        setattr(workflow, field, value)

    await db.flush()
    await db.refresh(workflow)
    return workflow


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await db.delete(workflow)
    await db.flush()


@router.post("/{workflow_id}/nodes", response_model=WorkflowNodeResponse, status_code=201)
async def add_node(
    workflow_id: UUID,
    body: WorkflowNodeCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    # Validate workflow exists and belongs to tenant
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Validate agent exists in tenant
    agent_result = await db.execute(
        select(Agent).where(Agent.id == body.agent_id, Agent.tenant_id == tenant_id)
    )
    if not agent_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Agent {body.agent_id} not found in tenant")

    node = WorkflowNode(
        workflow_id=workflow_id,
        agent_id=body.agent_id,
        name=body.name,
        node_type=body.node_type,
        position_x=body.position_x,
        position_y=body.position_y,
        config=body.config.model_dump() if body.config else None,
        execution_order=body.execution_order,
    )
    db.add(node)
    await db.flush()
    await db.refresh(node)
    return node


@router.delete("/{workflow_id}/nodes/{node_id}", status_code=204)
async def delete_node(
    workflow_id: UUID,
    node_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    # Validate workflow belongs to tenant
    wf_result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
    )
    if not wf_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    result = await db.execute(
        select(WorkflowNode).where(WorkflowNode.id == node_id, WorkflowNode.workflow_id == workflow_id)
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    await db.delete(node)
    await db.flush()


@router.post("/{workflow_id}/edges", response_model=WorkflowEdgeResponse, status_code=201)
async def add_edge(
    workflow_id: UUID,
    body: WorkflowEdgeCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    # Validate workflow belongs to tenant
    wf_result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
    )
    if not wf_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Validate both nodes belong to this workflow
    for nid in [body.source_node_id, body.target_node_id]:
        node_result = await db.execute(
            select(WorkflowNode).where(WorkflowNode.id == nid, WorkflowNode.workflow_id == workflow_id)
        )
        if not node_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Node {nid} not found in workflow")

    edge = WorkflowEdge(
        workflow_id=workflow_id,
        source_node_id=body.source_node_id,
        target_node_id=body.target_node_id,
        edge_type=body.edge_type,
        condition=body.condition,
        output_mapping=body.output_mapping,
    )
    db.add(edge)
    await db.flush()
    await db.refresh(edge)
    return edge


@router.delete("/{workflow_id}/edges/{edge_id}", status_code=204)
async def delete_edge(
    workflow_id: UUID,
    edge_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    # Validate workflow belongs to tenant
    wf_result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
    )
    if not wf_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    result = await db.execute(
        select(WorkflowEdge).where(WorkflowEdge.id == edge_id, WorkflowEdge.workflow_id == workflow_id)
    )
    edge = result.scalar_one_or_none()
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    await db.delete(edge)
    await db.flush()


@router.get("/{workflow_id}/executions", response_model=WorkflowExecutionListResponse)
async def list_executions(
    workflow_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    # Validate workflow belongs to tenant
    wf_result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
    )
    if not wf_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    result = await db.execute(
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == workflow_id, WorkflowExecution.tenant_id == tenant_id)
        .order_by(WorkflowExecution.created_at.desc())
    )
    executions = list(result.scalars().all())
    return WorkflowExecutionListResponse(executions=executions, total=len(executions))


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse, status_code=202)
async def execute_workflow(
    workflow_id: UUID,
    body: WorkflowExecuteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    # Validate workflow exists and belongs to tenant
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Validate workflow has nodes
    nodes_result = await db.execute(
        select(WorkflowNode).where(WorkflowNode.workflow_id == workflow_id)
    )
    if not list(nodes_result.scalars().all()):
        raise HTTPException(status_code=400, detail="Workflow has no nodes")

    from app.services.workflow_engine import WorkflowEngine
    engine = WorkflowEngine()
    input_data = {"message": body.message, **(body.input_data or {})}
    execution = await engine.run(
        workflow_id=workflow_id,
        input_data=input_data,
        user_id=current_user.id,
        tenant_id=tenant_id,
        db=db,
    )
    return execution


@router.get("/{workflow_id}/executions/{execution_id}", response_model=WorkflowExecutionDetailResponse)
async def get_execution_detail(
    workflow_id: UUID,
    execution_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    # Validate workflow belongs to tenant
    wf_result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
    )
    if not wf_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    result = await db.execute(
        select(WorkflowExecution).where(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.workflow_id == workflow_id,
            WorkflowExecution.tenant_id == tenant_id,
        )
    )
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    node_execs_result = await db.execute(
        select(WorkflowNodeExecution)
        .where(WorkflowNodeExecution.workflow_execution_id == execution_id)
        .order_by(WorkflowNodeExecution.started_at)
    )
    node_executions = list(node_execs_result.scalars().all())

    return WorkflowExecutionDetailResponse(
        id=execution.id,
        workflow_id=execution.workflow_id,
        status=execution.status,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        input_data=execution.input_data,
        output_data=execution.output_data,
        error=execution.error,
        tenant_id=execution.tenant_id,
        triggered_by=execution.triggered_by,
        thread_id=execution.thread_id,
        created_at=execution.created_at,
        updated_at=execution.updated_at,
        node_executions=[WorkflowNodeExecutionResponse.model_validate(ne) for ne in node_executions],
    )


@router.post("/{workflow_id}/executions/{execution_id}/cancel", response_model=WorkflowExecutionResponse)
async def cancel_execution(
    workflow_id: UUID,
    execution_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    from datetime import datetime, timezone

    # Validate workflow belongs to tenant
    wf_result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == tenant_id)
    )
    if not wf_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    result = await db.execute(
        select(WorkflowExecution).where(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.workflow_id == workflow_id,
            WorkflowExecution.tenant_id == tenant_id,
        )
    )
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    if execution.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail="Execution is not running")

    execution.status = "cancelled"
    execution.completed_at = datetime.now(timezone.utc)

    # Cancel pending/running node executions
    node_execs_result = await db.execute(
        select(WorkflowNodeExecution).where(
            WorkflowNodeExecution.workflow_execution_id == execution_id,
            WorkflowNodeExecution.status.in_(["pending", "running"]),
        )
    )
    for ne in node_execs_result.scalars().all():
        ne.status = "cancelled"
        ne.completed_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(execution)
    return execution
