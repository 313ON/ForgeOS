from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import router as api_router
from app.database import Base, get_db
from app.domain.models import User
from app.services.auth import hash_password
from app.services.reports import asset_report_rows

SYSTEMINFO_SAMPLE = (
    "Host Name: OFFICE-1\n"
    "OS Name: Microsoft Windows 11 Enterprise\n"
    "System Manufacturer: LENOVO\n"
    "System Serial Number: SN123\n"
    "Total Physical Memory: 32,538 MB\n"
    "Processor Core Count: 16"
)


def build_app() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as session:
        session.add(User(username="admin", password_hash=hash_password("admin-password"), role="ADMIN"))
        session.commit()
    app = FastAPI()
    app.include_router(api_router)

    def test_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    return TestClient(app), sessions


def login(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin-password"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_create_asset_generates_sequential_tags_and_null_status() -> None:
    client, _ = build_app()
    headers = login(client)

    first = client.post("/api/v1/assets", headers=headers, json={"type": "laptop", "status": ""})
    assert first.status_code in (200, 201)
    assert first.json()["asset_tag"] == "LAP-0001"
    assert first.json()["status"] is None

    second = client.post("/api/v1/assets", headers=headers, json={"type": "laptop"})
    assert second.json()["asset_tag"] == "LAP-0002"

    missing = client.post("/api/v1/assets", headers=headers, json={"asset_tag": "XXX-1234"})
    assert missing.status_code == 422


def test_asset_tag_validation_and_suggestion() -> None:
    client, _ = build_app()
    headers = login(client)

    suggestion = client.get("/api/v1/assets/tag-suggestion?type=laptop", headers=headers)
    assert suggestion.status_code == 200
    assert suggestion.json()["asset_tag"] == "LAP-0001"

    free = client.get("/api/v1/assets/tag-valid?asset_tag=LAP-0001", headers=headers)
    assert free.json()["valid"] is True

    client.post("/api/v1/assets", headers=headers, json={"type": "laptop"})

    taken = client.get("/api/v1/assets/tag-valid?asset_tag=LAP-0001", headers=headers)
    assert taken.json()["valid"] is False

    bad = client.get("/api/v1/assets/tag-valid?asset_tag=not-a-tag", headers=headers)
    assert bad.status_code == 400

    create_bad = client.post(
        "/api/v1/assets",
        headers=headers,
        json={"type": "laptop", "asset_tag": "not-a-tag"},
    )
    assert create_bad.status_code == 400


def test_specifications_and_numeric_fields_round_trip() -> None:
    client, _ = build_app()
    headers = login(client)

    created = client.post(
        "/api/v1/assets",
        headers=headers,
        json={
            "type": "laptop",
            "vendor_name": "Acme Corp",
            "invoice_number": "INV-42",
            "purchase_price": 0,
            "specifications": {"cpu_cores": 8, "architecture": "x64"},
        },
    )
    assert created.status_code in (200, 201)
    body = created.json()
    assert body["vendor_name"] == "Acme Corp"
    assert body["invoice_number"] == "INV-42"
    assert body["purchase_price"] == 0
    assert body["specifications"] == {"cpu_cores": 8, "architecture": "x64"}

    asset_id = body["id"]
    fetched = client.get(f"/api/v1/assets/{asset_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["specifications"] == {"cpu_cores": 8, "architecture": "x64"}

    patched = client.patch(f"/api/v1/assets/{asset_id}", headers=headers, json={"specifications": None})
    assert patched.status_code == 200
    assert patched.json()["specifications"] is None


def test_update_asset_renames_tag_and_clears_status() -> None:
    client, _ = build_app()
    headers = login(client)
    asset_id = client.post("/api/v1/assets", headers=headers, json={"type": "desktop", "status": "active"}).json()["id"]

    patched = client.patch(
        f"/api/v1/assets/{asset_id}",
        headers=headers,
        json={"asset_tag": "dsx-0042", "status": None},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["asset_tag"] == "DSX-0042"
    assert body["status"] is None


def test_report_rows_export_vendor_name_and_invoice_number() -> None:
    client, sessions = build_app()
    headers = login(client)
    client.post(
        "/api/v1/assets",
        headers=headers,
        json={
            "type": "server",
            "vendor_name": "HPE",
            "invoice_number": "INV-7",
            "purchase_price": 1200.5,
        },
    )

    with sessions() as session:
        rows = asset_report_rows(session)
        assert len(rows) == 1
        row = rows[0]
        keys = list(row.keys())
        assert len(keys) == len(set(keys)), f"duplicate report keys: {keys}"
        assert "vendor" not in keys
        assert row["vendor_name"] == "HPE"
        assert row["invoice_number"] == "INV-7"


def test_spec_extract_endpoint() -> None:
    client, _ = build_app()
    headers = login(client)

    ok = client.post("/api/v1/spec-extract", headers=headers, data={"text": SYSTEMINFO_SAMPLE})
    assert ok.status_code == 200
    body = ok.json()
    assert body["provider"]["id"] == "systeminfo"
    assert {c["key"] for c in body["candidates"]} >= {"hostname", "manufacturer", "ram_mb"}

    unknown = client.post("/api/v1/spec-extract", headers=headers, data={"text": "hello world"})
    assert unknown.status_code == 422

    assert client.post("/api/v1/spec-extract", data={"text": SYSTEMINFO_SAMPLE}).status_code == 401


def test_spec_extract_accepts_log_files() -> None:
    """The UI accepts .txt and .log; the endpoint must accept both."""
    client, _ = build_app()
    headers = login(client)

    log_upload = client.post(
        "/api/v1/spec-extract",
        headers=headers,
        files={"file": ("system.log", SYSTEMINFO_SAMPLE.encode("utf-8"), "text/plain")},
    )
    assert log_upload.status_code == 200
    assert log_upload.json()["provider"]["id"] == "systeminfo"

    txt_upload = client.post(
        "/api/v1/spec-extract",
        headers=headers,
        files={"file": ("system.txt", SYSTEMINFO_SAMPLE.encode("utf-8"), "text/plain")},
    )
    assert txt_upload.status_code == 200

    bad_ext = client.post(
        "/api/v1/spec-extract",
        headers=headers,
        files={"file": ("system.exe", SYSTEMINFO_SAMPLE.encode("utf-8"), "application/octet-stream")},
    )
    assert bad_ext.status_code == 415


def test_collector_scripts_downloadable() -> None:
    """Both collector scripts must be served by the static mount."""
    static_dir = Path(__file__).resolve().parents[2] / "app" / "static"
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    client = TestClient(app)

    for name in ("collect_windows_specs.ps1", "collect_linux_specs.sh"):
        resp = client.get(f"/static/scripts/{name}")
        assert resp.status_code == 200, f"{name} not downloadable"
        assert len(resp.content) > 100, f"{name} appears empty"
        # Verify expected content markers
        if name.endswith(".ps1"):
            assert "systeminfo" in resp.text
            assert "dxdiag" in resp.text
        else:
            assert "hostnamectl" in resp.text
            assert "lscpu" in resp.text
            # Shell scripts must use LF line endings
            assert b"\r\n" not in resp.content, f"{name} contains CRLF line endings"


def test_full_flow_extract_apply_create_asset_visible() -> None:
    """
    Regression test for the "Apply Selected but asset not visible" bug.

    Flow:
    1. Extract from multiple report files (simulated via multiple spec-extract calls)
    2. Apply selected candidates to form (frontend applyExtraction logic simulated)
    3. Create Asset via POST /api/v1/assets
    4. Verify asset appears in GET /api/v1/assets list
    """
    client, _ = build_app()
    headers = login(client)

    # Step 1: Extract from systeminfo report
    extract_resp = client.post("/api/v1/spec-extract", headers=headers, data={"text": SYSTEMINFO_SAMPLE})
    assert extract_resp.status_code == 200
    extract_data = extract_resp.json()
    assert extract_data["provider"]["id"] == "systeminfo"

    # Step 2: Simulate frontend applyExtraction - pick candidates to apply
    candidates = extract_data["candidates"]
    candidate_map = {c["key"]: c for c in candidates}

    # Build payload from selected extracted fields (simulating manual + extracted)
    payload = {
        "type": "laptop",  # Required field not in extraction
        "asset_name": "Extracted Laptop",  # Manual entry
        "hostname": candidate_map.get("hostname", {}).get("value", ""),
        "manufacturer": candidate_map.get("manufacturer", {}).get("value", ""),
        "model": candidate_map.get("model", {}).get("value", ""),
        "serial_number": candidate_map.get("serial_number", {}).get("value", ""),
        "ip_address": candidate_map.get("ip_address", {}).get("value", ""),
        "ram_mb": candidate_map.get("ram_mb", {}).get("value"),
        "cpu_name": candidate_map.get("cpu_name", {}).get("value", ""),
        "cpu_cores": candidate_map.get("cpu_cores", {}).get("value"),
        "logical_cpu_cores": candidate_map.get("logical_cpu_cores", {}).get("value"),
        "gpu_name": candidate_map.get("gpu_name", {}).get("value", ""),
        "specifications": {
            "cpu_cores": candidate_map.get("cpu_cores", {}).get("value"),
            "logical_cpu_cores": candidate_map.get("logical_cpu_cores", {}).get("value"),
        },
    }

    # Filter out None values
    payload = {k: v for k, v in payload.items() if v is not None and v != ""}

    # Step 3: Create Asset via POST
    create_resp = client.post("/api/v1/assets", headers=headers, json=payload)
    assert create_resp.status_code in (200, 201), f"Create failed: {create_resp.text}"
    created = create_resp.json()
    asset_id = created["id"]
    asset_tag = created["asset_tag"]

    # Verify extracted fields were persisted
    assert created["hostname"] == candidate_map["hostname"]["value"]
    assert created["manufacturer"] == candidate_map["manufacturer"]["value"]
    assert created["ram_mb"] == candidate_map["ram_mb"]["value"]
    assert created["specifications"]["cpu_cores"] == candidate_map["cpu_cores"]["value"]

    # Step 4: Verify asset appears in list (the critical bug was here)
    list_resp = client.get("/api/v1/assets", headers=headers)
    assert list_resp.status_code == 200
    assets = list_resp.json()
    asset_tags = [a["asset_tag"] for a in assets]
    assert asset_tag in asset_tags, f"Created asset {asset_tag} not found in list: {asset_tags}"

    # Also verify by ID
    get_resp = client.get(f"/api/v1/assets/{asset_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["asset_tag"] == asset_tag


def test_manual_mode_all_fields_editable() -> None:
    """
    Verify that all asset fields can be manually entered without extraction.
    This tests the 'Manual' button requirement - all fields including
    Procurement & Lifecycle and Location & Assignment should be available.
    """
    client, _ = build_app()
    headers = login(client)

    # Create asset with all possible fields manually entered
    payload = {
        "type": "desktop",
        "asset_tag": "MAN-0001",
        "asset_name": "Manual Desktop",
        "category": "Desktop",
        "manufacturer": "HP",
        "brand": "HP",
        "model": "EliteDesk 800",
        "serial_number": "SN-MANUAL-123",
        "ram_mb": 32768,
        "cpu_name": "Intel i7-13700",
        "gpu_name": "Intel UHD 770",
        "os_name": "Windows 11 Pro",
        "os_version": "23H2",
        "bios_version": "1.05",
        "hostname": "MANUAL-DT-01",
        "ip_address": "10.0.0.50",
        "location": "HQ Building",
        "building": "HQ",
        "room": "Server Room",
        "desk": "Rack 1",
        "rack": "R01",
        "rack_unit": "10",
        "org_unit": "IT Operations",
        "status": "active",
        "vendor_name": "CDW",
        "currency": "USD",
        "invoice_number": "INV-MAN-001",
        "purchase_date": "2024-01-15",
        "purchase_price": 1250.00,
        "warranty_expiration_date": "2027-01-15",
        "support_expiration_date": "2027-01-15",
        "notes": "Manually entered asset",
        "specifications": {
            "cpu_cores": 16,
            "logical_cpu_cores": 24,
            "architecture": "x64",
            "storage_type": "NVMe SSD",
            "storage_capacity": "1 TB",
        },
    }

    create_resp = client.post("/api/v1/assets", headers=headers, json=payload)
    assert create_resp.status_code in (200, 201), f"Create failed: {create_resp.text}"
    created = create_resp.json()

    # Verify all fields persisted correctly
    assert created["asset_tag"] == "MAN-0001"
    assert created["asset_name"] == "Manual Desktop"
    assert created["location"] == "HQ Building"
    assert created["building"] == "HQ"
    assert created["room"] == "Server Room"
    assert created["vendor_name"] == "CDW"
    assert created["purchase_price"] == 1250.00
    assert created["specifications"]["storage_type"] == "NVMe SSD"
    assert created["specifications"]["storage_capacity"] == "1 TB"

    # Verify appears in list
    list_resp = client.get("/api/v1/assets", headers=headers)
    assert list_resp.status_code == 200
    assets = list_resp.json()
    asset_tags = [a["asset_tag"] for a in assets]
    assert "MAN-0001" in asset_tags


def test_create_asset_purchase_price_zero_and_nullable_dates() -> None:
    """
    Verify purchase_price = 0 is accepted (not treated as missing)
    and nullable dates work correctly.
    """
    client, _ = build_app()
    headers = login(client)

    payload = {
        "type": "server",
        "asset_tag": "SRV-0001",  # Valid format
        "purchase_price": 0,  # Zero price should be valid
        "purchase_date": None,  # Unknown date
        "warranty_expiration_date": None,
        "support_expiration_date": None,
    }

    create_resp = client.post("/api/v1/assets", headers=headers, json=payload)
    assert create_resp.status_code in (200, 201), f"Create failed: {create_resp.text}"
    created = create_resp.json()

    assert created["purchase_price"] == 0
    assert created["purchase_date"] is None
    assert created["warranty_expiration_date"] is None
    assert created["support_expiration_date"] is None

    # Verify in list
    list_resp = client.get("/api/v1/assets", headers=headers)
    assert list_resp.status_code == 200
    assets = list_resp.json()
    assert any(a["asset_tag"] == "SRV-0001" for a in assets)


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
