from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..domain.models import Asset, ReferenceDocument, WarehouseItem, WarehouseMovement
from ..domain.schemas import (
    ReferenceDocumentRead,
    WarehouseItemCreate,
    WarehouseItemRead,
    WarehouseItemUpdate,
    WarehouseMovementCreate,
    WarehouseMovementRead,
)
from ..services.auth import AuthenticatedUser, get_current_user, require_admin
from ..services.reference_store import PREVIEW_EXTENSIONS, resolve_reference, save_reference

router = APIRouter(prefix="/api/v1")


def _warehouse_payload(item: WarehouseItem) -> dict[str, Any]:
    payload = {column.name: getattr(item, column.name) for column in WarehouseItem.__table__.columns}
    payload["low_stock"] = item.quantity <= item.minimum_stock
    return payload


@router.get("/warehouse/items", response_model=list[WarehouseItemRead])
def list_warehouse_items(
    search: str | None = None,
    category: str | None = None,
    location: str | None = None,
    condition: str | None = None,
    low_stock: bool | None = None,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    query = select(WarehouseItem)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.where(or_(WarehouseItem.sku.ilike(pattern), WarehouseItem.name.ilike(pattern), WarehouseItem.serial_number.ilike(pattern)))
    for field, value in ((WarehouseItem.category, category), (WarehouseItem.storage_location, location), (WarehouseItem.condition, condition)):
        if value:
            query = query.where(field.ilike(f"%{value.strip()}%"))
    if low_stock is True:
        query = query.where(WarehouseItem.quantity <= WarehouseItem.minimum_stock)
    return [_warehouse_payload(item) for item in db.scalars(query.order_by(WarehouseItem.name)).all()]


@router.post("/warehouse/items", response_model=WarehouseItemRead, status_code=status.HTTP_201_CREATED)
def create_warehouse_item(
    payload: WarehouseItemCreate,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_admin),
) -> dict[str, Any]:
    values = payload.model_dump()
    if values["linked_asset_id"] is not None and db.get(Asset, values["linked_asset_id"]) is None:
        raise HTTPException(422, "Linked asset not found")
    item = WarehouseItem(**values, quantity=0)
    db.add(item)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "SKU already exists") from error
    db.refresh(item)
    return _warehouse_payload(item)


@router.patch("/warehouse/items/{item_id}", response_model=WarehouseItemRead)
def update_warehouse_item(
    item_id: int,
    payload: WarehouseItemUpdate,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_admin),
) -> dict[str, Any]:
    item = db.get(WarehouseItem, item_id)
    if item is None:
        raise HTTPException(404, "Warehouse item not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("linked_asset_id") is not None and db.get(Asset, values["linked_asset_id"]) is None:
        raise HTTPException(422, "Linked asset not found")
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return _warehouse_payload(item)


@router.post("/warehouse/items/{item_id}/movements", response_model=WarehouseMovementRead, status_code=status.HTTP_201_CREATED)
def create_warehouse_movement(
    item_id: int,
    payload: WarehouseMovementCreate,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_admin),
) -> WarehouseMovement:
    item = db.get(WarehouseItem, item_id)
    if item is None:
        raise HTTPException(404, "Warehouse item not found")
    delta = payload.quantity if payload.movement_type in {"incoming", "adjustment_add"} else -payload.quantity
    if item.quantity + delta < 0:
        raise HTTPException(409, "Movement would make stock negative")
    item.quantity += delta
    movement = WarehouseMovement(
        item_id=item.id, actor_user_id=user.id, actor_username=user.username, **payload.model_dump()
    )
    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement


@router.get("/warehouse/items/{item_id}/movements", response_model=list[WarehouseMovementRead])
def list_warehouse_movements(
    item_id: int,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(get_current_user),
) -> list[WarehouseMovement]:
    if db.get(WarehouseItem, item_id) is None:
        raise HTTPException(404, "Warehouse item not found")
    return list(db.scalars(select(WarehouseMovement).where(WarehouseMovement.item_id == item_id).order_by(WarehouseMovement.created_at.desc(), WarehouseMovement.id.desc())).all())


def _reference_payload(document: ReferenceDocument) -> dict[str, Any]:
    payload = {column.name: getattr(document, column.name) for column in ReferenceDocument.__table__.columns}
    payload["tags"] = json.loads(document.tags) if document.tags else []
    payload["preview_supported"] = any(document.stored_name.casefold().endswith(ext) for ext in PREVIEW_EXTENSIONS)
    return payload


@router.get("/references", response_model=list[ReferenceDocumentRead])
def list_references(
    search: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    query = select(ReferenceDocument).where(ReferenceDocument.deleted_at.is_(None))
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.where(or_(ReferenceDocument.title.ilike(pattern), ReferenceDocument.description.ilike(pattern), ReferenceDocument.tags.ilike(pattern), ReferenceDocument.original_filename.ilike(pattern)))
    if category:
        query = query.where(ReferenceDocument.category.ilike(f"%{category.strip()}%"))
    return [_reference_payload(item) for item in db.scalars(query.order_by(ReferenceDocument.created_at.desc())).all()]


@router.post("/references", response_model=ReferenceDocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_reference(
    title: str = Form(min_length=1, max_length=255),
    category: str = Form(default="Other", max_length=100),
    tags: str = Form(default=""),
    description: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_admin),
) -> dict[str, Any]:
    content = await file.read()
    try:
        stored_name, media_type, _ = save_reference(content, file.filename or "")
    except (ValueError, OSError) as error:
        raise HTTPException(400, str(error)) from error
    normalized_tags = list(dict.fromkeys(tag.strip() for tag in tags.split(",") if tag.strip()))[:30]
    document = ReferenceDocument(
        title=title.strip(), category=category.strip() or "Other", tags=json.dumps(normalized_tags, ensure_ascii=False),
        description=description.strip() if description else None, original_filename=(file.filename or "document")[:255],
        stored_name=stored_name, media_type=media_type, size_bytes=len(content),
        uploaded_by_id=user.id, uploaded_by_username=user.username,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return _reference_payload(document)


@router.get("/references/{document_id}/download")
def download_reference(
    document_id: int,
    preview: bool = Query(False),
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(get_current_user),
) -> FileResponse:
    document = db.get(ReferenceDocument, document_id)
    if document is None or document.deleted_at is not None:
        raise HTTPException(404, "Reference document not found")
    try:
        path = resolve_reference(document.stored_name)
    except FileNotFoundError as error:
        raise HTTPException(404, "Reference file not found") from error
    disposition = "inline" if preview and any(document.stored_name.casefold().endswith(ext) for ext in PREVIEW_EXTENSIONS) else "attachment"
    return FileResponse(path, media_type=document.media_type, filename=document.original_filename, content_disposition_type=disposition)


@router.delete("/references/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reference(
    document_id: int,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_admin),
) -> None:
    """Soft-delete a reference document.

    The metadata row is retained for auditability, and the uploaded file is
    kept on disk; a future retention/purge job owns physical cleanup.
    """
    document = db.get(ReferenceDocument, document_id)
    if document is None or document.deleted_at is not None:
        raise HTTPException(404, "Reference document not found")
    document.deleted_at = func.now()
    db.commit()
