from __future__ import annotations

from datetime import date, datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    """Pydantic base model configured for SQLAlchemy objects."""

    model_config = ConfigDict(from_attributes=True)


class AssetBase(BaseModel):
    asset_tag: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=100)
    brand: str | None = None
    model: str | None = None
    serial_number: str | None = None
    location: str | None = None
    status: str = "active"
    purchase_date: date | None = None
    purchase_price: float | None = Field(default=None, ge=0)
    invoice_path: str | None = None
    notes: str | None = None


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    asset_tag: str | None = Field(default=None, min_length=1, max_length=100)
    type: str | None = Field(default=None, min_length=1, max_length=100)
    brand: str | None = None
    model: str | None = None
    serial_number: str | None = None
    location: str | None = None
    status: str | None = None
    purchase_date: date | None = None
    purchase_price: float | None = Field(default=None, ge=0)
    invoice_path: str | None = None
    notes: str | None = None


class AssetRead(ORMModel, AssetBase):
    id: int
    created_at: datetime


class PersonCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    org_unit: str | None = None
    email: str | None = None
    phone: str | None = None


class PersonRead(ORMModel, PersonCreate):
    id: int
    created_at: datetime


class AssignmentCreate(BaseModel):
    asset_id: int
    person_id: int | None = None
    location_override: str | None = None
    start_date: date
    end_date: date | None = None
    notes: str | None = None


class AssignmentRead(ORMModel, AssignmentCreate):
    id: int


class IngestResponse(BaseModel):
    snapshot_id: int
    source: str
    filename: str
    parsed: dict[str, str | int | None]
    suggested_profile: str


class TargetCreate(BaseModel):
    """Public fields accepted when registering a monitored target."""

    name: str = Field(min_length=1, max_length=150)
    ip_or_host: str = Field(min_length=1, max_length=255)
    target_type: str = Field(min_length=1, max_length=50)
    ping_interval_sec: int = Field(default=60, ge=5)
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    web_port: int | None = Field(default=None, ge=1, le=65535)
    camera_stream_url: str | None = Field(default=None, max_length=500)


class TargetUpdate(BaseModel):
    """Mutable target fields; credentials can only be supplied through PUT."""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    ip_or_host: str | None = Field(default=None, min_length=1, max_length=255)
    target_type: str | None = Field(default=None, min_length=1, max_length=50)
    ping_interval_sec: int | None = Field(default=None, ge=5)
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    web_port: int | None = Field(default=None, ge=1, le=65535)
    credentials_info: str | None = None
    camera_stream_url: str | None = Field(default=None, max_length=500)
    status: Literal["online", "offline", "unknown"] | None = None


class TargetOut(ORMModel):
    """Safe target response that never exposes credential contents."""

    id: int
    name: str
    ip_or_host: str
    target_type: str
    ping_interval_sec: int
    ssh_port: int | None
    web_port: int | None
    camera_stream_url: str | None
    status: Literal["online", "offline", "unknown"]
    last_latency_ms: float | None
    last_checked_at: datetime | None
    created_at: datetime
    credentials_configured: bool = False


TargetListItem = TargetOut


class NetworkLogOut(ORMModel):
    """A safe network check result for charting."""

    id: int
    target_id: int
    latency_ms: float | None
    status_code: Literal[-1, 0, 1]
    timestamp: datetime
