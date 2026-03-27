"""Unit tests for MarketplaceService with mocked Cosmos DB repositories."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.marketplace_service import MarketplaceService


TENANT_ID = "test-tenant-001"


def _make_agent_template_dict(**overrides):
    defaults = {
        "id": str(uuid.uuid4()),
        "name": "Test Template",
        "description": "A test template",
        "category": "general",
        "tags": ["test"],
        "system_prompt": "You are helpful",
        "config": {"temperature": 0.7, "max_tokens": 1024},
        "is_public": True,
        "is_featured": False,
        "install_count": 0,
        "tenant_id": TENANT_ID,
    }
    defaults.update(overrides)
    return defaults


def _make_agent_dict(**overrides):
    defaults = {
        "id": str(uuid.uuid4()),
        "name": "My Agent",
        "description": "An agent",
        "system_prompt": "You are helpful",
        "temperature": 0.7,
        "max_tokens": 1024,
        "timeout_seconds": 30,
        "tenant_id": TENANT_ID,
    }
    defaults.update(overrides)
    return defaults


class TestListAgentTemplates:
    @pytest.mark.asyncio
    async def test_returns_templates(self):
        templates = [_make_agent_template_dict(name="T1"), _make_agent_template_dict(name="T2")]
        with patch("app.services.marketplace_service._agent_template_repo") as mock_repo:
            mock_repo.query = AsyncMock(return_value=templates)
            result = await MarketplaceService.list_agent_templates(TENANT_ID)
            assert len(result) == 2
            assert result[0]["name"] == "T1"

    @pytest.mark.asyncio
    async def test_empty_result(self):
        with patch("app.services.marketplace_service._agent_template_repo") as mock_repo:
            mock_repo.query = AsyncMock(return_value=[])
            result = await MarketplaceService.list_agent_templates(TENANT_ID)
            assert result == []


class TestPublishAgentTemplate:
    @pytest.mark.asyncio
    async def test_publish_success(self):
        agent = _make_agent_dict()
        with patch("app.services.marketplace_service._agent_repo") as mock_agent_repo, \
             patch("app.services.marketplace_service._agent_template_repo") as mock_tmpl_repo:
            mock_agent_repo.get = AsyncMock(return_value=agent)
            mock_tmpl_repo.create = AsyncMock(side_effect=lambda tid, doc: doc)

            result = await MarketplaceService.publish_agent_template(
                tenant_id=TENANT_ID, agent_id=agent["id"],
                name="Published Agent", description="desc", category="general", tags=["ai"],
            )
            assert result is not None
            assert result["name"] == "Published Agent"
            mock_tmpl_repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_publish_agent_not_found(self):
        with patch("app.services.marketplace_service._agent_repo") as mock_agent_repo:
            mock_agent_repo.get = AsyncMock(return_value=None)

            result = await MarketplaceService.publish_agent_template(
                tenant_id=TENANT_ID, agent_id=str(uuid.uuid4()),
                name="X", description=None, category=None, tags=None,
            )
            assert result is None


class TestImportAgentTemplate:
    @pytest.mark.asyncio
    async def test_import_increments_install_count(self):
        template = _make_agent_template_dict(install_count=5)
        with patch("app.services.marketplace_service._agent_template_repo") as mock_tmpl_repo, \
             patch("app.services.marketplace_service._agent_repo") as mock_agent_repo:
            mock_tmpl_repo.get = AsyncMock(return_value=template)
            mock_tmpl_repo.update = AsyncMock()
            mock_agent_repo.create = AsyncMock(side_effect=lambda tid, doc: doc)

            result = await MarketplaceService.import_agent_template(
                tenant_id=TENANT_ID, template_id=template["id"],
            )
            assert result is not None
            assert template["install_count"] == 6
            mock_agent_repo.create.assert_awaited_once()
            mock_tmpl_repo.update.assert_awaited_once()
