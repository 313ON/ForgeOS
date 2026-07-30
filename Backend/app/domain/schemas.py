from __future__ import annotations

from datetime import date, datetime

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
