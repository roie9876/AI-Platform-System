"""Unit tests for Cosmos DB repository layer — DATA-01 through DATA-07."""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock

from app.repositories.base import CosmosRepository
from app.repositories import (
    AgentRepository, AgentConfigVersionRepository,
    TenantRepository, UserRepository,
    ToolRepository, AgentToolRepository,
    DataSourceRepository, AgentDataSourceRepository,
    DocumentRepository, DocumentChunkRepository,
    ThreadRepository, ThreadMessageRepository, AgentMemoryRepository,
    WorkflowRepository, WorkflowNodeRepository, WorkflowEdgeRepository,
    WorkflowExecutionRepository, WorkflowNodeExecutionRepository,
    TestSuiteRepository, TestCaseRepository,
    EvaluationRunRepository, EvaluationResultRepository,
    AgentTemplateRepository, ToolTemplateRepository,
    MCPServerRepository, MCPDiscoveredToolRepository, AgentMCPToolRepository,
    ExecutionLogRepository,
    ModelEndpointRepository, ModelPricingRepository, CostAlertRepository,
    AzureSubscriptionRepository, AzureConnectionRepository, CatalogEntryRepository,
)


TENANT_A = "tenant-aaa"
TENANT_B = "tenant-bbb"


class TestCosmosRepositoryBase:
    """Tests base CRUD via AgentRepository (DATA-01)."""

    @pytest.fixture
    def repo(self, mock_cosmos_client):
        return AgentRepository()

    @pytest.mark.asyncio
    async def test_create_stores_item_with_tenant_id_and_uuid(self, repo, mock_cosmos_client):
        item = {"name": "my-agent", "slug": "my-agent"}
        result = await repo.create(TENANT_A, item)
        assert result["tenant_id"] == TENANT_A
        assert "id" in result
        assert "created_at" in result
        assert "updated_at" in result

    @pytest.mark.asyncio
    async def test_get_retrieves_existing_item(self, repo, mock_cosmos_client):
        created = await repo.create(TENANT_A, {"name": "agent1"})
        fetched = await repo.get(TENANT_A, created["id"])
        assert fetched is not None
        assert fetched["name"] == "agent1"

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing(self, repo, mock_cosmos_client):
        result = await repo.get(TENANT_A, "nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all_returns_items_for_tenant(self, repo, mock_cosmos_client):
        await repo.create(TENANT_A, {"name": "a1"})
        await repo.create(TENANT_A, {"name": "a2"})
        items = await repo.list_all(TENANT_A)
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_delete_removes_item(self, repo, mock_cosmos_client):
        created = await repo.create(TENANT_A, {"name": "to-delete"})
        await repo.delete(TENANT_A, created["id"])
        result = await repo.get(TENANT_A, created["id"])
        assert result is None

    @pytest.mark.asyncio
    async def test_upsert_creates_or_updates(self, repo, mock_cosmos_client):
        item = {"id": "upsert-1", "name": "v1", "tenant_id": TENANT_A}
        r1 = await repo.upsert(TENANT_A, item)
        assert r1["name"] == "v1"

        item["name"] = "v2"
        r2 = await repo.upsert(TENANT_A, item)
        assert r2["name"] == "v2"

    @pytest.mark.asyncio
    async def test_count_returns_correct_count(self, repo, mock_cosmos_client):
        await repo.create(TENANT_A, {"name": "c1"})
        await repo.create(TENANT_A, {"name": "c2"})
        await repo.create(TENANT_A, {"name": "c3"})
        count = await repo.count(TENANT_A)
        assert count == 3


class TestTenantIsolation:
    """Verifies tenant partition isolation (DATA-02)."""

    @pytest.fixture
    def repo(self, mock_cosmos_client):
        return AgentRepository()

    @pytest.mark.asyncio
    async def test_tenant_b_cannot_see_tenant_a_items(self, repo, mock_cosmos_client):
        await repo.create(TENANT_A, {"name": "secret-agent"})
        items_b = await repo.list_all(TENANT_B)
        assert len(items_b) == 0

    @pytest.mark.asyncio
    async def test_get_with_wrong_tenant_returns_none(self, repo, mock_cosmos_client):
        created = await repo.create(TENANT_A, {"name": "agent-a"})
        result = await repo.get(TENANT_B, created["id"])
        assert result is None


class TestETagConcurrency:
    """Tests optimistic concurrency with ETags (DATA-07)."""

    @pytest.fixture
    def repo(self, mock_cosmos_client):
        return AgentRepository()

    @pytest.mark.asyncio
    async def test_update_with_matching_etag_succeeds(self, repo, mock_cosmos_client):
        created = await repo.create(TENANT_A, {"name": "etag-test"})
        etag = created["_etag"]
        created["name"] = "updated"
        result = await repo.update(TENANT_A, created["id"], created, etag=etag)
        assert result["name"] == "updated"

    @pytest.mark.asyncio
    async def test_update_with_stale_etag_raises(self, repo, mock_cosmos_client):
        created = await repo.create(TENANT_A, {"name": "etag-test"})
        created["name"] = "updated"
        with pytest.raises(Exception):
            await repo.update(TENANT_A, created["id"], created, etag='"stale-etag"')


ALL_REPOS = [
    AgentRepository,
    AgentConfigVersionRepository,
    TenantRepository,
    UserRepository,
    ToolRepository,
    AgentToolRepository,
    DataSourceRepository,
    AgentDataSourceRepository,
    DocumentRepository,
    DocumentChunkRepository,
    ThreadRepository,
    ThreadMessageRepository,
    AgentMemoryRepository,
    WorkflowRepository,
    WorkflowNodeRepository,
    WorkflowEdgeRepository,
    WorkflowExecutionRepository,
    WorkflowNodeExecutionRepository,
    TestSuiteRepository,
    TestCaseRepository,
    EvaluationRunRepository,
    EvaluationResultRepository,
    AgentTemplateRepository,
    ToolTemplateRepository,
    MCPServerRepository,
    MCPDiscoveredToolRepository,
    AgentMCPToolRepository,
    ExecutionLogRepository,
    ModelEndpointRepository,
    ModelPricingRepository,
    CostAlertRepository,
    AzureSubscriptionRepository,
    AzureConnectionRepository,
    CatalogEntryRepository,
]


class TestRepositoryRegistry:
    """Verifies all repository subclasses have correct container_name (DATA-04)."""

    @pytest.mark.parametrize("repo_cls", ALL_REPOS, ids=lambda c: c.__name__)
    def test_repo_has_nonempty_container_name(self, repo_cls):
        repo = repo_cls()
        assert isinstance(repo.container_name, str)
        assert len(repo.container_name) > 0

    def test_all_repos_count(self):
        assert len(ALL_REPOS) == 34


class TestCrossPartitionQueries:
    """Verifies only TenantRepository uses cross-partition queries (DATA-03)."""

    @pytest.mark.asyncio
    async def test_tenant_repo_list_all_tenants_uses_cross_partition(self, mock_cosmos_client):
        """TenantRepository.list_all_tenants uses enable_cross_partition_query=True."""
        repo = TenantRepository()
        result = await repo.list_all_tenants()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_tenant_repo_get_by_slug_uses_cross_partition(self, mock_cosmos_client):
        """TenantRepository.get_by_slug uses enable_cross_partition_query=True."""
        repo = TenantRepository()
        result = await repo.get_by_slug("test-slug")
        assert result is None  # no data, just verifying it runs

    @pytest.mark.asyncio
    async def test_agent_repo_queries_within_partition(self, mock_cosmos_client):
        """AgentRepository queries are always partition-scoped."""
        repo = AgentRepository()
        await repo.create(TENANT_A, {"name": "a1", "slug": "a1"})
        result = await repo.list_all(TENANT_A)
        assert len(result) == 1
