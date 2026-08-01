from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from ..database import SessionLocal
from ..domain.models import MonitoredTarget
from ..api.router import run_monitoring_check

logger = logging.getLogger("forgeos.monitoring")


async def monitoring_loop(stop_event: asyncio.Event) -> None:
    """Run due target checks in one non-blocking in-process scheduler."""
    while not stop_event.is_set():
        try:
            with SessionLocal() as session:
                targets = session.scalars(
                    select(MonitoredTarget).where(MonitoredTarget.enabled.is_(True))
                ).all()
                for target in targets:
                    if target.last_checked_at is None:
                        due = True
                    else:
                        last_checked = target.last_checked_at
                        if last_checked.tzinfo is None:
                            last_checked = last_checked.replace(tzinfo=timezone.utc)
                        due = (
                            datetime.now(timezone.utc) - last_checked
                        ).total_seconds() >= target.ping_interval_sec
                    if due:
                        await asyncio.to_thread(_run_target_check, target.id)
        except Exception:
            logger.exception("monitoring_scheduler_iteration_failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=5)
        except asyncio.TimeoutError:
            continue


def _run_target_check(target_id: int) -> None:
    """Run one target check with a scheduler-owned database session."""
    with SessionLocal() as session:
        target = session.get(MonitoredTarget, target_id)
        if target is not None and target.enabled:
            run_monitoring_check(target, session)
