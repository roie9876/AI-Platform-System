"""TestSuite, TestCase, EvaluationRun, and EvaluationResult repositories."""

from app.repositories.base import CosmosRepository


class TestSuiteRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("test_suites")

    async def list_by_agent(self, tenant_id: str, agent_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid",
            [{"name": "@tid", "value": tenant_id}, {"name": "@aid", "value": agent_id}],
        )


class TestCaseRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("test_cases")

    async def list_by_suite(self, tenant_id: str, suite_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.suite_id = @sid",
            [{"name": "@tid", "value": tenant_id}, {"name": "@sid", "value": suite_id}],
        )


class EvaluationRunRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("evaluation_runs")

    async def list_by_suite(self, tenant_id: str, suite_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.suite_id = @sid ORDER BY c.created_at DESC",
            [{"name": "@tid", "value": tenant_id}, {"name": "@sid", "value": suite_id}],
        )


class EvaluationResultRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("evaluation_results")

    async def list_by_run(self, tenant_id: str, run_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.run_id = @rid",
            [{"name": "@tid", "value": tenant_id}, {"name": "@rid", "value": run_id}],
        )
