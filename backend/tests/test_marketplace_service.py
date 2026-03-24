"""Unit tests for MarketplaceService with mocked AsyncSession."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.marketplace_service import MarketplaceService


def _make_mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _make_agent_template(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "name": "Test Template",
        "description": "A test template",
        "category": "general",
        "tags": ["test"],
        "system_prompt": "You are helpful",
        "config": {"temperature": 0.7, "max_tokens": 1024},
        "is_public": True,
        "is_featured": False,
        "install_count": 0,
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_agent(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "name": "My Agent",
        "description": "An agent",
        "system_prompt": "You are helpful",
        "temperature": 0.7,
        "max_tokens": 1024,
        "timeout_seconds": 30,
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


class TestListAgentTemplates:
    @pytest.mark.asyncio
    async def test_returns_templates(self):
        db = _make_mock_db()
        templates = [_make_agent_template(name="T1"), _make_agent_template(name="T2")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = templates
        db.execute.return_value = mock_result

        result = await MarketplaceService.list_agent_templates(db)
        assert len(result) == 2
        assert result[0].name == "T1"

    @pytest.mark.asyncio
    async def test_empty_result(self):
        db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        result = await MarketplaceService.list_agent_templates(db)
        assert result == []


class TestPublishAgentTemplate:
    @pytest.mark.asyncio
    async def test_publish_success(self):
        db = _make_mock_db()
        agent = _make_agent()
        tenant_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = agent
        db.execute.return_value = mock_result

        result = await MarketplaceService.publish_agent_template(
            db, agent_id=agent.id, tenant_id=tenant_id,
            name="Published Agent", description="desc", category="general", tags=["ai"],
        )
        assert result is not None
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_publish_agent_not_found(self):
        db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        result = await MarketplaceService.publish_agent_template(
            db, agent_id=uuid.uuid4(), tenant_id=uuid.uuid4(),
            name="X", description=None, category=None, tags=None,
        )
        assert result is None
        db.add.assert_not_called()


class TestImportAgentTemplate:
    @pytest.mark.asyncio
    async def test_import_increments_install_count(self):
        db = _make_mock_db()
        template = _make_agent_template(install_count=5)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = template
        db.execute.return_value = mock_result

        result = await MarketplaceService.import_agent_template(
            db, template_id=template.id, tenant_id=uuid.uuid4(),
        )
        assert result is not None
        assert template.install_count == 6
        db.add.assert_called_once()
        db.commit.assert_awaited_once()
