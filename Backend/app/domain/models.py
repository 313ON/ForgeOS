from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
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
    asset_tag: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asset_name: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(100))
    internal_inventory_number: Mapped[str | None] = mapped_column(String(100))
    brand: Mapped[str | None] = mapped_column(String(100))
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(150))
    ram_mb: Mapped[int | None] = mapped_column(Integer)
    cpu_name: Mapped[str | None] = mapped_column(String(255))
    gpu_name: Mapped[str | None] = mapped_column(String(255))
    os_name: Mapped[str | None] = mapped_column(String(255))
    os_version: Mapped[str | None] = mapped_column(String(255))
    bios_version: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(150))
    hostname: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(150))
    building: Mapped[str | None] = mapped_column(String(150))
    room: Mapped[str | None] = mapped_column(String(150))
    desk: Mapped[str | None] = mapped_column(String(150))
    rack: Mapped[str | None] = mapped_column(String(100))
    rack_unit: Mapped[str | None] = mapped_column(String(50))
    org_unit: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[str | None] = mapped_column(String(50))
    vendor_name: Mapped[str | None] = mapped_column(String(150))
    currency: Mapped[str | None] = mapped_column(String(10))
    invoice_number: Mapped[str | None] = mapped_column(String(100))
    purchase_date: Mapped[date | None] = mapped_column(Date)
    purchase_price: Mapped[float | None] = mapped_column(Float)
    warranty_expiration_date: Mapped[date | None] = mapped_column(Date)
    support_expiration_date: Mapped[date | None] = mapped_column(Date)
    invoice_path: Mapped[str | None] = mapped_column(String(500))
    specifications: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    warranties: Mapped[list[Warranty]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list[SystemSnapshot]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )


class User(Base):
    """A local ForgeOS operator account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="VIEW", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Person(Base):
    """A person who can receive an asset assignment."""

    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    org_unit: Mapped[str | None] = mapped_column(String(150))
    job_role: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str | None] = mapped_column(String(50), default="active")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    assignments: Mapped[list[Assignment]] = relationship(back_populates="person")


class Assignment(Base):
    """A dated assignment of an asset to a person or location."""

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"))
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
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
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
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    parsed_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    asset: Mapped[Asset | None] = relationship(back_populates="snapshots")


class MonitoredTarget(Base):
    """A website or network endpoint configured for health monitoring."""

    __tablename__ = "monitored_targets"
    __table_args__ = (
        CheckConstraint("ping_interval_sec >= 5", name="ck_monitored_targets_ping_interval_min"),
        Index("ix_monitored_targets_name", "name"),
        Index("ix_monitored_targets_ip_or_host", "ip_or_host"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    ip_or_host: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    ping_interval_sec: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    timeout_sec: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    expected_status_code: Mapped[int | None] = mapped_column(Integer)
    allow_private_networks: Mapped[bool] = mapped_column(default=False, nullable=False)
    ssh_port: Mapped[int | None] = mapped_column(Integer)
    web_port: Mapped[int | None] = mapped_column(Integer)
    credentials_info: Mapped[str | None] = mapped_column(Text)
    camera_stream_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="UNKNOWN", nullable=False)
    last_latency_ms: Mapped[float | None] = mapped_column(Float)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    ssl_metadata: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    logs: Mapped[list[NetworkLog]] = relationship(
        back_populates="target", cascade="all, delete-orphan", passive_deletes=True
    )


class NetworkLog(Base):
    """A point-in-time monitoring result for a target."""

    __tablename__ = "network_logs"
    __table_args__ = (
        CheckConstraint("status_code IN (-1, 0, 1)", name="ck_network_logs_status_code"),
        Index("ix_network_logs_timestamp", "timestamp"),
        Index("ix_network_logs_target_timestamp", "target_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(
        ForeignKey("monitored_targets.id", ondelete="CASCADE"), nullable=False
    )
    latency_ms: Mapped[float | None] = mapped_column(Float)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    check_type: Mapped[str] = mapped_column(String(30), default="network", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="UNKNOWN", nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    response_status_code: Mapped[int | None] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    target: Mapped[MonitoredTarget] = relationship(back_populates="logs")


class ExportLog(Base):
    """Record of a successful asset export."""

    __tablename__ = "export_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    export_type: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
