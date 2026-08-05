"""One-time, idempotent recovery of legacy user accounts from the backup database.

This script restores only the authentication-related data (users table)
from ``Backend/data/forgeos_backup.db`` into the current ``forgeos.db``.
It preserves existing password hashes exactly and does not touch any other
tables or application data.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

BACKUP_DB = Path(__file__).resolve().parents[1] / "Backend" / "data" / "forgeos_backup.db"
CURRENT_DB = Path(__file__).resolve().parents[1] / "Backend" / "data" / "forgeos.db"

USER_COLUMNS = ("id", "username", "password_hash", "role", "is_active", "created_at")


def _fetch_backup_users() -> list[tuple]:
    if not BACKUP_DB.exists():
        raise FileNotFoundError(f"Backup database not found: {BACKUP_DB}")

    with sqlite3.connect(BACKUP_DB) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM users")
        return [tuple(row[col] for col in USER_COLUMNS) for row in cursor.fetchall()]


def recover_users() -> list[str]:
    backup_users = _fetch_backup_users()
    if not backup_users:
        return []

    with sqlite3.connect(CURRENT_DB) as conn:
        cursor = conn.cursor()
        recovered = []
        for user in backup_users:
            user_id, username, password_hash, role, is_active, created_at = user
            cursor.execute(
                """
                INSERT INTO users (id, username, password_hash, role, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                ON CONFLICT(id) DO UPDATE SET
                    username = excluded.username,
                    password_hash = excluded.password_hash,
                    role = excluded.role,
                    is_active = excluded.is_active
                """,
                (user_id, username, password_hash, role, 1 if is_active else 0, created_at),
            )
            recovered.append(username)
        conn.commit()
    return recovered


if __name__ == "__main__":
    recovered = recover_users()
    print("Recovered users:", recovered)
