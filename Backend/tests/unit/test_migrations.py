import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool
from Backend.app.db.migrations import _repair_dangling_network_logs_fk

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
