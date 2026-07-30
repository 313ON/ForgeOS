"""Compatibility exports for API schemas."""

from .domain.schemas import (
    AssetCreate,
    AssetRead,
    AssetUpdate,
    AssignmentCreate,
    AssignmentRead,
    IngestResponse,
    PersonCreate,
    PersonRead,
)

AssetResponse = AssetRead

__all__ = [
    "AssetCreate",
    "AssetRead",
    "AssetResponse",
    "AssetUpdate",
    "AssignmentCreate",
    "AssignmentRead",
    "IngestResponse",
    "PersonCreate",
    "PersonRead",
]
