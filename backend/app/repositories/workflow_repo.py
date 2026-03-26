"""Workflow, WorkflowNode, WorkflowEdge, WorkflowExecution, and WorkflowNodeExecution repositories."""

from app.repositories.base import CosmosRepository


class WorkflowRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("workflows")

    async def list_by_tenant(self, tenant_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid ORDER BY c.created_at DESC",
            [{"name": "@tid", "value": tenant_id}],
        )


class WorkflowNodeRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("workflow_nodes")

    async def list_by_workflow(self, tenant_id: str, workflow_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.workflow_id = @wid",
            [{"name": "@tid", "value": tenant_id}, {"name": "@wid", "value": workflow_id}],
        )


class WorkflowEdgeRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("workflow_edges")

    async def list_by_workflow(self, tenant_id: str, workflow_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.workflow_id = @wid",
            [{"name": "@tid", "value": tenant_id}, {"name": "@wid", "value": workflow_id}],
        )


class WorkflowExecutionRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("workflow_executions")

    async def list_by_workflow(self, tenant_id: str, workflow_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.workflow_id = @wid ORDER BY c.created_at DESC",
            [{"name": "@tid", "value": tenant_id}, {"name": "@wid", "value": workflow_id}],
        )


class WorkflowNodeExecutionRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("workflow_node_executions")

    async def list_by_execution(self, tenant_id: str, execution_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.execution_id = @eid ORDER BY c.created_at ASC",
            [{"name": "@tid", "value": tenant_id}, {"name": "@eid", "value": execution_id}],
        )
