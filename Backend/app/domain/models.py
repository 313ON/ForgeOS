from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Asset(Base):
    """An IT asset managed by ForgeOS."""

    __tablename__ = "assets"
    __table_args__ = (
        Index("ix_assets_asset_tag", "asset_tag"),
        Index("ix_assets_serial_number", "serial_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_tag: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(150))
    serial_number: Mapped[str | None] = mapped_column(String(150))
    location: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    purchase_date: Mapped[date | None] = mapped_column(Date)
    purchase_price: Mapped[float | None] = mapped_column(Float)
    invoice_path: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )
    warranties: Mapped[list[Warranty]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )
    snapshots: Mapped[list[SystemSnapshot]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )


class Person(Base):
    """A person who can receive an asset assignment."""

    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    org_unit: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    assignments: Mapped[list[Assignment]] = relationship(back_populates="person")


class Assignment(Base):
    """A dated assignment of an asset to a person or location."""

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    person_id: Mapped[int | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"),
    )
    location_override: Mapped[str | None] = mapped_column(String(150))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    asset: Mapped[Asset] = relationship(back_populates="assignments")
    person: Mapped[Person | None] = relationship(back_populates="assignments")


class Warranty(Base):
    """Warranty or support coverage for an asset."""

    __tablename__ = "warranties"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    vendor: Mapped[str] = mapped_column(String(150), nullable=False)
    contract_no: Mapped[str | None] = mapped_column(String(100))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    asset: Mapped[Asset] = relationship(back_populates="warranties")


class SystemSnapshot(Base):
    """Parsed system information captured from an uploaded text report."""

    __tablename__ = "system_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    parsed_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    asset: Mapped[Asset | None] = relationship(back_populates="snapshots")
