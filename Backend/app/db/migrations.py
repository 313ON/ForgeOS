from __future__ import annotations

from sqlalchemy import Engine, inspect, text


TABLE_MIGRATIONS: dict[str, dict[str, str]] = {
    "assets": {
        "manufacturer": "VARCHAR(100)",
        "ram_mb": "INTEGER",
        "cpu_name": "VARCHAR(255)",
        "gpu_name": "VARCHAR(255)",
        "os_name": "VARCHAR(255)",
        "os_version": "VARCHAR(255)",
        "bios_version": "VARCHAR(255)",
        "purchase_date": "DATE",
        "purchase_price": "FLOAT",
        "invoice_path": "VARCHAR(500)",
        "hostname": "VARCHAR(255)",
        "ip_address": "VARCHAR(255)",
        "org_unit": "VARCHAR(150)",
        "updated_at": "DATETIME",
    },
    "people": {
        "job_role": "VARCHAR(150)",
        "status": "VARCHAR(50)",
        "notes": "TEXT",
    },
    "monitored_targets": {
        "timeout_sec": "FLOAT NOT NULL DEFAULT 5.0",
        "enabled": "BOOLEAN NOT NULL DEFAULT 1",
        "expected_status_code": "INTEGER",
        "allow_private_networks": "BOOLEAN NOT NULL DEFAULT 0",
        "last_error": "TEXT",
        "ssl_metadata": "TEXT",
    },
    "network_logs": {
        "check_type": "VARCHAR(30) NOT NULL DEFAULT 'network'",
        "status": "VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN'",
        "message": "TEXT",
        "response_status_code": "INTEGER",
    },
    "users": {},
}


def migrate_asset_columns(engine: Engine) -> list[str]:
    """Apply additive, idempotent SQLite migrations without deleting data."""
    added: list[str] = []
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    for table_name, columns in TABLE_MIGRATIONS.items():
        if table_name not in table_names:
            continue
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        missing = [(name, definition) for name, definition in columns.items() if name not in existing]
        if not missing:
            continue
        with engine.begin() as connection:
            for column_name, definition in missing:
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
                )
                added.append(f"{table_name}.{column_name}")
            if table_name == "assets" and any(name == "updated_at" for name, _ in missing):
                connection.execute(text("UPDATE assets SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"))
            if table_name == "network_logs":
                connection.execute(
                    text(
                        "UPDATE network_logs SET status = CASE status "
                        "WHEN 'online' THEN 'PASS' WHEN 'offline' THEN 'FAILED' "
                        "ELSE COALESCE(status, 'UNKNOWN') END"
                    )
                )
        inspector = inspect(engine)
    added.extend(_migrate_legacy_target_status_constraint(engine))
    return added


def _migrate_legacy_target_status_constraint(engine: Engine) -> list[str]:
    """Rebuild the legacy target table when its status CHECK blocks new statuses."""
    inspector = inspect(engine)
    if "monitored_targets" not in inspector.get_table_names():
        return []
    with engine.connect() as connection:
        table_sql = connection.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'monitored_targets'")
        ).scalar_one_or_none()
    if not table_sql or "status IN ('online', 'offline', 'unknown')" not in table_sql:
        return []

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        connection.execute(text("ALTER TABLE monitored_targets RENAME TO monitored_targets_legacy"))
        connection.execute(
            text(
                """
                CREATE TABLE monitored_targets (
                    id INTEGER NOT NULL PRIMARY KEY,
                    name VARCHAR(150) NOT NULL,
                    ip_or_host VARCHAR(255) NOT NULL,
                    target_type VARCHAR(50) NOT NULL,
                    ping_interval_sec INTEGER NOT NULL DEFAULT 60,
                    timeout_sec FLOAT NOT NULL DEFAULT 5.0,
                    enabled BOOLEAN NOT NULL DEFAULT 1,
                    expected_status_code INTEGER,
                    allow_private_networks BOOLEAN NOT NULL DEFAULT 0,
                    ssh_port INTEGER,
                    web_port INTEGER,
                    credentials_info TEXT,
                    camera_stream_url VARCHAR(500),
                    status VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
                    last_latency_ms FLOAT,
                    last_checked_at DATETIME,
                    last_error TEXT,
                    ssl_metadata TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO monitored_targets (
                    id, name, ip_or_host, target_type, ping_interval_sec,
                    ssh_port, web_port, credentials_info, camera_stream_url,
                    status, last_latency_ms, last_checked_at, created_at
                )
                SELECT id, name, ip_or_host, target_type, ping_interval_sec,
                    ssh_port, web_port, credentials_info, camera_stream_url,
                    CASE status WHEN 'online' THEN 'PASS'
                         WHEN 'offline' THEN 'FAILED' ELSE 'UNKNOWN' END,
                    last_latency_ms, last_checked_at, created_at
                FROM monitored_targets_legacy
                """
            )
        )
        connection.execute(text("DROP TABLE monitored_targets_legacy"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_monitored_targets_name ON monitored_targets(name)"))
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_monitored_targets_ip_or_host "
                "ON monitored_targets(ip_or_host)"
            )
        )
        connection.execute(text("PRAGMA foreign_keys=ON"))
    return ["monitored_targets.status_constraint"]
