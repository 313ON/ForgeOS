from __future__ import annotations

from datetime import date, timedelta
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import SessionLocal
from .domain.models import Asset, Assignment, Person, User, Warranty
from .services.auth import hash_password


def seed_database() -> bool:
    """Insert useful first-run sample data when the asset table is empty."""
    with SessionLocal() as session:
        if session.scalar(select(Asset.id).limit(1)) is not None:
            _ensure_admin(session)
            session.commit()
            return False
        _insert_seed_data(session)
        _ensure_admin(session)
        session.commit()
        return True


def _ensure_admin(session: Session) -> None:
    username = os.getenv("FORGEOS_ADMIN_USERNAME", "admin")
    existing = session.scalar(select(User).where(User.username == username))
    if existing is not None:
        existing.role = "ADMIN"
        existing.is_active = True
        return
    password = os.getenv("FORGEOS_ADMIN_PASSWORD", "ForgeOS-ChangeMe-2026!")
    session.add(User(username=username, password_hash=hash_password(password), role="ADMIN"))


def _insert_seed_data(session: Session) -> None:
    today = date.today()
    assets = [
        Asset(
            asset_tag="FOS-1001",
            type="Laptop",
            brand="Dell",
            model="Latitude 7440",
            serial_number="DL7440-0281",
            location="Tehran HQ",
            status="active",
        ),
        Asset(
            asset_tag="FOS-1002",
            type="Desktop",
            brand="Lenovo",
            model="ThinkCentre M90q",
            serial_number="LN-M90Q-114",
            location="Operations",
            status="active",
        ),
        Asset(
            asset_tag="FOS-1003",
            type="Server",
            brand="HPE",
            model="ProLiant DL360",
            serial_number="HPE-DL360-77",
            location="Datacenter A",
            status="active",
        ),
        Asset(
            asset_tag="FOS-1004",
            type="Laptop",
            brand="HP",
            model="EliteBook 840",
            serial_number=None,
            location="Tehran HQ",
            status="maintenance",
        ),
        Asset(
            asset_tag="FOS-1005",
            type="Monitor",
            brand="LG",
            model="UltraFine 27",
            serial_number="LG-UF27-991",
            location="Design Studio",
            status="active",
        ),
        Asset(
            asset_tag="FOS-1006",
            type="Network",
            brand="Cisco",
            model="Catalyst 9200",
            serial_number=None,
            location="Datacenter A",
            status="stock",
        ),
    ]
    people = [
        Person(
            full_name="Ava Rahimi",
            org_unit="Engineering",
            email="ava.rahimi@example.com",
            phone="+98 21 5550 1010",
        ),
        Person(
            full_name="Noah Karimi",
            org_unit="Operations",
            email="noah.karimi@example.com",
            phone="+98 21 5550 1020",
        ),
        Person(
            full_name="Mina Farzan",
            org_unit="Finance",
            email="mina.farzan@example.com",
            phone="+98 21 5550 1030",
        ),
    ]
    session.add_all([*assets, *people])
    session.flush()

    session.add_all(
        [
            Assignment(
                asset_id=assets[0].id,
                person_id=people[0].id,
                start_date=today - timedelta(days=90),
                notes="Primary engineering workstation",
            ),
            Assignment(
                asset_id=assets[1].id,
                person_id=people[1].id,
                start_date=today - timedelta(days=45),
            ),
            Assignment(
                asset_id=assets[3].id,
                person_id=people[2].id,
                start_date=today - timedelta(days=120),
                notes="Temporarily in maintenance",
            ),
            Warranty(
                asset_id=assets[0].id,
                vendor="Dell ProSupport",
                contract_no="DPS-7440-28",
                start_date=today - timedelta(days=700),
                end_date=today + timedelta(days=21),
            ),
            Warranty(
                asset_id=assets[2].id,
                vendor="HPE Foundation Care",
                contract_no="HPE-FC-360",
                start_date=today - timedelta(days=365),
                end_date=today + timedelta(days=240),
            ),
        ]
    )
