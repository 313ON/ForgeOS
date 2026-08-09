from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "forgeos.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"


class Base(DeclarativeBase):
    """Base class for ForgeOS database models."""


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
    """Enable SQLite foreign-key enforcement for every connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def initialize_database() -> None:
    """Create the SQLite database and all registered tables."""
    from .domain import models  # noqa: F401

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    from .db.migrations import (
        migrate_asset_columns,
        migrate_export_log_table,
        migrate_phase_6_topology,
    )

    migrate_asset_columns(engine)
    migrate_export_log_table(engine)
    migrate_phase_6_topology(engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for a FastAPI request."""
    with SessionLocal() as session:
        yield session
