"""Tenant middleware blocking tests — TENANT-04."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.tenant import TenantMiddleware, _tenant_status_cache


def _create_test_app():
    """Create a minimal FastAPI app with TenantMiddleware and a dummy endpoint."""
    app = FastAPI()
    app.add_middleware(TenantMiddleware)

    @app.get("/api/v1/test")
    async def test_endpoint():
        return {"result": "ok"}

    @app.get("/api/v1/tenants")
    async def tenants_endpoint():
        return {"tenants": []}

    return app


def _mock_validate_token(tenant_id: str, status: str = "active"):
    """Return mock claims for a given tenant."""

    async def mock_validate(token: str):
        return {"oid": "user-1", "tid": tenant_id, "preferred_username": "test@example.com", "name": "Test"}

    return mock_validate


class TestTenantMiddlewareBlocking:
    """Verifies middleware blocks suspended/deactivated/deleted/provisioning tenants."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        _tenant_status_cache.clear()
        yield
        _tenant_status_cache.clear()

    @pytest.mark.parametrize("status,expected_code", [
        ("active", 200),
        ("suspended", 403),
        ("deactivated", 403),
        ("deleted", 403),
        ("provisioning", 503),
    ])
    def test_tenant_status_response_codes(self, status, expected_code, mock_cosmos_client):
        app = _create_test_app()
        tenant = {"id": "t1", "tenant_id": "t1", "status": status}

        with patch("app.middleware.tenant.validate_entra_token", new=_mock_validate_token("t1")), \
             patch("app.middleware.tenant.extract_user_context", return_value={
                 "user_id": "user-1", "tenant_id": "t1", "email": "test@example.com",
                 "name": "Test", "roles": [],
             }), \
             patch("app.middleware.tenant.TenantRepository") as MockRepo:
            mock_instance = MockRepo.return_value
            mock_instance.get = AsyncMock(return_value=tenant)

            client = TestClient(app)
            response = client.get("/api/v1/test", headers={"Authorization": "Bearer fake-token"})

        assert response.status_code == expected_code

    def test_health_endpoints_bypass_tenant_check(self, mock_cosmos_client):
        app = _create_test_app()

        from app.health import health_router
        app.include_router(health_router)

        with patch("app.health.get_cosmos_client", new_callable=AsyncMock):
            client = TestClient(app)
            for path in ["/healthz", "/readyz", "/startupz"]:
                response = client.get(path)
                assert response.status_code == 200, f"{path} should bypass tenant check"

    def test_tenants_endpoint_bypasses_status_check(self, mock_cosmos_client):
        """Admin /api/v1/tenants endpoints skip tenant status check."""
        app = _create_test_app()
        tenant = {"id": "t1", "tenant_id": "t1", "status": "suspended"}

        with patch("app.middleware.tenant.validate_entra_token", new=_mock_validate_token("t1")), \
             patch("app.middleware.tenant.extract_user_context", return_value={
                 "user_id": "user-1", "tenant_id": "t1", "email": "test@example.com",
                 "name": "Test", "roles": [],
             }):
            client = TestClient(app)
            response = client.get("/api/v1/tenants", headers={"Authorization": "Bearer fake-token"})

        assert response.status_code == 200
