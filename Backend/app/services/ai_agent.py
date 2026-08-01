from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.models import Asset, NetworkLog


def ai_config() -> dict[str, str | None]:
    return {
        "base_url": os.getenv("FORGEOS_AI_BASE_URL", "https://openrouter.ai/api/v1"),
        "model": os.getenv("FORGEOS_AI_MODEL", "openai/gpt-4o-mini"),
        "api_key": os.getenv("OPENROUTER_API_KEY"),
    }


def query_asset_insights(
    db: Session,
    asset_id: int,
    backend: Callable[[dict[str, Any], dict[str, str | None]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise LookupError("Asset not found")
    warranty = max(asset.warranties, key=lambda item: item.end_date, default=None)
    logs = db.scalars(
        select(NetworkLog).order_by(NetworkLog.timestamp.desc()).limit(10)
    ).all()
    context = {
        "asset": {
            "id": asset.id,
            "tag": asset.asset_tag,
            "type": asset.type,
            "manufacturer": asset.manufacturer or asset.brand,
            "model": asset.model,
            "ram_mb": asset.ram_mb,
            "cpu_name": asset.cpu_name,
            "gpu_name": asset.gpu_name,
            "hostname": asset.hostname,
            "status": asset.status,
        },
        "warranty": {"vendor": warranty.vendor, "end_date": warranty.end_date.isoformat()} if warranty else None,
        "monitoring": [{"status": log.status, "message": log.message, "timestamp": log.timestamp.isoformat()} for log in logs],
    }
    if backend is None:
        return {
            "summary": "AI backend is not configured; structured asset context is ready.",
            "warnings": [],
            "warranty": context["warranty"],
            "notes": ["Set OPENROUTER_API_KEY to enable a pluggable backend."],
            "context": context,
        }
    return backend(context, ai_config())
