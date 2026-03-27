"""Tenant middleware tests — TENANT-04.

Tests the actual behaviour of TenantMiddleware.dispatch():
 - sets user_context / tenant_id on request.state for valid tokens
 - allows requests without a token (auth is enforced by route deps, not middleware)
 - skips token parsing for PUBLIC_PATHS
 - honours X-Tenant-Id header override
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.tenant import TenantMiddleware, _tenant_status_cache


def _create_test_app():
    """Create a minimal FastAPI app with TenantMiddleware and a dummy endpoint."""
    app = FastAPI()
    app.add_middleware(TenantMiddleware)

    @app.get("/api/v1/test")
    async def test_endpoint(request: Request):
        ctx = getattr(request.state, "user_context", None)
        tid = getattr(request.state, "tenant_id", None)
        return {"user_context": ctx, "tenant_id": tid}

    @app.get("/api/v1/tenants")
    async def tenants_endpoint():
        return {"tenants": []}

    return app


def _mock_validate_token(tenant_id: str):
    """Return mock claims for a given tenant."""

    async def mock_validate(token: str):
        return {"oid": "user-1", "tid": tenant_id, "preferred_username": "test@example.com", "name": "Test"}

    return mock_validate


class TestTenantMiddleware:
    """Verifies middleware sets user context when a valid token is present."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        _tenant_status_cache.clear()
        yield
        _tenant_status_cache.clear()

    def test_valid_token_sets_user_context(self, mock_cosmos_client):
        """Middleware should populate request.state with user_context from token claims."""
        app = _create_test_app()

        with patch("app.middleware.tenant.validate_entra_token", new=_mock_validate_token("t1")), \
             patch("app.middleware.tenant.extract_user_context", return_value={
                 "user_id": "user-1", "tenant_id": "t1", "email": "test@example.com",
                 "name": "Test", "roles": [],
             }):
            client = TestClient(app)
            response = client.get("/api/v1/test", headers={"Authorization": "Bearer fake-token"})

        assert response.status_code == 200
        body = response.json()
        assert body["user_context"]["user_id"] == "user-1"
        assert body["tenant_id"] == "t1"

    def test_no_token_passes_through(self, mock_cosmos_client):
        """Without a Bearer token the middleware still passes through (auth enforced later)."""
        app = _create_test_app()
        client = TestClient(app)
        response = client.get("/api/v1/test")

        assert response.status_code == 200
        body = response.json()
        assert body["user_context"] is None

    def test_x_tenant_id_header_overrides(self, mock_cosmos_client):
        """X-Tenant-Id header should override the tenant from the token."""
        app = _create_test_app()

        with patch("app.middleware.tenant.validate_entra_token", new=_mock_validate_token("t1")), \
             patch("app.middleware.tenant.extract_user_context", return_value={
                 "user_id": "user-1", "tenant_id": "t1", "email": "test@example.com",
                 "name": "Test", "roles": [],
             }):
            client = TestClient(app)
            response = client.get(
                "/api/v1/test",
                headers={"Authorization": "Bearer fake-token", "X-Tenant-Id": "override-tid"},
            )

        assert response.status_code == 200
        assert response.json()["tenant_id"] == "override-tid"

    def test_health_endpoints_bypass_token_parsing(self, mock_cosmos_client):
        app = _create_test_app()

        from app.health import health_router
        app.include_router(health_router)

        with patch("app.health.get_cosmos_client", new_callable=AsyncMock):
            client = TestClient(app)
            for path in ["/healthz", "/readyz", "/startupz"]:
                response = client.get(path)
                assert response.status_code == 200, f"{path} should bypass middleware"

    def test_tenants_endpoint_still_accessible(self, mock_cosmos_client):
        """Requests to /api/v1/tenants with a valid token should succeed."""
        app = _create_test_app()

        with patch("app.middleware.tenant.validate_entra_token", new=_mock_validate_token("t1")), \
             patch("app.middleware.tenant.extract_user_context", return_value={
                 "user_id": "user-1", "tenant_id": "t1", "email": "test@example.com",
                 "name": "Test", "roles": [],
             }):
            client = TestClient(app)
            response = client.get("/api/v1/tenants", headers={"Authorization": "Bearer fake-token"})

        assert response.status_code == 200
