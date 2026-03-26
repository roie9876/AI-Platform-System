from fastapi import APIRouter, Depends, HTTPException, Request

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.agent_repo import AgentRepository
from app.repositories.workflow_repo import (
    WorkflowRepository,
    WorkflowNodeRepository,
    WorkflowEdgeRepository,
    WorkflowExecutionRepository,
    WorkflowNodeExecutionRepository,
)
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

workflow_repo = WorkflowRepository()
node_repo = WorkflowNodeRepository()
edge_repo = WorkflowEdgeRepository()
execution_repo = WorkflowExecutionRepository()
node_execution_repo = WorkflowNodeExecutionRepository()
agent_repo = AgentRepository()


@router.post("", response_model=WorkflowDetailResponse, status_code=201)
async def create_workflow(
    body: WorkflowCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    workflow_data = {
        "name": body.name,
        "description": body.description,
        "workflow_type": body.workflow_type,
        "is_active": True,
        "created_by": current_user["user_id"],
    }
    workflow = await workflow_repo.create(tenant_id, workflow_data)

    created_nodes = []
    if body.nodes:
        for i, node_req in enumerate(body.nodes):
            agent = await agent_repo.get(tenant_id, str(node_req.agent_id))
            if not agent:
                raise HTTPException(status_code=400, detail=f"Agent {node_req.agent_id} not found in tenant")

            node_data = {
                "workflow_id": workflow["id"],
                "agent_id": str(node_req.agent_id),
                "name": node_req.name,
                "node_type": node_req.node_type,
                "position_x": node_req.position_x,
                "position_y": node_req.position_y,
                "config": node_req.config.model_dump() if node_req.config else None,
                "execution_order": node_req.execution_order if node_req.execution_order else i,
            }
            node = await node_repo.create(tenant_id, node_data)
            created_nodes.append(node)

    created_edges = []
    if body.edges and body.nodes:
        for edge_req in body.edges:
            edge_data = {
                "workflow_id": workflow["id"],
                "source_node_id": str(edge_req.source_node_id),
                "target_node_id": str(edge_req.target_node_id),
                "edge_type": edge_req.edge_type,
                "condition": edge_req.condition,
                "output_mapping": edge_req.output_mapping,
            }
            edge = await edge_repo.create(tenant_id, edge_data)
            created_edges.append(edge)

    return WorkflowDetailResponse(
        id=workflow["id"],
        name=workflow["name"],
        description=workflow.get("description"),
        workflow_type=workflow["workflow_type"],
        is_active=workflow.get("is_active", True),
        tenant_id=workflow["tenant_id"],
        created_by=workflow.get("created_by"),
        created_at=workflow["created_at"],
        updated_at=workflow["updated_at"],
        nodes=[WorkflowNodeResponse.model_validate(n) for n in created_nodes],
        edges=[WorkflowEdgeResponse.model_validate(e) for e in created_edges],
    )


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    workflows = await workflow_repo.list_by_tenant(tenant_id)
    return WorkflowListResponse(workflows=workflows, total=len(workflows))


@router.get("/{workflow_id}", response_model=WorkflowDetailResponse)
async def get_workflow(
    workflow_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    workflow = await workflow_repo.get(tenant_id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    nodes = await node_repo.list_by_workflow(tenant_id, workflow_id)
    edges = await edge_repo.list_by_workflow(tenant_id, workflow_id)

    return WorkflowDetailResponse(
        id=workflow["id"],
        name=workflow["name"],
        description=workflow.get("description"),
        workflow_type=workflow["workflow_type"],
        is_active=workflow.get("is_active", True),
        tenant_id=workflow["tenant_id"],
        created_by=workflow.get("created_by"),
        created_at=workflow["created_at"],
        updated_at=workflow["updated_at"],
        nodes=[WorkflowNodeResponse.model_validate(n) for n in nodes],
        edges=[WorkflowEdgeResponse.model_validate(e) for e in edges],
    )


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    body: WorkflowUpdateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    workflow = await workflow_repo.get(tenant_id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    workflow.update(update_data)
    updated = await workflow_repo.update(tenant_id, workflow_id, workflow)
    return WorkflowResponse.model_validate(updated)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    workflow = await workflow_repo.get(tenant_id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await workflow_repo.delete(tenant_id, workflow_id)


@router.post("/{workflow_id}/nodes", response_model=WorkflowNodeResponse, status_code=201)
async def add_node(
    workflow_id: str,
    body: WorkflowNodeCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    workflow = await workflow_repo.get(tenant_id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    agent = await agent_repo.get(tenant_id, str(body.agent_id))
    if not agent:
        raise HTTPException(status_code=400, detail=f"Agent {body.agent_id} not found in tenant")

    node_data = {
        "workflow_id": workflow_id,
        "agent_id": str(body.agent_id),
        "name": body.name,
        "node_type": body.node_type,
        "position_x": body.position_x,
        "position_y": body.position_y,
        "config": body.config.model_dump() if body.config else None,
        "execution_order": body.execution_order,
    }
    node = await node_repo.create(tenant_id, node_data)
    return WorkflowNodeResponse.model_validate(node)


@router.delete("/{workflow_id}/nodes/{node_id}", status_code=204)
async def delete_node(
    workflow_id: str,
    node_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    workflow = await workflow_repo.get(tenant_id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    node = await node_repo.get(tenant_id, node_id)
    if not node or node.get("workflow_id") != workflow_id:
        raise HTTPException(status_code=404, detail="Node not found")
    await node_repo.delete(tenant_id, node_id)


@router.post("/{workflow_id}/edges", response_model=WorkflowEdgeResponse, status_code=201)
async def add_edge(
    workflow_id: str,
    body: WorkflowEdgeCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    workflow = await workflow_repo.get(tenant_id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    for nid in [str(body.source_node_id), str(body.target_node_id)]:
        node = await node_repo.get(tenant_id, nid)
        if not node or node.get("workflow_id") != workflow_id:
            raise HTTPException(status_code=400, detail=f"Node {nid} not found in workflow")

    edge_data = {
        "workflow_id": workflow_id,
        "source_node_id": str(body.source_node_id),
        "target_node_id": str(body.target_node_id),
        "edge_type": body.edge_type,
        "condition": body.condition,
        "output_mapping": body.output_mapping,
    }
    edge = await edge_repo.create(tenant_id, edge_data)
    return WorkflowEdgeResponse.model_validate(edge)


@router.delete("/{workflow_id}/edges/{edge_id}", status_code=204)
async def delete_edge(
    workflow_id: str,
    edge_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    workflow = await workflow_repo.get(tenant_id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    edge = await edge_repo.get(tenant_id, edge_id)
    if not edge or edge.get("workflow_id") != workflow_id:
        raise HTTPException(status_code=404, detail="Edge not found")
    await edge_repo.delete(tenant_id, edge_id)


@router.get("/{workflow_id}/executions", response_model=WorkflowExecutionListResponse)
async def list_executions(
    workflow_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    workflow = await workflow_repo.get(tenant_id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    executions = await execution_repo.list_by_workflow(tenant_id, workflow_id)
    return WorkflowExecutionListResponse(executions=executions, total=len(executions))


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse, status_code=202)
async def execute_workflow(
    workflow_id: str,
    body: WorkflowExecuteRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    workflow = await workflow_repo.get(tenant_id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    nodes = await node_repo.list_by_workflow(tenant_id, workflow_id)
    if not nodes:
        raise HTTPException(status_code=400, detail="Workflow has no nodes")

    from app.services.workflow_engine import WorkflowEngine
    engine = WorkflowEngine()
    input_data = {"message": body.message, **(body.input_data or {})}
    execution = await engine.run(
        workflow_id=workflow_id,
        input_data=input_data,
        user_id=current_user["user_id"],
        tenant_id=tenant_id,
    )
    return execution


@router.get("/{workflow_id}/executions/{execution_id}", response_model=WorkflowExecutionDetailResponse)
async def get_execution_detail(
    workflow_id: str,
    execution_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    workflow = await workflow_repo.get(tenant_id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    execution = await execution_repo.get(tenant_id, execution_id)
    if not execution or execution.get("workflow_id") != workflow_id:
        raise HTTPException(status_code=404, detail="Execution not found")

    node_executions = await node_execution_repo.list_by_execution(tenant_id, execution_id)

    return WorkflowExecutionDetailResponse(
        id=execution["id"],
        workflow_id=execution["workflow_id"],
        status=execution["status"],
        started_at=execution.get("started_at"),
        completed_at=execution.get("completed_at"),
        input_data=execution.get("input_data"),
        output_data=execution.get("output_data"),
        error=execution.get("error"),
        tenant_id=execution["tenant_id"],
        triggered_by=execution.get("triggered_by"),
        thread_id=execution.get("thread_id"),
        created_at=execution["created_at"],
        updated_at=execution["updated_at"],
        node_executions=[WorkflowNodeExecutionResponse.model_validate(ne) for ne in node_executions],
    )


@router.post("/{workflow_id}/executions/{execution_id}/cancel", response_model=WorkflowExecutionResponse)
async def cancel_execution(
    workflow_id: str,
    execution_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    from datetime import datetime, timezone

    # Validate workflow belongs to tenant
    workflow = await workflow_repo.get(tenant_id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    execution = await execution_repo.get(tenant_id, execution_id)
    if not execution or execution.get("workflow_id") != workflow_id:
        raise HTTPException(status_code=404, detail="Execution not found")

    if execution.get("status") not in ("pending", "running"):
        raise HTTPException(status_code=400, detail="Execution is not running")

    execution["status"] = "cancelled"
    execution["completed_at"] = datetime.now(timezone.utc).isoformat()
    await execution_repo.update(tenant_id, execution_id, execution)

    # Cancel pending/running node executions
    node_execs = await node_execution_repo.query(
        tenant_id,
        "SELECT * FROM c WHERE c.tenant_id = @tid AND c.workflow_execution_id = @eid AND c.status IN ('pending', 'running')",
        [{"name": "@tid", "value": tenant_id}, {"name": "@eid", "value": execution_id}],
    )
    for ne in node_execs:
        ne["status"] = "cancelled"
        ne["completed_at"] = datetime.now(timezone.utc).isoformat()
        await node_execution_repo.update(tenant_id, ne["id"], ne)

    return execution
