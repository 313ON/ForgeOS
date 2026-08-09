from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.operations import router as operations_router
from app.api.router import compat_router, router as api_router
from app.database import Base, get_db
from app.domain.models import User
from app.services.auth import hash_password
from app.services import reference_store


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
    app.include_router(compat_router)
    app.include_router(operations_router)

    def test_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    return TestClient(app)


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_warehouse_movement_ledger_and_authorization() -> None:
    client = build_app()
    admin = login(client, "admin", "admin-password")
    viewer = login(client, "viewer", "viewer-password")

    assert client.post("/api/v1/warehouse/items", headers=viewer, json={"sku": "RAM-1", "name": "RAM"}).status_code == 403
    created = client.post(
        "/api/v1/warehouse/items",
        headers=admin,
        json={"sku": "RAM-1", "name": "DDR4 RAM", "category": "RAM", "minimum_stock": 2},
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    received = client.post(
        f"/api/v1/warehouse/items/{item_id}/movements",
        headers=admin,
        json={"movement_type": "incoming", "quantity": 5, "reference": "PO-1"},
    )
    assert received.status_code == 201
    issued = client.post(
        f"/api/v1/warehouse/items/{item_id}/movements",
        headers=admin,
        json={"movement_type": "outgoing", "quantity": 4},
    )
    assert issued.status_code == 201
    assert client.post(
        f"/api/v1/warehouse/items/{item_id}/movements",
        headers=admin,
        json={"movement_type": "outgoing", "quantity": 2},
    ).status_code == 409

    items = client.get("/api/v1/warehouse/items?low_stock=true", headers=viewer).json()
    assert items[0]["quantity"] == 1
    assert items[0]["low_stock"] is True
    assert len(client.get(f"/api/v1/warehouse/items/{item_id}/movements", headers=viewer).json()) == 2


def test_reference_upload_validation_and_download(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(reference_store, "REFERENCE_DIR", tmp_path / "references")
    client = build_app()
    admin = login(client, "admin", "admin-password")
    viewer = login(client, "viewer", "viewer-password")

    denied = client.post(
        "/api/v1/references",
        headers=viewer,
        data={"title": "Runbook"},
        files={"file": ("runbook.pdf", b"%PDF-test", "application/pdf")},
    )
    assert denied.status_code == 403
    bad = client.post(
        "/api/v1/references",
        headers=admin,
        data={"title": "Executable"},
        files={"file": ("payload.exe", b"MZ", "application/octet-stream")},
    )
    assert bad.status_code == 400
    uploaded = client.post(
        "/api/v1/references",
        headers=admin,
        data={"title": "Runbook", "category": "Tutorial", "tags": "network, critical"},
        files={"file": ("runbook.pdf", b"%PDF-test", "application/pdf")},
    )
    assert uploaded.status_code == 201
    body = uploaded.json()
    assert body["tags"] == ["network", "critical"]
    assert body["preview_supported"] is True
    download = client.get(f"/api/v1/references/{body['id']}/download", headers=viewer)
    assert download.status_code == 200
    assert download.content == b"%PDF-test"


def test_selected_exports_reject_missing_ids() -> None:
    client = build_app()
    viewer = login(client, "viewer", "viewer-password")
    response = client.get("/api/export/excel?asset_id=9999", headers=viewer)
    assert response.status_code == 404


def _upload_reference(client, admin, title="Runbook") -> int:
    response = client.post(
        "/api/v1/references",
        headers=admin,
        data={"title": title},
        files={"file": (f"{title}.pdf", b"%PDF-test", "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_reference_delete_authorization(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(reference_store, "REFERENCE_DIR", tmp_path / "references")
    client = build_app()
    admin = login(client, "admin", "admin-password")
    viewer = login(client, "viewer", "viewer-password")
    document_id = _upload_reference(client, admin)

    denied = client.delete(f"/api/v1/references/{document_id}", headers=viewer)
    assert denied.status_code == 403
    listed = client.get("/api/v1/references", headers=viewer).json()
    assert any(item["id"] == document_id for item in listed)


def test_reference_soft_delete_hides_from_list_and_download(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(reference_store, "REFERENCE_DIR", tmp_path / "references")
    client = build_app()
    admin = login(client, "admin", "admin-password")
    viewer = login(client, "viewer", "viewer-password")
    document_id = _upload_reference(client, admin)

    deleted = client.delete(f"/api/v1/references/{document_id}", headers=admin)
    assert deleted.status_code == 204

    listed = client.get("/api/v1/references", headers=viewer).json()
    assert all(item["id"] != document_id for item in listed)
    assert client.get(f"/api/v1/references/{document_id}/download", headers=viewer).status_code == 404


def test_reference_delete_is_idempotent_not_found(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(reference_store, "REFERENCE_DIR", tmp_path / "references")
    client = build_app()
    admin = login(client, "admin", "admin-password")
    viewer = login(client, "viewer", "viewer-password")
    document_id = _upload_reference(client, admin)

    assert client.delete(f"/api/v1/references/{document_id}", headers=admin).status_code == 204
    assert client.delete(f"/api/v1/references/{document_id}", headers=admin).status_code == 404
    assert client.delete("/api/v1/references/999999", headers=admin).status_code == 404
    assert client.delete("/api/v1/references/999999", headers=viewer).status_code == 403


def test_reference_soft_delete_keeps_file_on_disk(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(reference_store, "REFERENCE_DIR", tmp_path / "references")
    client = build_app()
    admin = login(client, "admin", "admin-password")

    document_id = _upload_reference(client, admin)
    assert len(list((tmp_path / "references").iterdir())) == 1

    assert client.delete(f"/api/v1/references/{document_id}", headers=admin).status_code == 204

    # The physical file is retained for a future retention/purge job.
    assert len(list((tmp_path / "references").iterdir())) == 1
    assert client.get("/api/v1/references", headers=admin).json() == []
