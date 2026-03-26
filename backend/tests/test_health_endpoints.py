"""Health endpoint tests — COMPUTE-07."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.health import health_router


def _create_health_app():
    app = FastAPI()
    app.include_router(health_router)
    return app


class TestHealthEndpoints:
    """Verify liveness, readiness, and startup probes return 200."""

    def test_healthz_returns_200(self):
        app = _create_health_app()
        client = TestClient(app)
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_readyz_returns_200(self):
        app = _create_health_app()
        with patch("app.health.get_cosmos_client", new_callable=AsyncMock):
            client = TestClient(app)
            response = client.get("/readyz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_startupz_returns_200(self):
        app = _create_health_app()
        client = TestClient(app)
        response = client.get("/startupz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
