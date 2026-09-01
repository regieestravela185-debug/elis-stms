from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from .extensions import db
from .models import Payment, Reservation, ReservationStatus, TenantProfile, Unit, UnitStatus, UtilityBill
from .email_helper import send_payment_reminder_email, send_renewal_reminder_email, send_utility_bill_reminder_email
from .billing_utils import get_or_create_utility_bill
from .socket_events import emit_utility_bill_notification


_scheduler: BackgroundScheduler | None = None


def shift_month(d: date, delta: int) -> date:
    """Add/subtract whole months from a date, clamping the day to the target month's length."""
    m = d.month - 1 + delta
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def send_renewal_and_payment_reminders(app: Flask) -> dict:
    """Daily check: email tenants whose contract or next rent payment is due
    within 7 days. Re-sent once per day (deduped via last_*_reminder_sent)
    until the tenant renews or pays — at which point the underlying
    condition stops matching and reminders stop automatically.
    """
    with app.app_context():
        today = date.today()
        threshold = today + timedelta(days=7)
        renewal_count = 0
        payment_count = 0

        profiles = (
            db.session.query(TenantProfile)
            .filter(TenantProfile.is_active == True)  # noqa: E712
            .all()
        )

        for profile in profiles:
            user = profile.user
            if not user or not user.email:
                continue
            unit_code = profile.unit.unit_code if profile.unit else "N/A"

            # --- Contract renewal reminder ---
            if (
                profile.contract_end
                and today <= profile.contract_end <= threshold
                and profile.last_renewal_reminder_sent != today
            ):
                days_remaining = (profile.contract_end - today).days
                send_renewal_reminder_email(
                    user.full_name, user.email, unit_code, profile.contract_end, days_remaining
                )
                profile.last_renewal_reminder_sent = today
                renewal_count += 1

            # --- Monthly rent payment reminder ---
            if profile.contract_start:
                due_day = min(profile.contract_start.day, calendar.monthrange(today.year, today.month)[1])
                next_due = date(today.year, today.month, due_day)
                if next_due < today:
                    next_due = shift_month(next_due, 1)

                days_until_due = (next_due - today).days
                if 0 <= days_until_due <= 7 and profile.last_payment_reminder_sent != today:
                    cycle_start = datetime.combine(shift_month(next_due, -1), datetime.min.time())
                    already_paid = (
                        db.session.query(Payment)
                        .filter(Payment.tenant_profile_id == profile.id)
                        .filter(Payment.is_deposit == False)  # noqa: E712
                        .filter(Payment.paid_at >= cycle_start)
                        .first()
                        is not None
                    )
                    if not already_paid:
                        amount = float(profile.unit.price_monthly) if profile.unit and profile.unit.price_monthly else 0
                        send_payment_reminder_email(
                            user.full_name, user.email, unit_code, next_due, days_until_due, amount
                        )
                        profile.last_payment_reminder_sent = today
                        payment_count += 1

        db.session.commit()
        return {"renewal_reminders": renewal_count, "payment_reminders": payment_count}


def send_renewal_reminder_now(app: Flask, tenant_profile_id: int) -> bool:
    """Manually nudge exactly one tenant about their upcoming renewal —
    used by the "Notify" button on Tenant Monitoring, which flags tenants up
    to 30 days out (wider than the 7-day auto-reminder window), so this
    bypasses that window. Still deduped to once per day. Returns whether an
    email was actually sent.
    """
    with app.app_context():
        profile = db.session.get(TenantProfile, tenant_profile_id)
        if not profile or not profile.contract_end:
            return False
        user = profile.user
        if not user or not user.email:
            return False
        if profile.last_renewal_reminder_sent == date.today():
            return False

        days_remaining = (profile.contract_end - date.today()).days
        unit_code = profile.unit.unit_code if profile.unit else "N/A"
        send_renewal_reminder_email(user.full_name, user.email, unit_code, profile.contract_end, days_remaining)
        profile.last_renewal_reminder_sent = date.today()
        db.session.commit()
        return True


def _send_utility_bill_reminder(profile: TenantProfile, bill: UtilityBill) -> None:
    """Shared send step used by both the daily job and the manual trigger —
    email + in-app push, then stamp reminder_sent_at (caller commits)."""
    user = profile.user
    unit_code = profile.unit.unit_code if profile.unit else "N/A"
    days_remaining = (bill.due_date - date.today()).days
    send_utility_bill_reminder_email(
        user.full_name, user.email, unit_code, bill.due_date, days_remaining,
        float(bill.rent_amount_snapshot), float(bill.electric_amount),
        float(bill.water_amount), float(bill.carried_over_amount),
        electric_paid=bill.electric_paid, water_paid=bill.water_paid,
        carried_over_electric=float(bill.carried_over_electric or 0),
        carried_over_water=float(bill.carried_over_water or 0),
    )
    still_owed = " and ".join(bill.unpaid_components) or "Balance"
    emit_utility_bill_notification(user.id, {
        "title": f"{still_owed} reminder — Unit {unit_code}",
        "subtitle": f"₱{bill.total_outstanding:,.2f} due {bill.due_date.strftime('%b %d, %Y')}",
    })
    bill.reminder_sent_at = date.today()


def send_utility_bill_reminders(app: Flask) -> dict:
    """Daily check: for every active RESIDENTIAL tenant, get/create this
    month's utility bill (see get_or_create_utility_bill — this is also
    where carry-over from an unpaid prior month gets computed) and, if it's
    unpaid with 0-7 days until due_date and not already reminded today,
    email + in-app push the itemized Rent+Electric+Water(+carry-over)=Total.
    Commercial tenants are never included — see UtilityBill's docstring."""
    with app.app_context():
        today = date.today()
        sent_count = 0

        profiles = (
            db.session.query(TenantProfile)
            .join(Unit, TenantProfile.unit_id == Unit.id)
            .filter(TenantProfile.is_active == True, Unit.type == "residential")  # noqa: E712
            .all()
        )
        for profile in profiles:
            user = profile.user
            if not user or not user.email or not profile.contract_start:
                continue

            billing_month = today.strftime("%Y-%m")
            bill = get_or_create_utility_bill(profile, billing_month)
            # Paused means the tenant has already told the administrator they
            # will settle next month — the balance still rolls forward, we
            # just stop nagging them about it.
            if bill.is_paid or bill.reminders_paused:
                continue

            days_until_due = (bill.due_date - today).days
            if 0 <= days_until_due <= 7 and bill.reminder_sent_at != today:
                _send_utility_bill_reminder(profile, bill)
                sent_count += 1

        db.session.commit()
        return {"utility_reminders": sent_count}


def send_utility_bill_reminder_now(app: Flask, utility_bill_id: int) -> bool:
    """Admin-button-triggered single-bill version of the utility reminder —
    used by the "Send Reminder Now" action on the Utility Billing page.
    Bypasses the 7-day window, still deduped to once per day. Returns
    whether an email was actually sent."""
    with app.app_context():
        bill = db.session.get(UtilityBill, utility_bill_id)
        # The manual button deliberately ignores reminders_paused: it is the
        # administrator asking for this one send, which overrides the pause
        # they themselves set.
        if not bill or bill.is_paid:
            return False
        profile = bill.tenant_profile
        user = profile.user if profile else None
        if not user or not user.email:
            return False
        if bill.reminder_sent_at == date.today():
            return False

        _send_utility_bill_reminder(profile, bill)
        db.session.commit()
        return True


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
    scheduler.add_job(
        func=send_renewal_and_payment_reminders,
        trigger="cron",
        hour=8,
        minute=0,
        args=[app],
        id="daily_tenant_reminders",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        func=send_utility_bill_reminders,
        trigger="cron",
        hour=8,
        minute=0,
        args=[app],
        id="daily_utility_bill_reminders",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    _scheduler = scheduler

