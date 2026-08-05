from __future__ import annotations

import re
from collections.abc import Mapping

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..domain.models import Asset

DEFAULT_PREFIXES: Mapping[str, str] = {
    "router": "ROT",
    "switch": "SWT",
    "laptop": "LAP",
    "desktop": "DSK",
    "server": "SRV",
    "printer": "PRT",
    "monitor": "MON",
    "mobile": "MOB",
    "peripheral": "PER",
    "network": "NET",
    "firewall": "FWL",
    "access point": "APT",
    "tablet": "MOB",
    "phone": "MOB",
}
TAG_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{1,9}-\d{4,}$")


def prefix_for_asset_type(asset_type: str) -> str:
    """Return the configured tag prefix for an asset type."""
    return DEFAULT_PREFIXES.get(asset_type.strip().casefold(), "FOS")


def validate_manual_tag(tag: str) -> str:
    """Normalize and validate a manually supplied asset tag."""
    normalized = tag.strip().upper()
    if not TAG_PATTERN.fullmatch(normalized):
        raise ValueError("Asset tag must match PREFIX-0001 format")
    return normalized


def generate_asset_tag(session: Session, asset_type: str) -> str:
    """Generate the next available tag for an asset type within a transaction."""
    prefix = prefix_for_asset_type(asset_type)
    pattern = f"{prefix}-%"
    rows = session.scalars(
        select(Asset.asset_tag).where(Asset.asset_tag.like(pattern)).with_for_update()
    ).all()
    highest = max(
        (int(value.rsplit("-", 1)[1]) for value in rows if value.rsplit("-", 1)[-1].isdigit()),
        default=0,
    )
    candidate = f"{prefix}-{highest + 1:04d}"
    while session.scalar(select(func.count(Asset.id)).where(Asset.asset_tag == candidate)):
        highest += 1
        candidate = f"{prefix}-{highest + 1:04d}"
    return candidate
