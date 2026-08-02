from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..domain.models import Asset, Assignment, ExportLog, MonitoredTarget, NetworkLog, Person, SystemSnapshot, User, Warranty
from ..domain.schemas import (
    AssetCreate, AssetRead, AssetUpdate, AssignmentCreate, AssignmentRead, ExportLogOut, IngestResponse,
    NetworkLogOut, PersonCreate, PersonRead, PersonUpdate, LoginRequest, UserCreate, UserRead, UserUpdate,
)
from ..services.ai_agent import query_asset_insights
from ..services.auth import AuthenticatedUser, UserRole, create_access_token, get_current_user, hash_password, require_admin, verify_password
from ..services.asset_tags import generate_asset_tag, validate_manual_tag
from ..services.ingestion import decode_report, detect_source, parse_report, suggest_hardware_profile
from ..services.monitoring import check_target, json_metadata, now_utc
from ..services.reports import asset_report_rows, create_excel_report, create_pdf_report
from forge.runtime.storage.file_store import content_type_for, resolve_invoice, save_invoice

logger = logging.getLogger("forgeos.api")
router = APIRouter(prefix="/api/v1")
compat_router = APIRouter(prefix="/api")


def active_assignment_filter() -> Any:
    """Return the canonical active-assignment predicate."""
    today = date.today()
    return or_(Assignment.end_date.is_(None), Assignment.end_date >= today)


@router.get("/health")
def health() -> dict[str, str]:
    """Return API health state."""
    return {"status": "ok", "service": "forgeos"}


@router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    try:
        role = UserRole(user.role.upper()).value
    except (AttributeError, ValueError):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User role is invalid") from None
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": {"id": user.id, "username": user.username, "role": role}}


@router.post("/auth/logout")
def logout(_: AuthenticatedUser = Depends(get_current_user)) -> dict[str, str]:
    return {"status": "logged_out"}


@router.get("/auth/me", response_model=UserRead)
def current_user(user: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    record = db.get(User, user.id)
    return {
        "id": record.id,
        "username": record.username,
        "role": user.role.value,
        "is_active": record.is_active,
        "created_at": record.created_at,
    }


@router.get("/users", response_model=list[UserRead])
def list_users(_: AuthenticatedUser = Depends(require_admin), db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)).all())


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, _: AuthenticatedUser = Depends(require_admin), db: Session = Depends(get_db)) -> User:
    user = User(username=payload.username, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    _commit_or_conflict(db, "Username already exists")
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    user = _get_or_404(db, User, user_id, "User")
    values = payload.model_dump(exclude_unset=True)
    if user.id == admin.id and values.get("is_active") is False:
        raise HTTPException(400, "You cannot deactivate your own account")
    if user.role == "ADMIN" and (values.get("role") == "VIEW" or values.get("is_active") is False):
        _require_another_admin(db, user.id)
    password = values.pop("password", None)
    if password:
        user.password_hash = hash_password(password)
    for key, value in values.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    user = _get_or_404(db, User, user_id, "User")
    if user.id == admin.id:
        raise HTTPException(400, "You cannot delete your own account")
    if user.role == "ADMIN":
        _require_another_admin(db, user.id)
    db.delete(user)
    db.commit()


@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db), _: AuthenticatedUser = Depends(get_current_user)) -> dict[str, Any]:
    """Return dashboard counts and operational warnings."""
    active = active_assignment_filter()
    assets = db.scalar(select(func.count(Asset.id))) or 0
    people = db.scalar(select(func.count(Person.id))) or 0
    assignments = db.scalar(select(func.count(Assignment.id)).where(active)) or 0
    snapshots = db.scalar(select(func.count(SystemSnapshot.id))) or 0
    unassigned = db.scalars(select(Asset).where(~Asset.id.in_(select(Assignment.asset_id).where(active)))).all()
    return {
        "counts": {"assets": assets, "people": people, "active_assignments": assignments, "system_snapshots": snapshots},
        "warnings": {"unassigned_assets": [{"asset_id": item.id, "asset_tag": item.asset_tag, "type": item.type} for item in unassigned]},
        "warning_count": len(unassigned),
        "recent_activity": _recent_activity(db),
    }


@router.get("/assets", response_model=list[AssetRead])
def list_assets(
    search: str | None = None,
    type: str | None = None,
    status: str | None = None,
    location: str | None = None,
    org_unit: str | None = None,
    custodian: int | None = None,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List assets with practical filters and current custodians."""
    query = select(Asset).order_by(Asset.created_at.desc(), Asset.id.desc())
    filters = []
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        filters.append(or_(*[field.ilike(pattern) for field in (Asset.asset_tag, Asset.type, Asset.brand, Asset.model, Asset.serial_number, Asset.location, Asset.hostname)]))
    for field, value in ((Asset.type, type), (Asset.status, status), (Asset.location, location), (Asset.org_unit, org_unit)):
        if value:
            filters.append(field.ilike(f"%{value.strip()}%"))
    if custodian is not None:
        query = query.join(Assignment).where(Assignment.person_id == custodian, active_assignment_filter())
    if filters:
        query = query.where(*filters)
    return [_asset_payload(db, asset) for asset in db.scalars(query).unique().all()]


@router.post("/assets", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)) -> dict[str, Any]:
    """Create an asset, generating a tag when omitted."""
    values = payload.model_dump()
    tag = values.pop("asset_tag", None)
    values["asset_tag"] = generate_asset_tag(db, values["type"]) if not tag else validate_manual_tag(tag)
    asset = Asset(**values)
    db.add(asset)
    _commit_or_conflict(db, "Asset tag already exists")
    db.refresh(asset)
    return _asset_payload(db, asset)


@router.get("/assets/{asset_id}", response_model=AssetRead)
def get_asset(asset_id: int, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(get_current_user)) -> dict[str, Any]:
    """Return an asset and its current custodian."""
    return _asset_payload(db, _get_or_404(db, Asset, asset_id, "Asset"))


@router.patch("/assets/{asset_id}", response_model=AssetRead)
def update_asset(asset_id: int, payload: AssetUpdate, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)) -> dict[str, Any]:
    """Apply a partial update without regenerating the asset tag."""
    asset = _get_or_404(db, Asset, asset_id, "Asset")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "asset_tag" and value is not None:
            value = validate_manual_tag(value)
        setattr(asset, key, value)
    _commit_or_conflict(db, "Asset tag already exists")
    db.refresh(asset)
    return _asset_payload(db, asset)


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: int, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)) -> None:
    """Delete an asset and dependent records."""
    db.delete(_get_or_404(db, Asset, asset_id, "Asset"))
    db.commit()


@router.get("/people", response_model=list[PersonRead])
def list_people(db: Session = Depends(get_db), _: AuthenticatedUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    """List people with active assigned assets."""
    return [_person_payload(db, person) for person in db.scalars(select(Person).order_by(Person.full_name)).all()]


@router.post("/people", response_model=PersonRead, status_code=status.HTTP_201_CREATED)
def create_person(payload: PersonCreate, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)) -> dict[str, Any]:
    """Create a person."""
    person = Person(**payload.model_dump())
    db.add(person)
    db.commit()
    db.refresh(person)
    return _person_payload(db, person)


@router.get("/people/{person_id}", response_model=PersonRead)
def get_person(person_id: int, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(get_current_user)) -> dict[str, Any]:
    """Return a person with active assigned assets."""
    return _person_payload(db, _get_or_404(db, Person, person_id, "Person"))


@router.patch("/people/{person_id}", response_model=PersonRead)
def update_person(person_id: int, payload: PersonUpdate, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)) -> dict[str, Any]:
    """Update a person."""
    person = _get_or_404(db, Person, person_id, "Person")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(person, key, value)
    db.commit()
    db.refresh(person)
    return _person_payload(db, person)


@router.delete("/people/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(person_id: int, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)) -> None:
    """Delete a person while retaining assignment history."""
    db.delete(_get_or_404(db, Person, person_id, "Person"))
    db.commit()


@router.get("/assignments", response_model=list[AssignmentRead])
def list_assignments(db: Session = Depends(get_db), _: AuthenticatedUser = Depends(get_current_user)) -> list[Assignment]:
    """List assignment history."""
    return list(db.scalars(select(Assignment).order_by(Assignment.start_date.desc(), Assignment.id.desc())).all())


@router.post("/assignments", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
def create_assignment(payload: AssignmentCreate, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)) -> Assignment:
    """Assign an asset and close any previous active assignment."""
    if payload.end_date and payload.end_date < payload.start_date:
        raise HTTPException(422, "end_date must be on or after start_date")
    _get_or_404(db, Asset, payload.asset_id, "Asset")
    if payload.person_id is not None:
        _get_or_404(db, Person, payload.person_id, "Person")
    for existing in db.scalars(select(Assignment).where(Assignment.asset_id == payload.asset_id, active_assignment_filter())).all():
        existing.end_date = payload.start_date - timedelta(days=1)
    assignment = Assignment(**payload.model_dump())
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/assets/{asset_id}/assign", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
def assign_asset(asset_id: int, payload: AssignmentCreate, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)) -> Assignment:
    """Explicitly assign an asset to a person."""
    if payload.asset_id != asset_id:
        raise HTTPException(400, "asset_id does not match path")
    return create_assignment(payload, db)


@router.post("/assets/{asset_id}/unassign", response_model=AssignmentRead)
def unassign_asset(asset_id: int, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)) -> Assignment:
    """Close the current active assignment for an asset."""
    assignment = db.scalar(select(Assignment).where(Assignment.asset_id == asset_id, active_assignment_filter()).order_by(Assignment.start_date.desc()))
    if assignment is None:
        raise HTTPException(404, "Active assignment not found")
    assignment.end_date = date.today() - timedelta(days=1)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/ingest", response_model=IngestResponse)
async def ingest_report(file: UploadFile = File(...), asset_id: int | None = Form(default=None), db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)) -> IngestResponse:
    """Parse and persist an uploaded DxDiag or systeminfo report."""
    filename = file.filename or "report.txt"
    if not filename.casefold().endswith(".txt"):
        raise HTTPException(415, "Only .txt reports are supported")
    if asset_id is not None:
        _get_or_404(db, Asset, asset_id, "Asset")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "Report exceeds the 5 MB upload limit")
    text = decode_report(content)
    source = detect_source(filename, text)
    if source is None:
        raise HTTPException(422, "Unable to identify report as DxDiag or systeminfo")
    parsed = parse_report(source, text)
    profile = suggest_hardware_profile(parsed)
    snapshot = SystemSnapshot(asset_id=asset_id, source=source, parsed_json=json.dumps(parsed, ensure_ascii=False))
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return IngestResponse(snapshot_id=snapshot.id, source=source, filename=filename, parsed=parsed, suggested_profile=profile, asset_draft=build_asset_draft(parsed))


@router.get("/monitoring/history", response_model=list[NetworkLogOut])
def monitoring_history(limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db), _: AuthenticatedUser = Depends(get_current_user)) -> list[NetworkLog]:
    """Return recent monitoring events."""
    return list(db.scalars(select(NetworkLog).order_by(NetworkLog.timestamp.desc()).limit(limit)).all())


@compat_router.post("/assets/{asset_id}/invoice")
async def upload_invoice(asset_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), _: AuthenticatedUser = Depends(require_admin)) -> dict[str, Any]:
    """Upload an invoice and attach it to an asset."""
    asset = _get_or_404(db, Asset, asset_id, "Asset")
    try:
        relative_path = save_invoice(await file.read(), file.filename or "")
    except (ValueError, OSError) as error:
        raise HTTPException(400, str(error)) from error
    asset.invoice_path = relative_path
    db.commit()
    return {"asset_id": asset.id, "invoice_path": asset.invoice_path}


@compat_router.get("/assets/{asset_id}/invoice")
def get_invoice(asset_id: int, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(get_current_user)) -> FileResponse:
    """Serve an attached invoice."""
    asset = _get_or_404(db, Asset, asset_id, "Asset")
    if not asset.invoice_path:
        raise HTTPException(404, "Invoice not attached")
    try:
        path = resolve_invoice(asset.invoice_path)
    except FileNotFoundError as error:
        raise HTTPException(404, "Invoice file not found") from error
    return FileResponse(path, media_type=content_type_for(path))


@compat_router.get("/export/excel")
def export_excel(lang: str = Query("en", pattern="^(en|fa)$"), db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)) -> StreamingResponse:
    """Download an Excel asset export."""
    report = create_excel_report(asset_report_rows(db), lang)
    db.add(ExportLog(export_type="excel", user_id=user.id, username=user.username))
    db.commit()
    return StreamingResponse(report, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@compat_router.get("/export/pdf")
def export_pdf(lang: str = Query("en", pattern="^(en|fa)$"), db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)) -> StreamingResponse:
    """Download a PDF asset export."""
    report = create_pdf_report(asset_report_rows(db), lang)
    db.add(ExportLog(export_type="pdf", user_id=user.id, username=user.username))
    db.commit()
    return StreamingResponse(report, media_type="application/pdf")


@router.get("/export/history", response_model=list[ExportLogOut])
def export_history(db: Session = Depends(get_db), _: AuthenticatedUser = Depends(get_current_user)) -> list[ExportLog]:
    """Return export history, newest first."""
    return list(db.scalars(select(ExportLog).order_by(ExportLog.created_at.desc())).all())


@compat_router.get("/export/json")
def export_json(db: Session = Depends(get_db), _: AuthenticatedUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    return asset_report_rows(db)


@router.get("/assets/{asset_id}/ai_insights")
def asset_ai_insights(asset_id: int, db: Session = Depends(get_db), _: AuthenticatedUser = Depends(get_current_user)) -> dict[str, Any]:
    try:
        return query_asset_insights(db, asset_id)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error


def run_monitoring_check(target: MonitoredTarget, db: Session) -> NetworkLog:
    """Run and persist one target check."""
    result = check_target(target)
    target.status = result.status
    target.last_latency_ms = result.latency_ms
    target.last_checked_at = now_utc()
    target.last_error = result.message
    target.ssl_metadata = json_metadata(result.ssl_metadata)
    status_code = {"PASS": 1, "FAILED": 0}.get(result.status, -1)
    event = NetworkLog(
        target_id=target.id, latency_ms=result.latency_ms, status_code=status_code,
        check_type=target.target_type, status=result.status, message=result.message,
        response_status_code=result.response_status_code,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    _trim_history(db, target.id)
    return event


def _trim_history(db: Session, target_id: int, keep: int = 500) -> None:
    ids = db.scalars(select(NetworkLog.id).where(NetworkLog.target_id == target_id).order_by(NetworkLog.timestamp.desc()).offset(keep)).all()
    if ids:
        db.query(NetworkLog).filter(NetworkLog.id.in_(ids)).delete(synchronize_session=False)
        db.commit()


def _asset_payload(db: Session, asset: Asset) -> dict[str, Any]:
    assignment = db.scalar(select(Assignment).where(Assignment.asset_id == asset.id, active_assignment_filter()).order_by(Assignment.start_date.desc()))
    return {**{column.name: getattr(asset, column.name) for column in Asset.__table__.columns}, "custodian": _person_summary(assignment.person) if assignment and assignment.person else None}


def _person_payload(db: Session, person: Person) -> dict[str, Any]:
    assignments = db.scalars(select(Assignment).where(Assignment.person_id == person.id, active_assignment_filter())).all()
    return {**{column.name: getattr(person, column.name) for column in Person.__table__.columns}, "assets": [_asset_summary(item.asset) for item in assignments]}


def _person_summary(person: Person) -> dict[str, Any]:
    return {"id": person.id, "full_name": person.full_name, "org_unit": person.org_unit, "job_role": person.job_role}


def _asset_summary(asset: Asset) -> dict[str, Any]:
    return {"id": asset.id, "asset_tag": asset.asset_tag, "type": asset.type, "status": asset.status, "location": asset.location}


def build_asset_draft(parsed: dict[str, object]) -> dict[str, object]:
    """Convert parsed inventory into a safe asset form draft."""
    return {
        "type": "Desktop",
        "hostname": parsed.get("hostname"),
        "manufacturer": parsed.get("manufacturer"),
        "brand": parsed.get("manufacturer"),
        "model": parsed.get("model"),
        "cpu_name": parsed.get("cpu_name"),
        "ram_mb": parsed.get("ram_mb"),
        "gpu_name": parsed.get("gpu_name"),
        "os_name": parsed.get("os_name"),
        "os_version": parsed.get("os_version"),
        "bios_version": parsed.get("bios_version"),
        "ip_address": parsed.get("ip_address"),
    }


def _get_or_404(db: Session, model: type[Any], record_id: int, label: str) -> Any:
    record = db.get(model, record_id)
    if record is None:
        raise HTTPException(404, f"{label} not found")
    return record


def _commit_or_conflict(db: Session, detail: str) -> None:
    try:
        db.commit()
    except (IntegrityError, ValueError) as error:
        db.rollback()
        raise HTTPException(409, detail) from error


def _require_another_admin(db: Session, excluded_user_id: int) -> None:
    other_admin = db.scalar(
        select(User.id).where(
            User.id != excluded_user_id,
            User.role == "ADMIN",
            User.is_active.is_(True),
        ).limit(1)
    )
    if other_admin is None:
        raise HTTPException(409, "At least one active administrator is required")


def _recent_activity(db: Session) -> list[dict[str, Any]]:
    return []
