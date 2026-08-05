from __future__ import annotations

import logging
import re
import sqlite3
from sqlalchemy import Engine, inspect, text


TABLE_MIGRATIONS: dict[str, dict[str, str]] = {
    "assets": {
        "manufacturer": "VARCHAR(100)",
        "asset_name": "VARCHAR(255)",
        "category": "VARCHAR(100)",
        "internal_inventory_number": "VARCHAR(100)",
        "ram_mb": "INTEGER",
        "cpu_name": "VARCHAR(255)",
        "gpu_name": "VARCHAR(255)",
        "os_name": "VARCHAR(255)",
        "os_version": "VARCHAR(255)",
        "bios_version": "VARCHAR(255)",
        "purchase_date": "DATE",
        "purchase_price": "FLOAT",
        "vendor_name": "VARCHAR(150)",
        "currency": "VARCHAR(10)",
        "invoice_number": "VARCHAR(100)",
        "warranty_expiration_date": "DATE",
        "support_expiration_date": "DATE",
        "building": "VARCHAR(150)",
        "room": "VARCHAR(150)",
        "desk": "VARCHAR(150)",
        "rack": "VARCHAR(100)",
        "rack_unit": "VARCHAR(50)",
        "specifications": "TEXT",
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
    added.extend(_repair_dangling_network_logs_fk(engine))
    added.extend(_make_asset_status_nullable(engine))
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE assets SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP) WHERE updated_at IS NULL")
        )
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


def _make_asset_status_nullable(engine: Engine) -> list[str]:
    """Drop the NOT NULL constraint on assets.status without touching row data.

    SQLite cannot ALTER a column, so when the legacy column is declared NOT NULL
    the table is rebuilt with the constraint removed. Existing status values are
    preserved verbatim; rows with a NULL status are simply left alone.
    """
    inspector = inspect(engine)
    if "assets" not in inspector.get_table_names():
        return []
    status_col = next(
        (column for column in inspector.get_columns("assets") if column["name"] == "status"),
        None,
    )
    if status_col is None or status_col.get("nullable", True):
        return []

    connection = engine.raw_connection()
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("PRAGMA legacy_alter_table=ON")
        cursor = connection.cursor()
        columns = [row[1] for row in cursor.execute("PRAGMA table_info(assets)").fetchall()]
        table_sql = cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'assets'"
        ).fetchone()[0]
        rebuilt_sql = re.sub(r"(?i)(status\s+[^,]+?)\s+NOT\s+NULL\b", r"\1", table_sql, count=1)
        if rebuilt_sql == table_sql:
            raise RuntimeError("Could not rewrite assets.status column to be nullable")
        index_defs = cursor.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type = 'index' AND tbl_name = 'assets' AND sql IS NOT NULL "
            "AND name NOT LIKE 'sqlite_autoindex%'"
        ).fetchall()
        index_columns = {
            name: [row[2] for row in cursor.execute(f"PRAGMA index_info('{name}')").fetchall()]
            for name, _ in index_defs
        }
        column_list = ", ".join(columns)
        cursor.execute("ALTER TABLE assets RENAME TO assets_legacy")
        cursor.execute(rebuilt_sql)
        cursor.execute(
            f"INSERT INTO assets ({column_list}) SELECT {column_list} FROM assets_legacy"
        )
        cursor.execute("DROP TABLE assets_legacy")
        new_columns = {row[1] for row in cursor.execute("PRAGMA table_info(assets)").fetchall()}
        for name, sql in index_defs:
            if all(column in new_columns for column in index_columns[name]):
                cursor.execute(sql)
        connection.commit()
        return ["assets.status_nullable"]
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA legacy_alter_table=OFF")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.close()


def _repair_dangling_network_logs_fk(engine: Engine) -> list[str]:
    """Re-point network_logs to monitored_targets when its FK is dangling.

    The legacy monitored_targets rebuild renames the original table to
    monitored_targets_legacy before recreating monitored_targets; if
    network_logs still references that dropped table, its foreign key is
    dangling. This rebuild is idempotent and only runs when a foreign key
    references monitored_targets_legacy, so it is safe to call on startup.
    """
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "network_logs" not in table_names:
        return []
    dangling = any(
        fk.get("referred_table") == "monitored_targets_legacy"
        for fk in inspector.get_foreign_keys("network_logs")
    )
    if not dangling:
        return []
    connection = engine.raw_connection()
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("PRAGMA legacy_alter_table=ON")
        cursor = connection.cursor()
        cursor.execute("PRAGMA table_info(network_logs)")
        column_list = ", ".join(row[1] for row in cursor.fetchall())
        cursor.execute("ALTER TABLE network_logs RENAME TO network_logs_legacy")
        cursor.execute(
            """
            CREATE TABLE network_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id INTEGER NOT NULL,
                latency_ms FLOAT,
                status_code INTEGER,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                check_type VARCHAR(30) NOT NULL DEFAULT 'network',
                status VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
                message TEXT,
                response_status_code INTEGER,
                FOREIGN KEY(target_id) REFERENCES monitored_targets(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            f"INSERT INTO network_logs ({column_list}) SELECT {column_list} FROM network_logs_legacy"
        )
        cursor.execute("DROP TABLE network_logs_legacy")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_network_logs_timestamp ON network_logs(timestamp)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_network_logs_target_timestamp ON network_logs(target_id, timestamp)"
        )
        connection.commit()
        return ["network_logs.foreign_key_repaired"]
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA legacy_alter_table=OFF")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.close()


def repair_network_logs_fk(db_path: str):
    logger = logging.getLogger("migrations")
    CREATE_TABLE_SQL = """
    CREATE TABLE network_logs_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER NOT NULL,
        latency_ms FLOAT,
        status_code INTEGER,
        timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        check_type VARCHAR(30) NOT NULL DEFAULT 'network',
        status VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
        message TEXT,
        response_status_code INTEGER,
        FOREIGN KEY(target_id) REFERENCES monitored_targets(id) ON DELETE CASCADE
    );
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute(CREATE_TABLE_SQL)
        cols = [row[1] for row in cursor.execute("PRAGMA table_info(network_logs)").fetchall()]
        col_str = ", ".join(cols)
        cursor.execute(f"INSERT INTO network_logs_new ({col_str}) SELECT {col_str} FROM network_logs")
        cursor.execute("DROP TABLE network_logs")
        cursor.execute("ALTER TABLE network_logs_new RENAME TO network_logs")
        
        fk_list = cursor.execute("PRAGMA foreign_key_list(network_logs)").fetchall()
        if not any(fk[2] == 'monitored_targets' for fk in fk_list):
            raise Exception("FK repair failed: Target mismatch.")

        cursor.execute("PRAGMA foreign_keys=ON")
        conn.commit()
        logger.info(f"Fixed FK for {db_path}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Migration error: {e}")
        raise
    finally:
        conn.close()


def migrate_export_log_table(engine: Engine) -> list[str]:
    """Create the export_logs table if it does not exist (idempotent)."""
    added: list[str] = []
    inspector = inspect(engine)
    if "export_logs" in inspector.get_table_names():
        return added
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE export_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    export_type VARCHAR(10) NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER NOT NULL,
                    username VARCHAR(100) NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )
        )
        added.append("export_logs")
    return added
