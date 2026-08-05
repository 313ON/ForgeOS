from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    """Pydantic base model configured for SQLAlchemy objects."""

    model_config = ConfigDict(from_attributes=True)


class PersonSummary(ORMModel):
    """Compact person representation embedded in asset responses."""

    id: int
    full_name: str
    org_unit: str | None = None
    job_role: str | None = None


class AssetSummary(ORMModel):
    """Compact asset representation embedded in person responses."""

    id: int
    asset_tag: str
    type: str
    status: str | None = None
    location: str | None = None


class AssetBase(BaseModel):
    asset_tag: str | None = Field(default=None, max_length=100)
    type: str = Field(min_length=1, max_length=100)
    asset_name: str | None = None
    category: str | None = None
    internal_inventory_number: str | None = None
    brand: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    ram_mb: int | None = Field(default=None, ge=0)
    cpu_name: str | None = None
    gpu_name: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    bios_version: str | None = None
    serial_number: str | None = None
    hostname: str | None = None
    ip_address: str | None = None
    location: str | None = None
    building: str | None = None
    room: str | None = None
    desk: str | None = None
    rack: str | None = None
    rack_unit: str | None = None
    org_unit: str | None = None
    status: str | None = None
    vendor_name: str | None = None
    currency: str | None = None
    invoice_number: str | None = None
    purchase_date: date | None = None
    purchase_price: float | None = Field(default=None, ge=0)
    warranty_expiration_date: date | None = None
    support_expiration_date: date | None = None
    invoice_path: str | None = None
    specifications: dict[str, Any] | None = None
    notes: str | None = None


class AssetCreate(AssetBase):
    """Fields accepted when creating an asset."""

    pass


class AssetUpdate(BaseModel):
    """Partial asset update; omitted fields remain unchanged."""

    asset_tag: str | None = Field(default=None, min_length=1, max_length=100)
    type: str | None = Field(default=None, min_length=1, max_length=100)
    asset_name: str | None = None
    category: str | None = None
    internal_inventory_number: str | None = None
    brand: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    ram_mb: int | None = Field(default=None, ge=0)
    cpu_name: str | None = None
    gpu_name: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    bios_version: str | None = None
    serial_number: str | None = None
    hostname: str | None = None
    ip_address: str | None = None
    location: str | None = None
    building: str | None = None
    room: str | None = None
    desk: str | None = None
    rack: str | None = None
    rack_unit: str | None = None
    org_unit: str | None = None
    status: str | None = None
    vendor_name: str | None = None
    currency: str | None = None
    invoice_number: str | None = None
    purchase_date: date | None = None
    purchase_price: float | None = Field(default=None, ge=0)
    warranty_expiration_date: date | None = None
    support_expiration_date: date | None = None
    invoice_path: str | None = None
    specifications: dict[str, Any] | None = None
    notes: str | None = None


class AssetRead(ORMModel, AssetBase):
    """Asset response including current custodian information."""

    id: int
    asset_tag: str
    created_at: datetime
    updated_at: datetime
    custodian: PersonSummary | None = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1)


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=10)
    role: Literal["ADMIN", "VIEW"] = "VIEW"


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=10)
    role: Literal["ADMIN", "VIEW"] | None = None
    is_active: bool | None = None


class UserRead(ORMModel):
    id: int
    username: str
    role: Literal["ADMIN", "VIEW"]
    is_active: bool
    created_at: datetime


class PersonCreate(BaseModel):
    """Fields accepted when creating or updating a person."""

    full_name: str = Field(min_length=1, max_length=150)
    org_unit: str | None = None
    job_role: str | None = None
    email: str | None = None
    phone: str | None = None
    status: str | None = "active"
    notes: str | None = None


class PersonUpdate(BaseModel):
    """Partial person update."""

    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    org_unit: str | None = None
    job_role: str | None = None
    email: str | None = None
    phone: str | None = None
    status: str | None = None
    notes: str | None = None


class PersonRead(ORMModel, PersonCreate):
    """Person response with currently assigned assets."""

    id: int
    created_at: datetime
    assets: list[AssetSummary] = Field(default_factory=list)


class AssignmentCreate(BaseModel):
    """Fields for creating an asset assignment."""

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
    parsed: dict[str, object]
    suggested_profile: str
    asset_draft: dict[str, object] | None = None


class ExtractCandidate(BaseModel):
    """A single field proposed by a report extraction provider."""

    key: str
    label: str
    value: str | int | float | None = None
    confidence: Literal["high", "medium", "low"]
    target: Literal["asset", "spec"] = "asset"
    source: str


class ExtractProvider(BaseModel):
    """Metadata for a report extraction provider."""

    id: str
    name: str
    sourceType: Literal["windows", "linux"]
    retentionPolicy: str


class ExtractResponse(BaseModel):
    """Field candidates extracted from a user-supplied report."""

    provider: ExtractProvider
    candidates: list[ExtractCandidate]


class TargetCreate(BaseModel):
    """Public fields accepted when registering a monitored target."""

    name: str = Field(min_length=1, max_length=150)
    ip_or_host: str = Field(min_length=1, max_length=255)
    target_type: Literal["website", "network"] = "network"
    ping_interval_sec: int = Field(default=60, ge=5)
    timeout_sec: float = Field(default=5.0, gt=0, le=60)
    enabled: bool = True
    expected_status_code: int | None = Field(default=None, ge=100, le=599)
    allow_private_networks: bool = False
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    web_port: int | None = Field(default=None, ge=1, le=65535)
    camera_stream_url: str | None = Field(default=None, max_length=500)


class TargetUpdate(BaseModel):
    """Mutable target fields; credential contents are never returned."""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    ip_or_host: str | None = Field(default=None, min_length=1, max_length=255)
    target_type: Literal["website", "network"] | None = None
    ping_interval_sec: int | None = Field(default=None, ge=5)
    timeout_sec: float | None = Field(default=None, gt=0, le=60)
    enabled: bool | None = None
    expected_status_code: int | None = Field(default=None, ge=100, le=599)
    allow_private_networks: bool | None = None
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    web_port: int | None = Field(default=None, ge=1, le=65535)
    credentials_info: str | None = None
    camera_stream_url: str | None = Field(default=None, max_length=500)
    status: Literal["PASS", "WARNING", "FAILED", "UNKNOWN"] | None = None


class TargetOut(ORMModel):
    """Safe target response that never exposes credential contents."""

    id: int
    name: str
    ip_or_host: str
    target_type: str
    ping_interval_sec: int
    timeout_sec: float
    enabled: bool
    expected_status_code: int | None
    allow_private_networks: bool
    ssh_port: int | None
    web_port: int | None
    camera_stream_url: str | None
    status: Literal["PASS", "WARNING", "FAILED", "UNKNOWN"]
    last_latency_ms: float | None
    last_checked_at: datetime | None
    last_error: str | None
    ssl_metadata: dict[str, object] | None = None
    created_at: datetime
    credentials_configured: bool = False


TargetListItem = TargetOut


class NetworkLogOut(ORMModel):
    """A safe monitoring event response."""

    id: int
    target_id: int
    latency_ms: float | None
    status_code: Literal[-1, 0, 1]
    check_type: str
    status: Literal["PASS", "WARNING", "FAILED", "UNKNOWN"]
    message: str | None = None
    response_status_code: int | None = None
    timestamp: datetime


class ExportLogOut(ORMModel):
    """A safe export log entry response."""

    id: int
    export_type: str
    created_at: datetime
    username: str
