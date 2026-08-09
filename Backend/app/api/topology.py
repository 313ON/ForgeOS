from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..domain.models import Asset, NetworkLink
from ..domain.schemas import (
    InternetSourceUpdate,
    NetworkLinkCreate,
    NetworkLinkRead,
    TopologyAsset,
    TopologyOut,
)
from ..services.auth import AuthenticatedUser, get_current_user, require_admin

router = APIRouter(prefix="/api/v1", tags=["topology"])


def _asset_payload(asset: Asset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "asset_tag": asset.asset_tag,
        "type": asset.type,
        "asset_name": asset.asset_name,
        "hostname": asset.hostname,
        "ip_address": asset.ip_address,
        "is_internet_source": bool(asset.is_internet_source),
        "status": asset.status,
    }


def _link_payload(link: NetworkLink) -> dict[str, Any]:
    return {
        "id": link.id,
        "source_id": link.source_id,
        "target_id": link.target_id,
        "link_type": link.link_type,
        "label": link.label,
    }


def _active_link_exists(db: Session, source_id: int, target_id: int, exclude_id: int | None = None) -> bool:
    stmt = (
        select(NetworkLink.id)
        .where(
            NetworkLink.source_id == source_id,
            NetworkLink.target_id == target_id,
            NetworkLink.deleted_at.is_(None),
        )
    )
    if exclude_id is not None:
        stmt = stmt.where(NetworkLink.id != exclude_id)
    return db.scalar(stmt) is not None


def _validate_link_payload(db: Session, payload: NetworkLinkCreate) -> None:
    if payload.source_id == payload.target_id:
        raise HTTPException(422, "source_id and target_id must be different assets")
    source = db.get(Asset, payload.source_id)
    target = db.get(Asset, payload.target_id)
    if source is None or target is None:
        raise HTTPException(404, "Source or target asset not found")


@router.get("/topology", response_model=TopologyOut)
def get_topology(
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Return a flat adjacency list of assets and active network links.

    Soft-deleted links are excluded from the response.
    """
    assets = db.scalars(select(Asset).order_by(Asset.id)).all()
    links = db.scalars(
        select(NetworkLink)
        .where(NetworkLink.deleted_at.is_(None))
        .order_by(NetworkLink.id)
    ).all()
    return {
        "assets": [_asset_payload(asset) for asset in assets],
        "links": [_link_payload(link) for link in links],
    }


@router.post("/topology/links", response_model=NetworkLinkRead, status_code=status.HTTP_201_CREATED)
def create_link(
    payload: NetworkLinkCreate,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_admin),
) -> dict[str, Any]:
    """Create a link between two assets (admin only)."""
    _validate_link_payload(db, payload)
    if _active_link_exists(db, payload.source_id, payload.target_id):
        raise HTTPException(409, "A link already exists between these assets")
    link = NetworkLink(
        source_id=payload.source_id,
        target_id=payload.target_id,
        link_type=payload.link_type,
        label=payload.label,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return _link_payload(link)


@router.put("/topology/links/{link_id}", response_model=NetworkLinkRead)
def update_link(
    link_id: int,
    payload: NetworkLinkCreate,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_admin),
) -> dict[str, Any]:
    """Update an existing link between two assets (admin only)."""
    link = db.get(NetworkLink, link_id)
    if link is None or link.deleted_at is not None:
        raise HTTPException(404, "Network link not found")
    _validate_link_payload(db, payload)
    if _active_link_exists(db, payload.source_id, payload.target_id, exclude_id=link_id):
        raise HTTPException(409, "A link already exists between these assets")
    link.source_id = payload.source_id
    link.target_id = payload.target_id
    link.link_type = payload.link_type
    link.label = payload.label
    db.commit()
    db.refresh(link)
    return _link_payload(link)


@router.delete("/topology/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(
    link_id: int,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_admin),
) -> None:
    """Soft-delete a link (admin only). The row is retained for auditability."""
    link = db.get(NetworkLink, link_id)
    if link is None or link.deleted_at is not None:
        raise HTTPException(404, "Network link not found")
    link.deleted_at = func.now()
    db.commit()


@router.patch("/assets/{asset_id}/topology", response_model=TopologyAsset)
def update_internet_source(
    asset_id: int,
    payload: InternetSourceUpdate,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_admin),
) -> dict[str, Any]:
    """Mark an asset as the internet entry point (admin only)."""
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    asset.is_internet_source = payload.is_internet_source
    db.commit()
    db.refresh(asset)
    return _asset_payload(asset)
