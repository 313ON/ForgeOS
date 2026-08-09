from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..domain.models import MonitoredTarget, NetworkLog
from ..domain.schemas import NetworkLogOut, TargetCreate, TargetListItem, TargetOut, TargetUpdate
from ..services.credentials import credential_protector
from ..services.auth import AuthenticatedUser, get_current_user, require_admin
from ..services.monitoring import check_target, json_metadata, validate_network_host, validate_website_url
from .router import run_monitoring_check

router = APIRouter(prefix="/api/targets", tags=["targets"])
v1_router = APIRouter(prefix="/api/v1/monitoring/targets", tags=["monitoring"])


@router.get("", response_model=list[TargetListItem])
@v1_router.get("", response_model=list[TargetListItem])
def list_targets(db: Session = Depends(get_db), _: AuthenticatedUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    """List monitored targets without returning credential contents."""
    targets = db.scalars(select(MonitoredTarget).order_by(MonitoredTarget.name)).all()
    return [_safe_target(target) for target in targets]


@router.post("", response_model=TargetOut, status_code=status.HTTP_201_CREATED)
@v1_router.post("", response_model=TargetOut, status_code=status.HTTP_201_CREATED)
def create_target(payload: TargetCreate, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)) -> dict[str, Any]:
    """Register a website or network target after validating its address."""
    _validate_target_address(payload.target_type, payload.ip_or_host, payload.allow_private_networks)
    target = MonitoredTarget(**payload.model_dump())
    db.add(target)
    db.commit()
    db.refresh(target)
    return _safe_target(target)


@router.put("/{target_id}", response_model=TargetOut)
@v1_router.put("/{target_id}", response_model=TargetOut)
def update_target(target_id: int, payload: TargetUpdate, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)) -> dict[str, Any]:
    """Update target configuration, including safe address validation."""
    target = _get_target_or_404(db, target_id)
    values = payload.model_dump(exclude_unset=True)
    target_type = values.get("target_type", target.target_type)
    address = values.get("ip_or_host", target.ip_or_host)
    allow_private = values.get("allow_private_networks", target.allow_private_networks)
    _validate_target_address(target_type, address, allow_private)
    if "credentials_info" in values:
        target.credentials_info = credential_protector.protect(values.pop("credentials_info"))
    for key, value in values.items():
        setattr(target, key, value)
    db.commit()
    db.refresh(target)
    return _safe_target(target)


@router.post("/{target_id}/check", response_model=NetworkLogOut)
@v1_router.post("/{target_id}/check", response_model=NetworkLogOut)
def check_target_now(target_id: int, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)) -> NetworkLog:
    """Run and persist one immediate target check."""
    return run_monitoring_check(_get_target_or_404(db, target_id), db)


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
@v1_router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(target_id: int, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)) -> None:
    """Delete a target and its dependent monitoring logs."""
    db.delete(_get_target_or_404(db, target_id))
    db.commit()


@router.get("/{target_id}/logs", response_model=list[NetworkLogOut])
@v1_router.get("/{target_id}/logs", response_model=list[NetworkLogOut])
def list_target_logs(
    target_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
    since: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(get_current_user),
) -> list[NetworkLog]:
    """Return recent target monitoring events."""
    _get_target_or_404(db, target_id)
    query = select(NetworkLog).where(NetworkLog.target_id == target_id).order_by(NetworkLog.timestamp.desc()).limit(limit)
    if since is not None:
        query = query.where(NetworkLog.timestamp >= since)
    return list(db.scalars(query).all())


def _get_target_or_404(db: Session, target_id: int) -> MonitoredTarget:
    target = db.get(MonitoredTarget, target_id)
    if target is None:
        raise HTTPException(404, "Monitored target not found")
    return target


def _validate_target_address(target_type: str, value: str, allow_private: bool) -> None:
    try:
        if target_type == "website":
            validate_website_url(value, allow_private)
        else:
            validate_network_host(value)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


def _safe_target(target: MonitoredTarget) -> dict[str, Any]:
    ssl_metadata = None
    if target.ssl_metadata:
        try:
            ssl_metadata = json.loads(target.ssl_metadata)
        except json.JSONDecodeError:
            ssl_metadata = None
    return {
        "id": target.id,
        "name": target.name,
        "ip_or_host": target.ip_or_host,
        "target_type": target.target_type,
        "ping_interval_sec": target.ping_interval_sec,
        "timeout_sec": target.timeout_sec,
        "enabled": target.enabled,
        "expected_status_code": target.expected_status_code,
        "allow_private_networks": target.allow_private_networks,
        "ssh_port": target.ssh_port,
        "web_port": target.web_port,
        "camera_stream_url": target.camera_stream_url,
        "status": _normalize_status(target.status),
        "last_latency_ms": target.last_latency_ms,
        "last_checked_at": target.last_checked_at,
        "last_success_at": target.last_success_at,
        "last_packet_loss_percent": target.last_packet_loss_percent,
        "last_jitter_ms": target.last_jitter_ms,
        "last_error": target.last_error,
        "ssl_metadata": ssl_metadata,
        "created_at": target.created_at,
        "credentials_configured": bool(target.credentials_info),
    }


def _normalize_status(value: str | None) -> str:
    return {"online": "PASS", "offline": "FAILED", "unknown": "UNKNOWN"}.get(value or "", value or "UNKNOWN")
