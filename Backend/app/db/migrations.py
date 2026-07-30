from __future__ import annotations

from sqlalchemy import Engine, inspect, text


ASSET_COLUMN_MIGRATIONS: dict[str, str] = {
    "purchase_date": "DATE",
    "purchase_price": "FLOAT",
    "invoice_path": "VARCHAR(500)",
}


def migrate_asset_columns(engine: Engine) -> list[str]:
    """Add missing nullable financial columns to an existing SQLite assets table."""
    inspector = inspect(engine)
    if "assets" not in inspector.get_table_names():
        return []

    existing_columns = {column["name"] for column in inspector.get_columns("assets")}
    added_columns: list[str] = []
    with engine.begin() as connection:
        for column_name, column_definition in ASSET_COLUMN_MIGRATIONS.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(f"ALTER TABLE assets ADD COLUMN {column_name} {column_definition}")
            )
            added_columns.append(column_name)
    return added_columns
