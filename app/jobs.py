from __future__ import annotations

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from .extensions import db
from .models import Reservation, ReservationStatus, Unit, UnitStatus


_scheduler: BackgroundScheduler | None = None


def _auto_cancel_expired_reservations(app: Flask) -> None:
    with app.app_context():
        hours = int(app.config.get("RESERVATION_AUTO_CANCEL_HOURS", 48))
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        expired = (
            db.session.query(Reservation)
            .filter(Reservation.status == ReservationStatus.PENDING)
            .filter(Reservation.created_at < cutoff)
            .all()
        )

        if not expired:
            return

        unit_ids = [r.unit_id for r in expired]
        for r in expired:
            r.status = ReservationStatus.CANCELLED

        (
            db.session.query(Unit)
            .filter(Unit.id.in_(unit_ids))
            .filter(Unit.status == UnitStatus.RESERVED)
            .update({Unit.status: UnitStatus.AVAILABLE}, synchronize_session=False)
        )

        db.session.commit()


def start_scheduler(app: Flask) -> None:
    global _scheduler
    if _scheduler is not None:
        return

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        func=_auto_cancel_expired_reservations,
        trigger="interval",
        minutes=10,
        args=[app],
        id="auto_cancel_reservations",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    _scheduler = scheduler

