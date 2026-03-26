"""Tenant service lifecycle, provisioning, and settings tests — TENANT-01 through TENANT-07."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.tenant_service import TenantService, VALID_TRANSITIONS
from app.services.tenant_provisioning import TenantProvisioningService


class TestTenantCRUD:
    """Tenant create, get, list, update (TENANT-01)."""

    @pytest.fixture
    def service(self, mock_cosmos_client):
        svc = TenantService()
        return svc

    @pytest.mark.asyncio
    async def test_create_tenant_with_provisioning_state(self, service):
        with patch.object(service, "repo") as mock_repo:
            mock_repo.get_by_slug = AsyncMock(return_value=None)
            mock_repo.create = AsyncMock(side_effect=lambda tid, item: item)
            # Prevent provisioning from running (lazy import inside create_tenant)
            with patch("app.services.tenant_provisioning.TenantProvisioningService") as MockProv:
                MockProv.return_value.provision_tenant = AsyncMock()
                result = await service.create_tenant("Test Co", "test-co", "admin@test.co")
        assert result["status"] == "provisioning"
        assert result["slug"] == "test-co"
        assert result["name"] == "Test Co"
        assert result["admin_email"] == "admin@test.co"

    @pytest.mark.asyncio
    async def test_create_tenant_rejects_duplicate_slug(self, service):
        with patch.object(service, "repo") as mock_repo:
            mock_repo.get_by_slug = AsyncMock(return_value={"slug": "dupe"})
            with pytest.raises(ValueError, match="already exists"):
                await service.create_tenant("Dupe", "dupe", "a@b.com")

    @pytest.mark.asyncio
    async def test_get_tenant(self, service):
        with patch.object(service, "repo") as mock_repo:
            mock_repo.get = AsyncMock(return_value={"id": "t1", "name": "T1"})
            result = await service.get_tenant("t1")
        assert result["name"] == "T1"

    @pytest.mark.asyncio
    async def test_update_tenant(self, service):
        existing = {"id": "t1", "tenant_id": "t1", "name": "Old", "admin_email": "old@x.com"}
        with patch.object(service, "repo") as mock_repo:
            mock_repo.get = AsyncMock(return_value=dict(existing))
            mock_repo.upsert = AsyncMock(side_effect=lambda tid, item: item)
            result = await service.update_tenant("t1", {"name": "New"})
        assert result["name"] == "New"


class TestLifecycleStateMachine:
    """Parametrized tests for all valid and invalid transitions (TENANT-03)."""

    @pytest.fixture
    def service(self, mock_cosmos_client):
        return TenantService()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("from_state,to_state", [
        ("provisioning", "active"),
        ("provisioning", "deleted"),
        ("active", "suspended"),
        ("active", "deactivated"),
        ("suspended", "active"),
        ("suspended", "deactivated"),
        ("deactivated", "deleted"),
    ])
    async def test_valid_transitions(self, service, from_state, to_state):
        tenant = {"id": "t1", "tenant_id": "t1", "status": from_state}
        with patch.object(service, "repo") as mock_repo:
            mock_repo.get = AsyncMock(return_value=dict(tenant))
            mock_repo.upsert = AsyncMock(side_effect=lambda tid, item: item)
            result = await service.transition_state("t1", to_state)
        assert result["status"] == to_state

    @pytest.mark.asyncio
    @pytest.mark.parametrize("from_state,to_state", [
        ("provisioning", "suspended"),
        ("provisioning", "deactivated"),
        ("active", "provisioning"),
        ("active", "deleted"),
        ("suspended", "provisioning"),
        ("suspended", "deleted"),
        ("deactivated", "active"),
        ("deactivated", "provisioning"),
        ("deleted", "active"),
        ("deleted", "provisioning"),
    ])
    async def test_invalid_transitions_rejected(self, service, from_state, to_state):
        tenant = {"id": "t1", "tenant_id": "t1", "status": from_state}
        with patch.object(service, "repo") as mock_repo:
            mock_repo.get = AsyncMock(return_value=dict(tenant))
            with pytest.raises(ValueError, match="Invalid transition"):
                await service.transition_state("t1", to_state)


class TestTenantSettings:
    """Test update_settings behavior (TENANT-05)."""

    @pytest.fixture
    def service(self, mock_cosmos_client):
        return TenantService()

    @pytest.mark.asyncio
    async def test_update_settings_stores_on_tenant(self, service):
        tenant = {"id": "t1", "tenant_id": "t1", "settings": {"display_name": "Old", "token_quota": 100}}
        with patch.object(service, "repo") as mock_repo:
            mock_repo.get = AsyncMock(return_value=dict(tenant))
            mock_repo.upsert = AsyncMock(side_effect=lambda tid, item: item)
            result = await service.update_settings("t1", {"display_name": "New Name", "token_quota": 500})
        assert result["settings"]["display_name"] == "New Name"
        assert result["settings"]["token_quota"] == 500

    @pytest.mark.asyncio
    async def test_delete_tenant_requires_deactivated(self, service):
        tenant = {"id": "t1", "tenant_id": "t1", "status": "active"}
        with patch.object(service, "repo") as mock_repo:
            mock_repo.get = AsyncMock(return_value=dict(tenant))
            with pytest.raises(ValueError, match="deactivated"):
                await service.delete_tenant("t1")


class TestTenantProvisioning:
    """Test TenantProvisioningService (TENANT-02, TENANT-06, TENANT-07)."""

    @pytest.mark.asyncio
    async def test_seed_default_data_creates_tools_and_catalog(self, mock_cosmos_client):
        prov = TenantProvisioningService()
        with patch.object(prov.tool_repo, "create", new_callable=AsyncMock) as mock_tool_create, \
             patch.object(prov.catalog_repo, "create", new_callable=AsyncMock) as mock_catalog_create:
            await prov._seed_default_data("t1")
        assert mock_tool_create.call_count == 2  # web_search + code_interpreter
        assert mock_catalog_create.call_count == 1  # Getting Started

    @pytest.mark.asyncio
    async def test_create_admin_user_creates_user_with_admin_role(self, mock_cosmos_client):
        prov = TenantProvisioningService()
        with patch.object(prov.user_repo, "get_by_email", new_callable=AsyncMock, return_value=None) as _, \
             patch.object(prov.user_repo, "create", new_callable=AsyncMock) as mock_create:
            await prov._create_admin_user("t1", "admin@example.com")
        created = mock_create.call_args[0][1]
        assert created["email"] == "admin@example.com"
        assert created["role"] == "admin"

    @pytest.mark.asyncio
    async def test_provision_tenant_calls_all_steps_and_activates(self, mock_cosmos_client):
        prov = TenantProvisioningService()
        tenant = {"id": "t1", "slug": "test-co", "admin_email": "admin@test.co"}
        mock_k8s = AsyncMock()
        mock_seed = AsyncMock()
        mock_admin = AsyncMock()
        prov._provision_k8s_namespace = mock_k8s
        prov._seed_default_data = mock_seed
        prov._create_admin_user = mock_admin

        # TenantService is lazy-imported inside provision_tenant
        with patch("app.services.tenant_service.TenantService") as MockSvc:
            mock_svc_instance = MockSvc.return_value
            mock_svc_instance.transition_state = AsyncMock()
            await prov.provision_tenant(tenant)

        mock_k8s.assert_called_once_with("test-co")
        mock_seed.assert_called_once_with("t1")
        mock_admin.assert_called_once_with("t1", "admin@test.co")
        mock_svc_instance.transition_state.assert_called_once_with("t1", "active")
