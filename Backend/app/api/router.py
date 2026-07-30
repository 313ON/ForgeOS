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
from ..domain.models import Asset, Assignment, Person, SystemSnapshot, Warranty
from ..domain.schemas import (
    AssetCreate,
    AssetRead,
    AssetUpdate,
    AssignmentCreate,
    AssignmentRead,
    IngestResponse,
    PersonCreate,
    PersonRead,
)
from ..services.ingestion import (
    decode_report,
    detect_source,
    parse_report,
    suggest_hardware_profile,
)
from ..services.reports import asset_report_rows, create_excel_report, create_pdf_report
from forge.runtime.storage.file_store import (
    content_type_for,
    resolve_invoice,
    save_invoice,
)

logger = logging.getLogger("forgeos.ingestion")
router = APIRouter(prefix="/api/v1")
compat_router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    """Return API health state."""
    return {"status": "ok", "service": "forgeos"}


@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return dashboard counts, warnings, and recent operational activity."""
    today = date.today()
    warranty_cutoff = today + timedelta(days=30)
    active_assignment = or_(Assignment.end_date.is_(None), Assignment.end_date >= today)

    asset_count = db.scalar(select(func.count(Asset.id))) or 0
    people_count = db.scalar(select(func.count(Person.id))) or 0
    assignment_count = (
        db.scalar(select(func.count(Assignment.id)).where(active_assignment)) or 0
    )
    snapshot_count = db.scalar(select(func.count(SystemSnapshot.id))) or 0

    expiring = db.execute(
        select(Warranty, Asset)
        .join(Asset, Warranty.asset_id == Asset.id)
        .where(Warranty.end_date.between(today, warranty_cutoff))
        .order_by(Warranty.end_date)
    ).all()
    missing_serial = db.scalars(
        select(Asset)
        .where(or_(Asset.serial_number.is_(None), func.trim(Asset.serial_number) == ""))
        .order_by(Asset.asset_tag)
    ).all()
    assigned_asset_ids = select(Assignment.asset_id).where(active_assignment)
    unassigned = db.scalars(
        select(Asset)
        .where(Asset.id.not_in(assigned_asset_ids))
        .order_by(Asset.asset_tag)
    ).all()

    warnings = {
        "expiring_warranties": [
            {
                "warranty_id": warranty.id,
                "asset_id": asset.id,
                "asset_tag": asset.asset_tag,
                "vendor": warranty.vendor,
                "end_date": warranty.end_date.isoformat(),
                "days_remaining": (warranty.end_date - today).days,
            }
            for warranty, asset in expiring
        ],
        "missing_serial": [
            {"asset_id": asset.id, "asset_tag": asset.asset_tag, "type": asset.type}
            for asset in missing_serial
        ],
        "unassigned_assets": [
            {"asset_id": asset.id, "asset_tag": asset.asset_tag, "type": asset.type}
            for asset in unassigned
        ],
    }
    return {
        "counts": {
            "assets": asset_count,
            "people": people_count,
            "active_assignments": assignment_count,
            "system_snapshots": snapshot_count,
        },
        "warnings": warnings,
        "warning_count": sum(len(items) for items in warnings.values()),
        "recent_activity": _recent_activity(db),
    }


@router.get("/assets", response_model=list[AssetRead])
def list_assets(
    search: str | None = None,
    db: Session = Depends(get_db),
) -> list[Asset]:
    """List assets, optionally filtered by common identifying fields."""
    query = select(Asset).order_by(Asset.created_at.desc(), Asset.id.desc())
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Asset.asset_tag.ilike(pattern),
                Asset.type.ilike(pattern),
                Asset.brand.ilike(pattern),
                Asset.model.ilike(pattern),
                Asset.serial_number.ilike(pattern),
                Asset.location.ilike(pattern),
            )
        )
    return list(db.scalars(query).all())


@router.post("/assets", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate, db: Session = Depends(get_db)) -> Asset:
    """Create an asset."""
    asset = Asset(**payload.model_dump())
    db.add(asset)
    _commit_or_conflict(db, "Asset tag already exists")
    db.refresh(asset)
    return asset


@router.get("/assets/{asset_id}", response_model=AssetRead)
def get_asset(asset_id: int, db: Session = Depends(get_db)) -> Asset:
    """Return a single asset."""
    return _get_or_404(db, Asset, asset_id, "Asset")


@router.patch("/assets/{asset_id}", response_model=AssetRead)
def update_asset(
    asset_id: int,
    payload: AssetUpdate,
    db: Session = Depends(get_db),
) -> Asset:
    """Apply a partial update to an asset."""
    asset = _get_or_404(db, Asset, asset_id, "Asset")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(asset, key, value)
    _commit_or_conflict(db, "Asset tag already exists")
    db.refresh(asset)
    return asset


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: int, db: Session = Depends(get_db)) -> None:
    """Delete an asset and its dependent records."""
    asset = _get_or_404(db, Asset, asset_id, "Asset")
    db.delete(asset)
    db.commit()


@router.get("/people", response_model=list[PersonRead])
def list_people(db: Session = Depends(get_db)) -> list[Person]:
    """List people."""
    return list(db.scalars(select(Person).order_by(Person.full_name)).all())


@router.post("/people", response_model=PersonRead, status_code=status.HTTP_201_CREATED)
def create_person(payload: PersonCreate, db: Session = Depends(get_db)) -> Person:
    """Create a person."""
    person = Person(**payload.model_dump())
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


@router.get("/assignments", response_model=list[AssignmentRead])
def list_assignments(db: Session = Depends(get_db)) -> list[Assignment]:
    """List assignments with newest starts first."""
    return list(
        db.scalars(
            select(Assignment).order_by(Assignment.start_date.desc(), Assignment.id.desc())
        ).all()
    )


@router.post(
    "/assignments",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
) -> Assignment:
    """Create an asset assignment."""
    if payload.end_date and payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be on or after start_date",
        )
    _get_or_404(db, Asset, payload.asset_id, "Asset")
    if payload.person_id is not None:
        _get_or_404(db, Person, payload.person_id, "Person")
    assignment = Assignment(**payload.model_dump())
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/ingest", response_model=IngestResponse)
async def ingest_report(
    file: UploadFile = File(...),
    asset_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
) -> IngestResponse:
    """Parse and persist an uploaded DxDiag or systeminfo text report."""
    filename = file.filename or "report.txt"
    if not filename.casefold().endswith(".txt"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only .txt reports are supported",
        )
    if asset_id is not None:
        _get_or_404(db, Asset, asset_id, "Asset")

    try:
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Report exceeds the 5 MB upload limit",
            )
        text = decode_report(content)
        source = detect_source(filename, text)
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unable to identify report as DxDiag or systeminfo",
            )
        parsed = parse_report(source, text)
        profile = suggest_hardware_profile(parsed)
        snapshot_payload = {**parsed, "suggested_profile": profile, "filename": filename}
        snapshot = SystemSnapshot(
            asset_id=asset_id,
            source=source,
            parsed_json=json.dumps(snapshot_payload, ensure_ascii=False),
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
    except HTTPException:
        raise
    except Exception as error:
        db.rollback()
        logger.exception(
            "ingestion_failed",
            extra={"filename": filename, "asset_id": asset_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report ingestion failed",
        ) from error

    return IngestResponse(
        snapshot_id=snapshot.id,
        source=source,
        filename=filename,
        parsed=parsed,
        suggested_profile=profile,
    )


@compat_router.post("/assets/{asset_id}/invoice")
async def upload_invoice(
    asset_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Upload an invoice image or PDF and attach it to an asset."""
    asset = _get_or_404(db, Asset, asset_id, "Asset")
    filename = file.filename or ""
    content_type = (file.content_type or "").casefold()
    allowed_content_types = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
    }
    if content_type and content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported invoice MIME type",
        )
    try:
        content = await file.read()
        relative_path = save_invoice(content, filename)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except OSError as error:
        logger.exception("invoice_storage_failed", extra={"asset_id": asset_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to store invoice",
        ) from error
    asset.invoice_path = relative_path
    db.commit()
    db.refresh(asset)
    return {"asset_id": asset.id, "invoice_path": asset.invoice_path}


@compat_router.get("/assets/{asset_id}/invoice")
def get_invoice(asset_id: int, db: Session = Depends(get_db)) -> FileResponse:
    """Serve an attached invoice for browser preview or download."""
    asset = _get_or_404(db, Asset, asset_id, "Asset")
    if not asset.invoice_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not attached",
        )
    try:
        invoice_path = resolve_invoice(asset.invoice_path)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice file not found",
        ) from error
    return FileResponse(invoice_path, media_type=content_type_for(invoice_path))


@compat_router.get("/export/excel")
def export_excel(
    lang: str = Query(default="en", pattern="^(en|fa)$"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Download a styled Excel export of all assets."""
    workbook = create_excel_report(asset_report_rows(db), lang=lang)
    filename = f"ForgeOS_Assets_Export_{date.today():%Y%m%d}.xlsx"
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@compat_router.get("/export/pdf")
def export_pdf(
    lang: str = Query(default="en", pattern="^(en|fa)$"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Download an executive PDF export of all assets."""
    report = create_pdf_report(asset_report_rows(db), lang=lang)
    filename = f"ForgeOS_Assets_Export_{date.today():%Y%m%d}.pdf"
    return StreamingResponse(
        report,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _get_or_404(db: Session, model: type[Any], record_id: int, label: str) -> Any:
    record = db.get(model, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")
    return record


def _commit_or_conflict(db: Session, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from error


def _recent_activity(db: Session) -> list[dict[str, Any]]:
    snapshots = db.execute(
        select(SystemSnapshot, Asset)
        .outerjoin(Asset, SystemSnapshot.asset_id == Asset.id)
        .order_by(SystemSnapshot.created_at.desc())
        .limit(6)
    ).all()
    assignments = db.execute(
        select(Assignment, Asset, Person)
        .join(Asset, Assignment.asset_id == Asset.id)
        .outerjoin(Person, Assignment.person_id == Person.id)
        .order_by(Assignment.start_date.desc())
        .limit(6)
    ).all()

    activity: list[dict[str, Any]] = [
        {
            "kind": "snapshot",
            "title": f"{snapshot.source} report imported",
            "detail": asset.asset_tag if asset else "Unlinked system report",
            "timestamp": _iso_datetime(snapshot.created_at),
        }
        for snapshot, asset in snapshots
    ]
    activity.extend(
        {
            "kind": "assignment",
            "title": f"{asset.asset_tag} assigned",
            "detail": person.full_name if person else assignment.location_override or "Location only",
            "timestamp": datetime.combine(
                assignment.start_date,
                time.min,
                tzinfo=timezone.utc,
            ).isoformat(),
        }
        for assignment, asset, person in assignments
    )
    return sorted(activity, key=lambda item: item["timestamp"], reverse=True)[:8]


def _iso_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
