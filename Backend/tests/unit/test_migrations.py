import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool
from Backend.app.db.migrations import _make_asset_status_nullable, _repair_dangling_network_logs_fk

def test_repair_dangling_network_logs_fk():
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE monitored_targets (id INTEGER PRIMARY KEY)")
        conn.exec_driver_sql("""
CREATE TABLE network_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(target_id) REFERENCES monitored_targets_legacy(id) ON DELETE CASCADE
)
""")
        conn.exec_driver_sql("INSERT INTO network_logs (target_id) VALUES (1)")

    # Assert broken FK
    inspector = inspect(engine)
    fks = inspector.get_foreign_keys("network_logs")
    assert fks[0]["referred_table"] == "monitored_targets_legacy"

    # Execute repair
    res = _repair_dangling_network_logs_fk(engine)
    assert res == ["network_logs.foreign_key_repaired"]

    # Assert repaired FK
    inspector = inspect(engine)
    fks = inspector.get_foreign_keys("network_logs")
    assert fks[0]["referred_table"] == "monitored_targets"

    # Assert data preserved
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT target_id FROM network_logs").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 1

    # Assert idempotency
    res_second = _repair_dangling_network_logs_fk(engine)
    assert res_second == []


def test_make_asset_status_nullable():
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE assets (
                id INTEGER NOT NULL PRIMARY KEY,
                asset_tag VARCHAR(100) NOT NULL UNIQUE,
                type VARCHAR(100) NOT NULL,
                status VARCHAR(50) NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.exec_driver_sql(
            "INSERT INTO assets (id, asset_tag, type, status) VALUES (1, 'LAP-0001', 'laptop', 'active')"
        )
        conn.exec_driver_sql(
            "INSERT INTO assets (id, asset_tag, type, status) VALUES (2, 'LAP-0002', 'laptop', 'maintenance')"
        )

    # Status starts NOT NULL
    inspector = inspect(engine)
    status_before = next(c for c in inspector.get_columns("assets") if c["name"] == "status")
    assert status_before["nullable"] is False

    # Execute migration
    res = _make_asset_status_nullable(engine)
    assert res == ["assets.status_nullable"]

    # Status is now nullable
    inspector = inspect(engine)
    status_after = next(c for c in inspector.get_columns("assets") if c["name"] == "status")
    assert status_after["nullable"] is True

    # Existing values preserved verbatim
    with engine.connect() as conn:
        values = conn.exec_driver_sql("SELECT status FROM assets ORDER BY id").fetchall()
        assert values == [("active",), ("maintenance",)]

    # NULL status can now be stored
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO assets (id, asset_tag, type, status) VALUES (3, 'LAP-0003', 'laptop', NULL)"
        )

    # Unique constraint on asset_tag preserved
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO assets (id, asset_tag, type, status) VALUES (4, 'LAP-0001', 'laptop', 'active')"
            )

    # Idempotency
    assert _make_asset_status_nullable(engine) == []


def test_make_asset_status_nullable_skips_when_already_nullable():
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE assets (
                id INTEGER NOT NULL PRIMARY KEY,
                asset_tag VARCHAR(100) NOT NULL UNIQUE,
                type VARCHAR(100) NOT NULL,
                status VARCHAR(50),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    assert _make_asset_status_nullable(engine) == []
