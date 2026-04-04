"""Tests for LLM Token Proxy — repository, proxy URL injection, and usage API."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.repositories.token_log_repository import TokenLogRepository


@pytest.fixture
def mock_container():
    """Mock Cosmos container for token_logs."""
    container = AsyncMock()
    container.create_item = AsyncMock(side_effect=lambda body, **kw: body)
    return container


@pytest.fixture
def token_repo(mock_container):
    repo = TokenLogRepository()
    repo._container = AsyncMock(return_value=mock_container)
    return repo


class TestTokenLogRepository:
    @pytest.mark.asyncio
    async def test_log_usage_creates_document(self, token_repo, mock_container):
        doc = {
            "id": "test-id",
            "tenant_id": "tenant-1",
            "agent_id": "agent-1",
            "model": "gpt-4.1",
            "total_tokens": 150,
            "prompt_tokens": 100,
            "completion_tokens": 50,
        }
        result = await token_repo.log_usage("tenant-1", doc)
        mock_container.create_item.assert_called_once()
        assert result["total_tokens"] == 150

    @pytest.mark.asyncio
    async def test_get_usage_by_date_range(self, token_repo, mock_container):
        mock_container.query_items = MagicMock(return_value=AsyncIteratorMock([
            {"id": "1", "tenant_id": "t1", "total_tokens": 100},
        ]))
        results = await token_repo.get_usage_by_date_range(
            "t1", "2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"
        )
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_tenant_total_tokens(self, token_repo, mock_container):
        mock_container.query_items = MagicMock(return_value=AsyncIteratorMock([500]))
        total = await token_repo.get_tenant_total_tokens(
            "t1", "2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"
        )
        assert total == 500


class TestProxyUrlInjection:
    def test_proxy_url_injected_in_deploy(self):
        """Verify openclaw_service.py contains proxy URL injection code."""
        svc_path = Path(__file__).resolve().parent.parent / "app" / "services" / "openclaw_service.py"
        content = svc_path.read_text()
        assert "TOKEN_PROXY_URL" in content
        assert "token-proxy.aiplatform.svc:8080" in content
        assert "/proxy/{tenant_slug}/{agent_id}/openai/v1" in content

    def test_proxy_url_in_both_deploy_and_update(self):
        """Both deploy and update methods inject proxy URL."""
        svc_path = Path(__file__).resolve().parent.parent / "app" / "services" / "openclaw_service.py"
        content = svc_path.read_text()
        # Should appear twice — once in deploy_openclaw_instance, once in update_agent
        assert content.count("TOKEN_PROXY_URL") >= 2


class TestTokenUsageApi:
    def test_router_has_routes(self):
        from app.api.v1.token_usage import router
        route_paths = [r.path for r in router.routes]
        assert "/token-usage" in route_paths or "" in route_paths
        assert len(router.routes) >= 2


class AsyncIteratorMock:
    """Helper to mock async iterators returned by Cosmos query_items."""
    def __init__(self, items):
        self._items = items
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item
