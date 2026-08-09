from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import router as api_router
from app.api.topology import router as topology_router
from app.database import Base, get_db
from app.domain.models import User
from app.services.auth import hash_password


def build_app() -> TestClient:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as session:
        session.add_all(
            [
                User(username="admin", password_hash=hash_password("admin-password"), role="ADMIN"),
                User(username="viewer", password_hash=hash_password("viewer-password"), role="VIEW"),
            ]
        )
        session.commit()
    app = FastAPI()
    app.include_router(api_router)
    app.include_router(topology_router)

    def test_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    return TestClient(app)


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_assets(client: TestClient, headers: dict[str, str], types: list[str]) -> list[int]:
    ids = []
    for asset_type in types:
        response = client.post("/api/v1/assets", headers=headers, json={"type": asset_type})
        assert response.status_code == 201
        ids.append(response.json()["id"])
    return ids


def test_topology_get_returns_flat_adjacency_list() -> None:
    client = build_app()
    admin = login(client, "admin", "admin-password")
    viewer = login(client, "viewer", "viewer-password")

    ids = _create_assets(client, admin, ["router", "switch", "laptop"])

    created = client.post(
        "/api/v1/topology/links",
        headers=admin,
        json={"source_id": ids[0], "target_id": ids[1], "link_type": "ethernet", "label": "Uplink 1"},
    )
    assert created.status_code == 201
    assert created.json()["source_id"] == ids[0]
    assert created.json()["target_id"] == ids[1]

    body = client.get("/api/v1/topology", headers=viewer).json()
    assert [asset["id"] for asset in body["assets"]] == ids
    assert len(body["links"]) == 1
    assert body["links"][0]["link_type"] == "ethernet"
    assert body["links"][0]["label"] == "Uplink 1"


def test_topology_link_requires_admin() -> None:
    client = build_app()
    admin = login(client, "admin", "admin-password")
    viewer = login(client, "viewer", "viewer-password")
    ids = _create_assets(client, admin, ["router", "switch"])

    denied = client.post(
        "/api/v1/topology/links",
        headers=viewer,
        json={"source_id": ids[0], "target_id": ids[1]},
    )
    assert denied.status_code == 403
    assert client.get("/api/v1/topology", headers=viewer).json()["links"] == []


def test_topology_link_validation() -> None:
    client = build_app()
    admin = login(client, "admin", "admin-password")
    ids = _create_assets(client, admin, ["router", "switch"])

    self_link = client.post(
        "/api/v1/topology/links",
        headers=admin,
        json={"source_id": ids[0], "target_id": ids[0]},
    )
    assert self_link.status_code == 422

    missing = client.post(
        "/api/v1/topology/links",
        headers=admin,
        json={"source_id": ids[0], "target_id": 999999},
    )
    assert missing.status_code == 404


def test_topology_link_delete_is_soft_and_idempotent() -> None:
    client = build_app()
    admin = login(client, "admin", "admin-password")
    viewer = login(client, "viewer", "viewer-password")
    ids = _create_assets(client, admin, ["router", "switch"])

    created = client.post(
        "/api/v1/topology/links",
        headers=admin,
        json={"source_id": ids[0], "target_id": ids[1]},
    )
    link_id = created.json()["id"]

    assert client.delete(f"/api/v1/topology/links/{link_id}", headers=viewer).status_code == 403
    assert client.delete(f"/api/v1/topology/links/{link_id}", headers=admin).status_code == 204
    assert client.delete(f"/api/v1/topology/links/{link_id}", headers=admin).status_code == 404
    assert client.delete("/api/v1/topology/links/999999", headers=admin).status_code == 404

    assert client.get("/api/v1/topology", headers=viewer).json()["links"] == []


def test_topology_link_duplicate_rejected() -> None:
    client = build_app()
    admin = login(client, "admin", "admin-password")
    ids = _create_assets(client, admin, ["router", "switch", "laptop"])

    first = client.post(
        "/api/v1/topology/links",
        headers=admin,
        json={"source_id": ids[0], "target_id": ids[1]},
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/api/v1/topology/links",
        headers=admin,
        json={"source_id": ids[0], "target_id": ids[1], "label": "again"},
    )
    assert duplicate.status_code == 409

    reverse = client.post(
        "/api/v1/topology/links",
        headers=admin,
        json={"source_id": ids[1], "target_id": ids[0]},
    )
    assert reverse.status_code == 201


def test_topology_link_update_endpoint() -> None:
    client = build_app()
    admin = login(client, "admin", "admin-password")
    viewer = login(client, "viewer", "viewer-password")
    ids = _create_assets(client, admin, ["router", "switch", "laptop"])

    created = client.post(
        "/api/v1/topology/links",
        headers=admin,
        json={"source_id": ids[0], "target_id": ids[1], "link_type": "ethernet", "label": "Uplink 1"},
    )
    link_id = created.json()["id"]

    assert client.put(
        f"/api/v1/topology/links/{link_id}",
        headers=viewer,
        json={"source_id": ids[0], "target_id": ids[1], "link_type": "ethernet"},
    ).status_code == 403

    updated = client.put(
        f"/api/v1/topology/links/{link_id}",
        headers=admin,
        json={"source_id": ids[0], "target_id": ids[2], "link_type": "wireless", "label": "Backup path"},
    )
    assert updated.status_code == 200
    assert updated.json()["target_id"] == ids[2]
    assert updated.json()["link_type"] == "wireless"
    assert updated.json()["label"] == "Backup path"

    body = client.get("/api/v1/topology", headers=viewer).json()
    assert len(body["links"]) == 1
    assert body["links"][0]["target_id"] == ids[2]

    self_link = client.put(
        f"/api/v1/topology/links/{link_id}",
        headers=admin,
        json={"source_id": ids[0], "target_id": ids[0]},
    )
    assert self_link.status_code == 422

    missing = client.put(
        "/api/v1/topology/links/999999",
        headers=admin,
        json={"source_id": ids[0], "target_id": ids[1]},
    )
    assert missing.status_code == 404

    dup = client.post(
        "/api/v1/topology/links",
        headers=admin,
        json={"source_id": ids[0], "target_id": ids[1]},
    )
    dup_link_id = dup.json()["id"]
    conflict = client.put(
        f"/api/v1/topology/links/{dup_link_id}",
        headers=admin,
        json={"source_id": ids[0], "target_id": ids[2]},
    )
    assert conflict.status_code == 409


def test_topology_wireless_link_round_trip() -> None:
    client = build_app()
    admin = login(client, "admin", "admin-password")
    ids = _create_assets(client, admin, ["router", "wireless"])

    created = client.post(
        "/api/v1/topology/links",
        headers=admin,
        json={"source_id": ids[0], "target_id": ids[1], "link_type": "wireless"},
    )
    assert created.status_code == 201
    assert created.json()["link_type"] == "wireless"

    body = client.get("/api/v1/topology", headers=admin).json()
    assert body["links"][0]["link_type"] == "wireless"


def test_internet_source_patch_updates_and_lists() -> None:
    client = build_app()
    admin = login(client, "admin", "admin-password")
    viewer = login(client, "viewer", "viewer-password")
    ids = _create_assets(client, admin, ["router", "switch"])

    patched = client.patch(
        f"/api/v1/assets/{ids[0]}/topology",
        headers=admin,
        json={"is_internet_source": True},
    )
    assert patched.status_code == 200
    assert patched.json()["is_internet_source"] is True

    denied = client.patch(
        f"/api/v1/assets/{ids[1]}/topology",
        headers=viewer,
        json={"is_internet_source": True},
    )
    assert denied.status_code == 403

    body = client.get("/api/v1/topology", headers=viewer).json()
    root = next(asset for asset in body["assets"] if asset["id"] == ids[0])
    assert root["is_internet_source"] is True

    cleared = client.patch(
        f"/api/v1/assets/{ids[0]}/topology",
        headers=admin,
        json={"is_internet_source": False},
    )
    assert cleared.json()["is_internet_source"] is False

    assert client.patch("/api/v1/assets/999999/topology", headers=admin, json={"is_internet_source": True}).status_code == 404
