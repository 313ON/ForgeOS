from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class AssetValidationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("status", check_fields=False)
    @classmethod
    def normalize_status(cls, value: str | None) -> str | None:
        return value.casefold() if value else None

    @field_validator("currency", check_fields=False)
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class AssetBase(AssetValidationModel):
    asset_tag: str | None = Field(default=None, max_length=100)
    type: str | None = Field(default=None, max_length=100)
    asset_name: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    internal_inventory_number: str | None = Field(default=None, max_length=100)
    brand: str | None = Field(default=None, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=150)
    ram_mb: int | None = Field(default=None, ge=0)
    cpu_name: str | None = Field(default=None, max_length=255)
    gpu_name: str | None = Field(default=None, max_length=255)
    os_name: str | None = Field(default=None, max_length=255)
    os_version: str | None = Field(default=None, max_length=255)
    bios_version: str | None = Field(default=None, max_length=255)
    serial_number: str | None = Field(default=None, max_length=150)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=150)
    building: str | None = Field(default=None, max_length=150)
    room: str | None = Field(default=None, max_length=150)
    desk: str | None = Field(default=None, max_length=150)
    rack: str | None = Field(default=None, max_length=100)
    rack_unit: str | None = Field(default=None, max_length=50)
    org_unit: str | None = Field(default=None, max_length=150)
    status: str | None = Field(default=None, max_length=50)
    vendor_name: str | None = Field(default=None, max_length=150)
    currency: str | None = Field(default=None, max_length=10)
    invoice_number: str | None = Field(default=None, max_length=100)
    purchase_date: date | None = None
    purchase_price: float | None = Field(default=None, ge=0)
    warranty_expiration_date: date | None = None
    support_expiration_date: date | None = None
    invoice_path: str | None = Field(default=None, max_length=500)
    specifications: dict[str, Any] | None = None
    notes: str | None = None


class AssetCreate(AssetBase):
    """Fields accepted when creating an asset."""

    cpu_cores: int | None = Field(default=None, ge=0)
    logical_cpu_cores: int | None = Field(default=None, ge=0)
    architecture: str | None = Field(default=None, max_length=100)


class AssetUpdate(AssetValidationModel):
    """Partial asset update; omitted fields remain unchanged."""

    asset_tag: str | None = Field(default=None, min_length=1, max_length=100)
    type: str | None = Field(default=None, min_length=1, max_length=100)
    asset_name: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    internal_inventory_number: str | None = Field(default=None, max_length=100)
    brand: str | None = Field(default=None, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=150)
    ram_mb: int | None = Field(default=None, ge=0)
    cpu_name: str | None = Field(default=None, max_length=255)
    gpu_name: str | None = Field(default=None, max_length=255)
    os_name: str | None = Field(default=None, max_length=255)
    os_version: str | None = Field(default=None, max_length=255)
    bios_version: str | None = Field(default=None, max_length=255)
    serial_number: str | None = Field(default=None, max_length=150)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=150)
    building: str | None = Field(default=None, max_length=150)
    room: str | None = Field(default=None, max_length=150)
    desk: str | None = Field(default=None, max_length=150)
    rack: str | None = Field(default=None, max_length=100)
    rack_unit: str | None = Field(default=None, max_length=50)
    org_unit: str | None = Field(default=None, max_length=150)
    status: str | None = Field(default=None, max_length=50)
    vendor_name: str | None = Field(default=None, max_length=150)
    currency: str | None = Field(default=None, max_length=10)
    invoice_number: str | None = Field(default=None, max_length=100)
    purchase_date: date | None = None
    purchase_price: float | None = Field(default=None, ge=0)
    warranty_expiration_date: date | None = None
    support_expiration_date: date | None = None
    invoice_path: str | None = Field(default=None, max_length=500)
    specifications: dict[str, Any] | None = None
    notes: str | None = None
    cpu_cores: int | None = Field(default=None, ge=0)
    logical_cpu_cores: int | None = Field(default=None, ge=0)
    architecture: str | None = Field(default=None, max_length=100)


class AssetRead(ORMModel, AssetBase):
    """Asset response including current custodian information."""

    id: int
    asset_tag: str | None = None
    created_at: datetime
    updated_at: datetime
    custodian: PersonSummary | None = None
    is_internet_source: bool = False


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
    source_file: str | None = None


class ExtractProvider(BaseModel):
    """Metadata for a report extraction provider."""

    id: str
    name: str
    sourceType: Literal["windows", "linux"]
    retentionPolicy: str


class ExtractSource(BaseModel):
    """Classification result for one supplied report."""

    filename: str
    format: str
    provider: ExtractProvider
    parsed_fields: dict[str, Any]


class ExtractIssue(BaseModel):
    """A per-file extraction warning or error."""

    filename: str
    message: str


class ExtractResponse(BaseModel):
    """Structured local extraction result with legacy candidate compatibility."""

    success: bool = True
    parsed_fields: dict[str, Any] = Field(default_factory=dict)
    sources: list[ExtractSource] = Field(default_factory=list)
    warnings: list[ExtractIssue] = Field(default_factory=list)
    unmapped: dict[str, list[str]] = Field(default_factory=dict)
    errors: list[ExtractIssue] = Field(default_factory=list)
    provider: ExtractProvider | None = None
    candidates: list[ExtractCandidate] = Field(default_factory=list)


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
    last_success_at: datetime | None = None
    last_packet_loss_percent: float | None = None
    last_jitter_ms: float | None = None
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
    packets_sent: int | None = None
    packets_received: int | None = None
    packet_loss_percent: float | None = None
    min_latency_ms: float | None = None
    max_latency_ms: float | None = None
    jitter_ms: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    probe_source: str = "local"
    timestamp: datetime


class ExportLogOut(ORMModel):
    """A safe export log entry response."""

    id: int
    export_type: str
    created_at: datetime
    username: str


class WarehouseItemCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="Other", min_length=1, max_length=100)
    unit: str = Field(default="piece", min_length=1, max_length=50)
    minimum_stock: int = Field(default=0, ge=0)
    storage_location: str | None = Field(default=None, max_length=150)
    bin_code: str | None = Field(default=None, max_length=100)
    condition: str | None = Field(default=None, max_length=50)
    vendor: str | None = Field(default=None, max_length=150)
    serial_number: str | None = Field(default=None, max_length=150)
    batch_number: str | None = Field(default=None, max_length=100)
    linked_asset_id: int | None = None
    notes: str | None = None


class WarehouseItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    unit: str | None = Field(default=None, min_length=1, max_length=50)
    minimum_stock: int | None = Field(default=None, ge=0)
    storage_location: str | None = Field(default=None, max_length=150)
    bin_code: str | None = Field(default=None, max_length=100)
    condition: str | None = Field(default=None, max_length=50)
    vendor: str | None = Field(default=None, max_length=150)
    serial_number: str | None = Field(default=None, max_length=150)
    batch_number: str | None = Field(default=None, max_length=100)
    linked_asset_id: int | None = None
    notes: str | None = None


class WarehouseMovementCreate(BaseModel):
    movement_type: Literal["incoming", "outgoing", "adjustment_add", "adjustment_remove"]
    quantity: int = Field(gt=0)
    reference: str | None = Field(default=None, max_length=200)
    notes: str | None = None


class WarehouseMovementRead(ORMModel):
    id: int
    item_id: int
    movement_type: str
    quantity: int
    reference: str | None
    notes: str | None
    actor_username: str
    created_at: datetime


class WarehouseItemRead(ORMModel):
    id: int
    sku: str
    name: str
    category: str
    quantity: int
    unit: str
    minimum_stock: int
    storage_location: str | None
    bin_code: str | None
    condition: str | None
    vendor: str | None
    serial_number: str | None
    batch_number: str | None
    linked_asset_id: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    low_stock: bool = False


class ReferenceDocumentRead(ORMModel):
    id: int
    title: str
    category: str
    tags: list[str] = Field(default_factory=list)
    description: str | None
    original_filename: str
    media_type: str
    size_bytes: int
    uploaded_by_username: str
    created_at: datetime
    preview_supported: bool = False


class TopologyAsset(ORMModel):
    """Compact asset record embedded in the topology response."""

    id: int
    asset_tag: str | None = None
    type: str | None = None
    asset_name: str | None = None
    hostname: str | None = None
    ip_address: str | None = None
    is_internet_source: bool = False
    status: str | None = None


class NetworkLinkRead(ORMModel):
    id: int
    source_id: int
    target_id: int
    link_type: str
    label: str | None = None


class NetworkLinkCreate(BaseModel):
    source_id: int
    target_id: int
    link_type: Literal["ethernet", "wireless"] = "ethernet"
    label: str | None = Field(default=None, max_length=200)


class InternetSourceUpdate(BaseModel):
    is_internet_source: bool


class TopologyOut(BaseModel):
    """Flat adjacency-list topology response."""

    assets: list[TopologyAsset]
    links: list[NetworkLinkRead]
