from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_main_app_registers_core_and_operations_routes() -> None:
    schema = TestClient(app).get("/openapi.json")

    assert schema.status_code == 200
    paths = schema.json()["paths"]
    assert "/api/v1/assets" in paths
    assert "/api/v1/monitoring/targets" in paths
    assert "/api/v1/warehouse/items" in paths
    assert "/api/v1/references" in paths
    assert "/api/v1/topology" in paths
    assert "/api/v1/topology/links" in paths
    assert "/api/v1/assets/{asset_id}/topology" in paths


def test_main_app_health_route_is_reachable() -> None:
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
