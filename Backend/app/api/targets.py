from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..domain.models import MonitoredTarget, NetworkLog
from ..domain.schemas import (
    NetworkLogOut,
    TargetCreate,
    TargetListItem,
    TargetOut,
    TargetUpdate,
)
from ..services.credentials import credential_protector

router = APIRouter(prefix="/api/targets", tags=["targets"])


@router.get("", response_model=list[TargetListItem])
def list_targets(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """List monitored targets without returning credential contents."""
    targets = db.scalars(select(MonitoredTarget).order_by(MonitoredTarget.name)).all()
    return [_safe_target(target) for target in targets]


@router.post("", response_model=TargetOut, status_code=status.HTTP_201_CREATED)
def create_target(payload: TargetCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Register a target for future monitoring."""
    target = MonitoredTarget(**payload.model_dump())
    db.add(target)
    db.commit()
    db.refresh(target)
    return _safe_target(target)


@router.put("/{target_id}", response_model=TargetOut)
def update_target(
    target_id: int,
    payload: TargetUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update target configuration, including credentials only through PUT."""
    target = _get_target_or_404(db, target_id)
    values = payload.model_dump(exclude_unset=True)
    if "credentials_info" in values:
        target.credentials_info = credential_protector.protect(values.pop("credentials_info"))
    for key, value in values.items():
        setattr(target, key, value)
    db.commit()
    db.refresh(target)
    return _safe_target(target)


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(target_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a target and its dependent network logs."""
    target = _get_target_or_404(db, target_id)
    db.delete(target)
    db.commit()


@router.get("/{target_id}/logs", response_model=list[NetworkLogOut])
def list_target_logs(
    target_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
    since: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[NetworkLog]:
    """Return recent target logs for charting."""
    _get_target_or_404(db, target_id)
    query = (
        select(NetworkLog)
        .where(NetworkLog.target_id == target_id)
        .order_by(NetworkLog.timestamp.desc())
        .limit(limit)
    )
    if since is not None:
        query = query.where(NetworkLog.timestamp >= since)
    return list(db.scalars(query).all())


def _get_target_or_404(db: Session, target_id: int) -> MonitoredTarget:
    target = db.get(MonitoredTarget, target_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitored target not found",
        )
    return target


def _safe_target(target: MonitoredTarget) -> dict[str, Any]:
    return {
        "id": target.id,
        "name": target.name,
        "ip_or_host": target.ip_or_host,
        "target_type": target.target_type,
        "ping_interval_sec": target.ping_interval_sec,
        "ssh_port": target.ssh_port,
        "web_port": target.web_port,
        "camera_stream_url": target.camera_stream_url,
        "status": target.status,
        "last_latency_ms": target.last_latency_ms,
        "last_checked_at": target.last_checked_at,
        "created_at": target.created_at,
        "credentials_configured": bool(target.credentials_info),
    }
