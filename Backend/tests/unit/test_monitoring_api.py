from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import router as api_router
from app.api.targets import v1_router as monitoring_router
from app.database import Base, get_db
from app.domain.models import MonitoredTarget, User
from app.services.auth import hash_password
from app.services.monitoring import CheckResult, PASS


def build_client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as session:
        session.add_all(
            [
                User(username="admin-test", password_hash=hash_password("admin-password"), role="ADMIN"),
                User(username="view-test", password_hash=hash_password("viewer-password"), role="VIEW"),
                MonitoredTarget(
                    name="Example",
                    ip_or_host="https://example.com",
                    target_type="website",
                    ping_interval_sec=60,
                ),
            ]
        )
        session.commit()

    app = FastAPI()
    app.include_router(api_router)
    app.include_router(monitoring_router)

    def test_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    return TestClient(app)


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_can_manage_and_check_monitoring_targets() -> None:
    client = build_client()
    headers = login(client, "admin-test", "admin-password")

    response = client.post(
        "/api/v1/monitoring/targets",
        headers=headers,
        json={
            "name": "Public website",
            "ip_or_host": "https://example.org",
            "target_type": "website",
            "ping_interval_sec": 60,
        },
    )
    assert response.status_code == 201

    with patch("app.api.router.check_target", return_value=CheckResult(PASS, 12.5)):
        response = client.post("/api/v1/monitoring/targets/1/check", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "PASS"


def test_view_can_read_but_cannot_manage_monitoring_targets() -> None:
    client = build_client()
    headers = login(client, "view-test", "viewer-password")

    assert client.get("/api/v1/monitoring/targets", headers=headers).status_code == 200
    assert client.get("/api/v1/monitoring/history", headers=headers).status_code == 200
    assert client.post("/api/v1/monitoring/targets/1/check", headers=headers).status_code == 403
    assert client.delete("/api/v1/monitoring/targets/1", headers=headers).status_code == 403


def test_monitoring_requires_authentication() -> None:
    client = build_client()
    assert client.get("/api/v1/monitoring/targets").status_code == 401
    assert client.get("/api/v1/monitoring/history").status_code == 401
