from __future__ import annotations

import json
from decimal import Decimal
import re
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for, Response
from flask_login import current_user, login_required
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import contains_eager, joinedload

from ...extensions import db
from ...upload_validation import validate_upload, DOCUMENT_TYPES, IMAGE_TYPES
from ...models import (
    ActivityLog,
    Announcement,
    BlockchainAlarmDismissal,
    Building,
    Concern,
    ConcernStatus,
    Document,
    Feedback,
    FeedbackStatus,
    IdentityVerification,
    MoveOutNotice,
    MoveOutNoticeStatus,
    Payment,
    PaymentLedger,
    PaymentRiskLevel,
    RenewalRequest,
    RenewalRequestStatus,
    Reservation,
    ReservationStatus,
    Role,
    TenantProfile,
    Unit,
    UnitStatus,
    User,
    UtilityBill,
    VerificationStatus,
    PAYMENT_STATUSES_NOT_COUNTED,
    payment_revenue_amount,
    UnitInventoryItem,
)
from ...inventory import (ensure_unit_inventory, inventory_summary,
                          INVENTORY_CONDITIONS, CONDITION_KEYS,
                          STANDARD_UNIT_INVENTORY)
from ...billing_utils import (get_payment_timeline, payment_standing,
                              final_settlement)
from ...security import sha256_hex
from ...ph_holidays import holidays_by_date
from ...smart_notifications import get_notification_system, NotificationPriority, NotificationType
from ...models import NotificationHistory

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _ensure_admin():
    if current_user.role != Role.ADMIN:  # type: ignore[attr-defined]
        abort(403)


_PHONE_UA_RE = re.compile(r"iPhone|iPod|Windows Phone|BlackBerry|Opera Mini|IEMobile", re.I)


def _is_phone_request() -> bool:
    """Admin dashboard is designed for tablet/laptop/desktop only. Detect
    phone-class user agents (not tablets — iPad and Android tablet Chrome
    UAs don't carry a "Mobile" token) so we can point phone visitors to a
    larger device instead of serving them a cramped admin UI."""
    ua = request.user_agent.string or ""
    if "iPad" in ua:
        return False
    if _PHONE_UA_RE.search(ua):
        return True
    return "Android" in ua and "Mobile" in ua


@bp.before_request
def _block_admin_on_phone():
    if not (current_user.is_authenticated and current_user.role == Role.ADMIN):  # type: ignore[attr-defined]
        return None
    if not _is_phone_request():
        return None
    if request.path.startswith("/admin/api/"):
        return jsonify({"error": "The admin dashboard is only available on tablet, laptop, or desktop devices."}), 403
    return render_template("admin/device_blocked.html"), 200


@bp.get("/api/search")
@login_required
def global_search():
    """Topbar search — scoped to whichever admin module the request came
    from (see admin_search_scope in app/__init__.py's nav context
    processor). Only queries the one relevant category instead of
    searching everything regardless of the current page."""
    _ensure_admin()
    from flask import jsonify
    from sqlalchemy import or_

    q = (request.args.get("q") or "").strip()
    scope = (request.args.get("scope") or "").strip()
    results = {"customers": [], "units": [], "reservations": [], "payments": [], "documents": []}
    if len(q) < 2:
        return jsonify(results)
    like = f"%{q}%"
    # "all" (Dashboard's overview search) queries every category, so keep
    # each one short; a single-module scope gets the full budget.
    limit = 5 if scope == "all" else 8

    if scope in ("customers", "all"):
        for u in (db.session.query(User)
                  .filter(User.role != Role.ADMIN,
                          or_(User.full_name.ilike(like), User.email.ilike(like)))
                  .limit(limit).all()):
            results["customers"].append({
                "label": u.full_name, "sub": u.email,
                "url": url_for("admin.user_details", user_id=u.id),
            })

    if scope in ("units", "all"):
        for un in (db.session.query(Unit).filter(Unit.is_archived == False, Unit.unit_code.ilike(like))  # noqa: E712
                   .order_by(Unit.unit_code.asc()).limit(limit).all()):
            results["units"].append({
                "label": un.unit_code, "sub": (un.type or "Unit"),
                "url": url_for("admin.edit_unit", unit_id=un.id),
            })

    if scope in ("reservations", "all"):
        for r in (db.session.query(Reservation)
                  .filter(or_(Reservation.full_name.ilike(like), Reservation.email.ilike(like)))
                  .order_by(Reservation.created_at.desc()).limit(limit).all()):
            results["reservations"].append({
                "label": r.full_name, "sub": r.email,
                "url": url_for("admin.reservations"),
            })

    if scope in ("payments", "all"):
        for p in (db.session.query(Payment)
                  .filter(or_(Payment.reference.ilike(like), Payment.receipt_number.ilike(like)))
                  .order_by(Payment.paid_at.desc()).limit(limit).all()):
            results["payments"].append({
                "label": (p.reference or p.receipt_number or ("Payment #%s" % p.id)),
                "sub": "₱{:,.2f}".format(float(p.amount)),
                "url": url_for("admin.payments"),
            })

    if scope in ("documents", "all"):
        for d in (db.session.query(Document).join(TenantProfile, Document.tenant_profile_id == TenantProfile.id)
                  .join(User, TenantProfile.user_id == User.id)
                  .filter(or_(Document.title.ilike(like), User.full_name.ilike(like)))
                  .order_by(Document.uploaded_at.desc()).limit(limit).all()):
            tenant_name = d.tenant_profile.user.full_name if d.tenant_profile and d.tenant_profile.user else "Unknown tenant"
            results["documents"].append({
                "label": d.title, "sub": tenant_name,
                "url": url_for("admin.documents"),
            })

    return jsonify(results)


@bp.get("/api/suggest-reply")
@login_required
def suggest_reply_api():
    """Rule-based draft reply for a concern or inquiry (no LLM)."""
    _ensure_admin()
    from flask import jsonify
    from ...ai_utils import suggest_reply
    from ...models import Concern, Inquiry

    cid = request.args.get("concern_id", type=int)
    iid = request.args.get("inquiry_id", type=int)
    if cid:
        c = db.session.get(Concern, cid)
        if c:
            text = " ".join(x for x in [c.subject, c.description] if x)
            return jsonify({"reply": suggest_reply(c.category, text)})
    if iid:
        i = db.session.get(Inquiry, iid)
        if i:
            text = " ".join(x for x in [i.subject, i.message] if x)
            return jsonify({"reply": suggest_reply(getattr(i, "category", None), text)})
    return jsonify({"reply": ""})


def _get_building_floor_limit(building_id: int) -> int:
    building = db.session.get(Building, building_id)
    if not building:
        return 4
    if building.code in ("B3", "B4", "B5"):
        return 3
    return 4


def _get_building_unit_type(building_id: int) -> str | None:
    """Buildings 1-4 are residential-only; Building 5 is commercial-only."""
    building = db.session.get(Building, building_id)
    if not building:
        return None
    if building.code == "B5":
        return "commercial"
    if building.code in ("B1", "B2", "B3", "B4"):
        return "residential"
    return None


def _parse_money(raw, field="amount", *, maximum=99_999_999.99):
    """Read a peso amount from a form, or say what is wrong with it.

    float() is more permissive than the field it fills. "1e999" becomes
    inf, "1e40" a number NUMERIC(12,2) cannot hold, and "-5" a negative
    price — all of which the previous try/except let through to fail at
    the database as an internal server error. Returns (value, error).
    """
    import math

    text = (str(raw) if raw is not None else "").strip()
    if not text:
        return None, f"Please enter a {field}."
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None, f"That {field} is not a number."
    if not math.isfinite(value):
        return None, f"That {field} is not a real number."
    if value < 0:
        return None, f"The {field} cannot be negative."
    if value > maximum:
        return None, f"That {field} is too large. The most allowed is {maximum:,.2f}."
    return round(value, 2), None


def _is_rent_payment_late(profile: TenantProfile, paid_at: datetime, payment_month: str = "") -> bool:
    """Whether a rent payment was made after its due date.

    Rent is due monthly on the same day-of-month as the tenant's contract
    start (mirrors the "next payment due" convention already used in
    app/blueprints/tenant/routes.py). When payment_month ("YYYY-MM") is
    given, the due date is anchored to that specific billing cycle instead
    of guessed from the payment's own date.
    """
    if not profile.contract_start:
        return False

    due_day = profile.contract_start.day

    if payment_month:
        try:
            year, month = (int(x) for x in payment_month.split("-"))
        except ValueError:
            year, month = paid_at.year, paid_at.month
    else:
        year, month = paid_at.year, paid_at.month

    import calendar
    due_day = min(due_day, calendar.monthrange(year, month)[1])
    due_date = date(year, month, due_day)

    return paid_at.date() > due_date


def _compute_final_month_charge(profile: "TenantProfile", actual_move_out_date: date) -> dict:
    """Rule-based computation for a residential tenant's final (partial)
    billing cycle when they move out mid-month.

    The billing cycle is anchored to the tenant's own move-in day, NOT the
    calendar month — e.g. a tenant who started Jan 5 has cycles Jan5-Feb4,
    Feb5-Mar4, etc. The half/full cutoff is 15 days INTO that cycle (day
    1-15 of the cycle = half month, day 16+ = full month), matching the
    owner's "kalagitnaan ng buwan" rule applied to their own anniversary
    day rather than the calendar's 1st-15th/16th-31st.

    - If that final cycle is already fully paid, no additional charge.
    - If unpaid and the cycle's due date hasn't arrived yet (admin is
      processing ahead of time / tenant gave early notice), the amount is
      just a recommendation for the normal Payment collected at that due
      date — nothing is auto-created.
    - If unpaid and the due date has already passed (late notice), the
      amount is meant to be deducted from the security deposit instead,
      since there's no more chance to collect it as a regular payment.
    """
    import calendar
    from ...jobs import shift_month

    unit_price = float(profile.unit.price_monthly) if profile.unit and profile.unit.price_monthly else 0.0

    # Locate the billing cycle (anchored to contract_start's day-of-month)
    # that covers the move-out date.
    cycle_start = None
    if profile.contract_start:
        due_day = min(profile.contract_start.day, calendar.monthrange(actual_move_out_date.year, actual_move_out_date.month)[1])
        this_month_due = date(actual_move_out_date.year, actual_move_out_date.month, due_day)
        cycle_start = this_month_due if this_month_due <= actual_move_out_date else shift_month(this_month_due, -1)

    if cycle_start:
        days_into_cycle = (actual_move_out_date - cycle_start).days + 1
    else:
        days_into_cycle = actual_move_out_date.day  # fallback if no contract_start on record
    half_or_full = "half" if days_into_cycle <= 15 else "full"
    amount = round(unit_price / 2, 2) if half_or_full == "half" else round(unit_price, 2)

    already_paid = False
    if cycle_start:
        cycle_start_dt = datetime.combine(cycle_start, datetime.min.time())
        already_paid = (
            db.session.query(Payment)
            .filter(Payment.tenant_profile_id == profile.id)
            .filter(Payment.is_deposit == False)  # noqa: E712
            .filter(Payment.payment_status.notin_(PAYMENT_STATUSES_NOT_COUNTED))
            .filter(Payment.paid_at >= cycle_start_dt)
            .first()
            is not None
        )

    due_date_passed = bool(cycle_start and date.today() >= cycle_start)
    needs_charge = not already_paid and cycle_start is not None
    is_late = needs_charge and due_date_passed

    return {
        "half_or_full": half_or_full,
        "amount": amount if needs_charge else 0.0,
        "needs_charge": needs_charge,
        "is_late": is_late,
        "already_paid": already_paid,
        "cycle_start": cycle_start,
    }


def _generate_payment_ledger(payment: Payment) -> None:
    """Generate a blockchain ledger entry for a payment."""
    from datetime import datetime
    import hashlib

    # Get previous ledger entry — use id (auto-increment) instead of created_at
    # because MySQL DATETIME may not have enough precision for rapid inserts
    previous_ledger = (
        db.session.query(PaymentLedger)
        .order_by(PaymentLedger.id.desc())
        .first()
    )

    previous_hash = previous_ledger.hash if previous_ledger else ""

    # Create payload - normalize timestamp to remove microseconds for consistency
    paid_at_normalized = payment.paid_at.replace(microsecond=0).isoformat()
    payload = {
        "payment_id": payment.id,
        "tenant_profile_id": payment.tenant_profile_id,
        "amount": float(payment.amount),
        "reference": payment.reference,
        "paid_at": paid_at_normalized,
    }

    payload_json = json.dumps(payload, sort_keys=True)

    # Generate hash
    hash_input = f"{previous_hash}{payload_json}"
    hash_value = hashlib.sha256(hash_input.encode()).hexdigest()

    # Create ledger entry
    ledger = PaymentLedger(
        payment_id=payment.id,
        payload_json=payload_json,
        previous_hash=previous_hash,
        hash=hash_value,
    )
    db.session.add(ledger)
    db.session.flush()  # critical: make visible to next ledger's previous_hash query


def verify_blockchain_chain() -> dict:
    """Verify the integrity of the blockchain ledger chain by comparing live data with hashes."""
    import hashlib
    import json
    
    ledgers = db.session.query(PaymentLedger).order_by(PaymentLedger.id.asc()).all()
    
    if not ledgers:
        return {"valid": True, "message": "No ledger entries to verify", "issues": [], "total_ledgers": 0}
    
    issues = []
    previous_hash = ""
    
    for i, ledger in enumerate(ledgers):
        # Fetch LIVE data from the payments table to compare
        payment = db.session.get(Payment, ledger.payment_id)
        
        if not payment:
            issues.append({
                "ledger_id": ledger.id,
                "payment_id": ledger.payment_id,
                "payment_amount": 0,
                "tenant_info": "Unknown",
                "issue": "Payment record missing in database"
            })
            continue

        # Reconstruct the payload using LIVE data from the database
        # Normalize timestamp to remove microseconds for consistency
        paid_at_normalized = payment.paid_at.replace(microsecond=0).isoformat()
        live_payload = {
            "payment_id": payment.id,
            "tenant_profile_id": payment.tenant_profile_id,
            "amount": float(payment.amount),
            "reference": payment.reference,
            "paid_at": paid_at_normalized,
        }
        live_payload_json = json.dumps(live_payload, sort_keys=True)

        # Recalculate hash from LIVE payload and previous hash
        hash_input = f"{previous_hash}{live_payload_json}"
        calculated_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        
        # Check if stored hash matches calculated hash (this detects tampering)
        if calculated_hash != ledger.hash:
            payment = db.session.get(Payment, ledger.payment_id)
            tenant_info = "Unknown Tenant"
            if payment and payment.tenant_profile and payment.tenant_profile.user:
                tenant_info = f"{payment.tenant_profile.user.full_name} ({payment.tenant_profile.unit.unit_code})"
            
            issues.append({
                "ledger_id": ledger.id,
                "payment_id": ledger.payment_id,
                "tenant_info": tenant_info,
                "payment_amount": float(payment.amount) if payment else 0,
                "issue": "Data mismatch - The payment record in the database does not match its blockchain signature.",
                "stored_hash": ledger.hash,
                "calculated_hash": calculated_hash
            })
        
        # Check if the chain is broken
        if i > 0 and ledger.previous_hash != previous_hash:
            payment = db.session.get(Payment, ledger.payment_id)
            tenant_info = "Unknown Tenant"
            if payment and payment.tenant_profile and payment.tenant_profile.user:
                tenant_info = f"{payment.tenant_profile.user.full_name} ({payment.tenant_profile.unit.unit_code})"

            issues.append({
                "ledger_id": ledger.id,
                "payment_id": ledger.payment_id,
                "payment_amount": float(payment.amount) if payment else 0,
                "tenant_info": tenant_info,
                "issue": "Chain link broken - Previous hash mismatch"
            })
        
        previous_hash = ledger.hash

    # A row written straight into `payments`, bypassing the app, never gets a
    # ledger entry — and walking the ledger alone would never look at it. It
    # would count toward revenue with nothing vouching for it, so the payments
    # side is checked too. Tenant-submitted proofs awaiting review are signed
    # at approval, not at submission, and a rejected one never is: neither is
    # missing a signature it was ever meant to have.
    signed = {l.payment_id for l in ledgers}
    unsigned = (db.session.query(Payment)
                .filter(Payment.payment_status.notin_(("pending", "rejected")))
                .order_by(Payment.id.asc()).all())
    for payment in unsigned:
        if payment.id in signed:
            continue
        tenant_info = "Unknown Tenant"
        if payment.tenant_profile and payment.tenant_profile.user:
            tenant_info = (f"{payment.tenant_profile.user.full_name} "
                           f"({payment.tenant_profile.unit.unit_code})")
        issues.append({
            "ledger_id": None,
            "payment_id": payment.id,
            "tenant_info": tenant_info,
            "payment_amount": float(payment.amount),
            "issue": "Unsigned payment - This payment has no blockchain entry. "
                     "It was not recorded through the system.",
        })

    return {
        "valid": len(issues) == 0,
        "message": "Blockchain chain is valid" if len(issues) == 0 else f"Found {len(issues)} integrity issue(s)",
        "issues": issues,
        "total_ledgers": len(ledgers)
    }


def _send_reservation_result_email(to_email: str, status: ReservationStatus, unit_code: str,
                                   to_name: str = "Tenant", reason: str | None = None) -> None:
    """Send reservation result email using Brevo HTTP API"""
    if not to_email:
        return

    from ...email_helper import send_reservation_result_email

    # Convert ReservationStatus enum to string
    status_str = status.value.lower()  # 'approved', 'rejected', 'cancelled'

    send_reservation_result_email(to_email, to_name, status_str, unit_code, reason=reason)


def _send_renewal_reminder_email(tenant_name: str, tenant_email: str, unit_code: str, contract_end: date, days_remaining: int) -> None:
    """Send renewal reminder email using Brevo HTTP API"""
    if not tenant_email:
        return
    
    from ...email_helper import send_renewal_reminder_email
    
    send_renewal_reminder_email(tenant_name, tenant_email, unit_code, contract_end, days_remaining)


@bp.post("/notifications/generate-automated")
@login_required
def generate_automated_notifications():
    """Generate automated smart notifications for tenants"""
    _ensure_admin()
    
    notification_system = get_notification_system()
    generated_count = 0
    emailed_count = 0

    tenants = db.session.query(TenantProfile).all()
    today = date.today()

    for tenant in tenants:
        if not tenant.is_active:
            continue

        user = tenant.user
        if not user:
            continue

        # Check for lease expiration notification — early (30-day) heads-up,
        # emailed to the tenant. The urgent 7-day reminder is handled by the
        # daily scheduled job (app/jobs.py) regardless of this button.
        if tenant.contract_end:
            days_until_expiry = (tenant.contract_end - today).days
            if days_until_expiry <= 30 and days_until_expiry > 0:
                notification = notification_system.get_renewal_reminder_notification(
                    user_id=user.id,
                    lease_end_date=tenant.contract_end,
                    days_until_expiry=days_until_expiry,
                )

                # Save to database
                try:
                    notif = NotificationHistory(
                        user_id=notification["user_id"],
                        notification_type=notification["notification_type"],
                        notification_priority=notification["notification_priority"],
                        automated_trigger_type=notification["automated_trigger_type"],
                        message=notification["message"],
                        status=notification["status"],
                    )
                    db.session.add(notif)
                    generated_count += 1
                except Exception as e:
                    print(f"Error saving notification: {e}")

                # Email the tenant — skip if already emailed today (e.g. by
                # the daily job or a previous click of this same button).
                if user.email and tenant.last_renewal_reminder_sent != today:
                    unit_code = tenant.unit.unit_code if tenant.unit else "N/A"
                    _send_renewal_reminder_email(
                        user.full_name, user.email, unit_code, tenant.contract_end, days_until_expiry
                    )
                    tenant.last_renewal_reminder_sent = today
                    emailed_count += 1

        # Check for high-risk notification — internal insight for admin only.
        # Deliberately NOT emailed to the tenant (it's an outreach cue for
        # staff, not a message meant for the tenant to read verbatim).
        if tenant.payment_risk_level and tenant.payment_risk_level.value == "high":
            notification = notification_system.get_high_risk_alert_notification(
                user_id=user.id,
                tenant_name=user.full_name,
                risk_score=float(tenant.prediction_score or 0.8),
            )

            # Save to database
            try:
                notif = NotificationHistory(
                    user_id=notification["user_id"],
                    notification_type=notification["notification_type"],
                    notification_priority=notification["notification_priority"],
                    automated_trigger_type=notification["automated_trigger_type"],
                    message=notification["message"],
                    status=notification["status"],
                )
                db.session.add(notif)
                generated_count += 1
            except Exception as e:
                print(f"Error saving notification: {e}")

    db.session.commit()

    flash(
        f"Generated {generated_count} notification(s) — {emailed_count} renewal reminder email(s) sent to tenants. "
        "High-risk alerts are admin-only and appear below.",
        "success",
    )
    return redirect(url_for("admin.dashboard"))


@bp.post("/analytics/update-risk-profiles")
@login_required
def update_risk_profiles():
    """Update payment risk profiles for all tenants using predictive analytics"""
    _ensure_admin()
    
    tenants = db.session.query(TenantProfile).all()
    updated_count = 0
    
    for tenant in tenants:
        # Get payment history for tenant
        payments = (
            db.session.query(Payment)
            .filter(Payment.tenant_profile_id == tenant.id)
            .order_by(Payment.paid_at.desc())
            .all()
        )
        
        # Convert payments to dict format for analysis
        payment_data = []
        for p in payments:
            payment_data.append({
                "paid_at": p.paid_at.isoformat(),
                "is_late": p.is_late,
                "amount": float(p.amount),
            })
        
        # Update tenant risk profile
        if payment_data:
            # Imported here, not at module load: pandas costs about 158 MB
            # of resident memory, and only this one call needs it.
            from ...predictive_analytics import update_tenant_risk_profile

            analysis = update_tenant_risk_profile(tenant, payment_data)
            if analysis:
                updated_count += 1
    
    db.session.commit()
    
    flash(f"Updated payment risk profiles for {updated_count} tenants.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.get("/dashboard")
@login_required
def dashboard():
    _ensure_admin()

    # Automatic Blockchain Integrity Check
    blockchain_status = verify_blockchain_chain()
    
    # Check if admin has dismissed the alarm
    alarm_dismissed = db.session.query(BlockchainAlarmDismissal).filter(
        BlockchainAlarmDismissal.user_id == current_user.id  # type: ignore[attr-defined]
    ).first() is not None
    
    total_units = db.session.query(Unit).filter(Unit.is_archived == False).count()
    available = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.AVAILABLE).count()
    occupied = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.OCCUPIED).count()
    reserved = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.RESERVED).count()
    unpaid = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.UNPAID).count()
    pending_res = (
        db.session.query(Reservation)
        .filter(Reservation.status == ReservationStatus.PENDING)
        .count()
    )

    total_tenants = db.session.query(TenantProfile).count()
    # Voided and rejected rows do not count toward revenue, so counting them
    # here made the tile disagree with every figure beside it.
    total_payments = (db.session.query(Payment)
                      .filter(Payment.payment_status.notin_(PAYMENT_STATUSES_NOT_COUNTED))
                      .count())
    # A voided or rejected payment must stop counting here too. The
    # Payments page already excluded them; this one did not, so voiding a
    # payment left the dashboard's revenue unchanged.
    _counted = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.payment_status.notin_(PAYMENT_STATUSES_NOT_COUNTED))
    # "Revenue" was rent and security deposits added together, which reads as
    # income the business does not have — a deposit is held and given back.
    # Worse, returning a deposit writes its own Payment row, so money paid
    # OUT was being added to revenue as though it had come in. Each part is
    # now counted for what it is.
    rent_revenue = _counted.filter(Payment.is_deposit == False).scalar() or 0  # noqa: E712
    _deposits = _counted.filter(Payment.is_deposit == True)  # noqa: E712
    deposit_returned = _deposits.filter(
        Payment.deposit_transaction_type == "deposit_returned").scalar() or 0
    deposit_revenue = _deposits.filter(db.func.coalesce(
        Payment.deposit_transaction_type, "") != "deposit_returned").scalar() or 0
    total_revenue = rent_revenue + deposit_revenue - deposit_returned
    total_deposits = (
        db.session.query(db.func.sum(Reservation.deposit_amount))
        .filter(Reservation.status == ReservationStatus.APPROVED)
        .filter(Reservation.deposit_status == "held")
        .scalar()
        or 0
    )

    # Status counts for charts
    res_pending = db.session.query(Reservation).filter(Reservation.status == ReservationStatus.PENDING).count()
    res_approved = db.session.query(Reservation).filter(Reservation.status == ReservationStatus.APPROVED).count()
    res_rejected = db.session.query(Reservation).filter(Reservation.status == ReservationStatus.REJECTED).count()
    res_cancelled = db.session.query(Reservation).filter(Reservation.status == ReservationStatus.CANCELLED).count()

    recent_reservations = (
        db.session.query(Reservation)
        .order_by(Reservation.created_at.desc())
        .limit(10)
        .all()
    )

    # Find tenants with contracts expiring in 7 days or less
    today = date.today()
    threshold = today + timedelta(days=7)
    expiring_soon = db.session.query(TenantProfile).filter(
        TenantProfile.contract_end.isnot(None),
        TenantProfile.contract_end <= threshold,
        TenantProfile.contract_end > today,
        TenantProfile.is_active == True
    ).order_by(TenantProfile.contract_end.asc()).all()

    # Revenue Trend (Last 6 Months INCLUDING current month)
    from sqlalchemy import extract, func
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    
    # Start from 5 months ago and iterate forward to current month = 6 months total
    start_month = (today.replace(day=1) - relativedelta(months=5))
    revenue_trend = []
    for i in range(6):
        month_date = start_month + relativedelta(months=i)
        month_revenue = db.session.query(func.sum(payment_revenue_amount())).filter(
            Payment.payment_status.notin_(PAYMENT_STATUSES_NOT_COUNTED),
            extract('year', Payment.paid_at) == month_date.year,
            extract('month', Payment.paid_at) == month_date.month
        ).scalar() or 0
        # Include year suffix if range spans years
        label = month_date.strftime('%b')
        if month_date.year != today.year:
            label = month_date.strftime('%b %y')
        revenue_trend.append({
            'month': label,
            'revenue': float(month_revenue)
        })

    # NEW: This Month's Summary
    current_month_start = today.replace(day=1)
    this_month_revenue = db.session.query(func.sum(payment_revenue_amount())).filter(
        Payment.payment_status.notin_(PAYMENT_STATUSES_NOT_COUNTED),
        Payment.paid_at >= current_month_start
    ).scalar() or 0
    
    last_month_start = (current_month_start - relativedelta(months=1))
    last_month_end = current_month_start - timedelta(days=1)
    last_month_revenue = db.session.query(func.sum(payment_revenue_amount())).filter(
        Payment.payment_status.notin_(PAYMENT_STATUSES_NOT_COUNTED),
        Payment.paid_at >= last_month_start,
        Payment.paid_at <= last_month_end
    ).scalar() or 0
    
    new_tenants_this_month = db.session.query(TenantProfile).filter(
        TenantProfile.created_at >= current_month_start
    ).count()
    
    payments_this_month = db.session.query(Payment).filter(
        Payment.paid_at >= current_month_start
    ).count()

    # NEW: Recent Activities (Last 5 of each)
    recent_payments = db.session.query(Payment).order_by(Payment.paid_at.desc()).limit(5).all()
    recent_concerns = db.session.query(Concern).filter(
        Concern.status != ConcernStatus.RESOLVED
    ).order_by(Concern.created_at.desc()).limit(5).all()
    recent_feedbacks = db.session.query(Feedback).order_by(Feedback.created_at.desc()).limit(5).all()
    recent_smart_notifications = (
        db.session.query(NotificationHistory)
        .order_by(NotificationHistory.sent_at.desc())
        .limit(8)
        .all()
    )

    # NEW: Pending Actions Summary
    pending_concerns = db.session.query(Concern).filter(
        Concern.status != ConcernStatus.RESOLVED
    ).count()
    pending_renewals = db.session.query(RenewalRequest).filter(
        RenewalRequest.status == RenewalRequestStatus.PENDING
    ).count()
    pending_feedbacks = db.session.query(Feedback).filter(
        Feedback.status == FeedbackStatus.SUBMITTED
    ).count()
    
    # NEW: Pending Inquiries
    from ...models import Inquiry, InquiryStatus
    pending_inquiries = db.session.query(Inquiry).filter(
        Inquiry.status == InquiryStatus.PENDING
    ).count()

    # NEW: Tenant Satisfaction Score
    avg_rating = db.session.query(func.avg(Feedback.rating)).filter(
        Feedback.rating.isnot(None)
    ).scalar()
    avg_rating = round(float(avg_rating), 1) if avg_rating else 0

    # NEW: Building Occupancy Analytics
    building_occupancy = []
    all_buildings_for_chart = db.session.query(Building).order_by(Building.code.asc()).all()
    for b in all_buildings_for_chart:
        b_total = db.session.query(Unit).filter(Unit.building_id == b.id, Unit.is_archived == False).count()
        b_occupied = db.session.query(Unit).filter(
            Unit.building_id == b.id,
            Unit.is_archived == False,
            Unit.status == UnitStatus.OCCUPIED
        ).count()
        rate = round((b_occupied / b_total * 100), 1) if b_total > 0 else 0
        building_occupancy.append({
            'code': b.code,
            'name': b.name,
            'total': b_total,
            'occupied': b_occupied,
            'rate': rate
        })

    # NEW: Concerns analytics
    total_concerns_count = db.session.query(Concern).count()
    resolved_concerns = db.session.query(Concern).filter(Concern.status == ConcernStatus.RESOLVED).count()
    resolution_rate = round((resolved_concerns / total_concerns_count * 100), 1) if total_concerns_count > 0 else 0

    # NEW: Payment Risk Analytics (predictive analytics on tenant payment behavior)
    risk_analyzed_tenants = (
        db.session.query(TenantProfile)
        .filter(TenantProfile.prediction_score.isnot(None))
        .all()
    )
    risk_counts = {"low": 0, "medium": 0, "high": 0}
    for t in risk_analyzed_tenants:
        level = t.payment_risk_level.value if t.payment_risk_level else "low"
        risk_counts[level] = risk_counts.get(level, 0) + 1
    risk_analyzed_count = len(risk_analyzed_tenants)
    risk_high_pct = round((risk_counts["high"] / risk_analyzed_count * 100), 1) if risk_analyzed_count > 0 else 0

    top_risk_tenants = (
        db.session.query(TenantProfile)
        .filter(TenantProfile.payment_risk_level == PaymentRiskLevel.HIGH)
        .filter(TenantProfile.prediction_score.isnot(None))
        .order_by(TenantProfile.prediction_score.desc())
        .limit(5)
        .all()
    )

    # Overall occupancy rate
    occupancy_rate = round((occupied / total_units * 100), 1) if total_units > 0 else 0

    # Revenue growth %
    revenue_growth_pct = 0
    if last_month_revenue > 0:
        revenue_growth_pct = round(((float(this_month_revenue) - float(last_month_revenue)) / float(last_month_revenue)) * 100, 1)

    cards = {
        "total_units": total_units,
        "available": available,
        "occupied": occupied,
        "reserved": reserved,
        "unpaid": unpaid,
        "pending_reservations": pending_res,
        "total_tenants": total_tenants,
        "total_payments": total_payments,
        "total_revenue": total_revenue,
        "rent_revenue": rent_revenue,
        "deposit_revenue": deposit_revenue,
        "deposit_returned": deposit_returned,
        "total_deposits": total_deposits,
        "res_pending": res_pending,
        "res_approved": res_approved,
        "res_rejected": res_rejected,
        "res_cancelled": res_cancelled,
    }

    # Forward-looking figures. Everything else on this page reports what has
    # already happened; these say what is about to, so the dashboard can be
    # planned from rather than only read.
    from ...forecasting import (contract_expiry_outlook, collection_outlook,
                                occupancy_outlook)

    return render_template(
        "admin/dashboard.html",
        expiry_outlook=contract_expiry_outlook(3),
        collection=collection_outlook(),
        occupancy_outlook=occupancy_outlook(),
        cards=cards,
        recent_reservations=recent_reservations,
        blockchain_status=blockchain_status,
        alarm_dismissed=alarm_dismissed,
        expiring_soon=expiring_soon,
        revenue_trend=revenue_trend,
        this_month_revenue=this_month_revenue,
        last_month_revenue=last_month_revenue,
        new_tenants_this_month=new_tenants_this_month,
        payments_this_month=payments_this_month,
        building_occupancy=building_occupancy,
        resolution_rate=resolution_rate,
        occupancy_rate=occupancy_rate,
        revenue_growth_pct=revenue_growth_pct,
        recent_payments=recent_payments,
        recent_concerns=recent_concerns,
        recent_feedbacks=recent_feedbacks,
        recent_smart_notifications=recent_smart_notifications,
        pending_concerns=pending_concerns,
        pending_renewals=pending_renewals,
        pending_feedbacks=pending_feedbacks,
        pending_inquiries=pending_inquiries,
        avg_rating=avg_rating,
        today=today,
        risk_counts=risk_counts,
        risk_analyzed_count=risk_analyzed_count,
        risk_high_pct=risk_high_pct,
        top_risk_tenants=top_risk_tenants,
    )


@bp.get("/calendar")
@login_required
def calendar_view():
    """Month-view calendar: PH holidays + tenant contract expiry/renewal dates."""
    _ensure_admin()
    import calendar as cal_module

    today = date.today()
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
        if month < 1 or month > 12:
            raise ValueError
    except ValueError:
        year, month = today.year, today.month

    cal = cal_module.Calendar(firstweekday=6)  # Sunday-first week, matches PH convention
    month_weeks = cal.monthdatescalendar(year, month)
    first_visible, last_visible = month_weeks[0][0], month_weeks[-1][-1]

    holidays = dict(holidays_by_date(year))
    if first_visible.year != year:
        holidays.update(holidays_by_date(first_visible.year))
    if last_visible.year != year:
        holidays.update(holidays_by_date(last_visible.year))

    expiry_by_date: dict = {}
    for t in (
        db.session.query(TenantProfile)
        .filter(
            TenantProfile.contract_end.isnot(None),
            TenantProfile.contract_end >= first_visible,
            TenantProfile.contract_end <= last_visible,
        )
        .all()
    ):
        expiry_by_date.setdefault(t.contract_end, []).append(t)

    renewal_by_date: dict = {}
    for r in (
        db.session.query(RenewalRequest)
        .filter(
            RenewalRequest.requested_end_date >= first_visible,
            RenewalRequest.requested_end_date <= last_visible,
        )
        .all()
    ):
        renewal_by_date.setdefault(r.requested_end_date, []).append(r)

    prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
    next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)

    return render_template(
        "admin/calendar.html",
        year=year,
        month=month,
        month_name=cal_module.month_name[month],
        today=today,
        month_weeks=month_weeks,
        holidays=holidays,
        expiry_by_date=expiry_by_date,
        renewal_by_date=renewal_by_date,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
    )


@bp.post("/renewal-reminders/send")
@login_required
def send_renewal_reminders():
    """Manually trigger the same daily renewal/payment reminder check on demand."""
    _ensure_admin()

    from ...jobs import send_renewal_and_payment_reminders
    counts = send_renewal_and_payment_reminders(current_app._get_current_object())
    total = counts["renewal_reminders"] + counts["payment_reminders"]

    if total:
        flash(
            f"Sent {counts['renewal_reminders']} renewal reminder(s) and "
            f"{counts['payment_reminders']} payment reminder(s).",
            "success",
        )
    else:
        flash("No reminders needed right now — everyone's up to date.", "info")

    return redirect(url_for("admin.dashboard"))


@bp.post("/tenants/<int:tenant_profile_id>/notify-renewal")
@login_required
def notify_tenant_renewal(tenant_profile_id: int):
    """Send a renewal reminder to exactly this one tenant (Tenant Monitoring 'Notify' button)."""
    _ensure_admin()
    profile = db.session.get(TenantProfile, tenant_profile_id)
    if not profile:
        abort(404)

    from ...jobs import send_renewal_reminder_now
    sent = send_renewal_reminder_now(current_app._get_current_object(), tenant_profile_id)

    tenant_name = profile.user.full_name if profile.user else "this tenant"
    if sent:
        flash(f"Renewal reminder sent to {tenant_name}.", "success")
    else:
        flash(f"No reminder sent — {tenant_name} was already notified today, or has no contract end date.", "info")

    return redirect(url_for("admin.tenant_monitoring"))


@bp.post("/blockchain-alarm/dismiss")
@login_required
def dismiss_blockchain_alarm():
    """Dismiss blockchain alarm - stops the sound"""
    _ensure_admin()
    
    # Check if already dismissed
    existing = db.session.query(BlockchainAlarmDismissal).filter(
        BlockchainAlarmDismissal.user_id == current_user.id  # type: ignore[attr-defined]
    ).first()
    
    if not existing:
        dismissal = BlockchainAlarmDismissal(
            user_id=current_user.id  # type: ignore[attr-defined]
        )
        db.session.add(dismissal)
        db.session.commit()
    
    return {"success": True, "message": "Alarm dismissed"}


@bp.post("/blockchain-alarm/reset")
@login_required
def reset_blockchain_alarm():
    """Reset blockchain alarm - allows it to play again"""
    _ensure_admin()
    
    # Delete dismissal record
    db.session.query(BlockchainAlarmDismissal).filter(
        BlockchainAlarmDismissal.user_id == current_user.id  # type: ignore[attr-defined]
    ).delete()
    db.session.commit()
    
    return {"success": True, "message": "Alarm reset"}
    
    expiring_tenants = db.session.query(TenantProfile).filter(
        TenantProfile.contract_end.isnot(None),
        TenantProfile.contract_end <= threshold,
        TenantProfile.contract_end > today,
        TenantProfile.is_active == True
    ).all()

    reminders_sent = 0
    for profile in expiring_tenants:
        days_remaining = (profile.contract_end - today).days
        unit = db.session.get(Unit, profile.unit_id)
        
        if unit and profile.user:
            _send_renewal_reminder_email(
                tenant_name=profile.user.full_name,
                tenant_email=profile.user.email,
                unit_code=unit.unit_code,
                contract_end=profile.contract_end,
                days_remaining=days_remaining
            )
            profile.last_renewal_reminder_sent = today
            reminders_sent += 1
    
    db.session.commit()
    flash(f"Renewal reminders sent to {reminders_sent} tenant(s).", "success")
    return redirect(url_for("admin.dashboard"))


@bp.get("/tenants/monitoring")
@login_required
def tenant_monitoring():
    _ensure_admin()
    from datetime import date, timedelta
    from sqlalchemy import func
    from ...ai_utils import churn_score
    
    search_query = request.args.get('search', '').strip()
    building_filter = request.args.get('building', '')
    urgent_filter = request.args.get('urgent') == '1'
    type_filter = request.args.get('type', '').strip()

    # Base query
    query = (
        db.session.query(TenantProfile)
        .join(User, TenantProfile.user_id == User.id)
        .join(Unit, TenantProfile.unit_id == Unit.id)
        # The rows are already joined for filtering, but the ORM would still
        # re-fetch .user and .unit one row at a time when the template reads
        # them. contains_eager reuses what the join already selected.
        .options(contains_eager(TenantProfile.user),
                 contains_eager(TenantProfile.unit))
        .filter(TenantProfile.is_active == True)
    )

    # Apply search filter (name or unit code)
    if search_query:
        query = query.filter(
            db.or_(
                User.full_name.ilike(f"%{search_query}%"),
                Unit.unit_code.ilike(f"%{search_query}%")
            )
        )

    # Apply building filter
    if building_filter:
        query = query.filter(Unit.building_id == int(building_filter))

    # Apply residential/commercial filter
    if type_filter == 'residential':
        query = query.filter(Unit.type.ilike('%residential%'))
    elif type_filter == 'commercial':
        query = query.filter(Unit.type.ilike('%commercial%'))
        
    today = date.today()
    threshold_urgent = today + timedelta(days=7)
    
    # Apply urgent filter (expiring in 1 week)
    if urgent_filter:
        query = query.filter(
            TenantProfile.contract_end.isnot(None),
            TenantProfile.contract_end <= threshold_urgent,
            TenantProfile.contract_end >= today
        )

    # Apply floor filter
    floor_filter = request.args.get('floor', '')
    if floor_filter:
        query = query.filter(Unit.floor == int(floor_filter))

    query = query.order_by(TenantProfile.contract_end.asc())
    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=20, error_out=False)
    tenants = pagination.items

    threshold_warning = today + timedelta(days=30) # 1 month

    # Active (pending/acknowledged) move-out notices, keyed by tenant_profile_id
    active_notices = (
        db.session.query(MoveOutNotice)
        .filter(MoveOutNotice.status.in_([MoveOutNoticeStatus.PENDING, MoveOutNoticeStatus.ACKNOWLEDGED]))
        .all()
    )
    notices_by_profile = {n.tenant_profile_id: n for n in active_notices}

    # Stat cards reflect ALL active tenants, not just the current page —
    # a lightweight pass (no per-tenant renewal/payment/concern subqueries,
    # those are only needed for the detailed table rows below).
    stat_counts = {"Normal": 0, "Urgent": 0, "Near Expiry": 0, "Expired": 0}
    all_active_tenants = (
        db.session.query(TenantProfile)
        .join(Unit, TenantProfile.unit_id == Unit.id)
        .filter(TenantProfile.is_active == True)  # noqa: E712
        .all()
    )
    for t in all_active_tenants:
        is_commercial = bool(t.unit and "commercial" in (t.unit.type or "").lower())
        days_remaining = (t.contract_end - today).days if t.contract_end else None
        s = "Normal"
        if days_remaining is not None:
            if days_remaining < 0:
                s = "Expired"
            elif days_remaining <= 7:
                s = "Urgent"
            elif days_remaining <= 30:
                s = "Near Expiry"
        if not is_commercial and notices_by_profile.get(t.id):
            s = "Moving Out"
        if s in stat_counts:
            stat_counts[s] += 1
    stat_total = len(all_active_tenants)

    # "Move-Out Notices Awaiting Review" is a review queue, not part of the
    # searchable/paginated tenant list below — it must always show every
    # pending notice regardless of which page/filter is currently active,
    # so it's built from the full active_notices set, not from `tenants`.
    notice_items = []
    if active_notices:
        notice_tenant_ids = [n.tenant_profile_id for n in active_notices]
        notice_profiles = (
            db.session.query(TenantProfile)
            .join(User, TenantProfile.user_id == User.id)
            .join(Unit, TenantProfile.unit_id == Unit.id)
            .filter(TenantProfile.id.in_(notice_tenant_ids), TenantProfile.is_active == True)  # noqa: E712
            .all()
        )
        for p in notice_profiles:
            notice_items.append({"profile": p, "move_out_notice": notices_by_profile.get(p.id)})

    # The churn score needs four figures per tenant. Asked row by row that is
    # four round trips each; asked once for the whole page it is four total,
    # and the page then costs the same whether it lists five tenants or fifty.
    _page_ids = [t.id for t in tenants]
    _pending_renewals_by_profile = {
        r.tenant_profile_id: r
        for r in db.session.query(RenewalRequest)
        .filter(RenewalRequest.tenant_profile_id.in_(_page_ids or [0]),
                RenewalRequest.status == RenewalRequestStatus.PENDING)
        .all()
    }
    _late_by_profile = dict(
        db.session.query(Payment.tenant_profile_id, func.count(Payment.id))
        .filter(Payment.tenant_profile_id.in_(_page_ids or [0]),
                Payment.is_late == True)  # noqa: E712
        .group_by(Payment.tenant_profile_id).all()
    )
    _concerns_by_profile = dict(
        db.session.query(Concern.tenant_profile_id, func.count(Concern.id))
        .filter(Concern.tenant_profile_id.in_(_page_ids or [0]),
                Concern.status != ConcernStatus.RESOLVED)
        .group_by(Concern.tenant_profile_id).all()
    )
    _rating_by_profile = dict(
        db.session.query(Feedback.tenant_profile_id, func.avg(Feedback.rating))
        .filter(Feedback.tenant_profile_id.in_(_page_ids or [0]),
                Feedback.rating.isnot(None))
        .group_by(Feedback.tenant_profile_id).all()
    )

    monitoring_data = []
    for t in tenants:
        is_commercial = bool(t.unit and "commercial" in (t.unit.type or "").lower())
        days_remaining = (t.contract_end - today).days if t.contract_end else None
        
        # Calculate duration
        duration_days = None
        if t.contract_start and t.contract_end:
            duration_days = (t.contract_end - t.contract_start).days
            
        status = "Normal"
        if days_remaining is not None:
            if days_remaining < 0:
                status = "Expired"
            elif days_remaining <= 7:
                status = "Urgent"
            elif days_remaining <= 30:
                status = "Near Expiry"

        move_out_notice = notices_by_profile.get(t.id) if not is_commercial else None
        if move_out_notice:
            status = "Moving Out"


        # All four read from the page-wide lookups above. A tenant absent
        # from one simply has none of that thing — no late payments, no open
        # concerns, no ratings — which is what the defaults say.
        renewal = _pending_renewals_by_profile.get(t.id)
        late_payments = _late_by_profile.get(t.id, 0)
        open_concerns = _concerns_by_profile.get(t.id, 0)
        avg_rating = _rating_by_profile.get(t.id)
        avg_rating = round(float(avg_rating), 1) if avg_rating else None
        churn = churn_score(days_remaining, late_payments, open_concerns, avg_rating)

        monitoring_data.append({
            "profile": t,
            "is_commercial": is_commercial,
            "days_remaining": days_remaining,
            "status": status,
            "has_pending_renewal": renewal is not None,
            "move_out_notice": move_out_notice,
            "duration_days": duration_days,
            "churn": churn,
        })

    buildings = db.session.query(Building).order_by(Building.code.asc()).all()

    # How far behind each tenant is, so the row itself answers "have they
    # been paying?" without opening anything. The month-by-month detail is
    # one click away in the Payment History modal.
    _profiles = [row["profile"] for row in monitoring_data if row.get("profile")]
    _ids = [p.id for p in _profiles]
    from ...billing_utils import load_paid_months, load_latest_bills
    _paid = load_paid_months(_ids)
    _bills = load_latest_bills(_ids)
    standings = {
        p.id: payment_standing(p, paid_months=_paid.get(p.id, set()),
                               latest_bill=_bills.get(p.id))
        for p in _profiles
    }

    return render_template(
        "admin/tenant_monitoring.html",
        standings=standings,
        monitoring_data=monitoring_data,
        notice_items=notice_items,
        pagination=pagination,
        buildings=buildings,
        today=today,
        stat_total=stat_total,
        stat_counts=stat_counts,
    )


@bp.get("/tenants/<int:profile_id>/generate-contract")
@login_required
def generate_contract_form(profile_id: int):
    """Form to fill in the legal details a lease contract needs that
    aren't otherwise tracked by the system (company name, representative,
    civil status, nationality, business nature, address). Everything else
    (unit, rent, deposit, lease term) is pre-filled from existing data."""
    _ensure_admin()
    profile = db.session.get(TenantProfile, profile_id)
    if not profile:
        abort(404)
    unit = db.session.get(Unit, profile.unit_id)
    if not unit or "commercial" not in (unit.type or "").lower():
        flash("Contract generation is only available for commercial units right now.", "warning")
        return redirect(url_for("admin.tenant_monitoring"))

    reservation = (
        db.session.query(Reservation)
        .filter(
            Reservation.user_id == profile.user_id,
            Reservation.unit_id == profile.unit_id,
            Reservation.status == ReservationStatus.APPROVED,
        )
        .order_by(Reservation.created_at.desc())
        .first()
    )

    return render_template(
        "admin/generate_contract.html",
        profile=profile,
        unit=unit,
        reservation=reservation,
    )


@bp.post("/tenants/<int:profile_id>/generate-contract")
@login_required
def generate_contract_pdf(profile_id: int):
    _ensure_admin()
    from flask import make_response

    profile = db.session.get(TenantProfile, profile_id)
    if not profile:
        abort(404)
    unit = db.session.get(Unit, profile.unit_id)
    if not unit or "commercial" not in (unit.type or "").lower():
        flash("Contract generation is only available for commercial units right now.", "warning")
        return redirect(url_for("admin.tenant_monitoring"))

    if not profile.contract_start or not profile.contract_end:
        flash("This tenant's lease start/end dates aren't set — check the unit assignment before generating a contract.", "warning")
        return redirect(url_for("admin.tenant_monitoring"))

    lessee_company = (request.form.get("lessee_company") or "").strip()
    lessee_position = (request.form.get("lessee_position") or "").strip()
    if lessee_company and not lessee_position:
        flash("Please provide the representative's position when a company name is given.", "warning")
        return redirect(url_for("admin.generate_contract_form", profile_id=profile_id))

    data = {
        "lessor_name": (request.form.get("lessor_name") or "").strip(),
        "lessor_business_name": (request.form.get("lessor_business_name") or "").strip(),
        "lessor_address": (request.form.get("lessor_address") or "").strip(),
        "lessee_name": (request.form.get("lessee_name") or "").strip(),
        "lessee_company": lessee_company,
        "lessee_position": lessee_position,
        "lessee_civil_status": (request.form.get("lessee_civil_status") or "single").strip(),
        "lessee_nationality": (request.form.get("lessee_nationality") or "Filipino").strip(),
        "lessee_address": (request.form.get("lessee_address") or "").strip(),
        "lessee_business_nature": (request.form.get("lessee_business_nature") or "").strip(),
        "unit_code": unit.unit_code,
        "monthly_rental": request.form.get("monthly_rental") or unit.price_monthly,
        "security_deposit": request.form.get("security_deposit") or "0",
        "lease_start": profile.contract_start,
        "lease_end": profile.contract_end,
    }

    required = ["lessor_name", "lessor_business_name", "lessor_address", "lessee_name", "lessee_address"]
    if any(not data[f] for f in required):
        flash("Please fill in all required fields.", "warning")
        return redirect(url_for("admin.generate_contract_form", profile_id=profile_id))

    from ...contract_generator import generate_lease_contract_pdf
    buffer = generate_lease_contract_pdf(data)

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename=Lease_Contract_{unit.unit_code}.pdf"
    return response


@bp.get("/tenants/<int:profile_id>/generate-kasunduan")
@login_required
def generate_kasunduan_form(profile_id: int):
    """Form to fill in the details the residential Kasunduan sa Pagpapaupa
    needs that aren't otherwise tracked (tenant's postal address, civil
    status of the lessor). Unit, rent, deposit, and move-in date are
    pre-filled from existing data."""
    _ensure_admin()
    profile = db.session.get(TenantProfile, profile_id)
    if not profile:
        abort(404)
    unit = db.session.get(Unit, profile.unit_id)
    if not unit or "commercial" in (unit.type or "").lower():
        flash("Kasunduan sa Pagpapaupa generation is only available for residential units.", "warning")
        return redirect(url_for("admin.tenant_monitoring"))

    reservation = (
        db.session.query(Reservation)
        .filter(
            Reservation.user_id == profile.user_id,
            Reservation.unit_id == profile.unit_id,
            Reservation.status == ReservationStatus.APPROVED,
        )
        .order_by(Reservation.created_at.desc())
        .first()
    )

    return render_template(
        "admin/generate_kasunduan.html",
        profile=profile,
        unit=unit,
        reservation=reservation,
    )


@bp.post("/tenants/<int:profile_id>/generate-kasunduan")
@login_required
def generate_kasunduan_pdf_route(profile_id: int):
    _ensure_admin()
    from flask import make_response

    profile = db.session.get(TenantProfile, profile_id)
    if not profile:
        abort(404)
    unit = db.session.get(Unit, profile.unit_id)
    if not unit or "commercial" in (unit.type or "").lower():
        flash("Kasunduan sa Pagpapaupa generation is only available for residential units.", "warning")
        return redirect(url_for("admin.tenant_monitoring"))

    if not profile.contract_start:
        flash("This tenant's move-in date isn't set — check the unit assignment before generating a kasunduan.", "warning")
        return redirect(url_for("admin.tenant_monitoring"))

    data = {
        "lessor_name": (request.form.get("lessor_name") or "").strip(),
        "lessor_civil_status": (request.form.get("lessor_civil_status") or "may asawa").strip(),
        "lessor_address": (request.form.get("lessor_address") or "").strip(),
        "lessee_name": (request.form.get("lessee_name") or "").strip(),
        "lessee_address": (request.form.get("lessee_address") or "").strip(),
        "unit_identifier": (request.form.get("unit_identifier") or unit.unit_code).strip(),
        "monthly_rental": request.form.get("monthly_rental") or unit.price_monthly,
        "security_deposit": request.form.get("security_deposit") or "0",
        "monthly_rental_words": (request.form.get("monthly_rental_words") or "").strip(),
        "security_deposit_words": (request.form.get("security_deposit_words") or "").strip(),
        "move_in_date": profile.contract_start,
        # Only items actually present are printed. A quantity of zero means
        # the unit does not have that fixture, so listing it would have the
        # tenant sign for something that is not there.
        "inventory": [
            {"label": row.label, "quantity": row.quantity,
             "condition": row.condition_label}
            for row in ensure_unit_inventory(unit)
            if (row.quantity or 0) > 0
        ],
    }

    required = ["lessor_name", "lessor_address", "lessee_name", "lessee_address", "unit_identifier"]
    if any(not data[f] for f in required):
        flash("Please fill in all required fields.", "warning")
        return redirect(url_for("admin.generate_kasunduan_form", profile_id=profile_id))

    from ...contract_generator import generate_kasunduan_pdf
    buffer = generate_kasunduan_pdf(data)

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename=Kasunduan_{unit.unit_code}.pdf"
    return response


@bp.get("/floorplan")
@login_required
def floorplan():
    _ensure_admin()
    buildings = db.session.query(Building).order_by(Building.code.asc()).all()
    building_floor_limits = {building.id: _get_building_floor_limit(building.id) for building in buildings}
    building_unit_types = {building.id: _get_building_unit_type(building.id) for building in buildings}
    # Exclude archived units from floorplan
    units = [
        unit
        for unit in db.session.query(Unit).filter(Unit.is_archived == False).order_by(Unit.building_id.asc(), Unit.unit_number.asc()).all()
        if (unit.floor or 0) <= building_floor_limits.get(unit.building_id, 4)
    ]

    # Current tenant per unit, batch-fetched so the floor plan can show
    # who's staying where at a glance instead of admin clicking every tile.
    tenant_by_unit = {}
    unit_ids = [u.id for u in units]
    if unit_ids:
        for profile in (
            db.session.query(TenantProfile)
            .filter(TenantProfile.unit_id.in_(unit_ids), TenantProfile.is_active == True)  # noqa: E712
            .all()
        ):
            if profile.user:
                tenant_by_unit[profile.unit_id] = profile.user.full_name

    return render_template(
        "admin/floorplan.html",
        buildings=buildings,
        units=units,
        tenant_by_unit=tenant_by_unit,
        building_unit_types=building_unit_types,
        building_floor_limits=building_floor_limits,
    )


@bp.get("/units")
@login_required
def units():
    _ensure_admin()
    
    # Filters
    search_query = request.args.get('search', '').strip()
    building_filter = request.args.get('building', '')
    status_filter = request.args.get('status', '')
    type_filter = request.args.get('type', '')
    show_archived = request.args.get('archived') == '1'
    
    # Base query - exclude archived by default
    query = db.session.query(Unit)
    
    if show_archived:
        query = query.filter(Unit.is_archived == True)
    else:
        query = query.filter(Unit.is_archived == False)
    
    # Apply search filter
    if search_query:
        query = query.filter(
            db.or_(
                Unit.unit_code.ilike(f"%{search_query}%"),
                Unit.unit_number.ilike(f"%{search_query}%"),
                Unit.description.ilike(f"%{search_query}%")
            )
        )
    
    # Apply building filter
    if building_filter:
        query = query.filter(Unit.building_id == int(building_filter))
    
    # Apply status filter
    if status_filter:
        query = query.filter(Unit.status == UnitStatus(status_filter))
    
    # Apply type filter
    if type_filter:
        query = query.filter(Unit.type == type_filter)
    
    query = query.order_by(Unit.building_id.asc(), Unit.unit_number.asc())
    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=30, error_out=False)
    units = pagination.items
    buildings = db.session.query(Building).order_by(Building.code.asc()).all()
    
    # Statistics
    total_units = db.session.query(Unit).filter(Unit.is_archived == False).count()
    available_count = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.AVAILABLE).count()
    occupied_count = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.OCCUPIED).count()
    reserved_count = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.RESERVED).count()
    unpaid_count = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.UNPAID).count()
    archived_count = db.session.query(Unit).filter(Unit.is_archived == True).count()
    
    stats = {
        'total': total_units,
        'available': available_count,
        'occupied': occupied_count,
        'reserved': reserved_count,
        'unpaid': unpaid_count,
        'archived': archived_count
    }

    building_floor_limits = {building.id: _get_building_floor_limit(building.id) for building in buildings}
    building_unit_types = {building.id: _get_building_unit_type(building.id) for building in buildings}

    return render_template("admin/units.html", buildings=buildings, units=units, pagination=pagination, stats=stats, show_archived=show_archived, building_floor_limits=building_floor_limits, building_unit_types=building_unit_types)


@bp.post("/buildings/<int:building_id>/cover")
@login_required
def update_building_cover(building_id: int):
    """Set or clear the photograph the homepage shows on this building's card.

    Stored on the building rather than borrowed from a unit, so the card can
    show the building itself. Clearing it is not a gap: the homepage falls
    back to a photographed unit inside, the way it did before covers existed.
    """
    _ensure_admin()
    building = db.session.get(Building, building_id)
    if not building:
        abort(404)

    if request.form.get("remove") == "1":
        building.cover_image = None
        db.session.commit()
        flash(f"{building.code}'s photo removed — its card now shows a unit "
              f"photo instead.", "success")
        return redirect(request.referrer or url_for("admin.units"))

    image = request.files.get("cover")
    if not image or not image.filename:
        flash("Choose a photo first.", "warning")
        return redirect(request.referrer or url_for("admin.units"))

    from pathlib import Path
    from werkzeug.utils import secure_filename
    from ... import supabase_storage
    filename = secure_filename(f"{building.code}_{image.filename}")
    if supabase_storage.is_enabled():
        # Persistent storage — the host's own disk is wiped on every deploy.
        building.cover_image = supabase_storage.upload_file_storage(
            image, f"buildings/{filename}")
    else:
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        Path(upload_folder).mkdir(parents=True, exist_ok=True)
        image.save(str(Path(upload_folder) / filename))
        building.cover_image = f"uploads/{filename}"

    db.session.commit()
    flash(f"{building.code}'s homepage photo updated.", "success")
    return redirect(request.referrer or url_for("admin.units"))


@bp.post("/units/create")
@login_required
def create_unit():
    _ensure_admin()
    from werkzeug.utils import secure_filename
    from pathlib import Path
    import os
    import json

    building_id = int(request.form.get("building_id") or "0")
    unit_number = (request.form.get("unit_number") or "").strip()
    unit_code = (request.form.get("unit_code") or "").strip()
    price_monthly = request.form.get("price_monthly") or "0"
    floor = request.form.get("floor")
    unit_type = (request.form.get("type") or "").strip()
    status = (request.form.get("status") or "available").strip()
    description = (request.form.get("description") or "").strip()
    pax_range = (request.form.get("pax_range") or "").strip()
    if pax_range not in ("1-2", "3-4", "5-6"):
        pax_range = None

    if not building_id or not unit_number or not unit_code or not price_monthly:
        flash("Please fill all required fields.", "warning")
        return redirect(url_for("admin.units"))

    if db.session.query(Unit).filter(Unit.unit_code == unit_code).first():
        flash(f"Unit code '{unit_code}' is already in use. Please choose a different code.", "warning")
        return redirect(url_for("admin.units"))

    if db.session.query(Unit).filter(
        Unit.building_id == building_id, Unit.unit_number == unit_number
    ).first():
        flash(f"Unit number '{unit_number}' already exists in this building. Please choose a different number.", "warning")
        return redirect(url_for("admin.units"))

    # float() accepts more than the field is meant to hold: "1e999" becomes
    # inf and "1e40" a number far past NUMERIC(12,2), and both sailed through
    # the old try/except to fail at the database as a 500. A negative price
    # passed too. Check the value is a real, sane amount of money.
    price_monthly, price_error = _parse_money(price_monthly, "price")
    if price_error:
        flash(price_error, "warning")
        return redirect(url_for("admin.units"))

    floor = int(floor) if floor else None

    # Validate floor number
    if floor is not None:
        if floor < 1:
            flash("Floor number must be at least 1.", "warning")
            return redirect(url_for("admin.units"))
        max_floor = _get_building_floor_limit(building_id)
        if floor > max_floor:
            flash(f"Floor number cannot exceed {max_floor} for this building.", "warning")
            return redirect(url_for("admin.units"))

    # Buildings 1-4 are residential-only, Building 5 is commercial-only.
    forced_type = _get_building_unit_type(building_id)
    if forced_type:
        unit_type = forced_type

    # Handle image uploads (maximum 4 images)
    image_files = request.files.getlist("images")
    for _img in image_files:
        if _img and _img.filename:
            _ok, _why = validate_upload(_img, IMAGE_TYPES, label="unit photo")
            if not _ok:
                flash(_why, "warning")
                return redirect(request.referrer or url_for("admin.units"))
    image_urls = []
    if image_files:
        # Limit to 4 images
        if len(image_files) > 4:
            flash("Maximum 4 images allowed. Only the first 4 images will be uploaded.", "warning")
            image_files = image_files[:4]
        
        from ... import supabase_storage

        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        Path(upload_folder).mkdir(parents=True, exist_ok=True)

        for image_file in image_files:
            if image_file and image_file.filename:
                filename = secure_filename(f"{unit_code}_{image_file.filename}")
                if supabase_storage.is_enabled():
                    # Persistent storage (survives Render redeploys)
                    url = supabase_storage.upload_file_storage(
                        image_file, f"units/{filename}"
                    )
                    image_urls.append(url)
                else:
                    file_path = Path(upload_folder) / filename
                    image_file.save(str(file_path))
                    image_urls.append(f"uploads/{filename}")

    unit = Unit(
        building_id=building_id,
        unit_number=unit_number,
        unit_code=unit_code,
        price_monthly=price_monthly,
        floor=floor,
        type=unit_type or None,
        status=UnitStatus(status),
        description=description or None,
        pax_range=pax_range,
        unit_images_json=json.dumps(image_urls) if image_urls else None
    )
    db.session.add(unit)
    db.session.commit()
    flash("Unit added successfully.", "success")
    return redirect(url_for("admin.units"))


@bp.get("/units/<int:unit_id>/edit")
@login_required
def edit_unit(unit_id: int):
    _ensure_admin()
    unit = db.session.get(Unit, unit_id)
    if not unit:
        abort(404)

    buildings = db.session.query(Building).order_by(Building.code.asc()).all()
    # Exclude archived units
    query = db.session.query(Unit).filter(Unit.is_archived == False).order_by(Unit.building_id.asc(), Unit.unit_number.asc())
    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=30, error_out=False)
    units = pagination.items

    # Statistics (same as units route)
    total_units = db.session.query(Unit).filter(Unit.is_archived == False).count()
    available_count = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.AVAILABLE).count()
    occupied_count = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.OCCUPIED).count()
    reserved_count = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.RESERVED).count()
    unpaid_count = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.UNPAID).count()
    archived_count = db.session.query(Unit).filter(Unit.is_archived == True).count()

    stats = {
        'total': total_units,
        'available': available_count,
        'occupied': occupied_count,
        'reserved': reserved_count,
        'unpaid': unpaid_count,
        'archived': archived_count
    }

    building_floor_limits = {building.id: _get_building_floor_limit(building.id) for building in buildings}
    building_unit_types = {building.id: _get_building_unit_type(building.id) for building in buildings}

    return render_template("admin/units.html", buildings=buildings, units=units, pagination=pagination, stats=stats, edit_unit=unit, show_archived=False, building_floor_limits=building_floor_limits, building_unit_types=building_unit_types)


@bp.post("/units/<int:unit_id>/update")
@login_required
def update_unit(unit_id: int):
    _ensure_admin()
    from werkzeug.utils import secure_filename
    from pathlib import Path
    import os
    import json

    unit = db.session.get(Unit, unit_id)
    if not unit:
        abort(404)

    building_id = int(request.form.get("building_id") or "0")
    unit_number = (request.form.get("unit_number") or "").strip()
    unit_code = (request.form.get("unit_code") or "").strip()
    price_monthly = request.form.get("price_monthly") or "0"
    floor = request.form.get("floor")
    unit_type = (request.form.get("type") or "").strip()
    status = (request.form.get("status") or "available").strip()
    description = (request.form.get("description") or "").strip()
    pax_range = (request.form.get("pax_range") or "").strip()
    if pax_range not in ("1-2", "3-4", "5-6"):
        pax_range = None

    if not building_id or not unit_number or not unit_code or not price_monthly:
        flash("Please fill all required fields.", "warning")
        return redirect(url_for("admin.edit_unit", unit_id=unit_id))

    if db.session.query(Unit).filter(Unit.unit_code == unit_code, Unit.id != unit_id).first():
        flash(f"Unit code '{unit_code}' is already in use. Please choose a different code.", "warning")
        return redirect(url_for("admin.edit_unit", unit_id=unit_id))

    if db.session.query(Unit).filter(
        Unit.building_id == building_id, Unit.unit_number == unit_number, Unit.id != unit_id
    ).first():
        flash(f"Unit number '{unit_number}' already exists in this building. Please choose a different number.", "warning")
        return redirect(url_for("admin.edit_unit", unit_id=unit_id))

    price_monthly, price_error = _parse_money(price_monthly, "price")
    if price_error:
        flash(price_error, "warning")
        return redirect(url_for("admin.edit_unit", unit_id=unit_id))

    floor = int(floor) if floor else None

    # Validate floor number
    if floor is not None:
        if floor < 1:
            flash("Floor number must be at least 1.", "warning")
            return redirect(url_for("admin.edit_unit", unit_id=unit_id))
        max_floor = _get_building_floor_limit(building_id)
        if floor > max_floor:
            flash(f"Floor number cannot exceed {max_floor} for this building.", "warning")
            return redirect(url_for("admin.edit_unit", unit_id=unit_id))

    # Buildings 1-4 are residential-only, Building 5 is commercial-only.
    forced_type = _get_building_unit_type(building_id)
    if forced_type:
        unit_type = forced_type

    # Handle image uploads (maximum 4 images)
    image_files = request.files.getlist("images")
    for _img in image_files:
        if _img and _img.filename:
            _ok, _why = validate_upload(_img, IMAGE_TYPES, label="unit photo")
            if not _ok:
                flash(_why, "warning")
                return redirect(request.referrer or url_for("admin.units"))
    # Photos the administrator ticked off in the form. Dropped from the unit's
    # list before anything new is added, so replacing a photo is one save:
    # remove the old, pick the new. Until this existed a unit already holding
    # four photos silently ignored every upload, with no way to free a slot.
    #
    # Only the reference is dropped, never the stored file: a unit copied with
    # "duplicate" shares the same image paths, and deleting the file would
    # empty the copy too.
    removed_images = {u for u in request.form.getlist("remove_images") if u}
    image_urls = json.loads(unit.unit_images_json) if unit.unit_images_json else []
    if removed_images:
        kept = [u for u in image_urls if u not in removed_images]
        if len(kept) != len(image_urls):
            image_urls = kept
            unit.unit_images_json = json.dumps(image_urls) if image_urls else None

    if image_files:
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        Path(upload_folder).mkdir(parents=True, exist_ok=True)

        # Calculate remaining slots
        remaining_slots = 4 - len(image_urls)

        if remaining_slots <= 0:
            flash("This unit already holds 4 photos. Remove one with its \u00d7 first, then upload.", "warning")
            image_files = []
        elif len(image_files) > remaining_slots:
            flash(f"Maximum 4 images total. You have {len(image_urls)} existing images. Only {remaining_slots} new image(s) will be added.", "warning")
            image_files = image_files[:remaining_slots]

        from ... import supabase_storage

        for image_file in image_files:
            if image_file and image_file.filename:
                filename = secure_filename(f"{unit_code}_{image_file.filename}")
                if supabase_storage.is_enabled():
                    url = supabase_storage.upload_file_storage(
                        image_file, f"units/{filename}"
                    )
                    image_urls.append(url)
                else:
                    file_path = Path(upload_folder) / filename
                    image_file.save(str(file_path))
                    image_urls.append(f"uploads/{filename}")

                # Stop if we reach 4 images
                if len(image_urls) >= 4:
                    break

        unit.unit_images_json = json.dumps(image_urls) if image_urls else None

    unit.building_id = building_id
    unit.unit_number = unit_number
    unit.unit_code = unit_code
    unit.price_monthly = price_monthly
    unit.floor = floor
    unit.type = unit_type or None
    # A pending reservation is a live claim on this unit. Moving the status off
    # "reserved" while one stands puts the unit back on the homepage as free
    # while somebody is still waiting on it, and a second person can reserve
    # the same room. The reservation has to be settled first — approve it, or
    # reject it — and either of those sets the unit's status itself.
    if status != UnitStatus.RESERVED.value:
        held = (db.session.query(Reservation)
                .filter(Reservation.unit_id == unit.id,
                        Reservation.status == ReservationStatus.PENDING)
                .order_by(Reservation.created_at.asc())
                .first())
        if held:
            flash(
                f"{unit.unit_code} is being held for {held.full_name}, whose reservation is "
                f"still pending. Approve or reject it under Reservations first — the status "
                f"follows from that. Everything else you changed has been saved.",
                "warning",
            )
            status = UnitStatus.RESERVED.value

    unit.status = UnitStatus(status)
    unit.description = description or None
    unit.pax_range = pax_range

    db.session.commit()

    from ...socket_events import emit_unit_status_update
    emit_unit_status_update()

    flash("Unit updated successfully.", "success")
    return redirect(url_for("admin.units"))


@bp.post("/units/<int:unit_id>/delete")
@login_required
def delete_unit(unit_id: int):
    """Archive unit instead of deleting (soft delete)"""
    _ensure_admin()
    unit = db.session.get(Unit, unit_id)
    if not unit:
        abort(404)

    # Soft delete - archive the unit
    unit.is_archived = True
    unit.archived_at = datetime.utcnow()
    unit.archived_by = current_user.id
    
    db.session.commit()
    flash("Unit archived successfully.", "success")
    return redirect(url_for("admin.units"))


@bp.post("/units/<int:unit_id>/purge")
@login_required
def purge_unit(unit_id: int):
    """Delete an archived unit for good.

    Archiving is the normal way to retire a unit and it is reversible, but a
    unit created by mistake — a duplicate, a test row — stayed in the archive
    with no way to be rid of it. This removes it outright, and only when
    nothing points at it: a unit with a tenancy, a reservation, an inventory
    or a rating behind it is history the property may need, and deleting it
    would leave those records pointing at a row that no longer exists.
    """
    _ensure_admin()
    unit = db.session.get(Unit, unit_id)
    if not unit:
        abort(404)

    if not unit.is_archived:
        flash("Archive the unit first — permanent deletion only applies to archived units.", "warning")
        return redirect(url_for("admin.units"))

    blockers = []
    tenancies = db.session.query(TenantProfile).filter_by(unit_id=unit.id).count()
    if tenancies:
        blockers.append(f"{tenancies} tenancy record{'s' if tenancies != 1 else ''}")
    # Only a live claim blocks. A reservation that was cancelled or rejected is
    # a closed application against a unit that is itself about to disappear —
    # counting those meant a unit anyone had ever applied for could never be
    # deleted, the same trap the inventory count set.
    live = (db.session.query(Reservation)
            .filter(Reservation.unit_id == unit.id,
                    Reservation.status.in_([ReservationStatus.PENDING, ReservationStatus.APPROVED]))
            .count())
    if live:
        blockers.append(f"{live} open reservation{'s' if live != 1 else ''}")
    ratings = db.session.query(Feedback).filter_by(unit_id=unit.id).count()
    if ratings:
        blockers.append(f"{ratings} rating{'s' if ratings != 1 else ''}")

    if blockers:
        flash(
            f"{unit.unit_code} cannot be deleted: it still has " + ", ".join(blockers)
            + ". It stays archived, which keeps that history readable.",
            "warning",
        )
        return redirect(url_for("admin.units", archived="1"))

    # The inventory is the unit's own description of what is inside it — the
    # Kasunduan fixture rows — and nothing else points at it, so it goes with
    # the unit. It used to be counted as a blocker, which meant a unit could
    # never be deleted once inventoried; zeroing the quantities did not help,
    # because a quantity of zero is still a row.
    code = unit.unit_code

    # Closed applications go with the unit, and so do the identity checks made
    # for them: those hold an applicant's ID number and photograph, and once
    # both the application and the unit are gone there is nothing left for them
    # to be evidence of.
    closed = (db.session.query(Reservation)
              .filter(Reservation.unit_id == unit.id)
              .all())
    dropped = len(closed)
    if closed:
        ids = [r.id for r in closed]
        db.session.query(IdentityVerification).filter(
            IdentityVerification.reservation_id.in_(ids)
        ).delete(synchronize_session=False)
        db.session.query(Reservation).filter(
            Reservation.id.in_(ids)
        ).delete(synchronize_session=False)

    db.session.query(UnitInventoryItem).filter_by(unit_id=unit.id).delete(synchronize_session=False)
    db.session.delete(unit)
    db.session.add(ActivityLog(actor_user_id=current_user.id, action="unit_deleted"))  # type: ignore[attr-defined]
    db.session.commit()
    if dropped:
        flash(
            f"{code} deleted permanently, along with {dropped} closed "
            f"reservation{'s' if dropped != 1 else ''} made against it.",
            "success",
        )
    else:
        flash(f"{code} deleted permanently.", "success")
    return redirect(url_for("admin.units", archived="1"))


@bp.post("/units/<int:unit_id>/restore")
@login_required
def restore_unit(unit_id: int):
    """Restore archived unit"""
    _ensure_admin()
    unit = db.session.get(Unit, unit_id)
    if not unit:
        abort(404)

    unit.is_archived = False
    unit.archived_at = None
    unit.archived_by = None
    
    db.session.commit()
    flash("Unit restored successfully.", "success")
    return redirect(url_for("admin.units", archived='1'))


@bp.post("/units/<int:unit_id>/duplicate")
@login_required
def duplicate_unit(unit_id: int):
    """Duplicate an existing unit"""
    _ensure_admin()
    original = db.session.get(Unit, unit_id)
    if not original:
        abort(404)
    
    # Generate a new unit code that doesn't collide (unit_code is globally unique)
    import re
    match = re.match(r'(.+?)(\d+)$', original.unit_code)
    prefix, number = (match.group(1), int(match.group(2))) if match else (original.unit_code, 0)
    new_code = f"{prefix}{number + 1}" if match else f"{original.unit_code}_copy"
    while db.session.query(Unit).filter(Unit.unit_code == new_code).first() is not None:
        number += 1
        new_code = f"{prefix}{number + 1}" if match else f"{new_code}_copy"

    # Generate a new unit_number that doesn't collide within the same building
    # (repeated duplication used to always try "<original>_copy" and crash the
    # second time).
    base_number = f"{original.unit_number}_copy"
    new_number = base_number
    suffix = 1
    while db.session.query(Unit).filter(
        Unit.building_id == original.building_id, Unit.unit_number == new_number
    ).first() is not None:
        suffix += 1
        new_number = f"{base_number}{suffix}"

    max_floor = _get_building_floor_limit(original.building_id)
    duplicate_floor = original.floor or 1
    if duplicate_floor > max_floor:
        duplicate_floor = max_floor

    # Create duplicate
    duplicate = Unit(
        building_id=original.building_id,
        unit_number=new_number,
        unit_code=new_code,
        price_monthly=original.price_monthly,
        status=UnitStatus.AVAILABLE,  # Always set to available
        floor=duplicate_floor,
        type=original.type,
        description=original.description,
        pax_range=original.pax_range,
        unit_images_json=original.unit_images_json
    )

    db.session.add(duplicate)
    db.session.commit()
    flash(f"Unit duplicated successfully as {new_code}.", "success")
    return redirect(url_for("admin.units"))


@bp.get("/units/export")
@login_required
def export_units():
    _ensure_admin()
    import csv
    from io import StringIO
    from datetime import datetime

    # Exclude archived units from export
    units = db.session.query(Unit).filter(Unit.is_archived == False).order_by(Unit.building_id.asc(), Unit.unit_number.asc()).all()

    output = StringIO()
    writer = csv.writer(output)

    # Header with Elis branding
    writer.writerow(["THE ELIS CENTER - Commercial and Residences"])
    writer.writerow(["Units Report"])
    writer.writerow([f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"])
    writer.writerow([])  # Empty row

    # Column headers
    writer.writerow(["Unit Code", "Building", "Unit Number", "Floor", "Type", "Price", "Status", "Description", "Created At"])

    for u in units:
        writer.writerow([
            u.unit_code,
            u.building.code,
            u.unit_number,
            u.floor or "",
            u.type or "",
            u.price_monthly,
            u.status.value,
            u.description or "",
            u.created_at.strftime("%Y-%m-%d %H:%M:%S")
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=Elis_Units_Report.csv"}
    )
    return response


@bp.get("/reservations")
@login_required
def reservations():
    _ensure_admin()
    from datetime import date
    q = (request.args.get("q") or "").strip().lower()
    status = (request.args.get("status") or "").strip().lower()
    building_filter = (request.args.get("building") or "").strip()
    floor_filter = (request.args.get("floor") or "").strip()
    type_filter = (request.args.get("type") or "").strip()
    sort_by = (request.args.get("sort") or "newest").strip()

    query = db.session.query(Reservation)
    if q:
        query = query.filter(
            (Reservation.full_name.ilike(f"%{q}%")) | (Reservation.email.ilike(f"%{q}%"))
        )
    if status in {"pending", "approved", "rejected", "cancelled"}:
        query = query.filter(Reservation.status == ReservationStatus(status))
    if building_filter or floor_filter or type_filter:
        query = query.join(Unit, Reservation.unit_id == Unit.id)
        if building_filter:
            query = query.join(Building, Unit.building_id == Building.id).filter(Building.code == building_filter)
        if floor_filter:
            query = query.filter(Unit.floor == int(floor_filter))
        if type_filter == 'residential':
            query = query.filter(Unit.type.ilike('%residential%'))
        elif type_filter == 'commercial':
            query = query.filter(Unit.type.ilike('%commercial%'))

    if sort_by == "oldest":
        query = query.order_by(Reservation.created_at.asc())
    elif sort_by == "move-in":
        query = query.order_by(Reservation.move_in_date.asc())
    elif sort_by == "name":
        query = query.order_by(Reservation.full_name.asc())
    else:  # newest (default)
        query = query.order_by(Reservation.created_at.desc())

    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=25, error_out=False)
    rows = pagination.items
    today = date.today()

    # Get all buildings for filter dropdown
    buildings = db.session.query(Building).order_by(Building.code.asc()).all()

    # Stat cards reflect ALL reservations, not just the current page/filter.
    reservation_stats = {
        "total": db.session.query(Reservation).count(),
        "pending": db.session.query(Reservation).filter(Reservation.status == ReservationStatus.PENDING).count(),
        "approved": db.session.query(Reservation).filter(Reservation.status == ReservationStatus.APPROVED).count(),
        "rejected": db.session.query(Reservation).filter(Reservation.status == ReservationStatus.REJECTED).count(),
        "cancelled": db.session.query(Reservation).filter(Reservation.status == ReservationStatus.CANCELLED).count(),
    }

    return render_template(
        "admin/reservations.html", rows=rows, pagination=pagination, q=q, status=status,
        today=today, buildings=buildings, reservation_stats=reservation_stats,
    )


@bp.get("/reservations/export")
@login_required
def export_reservations():
    _ensure_admin()
    import csv
    from io import StringIO
    from datetime import datetime

    reservations = db.session.query(Reservation).order_by(Reservation.created_at.desc()).all()

    output = StringIO()
    writer = csv.writer(output)

    # Header with Elis branding
    writer.writerow(["THE ELIS CENTER - Commercial and Residences"])
    writer.writerow(["Reservation Report"])
    writer.writerow([f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"])
    writer.writerow([])  # Empty row

    # Column headers
    writer.writerow(["Created", "Name", "Email", "Contact", "Unit", "Move-in Date", "Move-out Date", "Status", "ID Type", "ID Number", "ID Upload"])

    for r in reservations:
        writer.writerow([
            r.created_at.strftime("%Y-%m-%d %H:%M"),
            r.full_name,
            r.email,
            r.contact,
            r.unit.unit_code,
            r.move_in_date.strftime("%Y-%m-%d") if r.move_in_date else "",
            r.move_out_date.strftime("%Y-%m-%d") if r.move_out_date else "",
            r.status.value,
            r.id_type or "",
            r.id_number or "",
            r.id_upload_path or ""
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=Elis_Reservations_Report.csv"}
    )
    return response


def _award_unit_to(r: Reservation) -> list:
    """Give the unit to this reservation and cancel the rival claims.

    Several people may reserve the same unit — the listing keeps accepting
    reservations precisely so that it is the first payment, not the first
    form, that decides. The moment money lands against one of them, that
    reservation takes the unit and the rest are closed with a reason on
    file, so a tenant whose reservation disappears can be told why.
    """
    unit = db.session.get(Unit, r.unit_id)
    if unit and unit.status == UnitStatus.AVAILABLE:
        unit.status = UnitStatus.RESERVED

    losers = (db.session.query(Reservation)
              .filter(Reservation.unit_id == r.unit_id,
                      Reservation.id != r.id,
                      Reservation.status == ReservationStatus.PENDING)
              .all())
    for other in losers:
        # A rival who already paid something is NOT cancelled from here —
        # two paid claims on one unit is a refund question for a person,
        # not something to settle silently in a request handler.
        if float(other.amount_paid or 0) > 0:
            continue
        other.status = ReservationStatus.CANCELLED
        other.superseded_by_id = r.id
    cancelled = [o for o in losers if float(o.amount_paid or 0) <= 0]

    # Tell them, and say why. A reservation that simply disappears reads as
    # the office losing it; "someone else paid for the unit first" is the
    # actual rule and the tenant can act on it.
    for o in cancelled:
        try:
            _send_reservation_result_email(
                o.email, status=ReservationStatus.CANCELLED,
                unit_code=(unit.unit_code if unit else "the unit"),
                to_name=o.full_name or "Tenant",
                reason=("The unit was taken by another reservation that was paid for first. "
                        "A unit at Elis goes to whoever pays first rather than whoever books "
                        "first, and no payment had been recorded against your reservation."),
            )
        except Exception:
            current_app.logger.exception("Failed to email superseded reservation %s", o.id)
    return cancelled


@bp.post("/reservations/<int:reservation_id>/payment")
@login_required
def record_reservation_payment(reservation_id: int):
    """Record money paid against a reservation, in full or in part."""
    _ensure_admin()
    r = db.session.get(Reservation, reservation_id)
    if not r:
        abort(404)
    if r.status in (ReservationStatus.REJECTED, ReservationStatus.CANCELLED):
        flash("That reservation is closed, so no payment can be recorded against it.", "warning")
        return redirect(url_for("admin.reservations"))

    try:
        amount = float(request.form.get("amount") or 0)
    except ValueError:
        amount = 0.0
    if amount <= 0:
        flash("Enter the amount received.", "warning")
        return redirect(url_for("admin.reservations"))

    state_before = r.payment_state
    if amount > state_before["balance"] + 0.005:
        flash(f"That is more than the ₱{state_before['balance']:,.2f} still outstanding "
              f"on this reservation.", "warning")
        return redirect(url_for("admin.reservations"))

    # The first payment is what takes the unit off other people, so it has to
    # be worth taking it off them for. Anything at or below one month's rent
    # would hold a unit on a token, and the rent is not even what it is
    # credited to — the deposit is filled first. Later top-ups are only
    # clearing a balance already claimed, so they are not held to this.
    first_money = float(r.amount_paid or 0) <= 0
    if first_money and not state_before["settled"]:
        floor = state_before["rent_due"]
        if amount <= floor + 0.005 and amount < state_before["total_due"] - 0.005:
            flash(f"A part payment has to be more than one month’s rent "
                  f"(₱{floor:,.2f}). The first payment is what takes this unit "
                  f"away from everyone else holding a reservation on it, so it "
                  f"cannot be a token. Either collect more, or record the full "
                  f"move-in total of ₱{state_before['total_due']:,.2f}.", "warning")
            return redirect(url_for("admin.reservations"))

    from datetime import datetime as _dt
    now = _dt.utcnow().replace(microsecond=0)

    r.amount_paid = float(r.amount_paid or 0) + amount
    if first_money:
        r.first_paid_at = now
    if r.is_settled and not r.fully_paid_at:
        r.fully_paid_at = now

    cancelled = _award_unit_to(r) if first_money else []
    db.session.commit()

    after = r.payment_state
    unit = db.session.get(Unit, r.unit_id)
    try:
        from ...email_helper import send_reservation_payment_email
        from ...deposits import is_commercial
        send_reservation_payment_email(
            to_email=r.email, to_name=r.full_name or "Tenant",
            unit_code=(unit.unit_code if unit else "your unit"),
            amount=amount,
            deposit_paid=after["deposit_paid"], deposit_due=after["deposit_due"],
            rent_paid=after["rent_paid"], rent_due=after["rent_due"],
            balance=after["balance"], settled=after["settled"],
            is_commercial=is_commercial(unit) if unit else False,
        )
    except Exception:
        current_app.logger.exception("Failed to email payment receipt for reservation %s", r.id)
    msg = (f"Recorded ₱{amount:,.2f} for {r.full_name}. "
           f"Security deposit {after['deposit_paid']:,.2f} of {after['deposit_due']:,.2f}; "
           f"first month's rent {after['rent_paid']:,.2f} of {after['rent_due']:,.2f}.")
    if after["settled"]:
        msg += " Fully settled — the reservation can now be approved."
    else:
        msg += f" ₱{after['balance']:,.2f} still to follow."
    if cancelled:
        msg += (f" {len(cancelled)} other reservation(s) on this unit were cancelled, "
                f"since this one paid first.")
    flash(msg, "success")
    return redirect(url_for("admin.reservations"))


@bp.post("/reservations/<int:reservation_id>/approve")
@login_required
def approve_reservation(reservation_id: int):
    _ensure_admin()
    r = db.session.get(Reservation, reservation_id)
    if not r:
        abort(404)
    if r.status != ReservationStatus.PENDING:
        flash("Reservation is not pending.", "warning")
        return redirect(url_for("admin.reservations"))

    user = db.session.get(User, r.user_id)
    unit = db.session.get(Unit, r.unit_id)
    if not user or not unit:
        abort(400)

    # Approving books the tenancy and settles the first month, so a
    # reservation that has only been part paid must not go through on a
    # mis-click. Record the payment first; approving on a balance is still
    # allowed, but it has to be said out loud.
    pay_now = r.payment_state
    if not pay_now["settled"] and request.form.get("confirm_partial") != "yes":
        if pay_now["paid"] <= 0:
            flash(f"No payment has been recorded for this reservation. The move-in "
                  f"total is ₱{pay_now['total_due']:,.2f} "
                  f"(security deposit ₱{pay_now['deposit_due']:,.2f} + first month's "
                  f"rent ₱{pay_now['rent_due']:,.2f}). Record what was received "
                  f"first, or use Approve with balance.", "warning")
        else:
            flash(f"This reservation is only part paid — ₱{pay_now['paid']:,.2f} "
                  f"of ₱{pay_now['total_due']:,.2f}, leaving "
                  f"₱{pay_now['balance']:,.2f} outstanding "
                  f"(₱{pay_now['deposit_balance']:,.2f} of the security deposit and "
                  f"₱{pay_now['rent_balance']:,.2f} of the first month's rent). "
                  f"Record the balance first, or use Approve with balance.", "warning")
        return redirect(url_for("admin.reservations"))

    # Use customer's move-out date directly
    contract_start = r.move_in_date or date.today()
    contract_end = r.move_out_date

    # One tenant holds one unit at Elis. Approving a second reservation for
    # someone already renting used to MOVE them — silently ending the first
    # tenancy and its billing. Refuse it and say which unit they hold; a
    # genuine transfer is a move-out on the old unit first.
    existing_profile = db.session.query(TenantProfile).filter_by(user_id=user.id).first()
    if (existing_profile and existing_profile.is_active
            and existing_profile.unit_id != unit.id):
        held = existing_profile.unit.unit_code if existing_profile.unit else "another unit"
        flash(f"{user.full_name} already rents {held}. A tenant may hold only "
              f"one unit, so process the move-out on {held} before approving "
              f"this reservation.", "warning")
        return redirect(url_for("admin.reservations"))

    if existing_profile:
        existing_profile.unit_id = unit.id
        existing_profile.contract_start = contract_start
        existing_profile.contract_end = contract_end
        existing_profile.is_active = True
        # This is a new contract on a new unit, so the rent is that unit's,
        # not whatever the tenant paid on the one they left. contract_rent
        # is read from here for arrears, reminders and the settlement, so
        # leaving the old figure would bill a returning tenant at their
        # previous unit's rate indefinitely.
        existing_profile.monthly_rent = unit.price_monthly
        existing_profile.moved_out_on = None  # they are moving in, not out
        profile = existing_profile
    else:
        profile = TenantProfile(user_id=user.id, unit_id=unit.id, contract_start=contract_start,
                            contract_end=contract_end, monthly_rent=unit.price_monthly)
        db.session.add(profile)

    user.role = Role.TENANT
    r.status = ReservationStatus.APPROVED
    unit.status = UnitStatus.OCCUPIED

    # Flush session to get profile.id if it was newly created
    db.session.flush()

    # Create separate payment entries for monthly payment and deposit
    # Set paid_at with normalized timestamp (no microseconds) for blockchain consistency
    from datetime import datetime
    paid_at_normalized = datetime.utcnow().replace(microsecond=0)
    
    # Tag the cycle this settles. Without it the payment counts as revenue
    # but settles no month, so the tenant's very first month reads as unpaid
    # from the day they move in — payment_month is what every arrears and
    # outstanding check matches on.
    from ...billing_utils import billing_month_for
    first_cycle = billing_month_for(profile, profile.contract_start)

    # Record what the tenant actually handed over, not what the unit asks
    # for. A reservation may be settled in instalments, and whatever has
    # arrived is credited to the security deposit first with the month's
    # rent left whole — see app/deposits.py. Approving on a part payment
    # must not book rent nobody paid.
    paid = r.payment_state
    if float(r.amount_paid or 0) <= 0:
        # Nothing was recorded against the reservation itself, which is how
        # every reservation approved before instalments existed looks. Treat
        # it as settled in full, exactly as it used to be.
        paid = {"deposit_paid": float(r.deposit_amount or 0),
                "rent_paid": float(profile.contract_rent or 0),
                "balance": 0.0, "settled": True}

    monthly_payment = deposit_payment = None
    if paid["rent_paid"] > 0:
        monthly_payment = Payment(
            tenant_profile_id=profile.id,
            amount=paid["rent_paid"],
            reference=f"Monthly - {unit.unit_code}",
            notes="First month payment",
            is_deposit=False,
            payment_month=first_cycle,
            paid_at=paid_at_normalized
        )
        db.session.add(monthly_payment)

    if paid["deposit_paid"] > 0:
        part = "" if paid["settled"] else " (part payment)"
        deposit_payment = Payment(
            tenant_profile_id=profile.id,
            amount=paid["deposit_paid"],
            reference=f"Security Deposit - {unit.unit_code}",
            notes=f"Reservation security deposit{part} "
                  f"(refundable after contract ends)",
            is_deposit=True,
            deposit_transaction_type="deposit_paid",
            paid_at=paid_at_normalized
        )
        db.session.add(deposit_payment)

    # Money received that clears the deposit but cannot yet cover the whole
    # of the first month. It is deliberately not tagged with a payment_month
    # — a half-settled cycle reads as a settled one to every arrears check —
    # so it is recorded as an advance and the month stays open until the
    # balance arrives.
    advance_payment = None
    if paid.get("advance", 0) > 0:
        advance_payment = Payment(
            tenant_profile_id=profile.id,
            amount=paid["advance"],
            reference=f"Advance on First Month - {unit.unit_code}",
            notes="Received towards the first month's rent; the month is "
                  "settled once the balance is paid.",
            is_deposit=False,
            paid_at=paid_at_normalized
        )
        db.session.add(advance_payment)
    db.session.flush()

    for p in (monthly_payment, deposit_payment, advance_payment):
        if p is not None:
            _generate_payment_ledger(p)

    # Somebody shopping for a place may reserve several units while they make
    # up their mind, and each reservation takes its unit off the market so two
    # people cannot claim the same one. The moment they are approved for one,
    # the rest are settled here. One email is one account is one unit at Elis
    # — User.email and TenantProfile.user_id are both unique — so the others
    # could never have been approved anyway. Left alone they stayed PENDING
    # forever and held their units at RESERVED: invisible on the homepage,
    # unrentable, with nothing on any screen saying why.
    released = []
    others = (db.session.query(Reservation)
              .filter(Reservation.user_id == user.id,
                      Reservation.id != r.id,
                      Reservation.status == ReservationStatus.PENDING)
              .all())
    for other in others:
        other.status = ReservationStatus.CANCELLED
        other_unit = db.session.get(Unit, other.unit_id)
        if not other_unit or other_unit.id == unit.id:
            continue  # a second claim on the unit they just took; it is theirs
        # Someone else may be waiting on that same unit. Only hand it back to
        # the market when this was the last claim on it, and only from
        # RESERVED — never overrule an OCCUPIED or UNPAID unit.
        still_claimed = (db.session.query(Reservation)
                         .filter(Reservation.unit_id == other_unit.id,
                                 Reservation.id != other.id,
                                 Reservation.status == ReservationStatus.PENDING)
                         .count())
        if not still_claimed and other_unit.status == UnitStatus.RESERVED:
            other_unit.status = UnitStatus.AVAILABLE
            released.append(other_unit.unit_code)

    db.session.add(ActivityLog(actor_user_id=current_user.id, action="reservation_approved"))  # type: ignore[attr-defined]
    db.session.commit()

    from ...socket_events import emit_payment_notification, emit_unit_status_update
    emit_payment_notification(user.id, {
        "amount": float(monthly_payment.amount),
        "tenant_name": user.full_name,
        "unit_code": unit.unit_code,
    })
    emit_unit_status_update()

    _send_reservation_result_email(r.email, status=ReservationStatus.APPROVED, unit_code=unit.unit_code)
    msg = "Reservation approved. User is now a Tenant. Deposit and monthly payment recorded."
    if others:
        msg += f" Their {len(others)} other pending reservation{'s' if len(others) != 1 else ''} were cancelled"
        msg += f", returning {', '.join(released)} to Available." if released else "."
    flash(msg, "success")
    return redirect(url_for("admin.reservations"))


@bp.post("/reservations/<int:reservation_id>/reject")
@login_required
def reject_reservation(reservation_id: int):
    _ensure_admin()
    r = db.session.get(Reservation, reservation_id)
    if not r:
        abort(404)
    unit = db.session.get(Unit, r.unit_id)
    if unit:
        unit.status = UnitStatus.AVAILABLE
    r.status = ReservationStatus.REJECTED
    db.session.add(ActivityLog(actor_user_id=current_user.id, action="reservation_rejected"))  # type: ignore[attr-defined]
    db.session.commit()

    from ...socket_events import emit_unit_status_update
    emit_unit_status_update()

    _send_reservation_result_email(r.email, status=ReservationStatus.REJECTED, unit_code=(unit.unit_code if unit else "your requested unit"))
    flash("Reservation rejected.", "info")
    return redirect(url_for("admin.reservations"))


@bp.post("/reservations/<int:reservation_id>/cancel")
@login_required
def cancel_reservation(reservation_id: int):
    _ensure_admin()
    r = db.session.get(Reservation, reservation_id)
    if not r:
        abort(404)
    unit = db.session.get(Unit, r.unit_id)
    if unit:
        unit.status = UnitStatus.AVAILABLE
    r.status = ReservationStatus.CANCELLED
    db.session.add(ActivityLog(actor_user_id=current_user.id, action="reservation_cancelled"))  # type: ignore[attr-defined]
    db.session.commit()

    from ...socket_events import emit_unit_status_update
    emit_unit_status_update()

    _send_reservation_result_email(r.email, status=ReservationStatus.CANCELLED, unit_code=(unit.unit_code if unit else "your requested unit"))
    flash("Reservation cancelled.", "info")
    return redirect(url_for("admin.reservations"))


@bp.get("/api/reservations/<int:reservation_id>/verification")
@login_required
def get_reservation_verification(reservation_id: int):
    """Get verification details for a reservation (for admin modal)"""
    _ensure_admin()
    from flask import jsonify
    
    r = db.session.get(Reservation, reservation_id)
    if not r:
        return jsonify({"error": "Reservation not found"}), 404
    
    # Get verification log
    verification = db.session.query(IdentityVerification).filter_by(reservation_id=reservation_id).first()
    
    result = {
        "reservation_id": r.id,
        "full_name": r.full_name,
        "email": r.email,
        "id_type": r.id_type,
        "id_number": r.id_number,
        "id_upload_path": r.id_upload_path,
        "selfie_image": r.selfie_image,
        "verification_status": r.verification_status.value if r.verification_status else "pending",
        "face_match_score": float(r.face_match_score) if r.face_match_score else None,
        "fake_id_flag": r.fake_id_flag,
        "id_authenticity_score": float(r.id_authenticity_score) if r.id_authenticity_score else None,
    }
    
    if verification:
        result["verification_log"] = {
            "id": verification.id,
            "id_type_detected": verification.id_type_detected,
            "id_number_detected": verification.id_number_detected,
            "fake_score": float(verification.fake_score) if verification.fake_score else None,
            "is_fake": verification.is_fake,
            "ela_score": float(verification.ela_score) if verification.ela_score else None,
            "noise_score": float(verification.noise_score) if verification.noise_score else None,
            "has_exif": verification.has_exif,
            "qr_detected": verification.qr_detected,
            "qr_valid": verification.qr_valid,
            "detection_reasons": json.loads(verification.detection_reasons_json) if verification.detection_reasons_json else [],
            "face_detected_in_id": verification.face_detected_in_id,
            "face_detected_in_selfie": verification.face_detected_in_selfie,
            "face_match_score": float(verification.face_match_score) if verification.face_match_score else None,
            "face_match_result": verification.face_match_result.value if verification.face_match_result else None,
            "verification_result": verification.verification_result.value if verification.verification_result else None,
            "verified_at": verification.verified_at.isoformat() if verification.verified_at else None,
            "reviewed_by": verification.reviewer.full_name if verification.reviewer else None,
            "reviewed_at": verification.reviewed_at.isoformat() if verification.reviewed_at else None,
            "review_notes": verification.review_notes,
        }
    
    return jsonify(result)


@bp.get("/api/units/<int:unit_id>/quick-info")
@login_required
def get_unit_quick_info(unit_id: int):
    """Lightweight unit + current-tenant summary for the floorplan tile-click modal."""
    _ensure_admin()
    from flask import jsonify

    unit = db.session.get(Unit, unit_id)
    if not unit:
        return jsonify({"error": "Unit not found"}), 404

    image_url = None
    if unit.unit_images_json:
        try:
            imgs = json.loads(unit.unit_images_json)
            if imgs:
                first = str(imgs[0])
                image_url = first if first.startswith(("http://", "https://", "//")) else url_for("static", filename=first.lstrip("/"))
        except (ValueError, TypeError):
            pass

    result = {
        "id": unit.id,
        "unit_code": unit.unit_code,
        "unit_number": unit.unit_number,
        "building_code": unit.building.code if unit.building else None,
        "floor": unit.floor,
        "type": unit.type,
        "price_monthly": float(unit.price_monthly) if unit.price_monthly else 0,
        "status": unit.status.value,
        "description": unit.description,
        "image_url": image_url,
        "edit_url": url_for("admin.edit_unit", unit_id=unit.id),
        "tenant": None,
    }

    profile = (
        db.session.query(TenantProfile)
        .filter(TenantProfile.unit_id == unit.id, TenantProfile.is_active == True)  # noqa: E712
        .first()
    )
    if profile and profile.user:
        import calendar
        from ...jobs import shift_month

        is_commercial = bool(unit.type and "commercial" in unit.type.lower())

        # Has this billing cycle been paid yet? Same check used on the
        # Payments page's "Outstanding This Month" list.
        paid_this_month = None
        if profile.contract_start:
            today = date.today()
            due_day = min(profile.contract_start.day, calendar.monthrange(today.year, today.month)[1])
            next_due = date(today.year, today.month, due_day)
            if next_due < today:
                next_due = shift_month(next_due, 1)
            cycle_start = datetime.combine(shift_month(next_due, -1), datetime.min.time())
            paid_this_month = (
                db.session.query(Payment)
                .filter(Payment.tenant_profile_id == profile.id)
                .filter(Payment.is_deposit == False)  # noqa: E712
                .filter(Payment.payment_status.notin_(PAYMENT_STATUSES_NOT_COUNTED))
                .filter(Payment.paid_at >= cycle_start)
                .first()
                is not None
            )

        result["tenant"] = {
            "name": profile.user.full_name,
            "email": profile.user.email,
            "move_in": profile.contract_start.strftime("%b %d, %Y") if profile.contract_start else None,
            "contract_end": profile.contract_end.strftime("%b %d, %Y") if profile.contract_end else None,
            "is_commercial": is_commercial,
            "paid_this_month": paid_this_month,
            "user_details_url": url_for("admin.user_details", user_id=profile.user.id),
        }

    return jsonify(result)


@bp.get("/payments")
@login_required
def payments():
    _ensure_admin()
    from datetime import date, datetime as dt, timedelta
    import calendar
    from ...jobs import shift_month

    today = date.today()
    today_dt = dt.combine(today, dt.min.time())  # Convert to datetime for comparison

    tenants = (db.session.query(TenantProfile)
               .options(joinedload(TenantProfile.user),
                        joinedload(TenantProfile.unit).joinedload(Unit.building))
               .order_by(TenantProfile.created_at.desc()).limit(200).all())

    # Confirmed payments only — tenant-submitted proofs awaiting review live
    # in their own "Pending Payment Proofs" section below, and rejected ones
    # aren't real recorded payments, so neither belongs in this list/stats.
    search_query = (request.args.get('search') or '').strip()
    type_filter = (request.args.get('type') or '').strip()
    method_filter = (request.args.get('method') or '').strip()
    building_filter = (request.args.get('building') or '').strip()
    floor_filter = (request.args.get('floor') or '').strip()
    sort_by = (request.args.get('sort') or 'newest').strip()

    payments_query = db.session.query(Payment).filter(Payment.payment_status.notin_(['pending', 'rejected']))

    needs_join = bool(search_query or building_filter or floor_filter or sort_by == 'tenant')
    if needs_join:
        payments_query = (
            payments_query
            .join(TenantProfile, Payment.tenant_profile_id == TenantProfile.id)
            .join(User, TenantProfile.user_id == User.id)
            .join(Unit, TenantProfile.unit_id == Unit.id)
        )
    if search_query:
        payments_query = payments_query.filter(
            db.or_(User.full_name.ilike(f"%{search_query}%"), Unit.unit_code.ilike(f"%{search_query}%"))
        )
    if building_filter:
        payments_query = payments_query.join(Building, Unit.building_id == Building.id).filter(Building.code == building_filter)
    if floor_filter:
        payments_query = payments_query.filter(Unit.floor == int(floor_filter))

    if type_filter == 'monthly':
        payments_query = payments_query.filter(Payment.is_deposit == False)  # noqa: E712
    elif type_filter == 'deposit':
        payments_query = payments_query.filter(Payment.is_deposit == True)  # noqa: E712

    if method_filter == 'cash':
        payments_query = payments_query.filter(db.or_(Payment.payment_method == 'cash', Payment.payment_method.is_(None)))
    elif method_filter:
        payments_query = payments_query.filter(Payment.payment_method == method_filter)

    if sort_by == 'oldest':
        payments_query = payments_query.order_by(Payment.paid_at.asc())
    elif sort_by == 'amount-high':
        payments_query = payments_query.order_by(Payment.amount.desc())
    elif sort_by == 'amount-low':
        payments_query = payments_query.order_by(Payment.amount.asc())
    elif sort_by == 'tenant':
        payments_query = payments_query.order_by(User.full_name.asc())
    else:  # newest (default)
        payments_query = payments_query.order_by(Payment.paid_at.desc())

    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(payments_query, page=page, per_page=25, error_out=False)
    payments = pagination.items

    # Stat cards (Total/This Month/Last Month Revenue, Tenants Paid) reflect
    # ALL confirmed payments via real SQL SUM/COUNT — they used to be
    # computed by summing just the `payments` list here, which was capped
    # at 100 (now paginated to 25), so "Total Revenue" was quietly only
    # ever the most recent 100 payments, never the true total.
    from sqlalchemy import func as _func, case as _case
    _confirmed = db.session.query(Payment).filter(Payment.payment_status.notin_(PAYMENT_STATUSES_NOT_COUNTED))
    this_month_start_dt = dt.combine(today.replace(day=1), dt.min.time())
    last_month_end_dt = this_month_start_dt
    last_month_start_dt = dt.combine((today.replace(day=1) - timedelta(days=1)).replace(day=1), dt.min.time())

    _rent_only = _confirmed.filter(Payment.is_deposit == False)  # noqa: E712
    _deposit_only = _confirmed.filter(Payment.is_deposit == True)  # noqa: E712
    # Returning a deposit records a Payment of its own, so it has to be taken
    # back out rather than added: it is money leaving, not arriving.
    _returned = Payment.deposit_transaction_type == "deposit_returned"
    _not_returned = _func.coalesce(Payment.deposit_transaction_type, "") != "deposit_returned"

    def _sum(q):
        return float(q.with_entities(_func.coalesce(_func.sum(Payment.amount), 0)).scalar() or 0)

    # Total Revenue was rent and deposits in one number, which hides how much
    # of it is actually earned. Every part is reported alongside it.
    total_rent = _sum(_rent_only)
    total_deposit = _sum(_deposit_only.filter(_not_returned))
    total_returned = _sum(_deposit_only.filter(_returned))
    total_revenue = total_rent + total_deposit - total_returned
    _net = _func.coalesce(_func.sum(payment_revenue_amount()), 0)
    this_month_revenue = _confirmed.filter(Payment.paid_at >= this_month_start_dt).with_entities(_net).scalar()
    last_month_revenue = _confirmed.filter(Payment.paid_at >= last_month_start_dt, Payment.paid_at < last_month_end_dt).with_entities(_net).scalar()
    tenants_paid_count = _confirmed.with_entities(_func.count(_func.distinct(Payment.tenant_profile_id))).scalar()

    # Revenue over a chosen period. "Total revenue" answers how much has
    # ever come in, which is not the question being asked of it — what is
    # wanted is August alone, or September through December. Dates arrive
    # as YYYY-MM-DD from the pickers; the end date is inclusive, so a range
    # of the same day covers that whole day.
    rev_from_raw = (request.args.get('rev_from') or '').strip()
    rev_to_raw = (request.args.get('rev_to') or '').strip()

    def _as_date(text):
        try:
            return dt.strptime(text, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None

    rev_from = _as_date(rev_from_raw)
    rev_to = _as_date(rev_to_raw)
    # An inverted range is a slip, not an empty result: read it the way it
    # was meant rather than reporting zero.
    if rev_from and rev_to and rev_from > rev_to:
        rev_from, rev_to = rev_to, rev_from

    period_q = _confirmed
    if rev_from:
        period_q = period_q.filter(Payment.paid_at >= dt.combine(rev_from, dt.min.time()))
    if rev_to:
        period_q = period_q.filter(Payment.paid_at < dt.combine(rev_to + timedelta(days=1), dt.min.time()))

    period_count = period_q.with_entities(_func.count(Payment.id)).scalar()
    period_rent = _sum(period_q.filter(Payment.is_deposit == False))  # noqa: E712
    _period_dep = period_q.filter(Payment.is_deposit == True)  # noqa: E712
    period_deposit = _sum(_period_dep.filter(_not_returned))
    period_returned = _sum(_period_dep.filter(_returned))
    period_revenue = period_rent + period_deposit - period_returned

    # Month-by-month inside the chosen period, so a range of several months
    # shows where the money actually came from rather than one lump sum.
    period_months = []
    if rev_from or rev_to:
        rows = (period_q
                .with_entities(_func.to_char(Payment.paid_at, 'YYYY-MM').label('m'),
                               _func.coalesce(_func.sum(Payment.amount), 0),
                               _func.count(Payment.id),
                               _func.coalesce(_func.sum(_case(
                                   (Payment.is_deposit == False, Payment.amount),  # noqa: E712
                                   else_=0)), 0),
                               _func.coalesce(_func.sum(_case(
                                   (db.and_(Payment.is_deposit == True,  # noqa: E712
                                            _not_returned), Payment.amount),
                                   else_=0)), 0),
                               _func.coalesce(_func.sum(_case(
                                   (db.and_(Payment.is_deposit == True,  # noqa: E712
                                            _returned), Payment.amount),
                                   else_=0)), 0))
                .group_by('m').order_by('m').all())
        for month, _gross, count, rent, deposit, returned in rows:
            period_months.append({
                'month': month,
                'label': dt.strptime(month, '%Y-%m').strftime('%B %Y'),
                'rent': float(rent or 0),
                'deposit': float(deposit or 0),
                'returned': float(returned or 0),
                'amount': float(rent or 0) + float(deposit or 0) - float(returned or 0),
                'count': count or 0,
            })

    payment_stats = {
        'total_revenue': float(total_revenue or 0),
        'total_rent': float(total_rent or 0),
        'total_deposit': float(total_deposit or 0),
        'total_returned': float(total_returned or 0),
        'this_month_revenue': float(this_month_revenue or 0),
        'last_month_revenue': float(last_month_revenue or 0),
        'tenants_paid': tenants_paid_count or 0,
        'period_revenue': float(period_revenue or 0),
        'period_rent': float(period_rent or 0),
        'period_deposit': float(period_deposit or 0),
        'period_returned': float(period_returned or 0),
        'period_count': period_count or 0,
        'period_months': period_months,
        'rev_from': rev_from.isoformat() if rev_from else '',
        'rev_to': rev_to.isoformat() if rev_to else '',
        'rev_from_label': rev_from.strftime('%b %d, %Y') if rev_from else '',
        'rev_to_label': rev_to.strftime('%b %d, %Y') if rev_to else '',
        'has_period': bool(rev_from or rev_to),
    }

    # One-click periods, so the common questions do not need the pickers.
    _lm_end = today.replace(day=1) - timedelta(days=1)
    payment_stats['rev_presets'] = [
        ('This month', today.replace(day=1).isoformat(), today.isoformat()),
        ('Last month', _lm_end.replace(day=1).isoformat(), _lm_end.isoformat()),
        ('This year', today.replace(month=1, day=1).isoformat(), today.isoformat()),
    ]

    buildings = db.session.query(Building).order_by(Building.code.asc()).all()

    # "Who hasn't paid this month" — cross-checks each active tenant's
    # current billing cycle against actual payment records, instead of
    # relying on admin to manually remember/track who's settled.
    unpaid_this_month = []
    for profile in db.session.query(TenantProfile).filter(TenantProfile.is_active == True).all():  # noqa: E712
        if not profile.contract_start or not profile.user or not profile.unit:
            continue

        due_day = min(profile.contract_start.day, calendar.monthrange(today.year, today.month)[1])
        next_due = date(today.year, today.month, due_day)
        if next_due < today:
            next_due = shift_month(next_due, 1)

        cycle_start = dt.combine(shift_month(next_due, -1), dt.min.time())
        already_paid = (
            db.session.query(Payment)
            .filter(Payment.tenant_profile_id == profile.id)
            .filter(Payment.is_deposit == False)  # noqa: E712
            .filter(Payment.payment_status.notin_(PAYMENT_STATUSES_NOT_COUNTED))
            .filter(Payment.paid_at >= cycle_start)
            .first()
            is not None
        )
        cycle_key = next_due.strftime('%Y-%m')
        if not already_paid and profile.dismissed_outstanding_month != cycle_key:
            unpaid_this_month.append({
                "tenant_profile_id": profile.id,
                "tenant_name": profile.user.full_name,
                "unit_code": profile.unit.unit_code,
                "due_date": next_due,
                "cycle_key": cycle_key,
                "days": (next_due - today).days,  # negative = overdue
            })

    unpaid_this_month.sort(key=lambda x: x["days"])

    blockchain_status = verify_blockchain_chain()

    # Tenant-submitted bank transfer proofs awaiting admin review.
    pending_proofs = (
        db.session.query(Payment)
        .filter(Payment.payment_status == 'pending')
        .order_by(Payment.paid_at.desc())
        .all()
    )

    # What each pending proof's month still owes on electric and water, so the
    # approval screen can offer to settle them in the same action rather than
    # sending the administrator off to Utility Billing afterwards.
    proof_utilities = {}
    for proof in pending_proofs:
        profile = proof.tenant_profile
        if not profile or not profile.unit or profile.unit.type != "residential":
            continue
        bill = _bill_for_payment(proof, profile)
        if bill is None or bill.is_paid:
            continue
        proof_utilities[proof.id] = {
            "billing_month": bill.billing_month,
            "electric": None if bill.electric_paid else bill.electric_due,
            "water": None if bill.water_paid else bill.water_due,
            "rent": float(profile.contract_rent or 0),
            "total": bill.total_outstanding,
        }

    # Rent arrears per tenant, so the Add Payment form can tell the admin
    # "this tenant has 3 unpaid months" and prefill the real total instead of
    # a single month's rate. Keyed by profile id for the template's data-*
    # attributes; see get_rent_arrears() for how a month counts as unpaid.
    from ...billing_utils import get_rent_arrears
    from ...billing_utils import load_paid_months
    _active = [t for t in tenants if t.is_active]
    _paid_months = load_paid_months([t.id for t in _active])
    rent_arrears = {t.id: get_rent_arrears(t, paid_months=_paid_months.get(t.id, set()))
                    for t in _active}

    return render_template(
        "admin/payments.html",
        rent_arrears=rent_arrears,
        tenants=tenants,
        payments=payments,
        pagination=pagination,
        payment_stats=payment_stats,
        buildings=buildings,
        today=today,
        today_dt=today_dt,
        timedelta=timedelta,
        unpaid_this_month=unpaid_this_month,
        blockchain_status=blockchain_status,
        pending_proofs=pending_proofs,
        proof_utilities=proof_utilities,
    )


@bp.post("/tenants/<int:profile_id>/dismiss-outstanding")
@login_required
def dismiss_outstanding(profile_id: int):
    """Excuse ONE tenant's current billing cycle from the "Outstanding This
    Month" list — e.g. admin already knows/agreed they'll pay late this
    cycle with no penalty. Only suppresses this specific cycle; it
    reappears automatically once the next due date rolls around."""
    _ensure_admin()
    import calendar
    from ...jobs import shift_month

    profile = db.session.get(TenantProfile, profile_id)
    if not profile or not profile.contract_start:
        abort(404)

    today = date.today()
    due_day = min(profile.contract_start.day, calendar.monthrange(today.year, today.month)[1])
    next_due = date(today.year, today.month, due_day)
    if next_due < today:
        next_due = shift_month(next_due, 1)

    profile.dismissed_outstanding_month = next_due.strftime('%Y-%m')
    db.session.commit()

    flash(f"Outstanding notice dismissed for {profile.user.full_name} for this billing cycle.", "success")
    return redirect(url_for("admin.payments"))


@bp.get("/tenants/utility-billing")
@login_required
def utility_billing():
    """One row per active RESIDENTIAL tenant for the selected billing
    month — water is prefilled from the pax_range formula, electric is
    admin-entered (no formula, varies by actual usage). Opening this page
    for a month creates that month's UtilityBill row per tenant if it
    doesn't exist yet (via get_or_create_utility_bill, which also computes
    any carry-over from an unpaid prior month)."""
    _ensure_admin()
    from ...billing_utils import get_or_create_utility_bill

    billing_month = (request.args.get('month') or '').strip() or date.today().strftime('%Y-%m')

    tenants = (
        db.session.query(TenantProfile)
        .join(Unit, TenantProfile.unit_id == Unit.id)
        .filter(TenantProfile.is_active == True, Unit.type == 'residential')  # noqa: E712
        .order_by(Unit.unit_code.asc())
        .all()
    )
    # A tenant is skipped for any month before their first billable one —
    # utilities start the month after move-in, so the month they moved in
    # has no bill and must not appear as an empty row to fill in.
    # Whether the rent for this same month has been settled. The page shows
    # rent beside the utilities, and the Outstanding column used to add it in
    # unconditionally — so a tenant who had already paid their rent still read
    # as owing it, on top of a water bill they did owe.
    from ...billing_utils import load_paid_months
    paid_months = load_paid_months([t.id for t in tenants])

    rows = []
    not_yet_billable = []
    for t in tenants:
        bill = get_or_create_utility_bill(t, billing_month)
        if bill is None:
            not_yet_billable.append(t)
        else:
            rows.append({"profile": t, "bill": bill,
                         "rent_paid": billing_month in paid_months.get(t.id, set())})
    db.session.commit()  # persist any newly-created bill rows

    return render_template("admin/utility_billing.html", rows=rows,
                           not_yet_billable=not_yet_billable,
                           billing_month=billing_month)


@bp.post("/tenants/utility-billing")
@login_required
def utility_billing_save():
    """Single form submit saves every edited row at once — inputs are
    named electric_<bill_id> / water_<bill_id> per row."""
    _ensure_admin()
    billing_month = (request.form.get('billing_month') or '').strip() or date.today().strftime('%Y-%m')

    updated_ids = set()
    for key, value in request.form.items():
        if not (key.startswith("electric_") or key.startswith("water_")):
            continue
        if value.strip() == "":
            continue
        try:
            field, bill_id_str = key.split("_", 1)
            bill_id = int(bill_id_str)
            amount = float(value)
        except ValueError:
            continue
        bill = db.session.get(UtilityBill, bill_id)
        if not bill:
            continue
        # A settled component is read-only: its input is rendered disabled,
        # so it never submits normally. Re-check server-side anyway, so a
        # replayed or hand-built POST cannot revise an amount the tenant has
        # already paid — and with it the carry-over already derived from it.
        if field == "electric" and not bill.electric_paid:
            bill.electric_amount = amount
        elif field == "water" and not bill.water_paid:
            bill.water_amount = amount
        else:
            continue
        updated_ids.add(bill_id)

    db.session.commit()
    flash(f"Saved utility bills for {len(updated_ids)} tenant(s).", "success")
    return redirect(url_for("admin.utility_billing", month=billing_month))


@bp.post("/tenants/utility-bills/<int:bill_id>/electric-bill")
@login_required
def upload_electric_bill(bill_id: int):
    """Attach the electricity bill to one month's charge.

    Units are submetered, so a tenant's electricity is a share of one
    Meralco bill and "why is mine this high" cannot be answered by the
    figure alone. The bill used to travel over Messenger, where it was
    detached from the charge and lost. Uploading it here puts the proof on
    the tenant's own Payments page, next to the amount it explains.
    """
    _ensure_admin()
    bill = db.session.get(UtilityBill, bill_id)
    if not bill:
        flash("Utility bill not found.", "error")
        return redirect(url_for("admin.utility_billing"))

    month = request.form.get("billing_month") or bill.billing_month
    note = (request.form.get("electric_note") or "").strip()
    bill.electric_note = note[:500] or None
    attached = False

    upload = request.files.get("electric_bill")
    if upload and upload.filename:
        ok, why = validate_upload(upload, DOCUMENT_TYPES, label="electricity bill")
        if not ok:
            flash(why, "warning")
            return redirect(url_for("admin.utility_billing", month=month))

        from pathlib import Path
        from werkzeug.utils import secure_filename

        from ... import supabase_storage

        safe_month = bill.billing_month.replace("-", "")
        filename = secure_filename(f"electricity_{bill.tenant_profile_id}_{safe_month}_{upload.filename}")
        if supabase_storage.is_enabled():
            stored = supabase_storage.upload_file_storage(upload, f"utility_bills/{filename}")
        else:
            upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
            Path(upload_folder).mkdir(parents=True, exist_ok=True)
            upload.save(str(Path(upload_folder) / filename))
            stored = f"uploads/{filename}"

        if not stored:
            flash("The bill could not be stored. Please try again.", "error")
            return redirect(url_for("admin.utility_billing", month=month))

        bill.electric_bill_path = stored
        bill.electric_bill_name = upload.filename[:255]
        bill.electric_bill_uploaded_at = datetime.utcnow()
        attached = True
        flash("Electricity bill attached — the tenant can now see it on their Payments page.", "success")
    elif note:
        flash("Note saved.", "success")
    else:
        flash("Choose a bill image or PDF, or write a note, before saving.", "info")
        return redirect(url_for("admin.utility_billing", month=month))

    db.session.commit()

    # Telling the tenant is the point of attaching it. The monthly reminder
    # carries the bill too, but that goes out seven days before the due
    # date — a bill attached afterwards, usually because the tenant asked
    # why the charge is high, would otherwise sit on a page they have no
    # reason to reopen.
    if request.form.get("notify") == "1":
        _notify_electric_bill(bill, attached)

    return redirect(url_for("admin.utility_billing", month=month))


def _notify_electric_bill(bill, attached: bool) -> None:
    """Email and in-app push for a newly attached electricity bill.

    Never raises: a mail provider being down must not lose the upload that
    has already been committed.
    """
    from ...email_helper import send_electric_bill_attached_email
    from ...socket_events import emit_utility_bill_notification
    from ...jobs import _absolute

    profile = bill.tenant_profile
    user = profile.user if profile else None
    if not user:
        return

    unit_code = profile.unit.unit_code if profile.unit else "N/A"
    try:
        if user.email:
            send_electric_bill_attached_email(
                user.full_name, user.email, unit_code, bill.billing_month,
                float(bill.electric_amount or 0),
                bill_url=_absolute(bill.electric_bill_url),
                note=bill.electric_note,
            )
        emit_utility_bill_notification(user.id, {
            "title": f"Electricity bill for {bill.billing_month} — Unit {unit_code}",
            "subtitle": ("The bill is on your Payments page" if attached
                         else "A note was added to your electricity charge"),
        })
        flash("The tenant was notified by email and in the app.", "success")
    except Exception as exc:  # pragma: no cover
        current_app.logger.warning("Electricity bill notice failed for bill %s: %s",
                                   bill.id, exc)
        flash("Saved, but the tenant could not be notified just now. "
              "They will still see it on their Payments page.", "warning")


@bp.post("/tenants/utility-bills/<int:bill_id>/electric-bill/remove")
@login_required
def remove_electric_bill(bill_id: int):
    """Detach a bill uploaded against the wrong month or tenant."""
    _ensure_admin()
    bill = db.session.get(UtilityBill, bill_id)
    if not bill:
        flash("Utility bill not found.", "error")
        return redirect(url_for("admin.utility_billing"))

    month = request.form.get("billing_month") or bill.billing_month
    bill.electric_bill_path = None
    bill.electric_bill_name = None
    bill.electric_bill_uploaded_at = None
    db.session.commit()
    flash("Attachment removed.", "success")
    return redirect(url_for("admin.utility_billing", month=month))


@bp.post("/tenants/utility-bills/<int:bill_id>/notify")
@login_required
def notify_utility_bill(bill_id: int):
    """Manual "Send Reminder Now" — in case the automatic 7-day reminder
    didn't fire or admin wants to nudge a tenant early."""
    _ensure_admin()
    from ...jobs import send_utility_bill_reminder_now

    sent = send_utility_bill_reminder_now(current_app._get_current_object(), bill_id)
    if sent:
        flash("Bill reminder sent.", "success")
    else:
        flash("Not sent — already reminded today, already paid, or tenant has no email on file.", "info")
    return redirect(url_for("admin.utility_billing", month=request.form.get("billing_month")))


def _settle_utility_components(bill, component: str, settled_by: int, undo: bool = False) -> int:
    """Mark a utility bill's electric, water, or both as settled.

    Earlier months whose charge this bill already carries are settled with
    it: this bill's amount INCLUDES what rolled forward from them, so
    leaving them open would count the same peso twice — once here and once
    there. Returns how many earlier months were closed along the way.

    Undo only reopens THIS bill. An earlier month may have been settled on
    its own before this one existed, and reopening it would assert
    something the administrator never said.

    Does not commit — the caller owns the transaction.
    """
    now = None if undo else datetime.utcnow()
    earlier = (db.session.query(UtilityBill)
               .filter(UtilityBill.tenant_profile_id == bill.tenant_profile_id,
                       UtilityBill.billing_month < bill.billing_month)
               .all())

    def apply(target, field):
        setattr(target, f"{field}_paid", not undo)
        setattr(target, f"{field}_paid_at", now)

    cascaded = 0
    for field in ("electric", "water"):
        if component not in (field, "both"):
            continue
        apply(bill, field)
        for prior in earlier:
            if not undo and not getattr(prior, f"{field}_paid"):
                apply(prior, field)
                prior.sync_totals()
                cascaded += 1

    bill.marked_paid_by = None if undo else settled_by
    bill.sync_totals()
    return cascaded


@bp.post("/tenants/utility-bills/<int:bill_id>/mark-paid")
@login_required
def mark_utility_bill_paid(bill_id: int):
    """Settle one component of a utility bill, or both.

    Electric and water are settled independently — a tenant may pay the
    electric and leave the water — so this takes a `component` of
    "electric", "water" or "both". Whatever is left unsettled is what
    rolls into next month's bill (see get_or_create_utility_bill).

    Intentionally decoupled from Payment/PaymentLedger (no ledger entry
    created): utilities are billed and settled outside that flow, and
    only rent goes on the chain."""
    _ensure_admin()
    bill = db.session.get(UtilityBill, bill_id)
    if not bill:
        abort(404)

    component = (request.form.get("component") or "both").strip().lower()
    if component not in ("electric", "water", "both"):
        component = "both"
    undo = request.form.get("undo") == "1"

    cascaded = _settle_utility_components(bill, component, current_user.id, undo)
    db.session.commit()

    label = {"electric": "Electric", "water": "Water", "both": "Electric and water"}[component]
    if cascaded:
        flash(f"{cascaded} earlier unpaid month(s) settled too — this bill "
              f"already carried their balance.", "info")
    if undo:
        flash(f"{label} marked as unpaid — it will carry into next month.", "info")
    elif bill.is_paid:
        flash("Utility bill fully settled.", "success")
    else:
        remaining = " and ".join(bill.unpaid_components)
        flash(f"{label} marked as paid. {remaining} still outstanding "
              f"(₱{bill.total_outstanding:,.2f}) — it will carry into next month.",
              "success")
    return redirect(request.referrer or url_for("admin.utility_billing"))


@bp.post("/tenants/utility-bills/<int:bill_id>/pause-reminders")
@login_required
def pause_utility_bill_reminders(bill_id: int):
    """Stop (or resume) the automated reminder for THIS bill only.

    Used when a tenant tells the administrator they will settle next
    month: the balance still rolls forward exactly as before, we just
    stop emailing them about it.

    The pause is deliberately scoped to this one bill and cannot outlive
    it. Next month is a separate row created by
    get_or_create_utility_bill() with reminders_paused defaulting to
    False, so the tenant is alerted again on their own as that month's
    due date approaches, carrying the unpaid balance with it. A pause
    can therefore never silently persist and leave a tenant unreminded
    indefinitely. The manual "Send Reminder Now" button also still works
    while paused — it is the administrator overriding their own pause."""
    _ensure_admin()
    bill = db.session.get(UtilityBill, bill_id)
    if not bill:
        abort(404)

    resume = request.form.get("resume") == "1"
    bill.reminders_paused = not resume
    bill.reminders_paused_at = None if resume else datetime.utcnow()
    bill.reminders_paused_by = None if resume else current_user.id
    bill.reminders_paused_note = (
        None if resume else (request.form.get("note") or "").strip()[:255] or None
    )
    db.session.commit()

    if resume:
        flash("Automatic reminders resumed for this bill.", "success")
    else:
        flash("Automatic reminders stopped for this month's bill. The unpaid "
              "balance still carries into next month, and next month's bill "
              "turns reminders back on by itself as its due date approaches.",
              "success")
    return redirect(request.referrer or url_for("admin.utility_billing"))


@bp.post("/units/<int:unit_id>/inventory/<int:item_id>/repair-ticket")
@login_required
def raise_repair_ticket(unit_id: int, item_id: int):
    """Turn a fixture recorded as damaged or missing into a repair ticket.

    Maintenance is already tracked as a concern, so this raises one rather
    than inventing a parallel queue — the difference is that it carries the
    inventory row it came from, so closing it is the cue to update the
    item's condition, and the final settlement stops charging for it once
    it is fixed.

    A concern belongs to a tenant, so a vacant unit has nobody to raise it
    against. That is reported rather than worked around: repairing a vacant
    unit is scheduling, not a tenant complaint."""
    _ensure_admin()
    item = db.session.get(UnitInventoryItem, item_id)
    if not item or item.unit_id != unit_id:
        abort(404)

    existing = (db.session.query(Concern)
                .filter(Concern.unit_inventory_item_id == item.id,
                        Concern.status != ConcernStatus.RESOLVED,
                        Concern.is_cancelled.is_(False))
                .first())
    if existing:
        flash(f"A repair ticket for {item.label} is already open.", "info")
        return redirect(url_for("admin.unit_inventory", unit_id=unit_id))

    profile = (db.session.query(TenantProfile)
               .filter(TenantProfile.unit_id == unit_id,
                       TenantProfile.is_active.is_(True))
               .first())
    if not profile:
        flash(f"{item.label} is recorded as {item.condition_label.lower()}, but "
              f"this unit has no active tenant to raise a concern against. "
              f"Schedule the repair before the next tenant moves in.", "warning")
        return redirect(url_for("admin.unit_inventory", unit_id=unit_id))

    concern = Concern(
        tenant_profile_id=profile.id,
        subject=f"Repair: {item.label}",
        description=(
            f"{item.label} (x{item.quantity}) in unit {item.unit.unit_code} is "
            f"recorded as {item.condition_label.lower()} in the unit inventory."
            + (f"\n\nNote: {item.notes}" if item.notes else "")
            + "\n\nRaised from the unit inventory by the administrator."
        ),
        category="maintenance",
        # Missing means it is not there at all; damaged still functions in
        # some form, so it waits behind anything missing.
        priority="high" if item.condition == "missing" else "medium",
        unit_inventory_item_id=item.id,
    )
    db.session.add(concern)
    db.session.commit()
    flash(f"Repair ticket raised for {item.label} — tracked under Concerns.",
          "success")
    return redirect(url_for("admin.unit_inventory", unit_id=unit_id))


@bp.get("/tenants/<int:profile_id>/settlement")
@login_required
def tenant_settlement(profile_id: int):
    """Final statement for a tenant who has moved out: unpaid rent,
    outstanding electric and water, and damaged or missing fixtures, set
    against their security deposit.

    Nothing here is applied automatically. Two outcomes are possible and
    only the administrator knows which happened — the charges come out of
    the deposit and the balance is returned, or the tenant settles them
    separately and takes the deposit back whole."""
    _ensure_admin()
    profile = db.session.get(TenantProfile, profile_id)
    if not profile:
        abort(404)
    return render_template(
        "admin/tenant_settlement.html",
        profile=profile,
        s=final_settlement(profile),
        timeline=get_payment_timeline(profile),
    )


@bp.post("/tenants/<int:profile_id>/settlement")
@login_required
def tenant_settlement_save(profile_id: int):
    """Record the move-out date, or close the settlement one of two ways."""
    _ensure_admin()
    profile = db.session.get(TenantProfile, profile_id)
    if not profile:
        abort(404)
    action = (request.form.get("action") or "").strip()

    if action == "set_move_out":
        raw = (request.form.get("moved_out_on") or "").strip()
        try:
            profile.moved_out_on = datetime.strptime(raw, "%Y-%m-%d").date() if raw else None
        except ValueError:
            flash("That move-out date could not be read.", "warning")
            return redirect(url_for("admin.tenant_settlement", profile_id=profile.id))
        db.session.commit()
        if profile.moved_out_on:
            flash(f"Move-out recorded. The deposit is held until "
                  f"{profile.deposit_releasable_on:%b %d, %Y} to allow the final "
                  f"charges to be totalled.", "success")
        else:
            flash("Move-out date cleared.", "info")
        return redirect(url_for("admin.tenant_settlement", profile_id=profile.id))

    st = final_settlement(profile)
    reservation = st["reservation"]
    if not reservation:
        flash("No reservation found for this tenant, so there is no deposit "
              "record to settle against.", "warning")
        return redirect(url_for("admin.tenant_settlement", profile_id=profile.id))

    # Structured, so the amounts can be read back and totalled later rather
    # than only re-parsed out of the sentence they were printed in.
    _today = date.today().isoformat()
    entries = []
    if st["rent"]["total"]:
        entries.append({"amount": float(st["rent"]["total"]), "date": _today,
                        "reason": f"Unpaid rent ({st['rent']['count']} month(s))"})
    if st["electric_owed"]:
        entries.append({"amount": float(st["electric_owed"]), "date": _today,
                        "reason": "Unpaid electric"})
    if st["water_owed"]:
        entries.append({"amount": float(st["water_owed"]), "date": _today,
                        "reason": "Unpaid water"})
    for d in st["damaged"]:
        if d["is_priced"]:
            entries.append({"amount": float(d["line_total"]), "date": _today,
                            "reason": f"{d['label']} x{d['quantity']} ({d['condition']})"})

    if action == "deduct":
        reservation.deposit_deductions = json.dumps(entries) if entries else None
        reservation.deposit_return_amount = st["refund_after_deduction"]
        reservation.deposit_return_date = date.today()
        note = (f"Settled {date.today():%Y-%m-%d} by {current_user.full_name}: "
                f"charges \u20b1{st['total_owed']:,.2f} deducted from deposit "
                f"\u20b1{st['deposit']:,.2f}.")
        if st["shortfall"]:
            note += f" Shortfall \u20b1{st['shortfall']:,.2f} still collectible."
        reservation.deposit_notes = note
        db.session.commit()
        flash(f"Charges deducted. Refund due to tenant: "
              f"\u20b1{st['refund_after_deduction']:,.2f}."
              + (f" A shortfall of \u20b1{st['shortfall']:,.2f} remains uncovered."
                 if st["shortfall"] else ""), "success")

    elif action == "tenant_paid":
        reservation.deposit_deductions = None
        reservation.deposit_return_amount = st["deposit"]
        reservation.deposit_return_date = date.today()
        reservation.deposit_notes = (
            f"Settled {date.today():%Y-%m-%d} by {current_user.full_name}: tenant "
            f"paid the \u20b1{st['total_owed']:,.2f} in charges separately, so the "
            f"deposit of \u20b1{st['deposit']:,.2f} returns in full.")
        db.session.commit()
        flash(f"Recorded as settled by the tenant. Full deposit of "
              f"\u20b1{st['deposit']:,.2f} is returnable.", "success")
    else:
        flash("Unknown action.", "warning")

    return redirect(url_for("admin.tenant_settlement", profile_id=profile.id))


@bp.get("/tenants/<int:profile_id>/payment-history")
@login_required
def tenant_payment_history(profile_id: int):
    """This ONE tenant's month-by-month payment record, newest first.

    Answers the question the panel raised: which months has this tenant
    not paid, and since when. The system could always compute it — until
    now nothing displayed it, so "Outstanding This Month" was the only
    view and it forgot everything older than the current cycle."""
    _ensure_admin()
    profile = db.session.get(TenantProfile, profile_id)
    if not profile:
        abort(404)
    return render_template(
        "admin/_payment_history_modal.html",
        profile=profile,
        timeline=get_payment_timeline(profile),
        standing=payment_standing(profile),
    )


@bp.get("/tenants/<int:profile_id>/utility-bills")
@login_required
def tenant_utility_bills_partial(profile_id: int):
    """This ONE tenant's full utility bill history, newest first — powers
    the "Utility Bills" modal on the Tenant Monitoring row, so paid/unpaid
    history is clearly tied to that specific tenant's own record."""
    _ensure_admin()
    profile = db.session.get(TenantProfile, profile_id)
    if not profile:
        abort(404)
    bills = (
        db.session.query(UtilityBill)
        .filter(UtilityBill.tenant_profile_id == profile_id)
        .order_by(UtilityBill.billing_month.desc())
        .all()
    )
    return render_template("admin/_utility_bills_modal.html", bills=bills, profile=profile)


@bp.get("/units/inventory-standard")
@login_required
def standard_inventory():
    """Set the fixture list once and apply it to every residential unit.

    The units are the same studio type, so encoding seventeen items on each
    of them by hand is the same figures typed five times over. This records
    them once; anything genuinely particular to one unit — a damaged door,
    a missing key — is then corrected on that unit's own page."""
    _ensure_admin()
    units = (db.session.query(Unit)
             .filter(Unit.type == "residential", Unit.is_archived.is_(False))
             .order_by(Unit.unit_code).all())

    # Which units already hold real figures, so the page can say plainly
    # what an overwrite would discard.
    encoded = []
    for u in units:
        rows = (db.session.query(UnitInventoryItem)
                .filter(UnitInventoryItem.unit_id == u.id,
                        UnitInventoryItem.quantity > 0).count())
        if rows:
            encoded.append(u)

    return render_template(
        "admin/standard_inventory.html",
        items=STANDARD_UNIT_INVENTORY,
        conditions=INVENTORY_CONDITIONS,
        units=units, encoded=encoded,
    )


@bp.post("/units/inventory-standard")
@login_required
def standard_inventory_apply():
    """Write the standard figures onto every residential unit.

    Units already carrying figures are skipped unless the administrator
    asks for them too. That default matters once the system has been in
    use: a unit whose door is recorded as damaged, or whose bulb count was
    corrected, should not be silently reset by someone re-running this to
    add a new unit."""
    _ensure_admin()
    overwrite = request.form.get("overwrite") == "1"

    units = (db.session.query(Unit)
             .filter(Unit.type == "residential", Unit.is_archived.is_(False))
             .order_by(Unit.unit_code).all())

    # Read the form once — the same figures go to every unit.
    standard = {}
    for idx, label in enumerate(STANDARD_UNIT_INVENTORY):
        try:
            qty = max(0, int(request.form.get(f"quantity_{idx}") or 0))
        except ValueError:
            qty = 0
        cond = (request.form.get(f"condition_{idx}") or "good").strip()
        if cond not in CONDITION_KEYS:
            cond = "good"
        def _money(name):
            raw = request.form.get(name)
            if raw is None or str(raw).strip() == "":
                return 0.0
            value, err = _parse_money(raw, field="cost")
            return 0.0 if err else value

        cost = _money(f"cost_{idx}")
        repair = _money(f"repair_{idx}")
        standard[label] = (qty, cond, cost, repair)

    applied, skipped = 0, []
    for unit in units:
        rows = ensure_unit_inventory(unit)
        already = any((r.quantity or 0) > 0 for r in rows)
        if already and not overwrite:
            skipped.append(unit.unit_code)
            continue
        for row in rows:
            if row.label not in standard:
                continue  # an item the administrator added by hand; leave it
            (row.quantity, row.condition,
             row.replacement_cost, row.repair_cost) = standard[row.label]
        applied += 1

    db.session.commit()

    msg = f"Standard inventory applied to {applied} unit(s)."
    if skipped:
        msg += (f" Skipped {len(skipped)} already inventoried "
                f"({', '.join(skipped[:6])}{'…' if len(skipped) > 6 else ''}) — "
                f"tick the overwrite box to include them.")
    flash(msg, "success")
    return redirect(url_for("admin.units"))


@bp.get("/units/<int:unit_id>/inventory")
@login_required
def unit_inventory(unit_id: int):
    """Encode what a unit comes with: the fixtures and furnishings listed
    in the Kasunduan, with how many there are and what state they are in.

    The rows are created on first view rather than by a separate setup
    step, so a unit added after the migration still opens with the full
    standard list ready to fill in."""
    _ensure_admin()
    unit = db.session.get(Unit, unit_id)
    if not unit:
        abort(404)
    items = ensure_unit_inventory(unit, commit=True)
    open_tickets = {
        c.unit_inventory_item_id: c
        for c in db.session.query(Concern)
        .filter(Concern.unit_inventory_item_id.in_([i.id for i in items] or [0]),
                Concern.status != ConcernStatus.RESOLVED,
                Concern.is_cancelled.is_(False))
        .all()
    }
    return render_template(
        "admin/unit_inventory.html",
        unit=unit, items=items, open_tickets=open_tickets,
        conditions=INVENTORY_CONDITIONS,
        summary=inventory_summary(items),
    )


@bp.post("/units/<int:unit_id>/inventory")
@login_required
def unit_inventory_save(unit_id: int):
    """Save the whole inventory in one submit — quantity, condition and
    note per row, named by row id."""
    _ensure_admin()
    unit = db.session.get(Unit, unit_id)
    if not unit:
        abort(404)

    rows = {r.id: r for r in ensure_unit_inventory(unit)}
    changed = 0
    for row_id, row in rows.items():
        qty_raw = request.form.get(f"quantity_{row_id}")
        if qty_raw is None:
            continue  # row absent from this submit; leave it alone
        try:
            quantity = max(0, int(qty_raw or 0))
        except ValueError:
            continue
        condition = (request.form.get(f"condition_{row_id}") or "").strip()
        if condition not in CONDITION_KEYS:
            condition = row.condition
        note = (request.form.get(f"notes_{row_id}") or "").strip()[:255] or None

        # Two prices, because the conditions are charged differently: `fair`
        # against the repair cost, `damaged` and `missing` against the
        # replacement cost. _parse_money rejects "1e999" and the like, which
        # a bare float() would happily turn into infinity.
        def _cost(name, current):
            # Blank clears the price to zero — an item can stop being priced.
            # Anything unreadable leaves the stored figure alone rather than
            # silently zeroing a price the administrator did set.
            raw = request.form.get(name)
            if raw is None or str(raw).strip() == "":
                return 0.0
            value, err = _parse_money(raw, field="cost")
            return float(current or 0) if err else value

        cost = _cost(f"cost_{row_id}", row.replacement_cost)
        repair = _cost(f"repair_{row_id}", row.repair_cost)

        if (row.quantity, row.condition, row.notes,
                float(row.replacement_cost or 0), float(row.repair_cost or 0)) != \
                (quantity, condition, note, cost, repair):
            row.quantity, row.condition, row.notes = quantity, condition, note
            row.replacement_cost = cost
            row.repair_cost = repair
            changed += 1

    db.session.commit()
    if changed:
        flash(f"Inventory saved for {unit.unit_code} — {changed} item(s) updated.",
              "success")
    else:
        flash("No changes to save.", "info")
    return redirect(url_for("admin.unit_inventory", unit_id=unit.id))


@bp.get("/deposits")
@login_required
def deposits():
    _ensure_admin()
    from datetime import date, timedelta
    from sqlalchemy import func as _func

    today = date.today()

    base_query = db.session.query(Reservation).filter(Reservation.status == ReservationStatus.APPROVED)

    # Filters (for the table only — stat cards below always use base_query,
    # i.e. every approved reservation, regardless of these filters).
    search_query = (request.args.get('search') or '').strip()
    status_filter = (request.args.get('status') or '').strip()
    building_filter = (request.args.get('building') or '').strip()
    floor_filter = (request.args.get('floor') or '').strip()
    sort_by = (request.args.get('sort') or 'newest').strip()

    filtered_query = base_query
    if search_query:
        filtered_query = filtered_query.filter(
            db.or_(Reservation.full_name.ilike(f"%{search_query}%"), Reservation.email.ilike(f"%{search_query}%"))
        )
    if status_filter:
        filtered_query = filtered_query.filter(Reservation.deposit_status == status_filter)
    if building_filter or floor_filter:
        filtered_query = filtered_query.join(Unit, Reservation.unit_id == Unit.id)
        if building_filter:
            filtered_query = filtered_query.join(Building, Unit.building_id == Building.id).filter(Building.code == building_filter)
        if floor_filter:
            filtered_query = filtered_query.filter(Unit.floor == int(floor_filter))

    if sort_by == 'oldest':
        filtered_query = filtered_query.order_by(Reservation.created_at.asc())
    elif sort_by == 'amount-high':
        filtered_query = filtered_query.order_by(Reservation.deposit_amount.desc())
    elif sort_by == 'amount-low':
        filtered_query = filtered_query.order_by(Reservation.deposit_amount.asc())
    elif sort_by == 'expiring':
        filtered_query = filtered_query.order_by(Reservation.move_out_date.asc().nullslast())
    else:  # newest (default)
        filtered_query = filtered_query.order_by(Reservation.created_at.desc())

    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(filtered_query, page=page, per_page=25, error_out=False)
    reservations = pagination.items

    # Stat cards reflect ALL approved reservations' deposits, not just the
    # current page — they used to be summed from the `reservations` list
    # here directly, which is exactly the kind of "only counts what's on
    # this page" bug pagination would otherwise introduce.
    total_held = base_query.filter(Reservation.deposit_status == 'held').with_entities(
        _func.coalesce(_func.sum(Reservation.deposit_amount), 0)
    ).scalar()
    total_returned = base_query.filter(
        Reservation.deposit_status.in_(['full_return', 'partial_return']),
        Reservation.deposit_return_amount.isnot(None),
    ).with_entities(_func.coalesce(_func.sum(Reservation.deposit_return_amount), 0)).scalar()
    active_deposits = base_query.filter(Reservation.deposit_status == 'held').count()
    pending_soon = base_query.filter(
        Reservation.deposit_status == 'held',
        Reservation.move_out_date.isnot(None),
        Reservation.move_out_date <= today + timedelta(days=30),
    ).count()
    # Deductions = deposit_amount - deposit_return_amount, summed only over
    # rows that actually have a return amount recorded — computed in
    # Python since it's a per-row difference, not a plain column sum.
    deduction_pairs = base_query.filter(Reservation.deposit_return_amount.isnot(None)).with_entities(
        Reservation.deposit_amount, Reservation.deposit_return_amount
    ).all()
    total_deductions = sum(float(amt) - float(ret) for amt, ret in deduction_pairs)

    deposit_stats = {
        'total_held': float(total_held or 0),
        'total_returned': float(total_returned or 0),
        'total_deductions': total_deductions,
        'active_deposits': active_deposits,
        'pending_soon': pending_soon,
    }

    buildings = db.session.query(Building).order_by(Building.code.asc()).all()

    return render_template(
        "admin/deposits.html", reservations=reservations, pagination=pagination,
        deposit_stats=deposit_stats, buildings=buildings, today=today,
    )


@bp.get("/deposits/export")
@login_required
def export_deposits():
    _ensure_admin()
    import csv
    from io import StringIO
    from datetime import date
    
    reservations = (
        db.session.query(Reservation)
        .filter(Reservation.status == ReservationStatus.APPROVED)
        .order_by(Reservation.created_at.desc())
        .all()
    )
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Tenant Name',
        'Email',
        'Building',
        'Unit',
        'Move-in Date',
        'Contract End',
        'Deposit Amount',
        'Deductions',
        'Return Amount',
        'Status',
        'Return Date'
    ])
    
    # Data
    for r in reservations:
        deducted_amount = r.deposit_amount - r.deposit_return_amount if r.deposit_return_amount else 0
        writer.writerow([
            r.full_name,
            r.email,
            r.unit.building.code.upper(),
            r.unit.unit_code,
            r.move_in_date.strftime('%Y-%m-%d') if r.move_in_date else '',
            r.move_out_date.strftime('%Y-%m-%d') if r.move_out_date else '',
            f'{r.deposit_amount:.2f}',
            f'{deducted_amount:.2f}',
            f'{r.deposit_return_amount:.2f}' if r.deposit_return_amount else f'{r.deposit_amount:.2f}',
            r.deposit_status.replace('_', ' ').title(),
            r.deposit_return_date.strftime('%Y-%m-%d') if r.deposit_return_date else ''
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=deposits_export_{date.today().isoformat()}.csv'}
    )


@bp.get("/users")
@login_required
def users():
    _ensure_admin()

    # Get filter parameters
    search_query = request.args.get('search', '').strip()
    role_filter = request.args.get('role', '')
    verified_filter = request.args.get('verified', '')
    status_filter = request.args.get('status', '')
    sort_by = request.args.get('sort', 'newest')

    # Base query - exclude admins
    query = db.session.query(User).filter(User.role != Role.ADMIN)

    # Apply search filter
    if search_query:
        query = query.filter(
            db.or_(
                User.full_name.ilike(f"%{search_query}%"),
                User.email.ilike(f"%{search_query}%")
            )
        )

    # Apply role filter
    if role_filter:
        query = query.filter(User.role == Role(role_filter))

    # Apply status filter
    if status_filter == 'active':
        query = query.filter(User.is_archived == False, User.is_banned == False)
    elif status_filter == 'archived':
        query = query.filter(User.is_archived == True)
    elif status_filter == 'banned':
        query = query.filter(User.is_banned == True)

    # Apply verification filter
    if verified_filter == 'verified':
        query = query.filter(User.is_email_verified == True)
    elif verified_filter == 'unverified':
        query = query.filter(User.is_email_verified == False)
    
    # Apply sorting
    if sort_by == 'newest':
        query = query.order_by(User.created_at.desc())
    elif sort_by == 'oldest':
        query = query.order_by(User.created_at.asc())
    elif sort_by == 'name':
        query = query.order_by(User.full_name.asc())
    elif sort_by == 'name-desc':
        query = query.order_by(User.full_name.desc())
    elif sort_by == 'last_login':
        query = query.order_by(User.last_login_at.desc().nullslast())

    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=30, error_out=False)
    all_users = pagination.items

    # Calculate statistics
    total_customers = db.session.query(User).filter(User.role != Role.ADMIN).count()
    verified_users = db.session.query(User).filter(User.role != Role.ADMIN, User.is_email_verified == True).count()
    active_tenants = db.session.query(User).filter(User.role == Role.TENANT).count()
    pending_verifications = db.session.query(User).filter(User.role != Role.ADMIN, User.is_email_verified == False).count()
    
    stats = {
        'total': total_customers,
        'verified': verified_users,
        'tenants': active_tenants,
        'pending': pending_verifications
    }
    
    return render_template("admin/users.html", all_users=all_users, pagination=pagination, stats=stats)


@bp.get("/users/export")
@login_required
def export_users():
    _ensure_admin()
    import csv
    from io import StringIO
    from datetime import datetime
    
    # Get all non-admin users
    users = db.session.query(User).filter(User.role != Role.ADMIN).order_by(User.created_at.desc()).all()
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(["THE ELIS CENTER - Customers Report"])
    writer.writerow([f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"])
    writer.writerow([])
    
    # Column headers
    writer.writerow(["ID", "Full Name", "Email", "Role", "Email Verified", "Joined Date", "Last Login"])
    
    # Data rows
    for user in users:
        writer.writerow([
            user.id,
            user.full_name,
            user.email,
            user.role.value.title(),
            "Yes" if user.is_email_verified else "No",
            user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            user.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if user.last_login_at else "Never"
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=customers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )


@bp.post("/users/<int:user_id>/reset-password")
@login_required
def reset_user_password(user_id: int):
    """Issue a one-time password for a tenant who cannot get into their account.

    The stored password cannot be read back — it is a salted hash, which is
    the point of it — so helping someone who has forgotten theirs means
    issuing a new one rather than looking the old one up. The temporary
    password is shown to the administrator once, here, and never stored in
    the clear; the tenant is expected to change it from Settings once they
    are in.
    """
    _ensure_admin()
    user = db.session.get(User, user_id)
    if not user or user.role == Role.ADMIN:
        abort(404)

    import secrets as _secrets
    from ...security import hash_password
    # Readable over the phone: no look-alike characters.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    temp = "".join(_secrets.choice(alphabet) for _ in range(10))

    user.password_hash = hash_password(temp)
    user.reset_token = None
    user.reset_token_expires_at = None
    db.session.commit()

    db.session.add(ActivityLog(actor_user_id=current_user.id,  # type: ignore[attr-defined]
                               action="temp_password_issued"))
    db.session.commit()

    # Emailed as well as shown, never instead. This exists for the tenant
    # who cannot reach their own email, and for them the administrator
    # reading it out is the only route that works — so the password appears
    # on screen whether or not the send succeeds.
    emailed = False
    try:
        from ...email_helper import send_temporary_password_email
        send_temporary_password_email(user.email, user.full_name or "Tenant", temp)
        emailed = True
    except Exception:
        current_app.logger.exception("Temporary password email failed for %s", user.email)

    sent = ("It has also been emailed to them."
            if emailed else
            "The email could not be sent, so pass it on directly.")
    flash(f"Temporary password for {user.full_name} ({user.email}): {temp} — "
          f"ask them to change it in Settings. {sent} "
          f"It is shown here once and is not stored in readable form.", "success")
    return redirect(url_for("admin.user_details", user_id=user.id))


@bp.get("/users/<int:user_id>/details")
@login_required
def user_details(user_id: int):
    _ensure_admin()
    user = db.session.get(User, user_id)
    if not user or user.role == Role.ADMIN:
        abort(404)
    
    # Get user's reservations
    reservations = db.session.query(Reservation).filter(Reservation.user_id == user_id).order_by(Reservation.created_at.desc()).all()
    
    # Get tenant profile if exists — looked up regardless of the user's
    # CURRENT role, since an archived former tenant (e.g. after move-out or
    # an expired contract) is reverted to Role.USER but should still show
    # their full history here rather than disappearing.
    tenant_profile = None
    payments = []
    concerns = []
    documents = []
    feedbacks = []
    if user.role in (Role.TENANT, Role.USER):
        tenant_profile = db.session.query(TenantProfile).filter(TenantProfile.user_id == user_id).order_by(TenantProfile.id.desc()).first()
        if tenant_profile:
            payments = db.session.query(Payment).filter(Payment.tenant_profile_id == tenant_profile.id).order_by(Payment.paid_at.desc()).limit(10).all()
            concerns = db.session.query(Concern).filter(Concern.tenant_profile_id == tenant_profile.id).order_by(Concern.created_at.desc()).limit(10).all()
            documents = db.session.query(Document).filter(Document.tenant_profile_id == tenant_profile.id).order_by(Document.uploaded_at.desc()).limit(10).all()
            feedbacks = db.session.query(Feedback).filter(Feedback.tenant_profile_id == tenant_profile.id).order_by(Feedback.created_at.desc()).limit(10).all()

    return render_template("admin/user_details.html",
                         user=user,
                         reservations=reservations,
                         tenant_profile=tenant_profile,
                         payments=payments,
                         concerns=concerns,
                         documents=documents,
                         feedbacks=feedbacks)


@bp.post("/users/<int:user_id>/ban")
@login_required
def ban_user(user_id: int):
    _ensure_admin()
    user = db.session.get(User, user_id)
    if not user or user.role == Role.ADMIN:
        abort(404)

    reason = (request.form.get("reason") or "").strip()
    user.is_banned = True
    user.banned_at = datetime.utcnow()
    user.ban_reason = reason or "Violation of terms of service"

    db.session.add(ActivityLog(
        actor_user_id=current_user.id,  # type: ignore[attr-defined]
        action=f"user_banned:{user.id}",
        meta_json=json.dumps({"reason": user.ban_reason})
    ))
    db.session.commit()
    
    # Send email notification using HTTP API (works on Render free tier)
    from app.email_helper import send_ban_notification
    send_ban_notification(user.email, user.full_name, user.ban_reason)
    
    flash(f"{user.full_name} has been banned. They will no longer be able to log in.", "warning")
    return redirect(url_for("admin.users"))


@bp.post("/users/<int:user_id>/unban")
@login_required
def unban_user(user_id: int):
    _ensure_admin()
    user = db.session.get(User, user_id)
    if not user or user.role == Role.ADMIN:
        abort(404)

    user.is_banned = False
    user.banned_at = None
    user.ban_reason = None

    db.session.add(ActivityLog(
        actor_user_id=current_user.id,  # type: ignore[attr-defined]
        action=f"user_unbanned:{user.id}",
    ))
    db.session.commit()
    
    # Send email notification using HTTP API (works on Render free tier)
    from app.email_helper import send_unban_notification
    send_unban_notification(user.email, user.full_name)
    
    flash(f"{user.full_name} has been unbanned and can now log in again.", "success")
    return redirect(url_for("admin.users"))
    flash(f"{user.full_name} has been unbanned and can now log in again.", "success")
    return redirect(url_for("admin.users"))
    db.session.commit()
    flash(f"{user.full_name} has been unbanned and can now log in again.", "success")
    return redirect(url_for("admin.users"))


@bp.post("/users/<int:user_id>/archive")
@login_required
def archive_user(user_id: int):
    _ensure_admin()
    user = db.session.get(User, user_id)
    if not user or user.role == Role.ADMIN:
        abort(404)

    # If user is a tenant, check if contract is expired before archiving
    if user.role == Role.TENANT:
        profile = db.session.query(TenantProfile).filter_by(user_id=user.id).first()
        if profile and profile.contract_end:
            today = date.today()
            if profile.contract_end > today:
                flash(f"Cannot archive {user.full_name}. Their contract is still active until {profile.contract_end}.", "danger")
                return redirect(url_for("admin.users"))

    user.is_archived = True
    user.archived_at = datetime.utcnow()

    # If user is a tenant with expired contract, revert role and deactivate
    if user.role == Role.TENANT:
        profile = db.session.query(TenantProfile).filter_by(user_id=user.id).first()
        if profile:
            profile.is_active = False
            # Free up the unit
            unit = db.session.get(Unit, profile.unit_id)
            if unit and unit.status == UnitStatus.OCCUPIED:
                unit.status = UnitStatus.AVAILABLE
            user.archive_reason = "Contract expired"
        user.role = Role.USER
    else:
        user.archive_reason = "Manually archived by admin"

    db.session.add(ActivityLog(
        actor_user_id=current_user.id,  # type: ignore[attr-defined]
        action=f"user_archived:{user.id}",
    ))
    db.session.commit()
    flash(f"{user.full_name} has been archived. Their account is preserved but hidden from active lists.", "info")
    return redirect(url_for("admin.users"))


@bp.post("/users/<int:user_id>/unarchive")
@login_required
def unarchive_user(user_id: int):
    _ensure_admin()
    user = db.session.get(User, user_id)
    if not user or user.role == Role.ADMIN:
        abort(404)

    user.is_archived = False
    user.archived_at = None
    user.archive_reason = None

    # Note: User remains as USER (not TENANT) and unit remains available
    # To become a tenant again, admin must assign a new unit through normal process

    db.session.add(ActivityLog(
        actor_user_id=current_user.id,  # type: ignore[attr-defined]
        action=f"user_unarchived:{user.id}",
    ))
    db.session.commit()
    flash(f"{user.full_name} has been restored from the archive as a regular user.", "success")
    return redirect(url_for("admin.users"))


@bp.post("/deposits/<int:reservation_id>/process")
@login_required
def process_deposit(reservation_id: int):
    _ensure_admin()
    import json

    r = db.session.get(Reservation, reservation_id)
    if not r:
        abort(404)

    action = request.form.get("action")
    
    if action == "add_deduction":
        # Three faults met here. The amount was float()'d with no guard, so a
        # typo was a 500. Deductions were WRITTEN as display text ("• ₱500.00
        # - reason (date)") but READ back with json.loads, which always threw
        # and silently reset the list, losing every earlier deduction. And
        # deposit_amount is NUMERIC, so Python hands back a Decimal —
        # subtracting a float raised TypeError, which is the internal server
        # error being reported. Deductions are stored as JSON now, and every
        # amount is a Decimal from the point it is read.
        amount_value, amount_error = _parse_money(
            request.form.get("deduction_amount"), "deduction amount")
        deduction_reason = (request.form.get("deduction_reason") or "").strip()

        if amount_error or not amount_value:
            flash(amount_error or "Please enter a deduction amount above zero.",
                  "warning")
            return redirect(url_for("admin.deposits"))
        if not deduction_reason:
            flash("Please give a reason for the deduction.", "warning")
            return redirect(url_for("admin.deposits"))

        deposit_amount = Decimal(str(r.deposit_amount or 0))
        deduction = Decimal(str(amount_value))

        deductions = []
        if r.deposit_deductions:
            try:
                parsed = json.loads(r.deposit_deductions)
                if isinstance(parsed, list):
                    deductions = parsed
            except (ValueError, TypeError):
                # Rows written before this fix hold display text, not JSON.
                # Keep them as one historical line rather than dropping them.
                deductions = [{"amount": None, "reason": r.deposit_deductions,
                               "date": None, "legacy": True}]

        deductions.append({
            "amount": f"{deduction:.2f}",
            "reason": deduction_reason,
            "date": date.today().isoformat(),
        })

        total_deductions = sum(
            (Decimal(str(d["amount"])) for d in deductions if d.get("amount")),
            Decimal("0"))

        r.deposit_deductions = json.dumps(deductions)
        r.deposit_return_amount = max(Decimal("0"), deposit_amount - total_deductions)
        r.deposit_status = ("full_return" if total_deductions >= deposit_amount
                            else "partial_return")

        flash(f"Deduction of \u20b1{deduction:,.2f} added. Total deductions: "
              f"\u20b1{total_deductions:,.2f} of \u20b1{deposit_amount:,.2f}.", "success")
        
    elif action == "return_deposit":
        # Create payment record for deposit return
        if not r.deposit_return_amount:
            r.deposit_return_amount = r.deposit_amount
        
        # Find tenant profile
        tenant_profile = db.session.query(TenantProfile).filter(
            TenantProfile.user_id == r.user_id,
            TenantProfile.unit_id == r.unit_id
        ).first()
        
        if tenant_profile:
            # Create payment record for blockchain
            from datetime import datetime
            paid_at_normalized = datetime.now().replace(microsecond=0)
            payment = Payment(
                tenant_profile_id=tenant_profile.id,
                amount=r.deposit_return_amount,
                reference=f"Security Deposit Return - {r.unit.unit_code}",
                paid_at=paid_at_normalized,
                is_deposit=True,
                deposit_transaction_type="deposit_returned"
            )
            db.session.add(payment)
            
            # Generate blockchain ledger
            _generate_payment_ledger(payment)
        
        r.deposit_status = "full_return"
        r.deposit_return_date = date.today()
        flash(f"Deposit of ₱{r.deposit_return_amount:.2f} returned and recorded in blockchain.", "success")
        
    elif action == "return_remaining":
        # Find tenant profile
        tenant_profile = db.session.query(TenantProfile).filter(
            TenantProfile.user_id == r.user_id,
            TenantProfile.unit_id == r.unit_id
        ).first()
        
        if tenant_profile and r.deposit_return_amount:
            # Create payment record for blockchain
            from datetime import datetime
            paid_at_normalized = datetime.now().replace(microsecond=0)
            payment = Payment(
                tenant_profile_id=tenant_profile.id,
                amount=r.deposit_return_amount,
                reference=f"Remaining Security Deposit Return - {r.unit.unit_code}",
                paid_at=paid_at_normalized,
                is_deposit=True,
                deposit_transaction_type="deposit_returned"
            )
            db.session.add(payment)
            
            # Generate blockchain ledger
            _generate_payment_ledger(payment)
        
        r.deposit_status = "full_return"
        r.deposit_return_date = date.today()
        flash("Remaining deposit returned and recorded in blockchain.", "success")
    
    db.session.commit()
    return redirect(url_for("admin.deposits"))


@bp.post("/payments/add")
@login_required
def add_payment():
    _ensure_admin()
    tenant_profile_id = int(request.form.get("tenant_profile_id") or "0")
    amount = request.form.get("amount") or "0"
    reference = (request.form.get("reference") or "").strip()
    payment_month = (request.form.get("payment_month") or "").strip()
    payment_method = (request.form.get("payment_method") or "cash").strip()
    if payment_method not in ("cash", "bank_transfer", "other"):
        payment_method = "cash"

    profile = db.session.get(TenantProfile, tenant_profile_id)
    if not profile:
        abort(404)

    # Build reference with payment month if provided
    if payment_month:
        from datetime import datetime
        try:
            month_date = datetime.strptime(payment_month, "%Y-%m")
            month_name = month_date.strftime("%B %Y")
            if reference:
                reference = f"{reference} - {month_name}"
            else:
                reference = f"Rent - {month_name}"
        except ValueError:
            pass

    # Duplicate-entry check: does this tenant already have a non-deposit
    # payment tagged with the same billing month? Doesn't block — admin may
    # genuinely have a legitimate second entry (e.g. a partial payment) —
    # just flags it so a manual double-entry mistake doesn't slip by unnoticed.
    duplicate_warning = None
    if payment_month:
        existing = (
            db.session.query(Payment)
            .filter(Payment.tenant_profile_id == profile.id)
            .filter(Payment.is_deposit == False)  # noqa: E712
            .filter(Payment.payment_month == payment_month)
            .first()
        )
        if existing:
            duplicate_warning = (
                f"Note: {profile.user.full_name if profile.user else 'this tenant'} already has a payment "
                f"recorded for {payment_month} (₱{existing.amount:,.2f} on {existing.paid_at.strftime('%b %d, %Y')}). "
                "Please verify this isn't a duplicate entry."
            )

    # Create payment with normalized timestamp for blockchain consistency
    from datetime import datetime
    paid_at_normalized = datetime.utcnow().replace(microsecond=0)
    # A tenant settling several months at once hands over one amount, but
    # each month has to stay its own Payment row: payment_month is what
    # marks a cycle as settled everywhere else in the app (arrears,
    # "Outstanding This Month", the tenant portal). So the lump sum is
    # allocated oldest-first across whole months, and only the remainder —
    # if any — stays on the month the admin picked.
    # A tenant settling several months at once hands over one amount, but
    # each month has to stay its own Payment row: payment_month is what
    # marks a cycle as settled everywhere else in the app (arrears,
    # "Outstanding This Month", the tenant portal). So a lump sum that
    # covers two or more whole months is allocated oldest-first, with the
    # main row below carrying one month and the rest written after it.
    extra_months = []
    if payment_month:
        from ...billing_utils import get_rent_arrears
        arrears = get_rent_arrears(profile)
        rate = arrears["monthly_rate"]
        covered = arrears["months"]  # oldest first
        if rate > 0 and len(covered) > 1 and float(amount) >= rate * 2:
            months = covered[:min(int(float(amount) // rate), len(covered))]
            main_month = payment_month if payment_month in months else months[0]
            extra_months = [m for m in months if m != main_month]
            if extra_months:
                amount = rate
                payment_month = main_month
                month_name = datetime.strptime(main_month, "%Y-%m").strftime("%B %Y")
                reference = f"Rent - {month_name}"

    is_late = _is_rent_payment_late(profile, paid_at_normalized, payment_month)
    p = Payment(
        tenant_profile_id=profile.id,
        amount=amount,
        reference=reference,
        paid_at=paid_at_normalized,
        is_late=is_late,
        payment_status="late" if is_late else "verified",
        payment_month=payment_month or None,
        payment_method=payment_method,
    )
    db.session.add(p)
    db.session.flush()

    _generate_payment_ledger(p)

    # Remaining months of a multi-month settlement, each its own row and its
    # own ledger entry so the chain reflects one entry per cycle settled.
    for month in extra_months:
        month_name = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
        extra = Payment(
            tenant_profile_id=profile.id,
            amount=amount,
            reference=f"Rent - {month_name}",
            paid_at=paid_at_normalized,
            is_late=_is_rent_payment_late(profile, paid_at_normalized, month),
            payment_status="late" if _is_rent_payment_late(profile, paid_at_normalized, month) else "verified",
            payment_month=month,
            payment_method=payment_method,
            notes="Part of a multi-month settlement recorded in one transaction.",
        )
        db.session.add(extra)
        db.session.flush()
        _generate_payment_ledger(extra)

    # Optional: mark unit as occupied (and clear unpaid flag)
    unit = db.session.get(Unit, profile.unit_id)
    if unit and unit.status == UnitStatus.UNPAID:
        unit.status = UnitStatus.OCCUPIED

    db.session.commit()

    from ...socket_events import emit_payment_notification
    emit_payment_notification(profile.user_id, {
        "amount": float(p.amount),
        "tenant_name": profile.user.full_name if profile.user else None,
        "unit_code": unit.unit_code if unit else None,
    })

    if profile.user and profile.user.email:
        from ...email_helper import send_payment_verified_email
        send_payment_verified_email(
            tenant_name=profile.user.full_name,
            tenant_email=profile.user.email,
            amount=float(p.amount),
            unit_code=unit.unit_code if unit else "N/A",
            payment_method=payment_method,
            payment_month=payment_month or None,
        )

    if duplicate_warning:
        flash(duplicate_warning, "warning")
    elif extra_months:
        settled = [payment_month] + extra_months
        flash(f"Payment recorded for {len(settled)} months "
              f"({', '.join(sorted(settled))}) — one ledger entry each. "
              f"Total ₱{float(amount) * len(settled):,.2f}.", "success")
    else:
        flash("Payment recorded (with ledger hash).", "success")
    return redirect(url_for("admin.payments"))


def _bill_for_payment(payment, profile, create: bool = False):
    """The utility bill the month of this payment belongs to, or None.

    A payment carries the rent month it settles; the utility bill for the
    same month is the one the tenant would have been shown alongside it.
    Falls back to the current calendar month when the payment names none,
    which is what the reminder job bills on too. Returns None when the
    tenant has no bill for that month — utilities begin the month after
    move-in, so their first month genuinely has none.

    `create` stays off for the read path: rendering a page is no reason to
    write a bill row the administrator never asked for.
    """
    month = payment.payment_month or date.today().strftime("%Y-%m")
    if create:
        from ...billing_utils import get_or_create_utility_bill
        return get_or_create_utility_bill(profile, month)
    return (db.session.query(UtilityBill)
            .filter(UtilityBill.tenant_profile_id == profile.id,
                    UtilityBill.billing_month == month)
            .first())


@bp.post("/payments/<int:payment_id>/approve")
@login_required
def approve_payment_proof(payment_id: int):
    """Approve a tenant-submitted bank transfer proof — turns it into a
    real, ledger-backed payment record, same as one admin enters directly."""
    _ensure_admin()
    payment = db.session.get(Payment, payment_id)
    if not payment or payment.payment_status != 'pending':
        abort(404)

    profile = db.session.get(TenantProfile, payment.tenant_profile_id)
    if not profile:
        abort(404)

    # Admin can correct the amount before approving — e.g. a residential
    # tenant's final move-out payment is a half-month amount, but they
    # submitted proof for the full monthly rent by mistake (or vice versa).
    amount_override = (request.form.get("amount") or "").strip()
    if amount_override:
        try:
            new_amount = float(amount_override)
            if new_amount > 0:
                payment.amount = new_amount
        except ValueError:
            pass

    is_late = _is_rent_payment_late(profile, payment.paid_at, payment.payment_month or "")
    payment.payment_status = "late" if is_late else "verified"
    payment.is_late = is_late

    _generate_payment_ledger(payment)

    unit = db.session.get(Unit, profile.unit_id)
    if unit and unit.status == UnitStatus.UNPAID:
        unit.status = UnitStatus.OCCUPIED

    # A tenant sending one transfer for rent plus electric and water used to
    # need two separate actions from the administrator — this approval, then
    # a second trip to Utility Billing — and the second was easy to forget,
    # leaving a tenant chased for a bill they had already settled. The
    # approval screen now offers the month's outstanding components, and
    # whichever were ticked are settled here, in the same transaction.
    # Untouched by default: only what the administrator ticks is settled,
    # because only they can see whether the amount actually covered it.
    settled_note = ""
    components = [c for c in request.form.getlist("settle_utility")
                  if c in ("electric", "water")]
    if components:
        bill = _bill_for_payment(payment, profile, create=True)
        if bill:
            component = "both" if len(components) == 2 else components[0]
            cascaded = _settle_utility_components(bill, component, current_user.id)
            label = {"electric": "Electric", "water": "Water",
                     "both": "Electric and water"}[component]
            settled_note = f" {label} for {bill.billing_month} settled too."
            if cascaded:
                settled_note += (f" {cascaded} earlier unpaid month(s) closed with it "
                                 f"— this bill already carried their balance.")

    db.session.commit()

    from ...socket_events import emit_payment_notification
    emit_payment_notification(profile.user_id, {
        "amount": float(payment.amount),
        "tenant_name": profile.user.full_name if profile.user else None,
        "unit_code": unit.unit_code if unit else None,
    })

    if profile.user and profile.user.email:
        from ...email_helper import send_payment_verified_email
        send_payment_verified_email(
            tenant_name=profile.user.full_name,
            tenant_email=profile.user.email,
            amount=float(payment.amount),
            unit_code=unit.unit_code if unit else "N/A",
            payment_method=payment.payment_method or "bank_transfer",
            payment_month=payment.payment_month,
        )

    flash(f"Payment proof approved and recorded (with ledger hash).{settled_note}", "success")
    return redirect(url_for("admin.payments"))


@bp.post("/payments/<int:payment_id>/reject")
@login_required
def reject_payment_proof(payment_id: int):
    """Reject a tenant-submitted bank transfer proof (e.g. unreadable receipt,
    amount mismatch). Keeps the record — with the tenant's reason attached —
    instead of deleting it, so there's a visible trail on both sides."""
    _ensure_admin()
    payment = db.session.get(Payment, payment_id)
    if not payment or payment.payment_status != 'pending':
        abort(404)

    profile = db.session.get(TenantProfile, payment.tenant_profile_id)
    unit = db.session.get(Unit, profile.unit_id) if profile else None

    reason = (request.form.get("reason") or "").strip()
    final_reason = reason or "Rejected by admin — please resubmit with a clearer receipt or correct details."
    payment.payment_status = "rejected"
    payment.notes = final_reason
    db.session.commit()

    if profile and profile.user and profile.user.email:
        from ...email_helper import send_payment_rejected_email
        send_payment_rejected_email(
            tenant_name=profile.user.full_name,
            tenant_email=profile.user.email,
            amount=float(payment.amount),
            unit_code=unit.unit_code if unit else "N/A",
            reason=final_reason,
        )

    flash("Payment proof rejected. The tenant has been notified.", "success")
    return redirect(url_for("admin.payments"))


@bp.post("/payments/<int:payment_id>/void")
@login_required
def void_payment(payment_id: int):
    """Undo a rent payment the administrator entered by mistake.

    The row is kept and only its status changes. The ledger hash covers
    the payment's amount, reference and timestamp but NOT its status
    (see _generate_payment_ledger), so voiding leaves every hash in the
    chain valid — whereas deleting the row would orphan its ledger entry
    and raise a tampering alarm on the Payments page.

    A voided payment stops counting everywhere money is counted: revenue
    totals, "already paid this cycle", and the rent arrears that drive
    the Add Payment prefill. It stays visible in the payments list so it
    can be reviewed, and restored if the void itself was the mistake.

    Tenant-submitted proofs still awaiting review are not voided here —
    those are approved or rejected through their own actions."""
    _ensure_admin()
    payment = db.session.get(Payment, payment_id)
    if not payment:
        abort(404)
    if payment.payment_status == "pending":
        flash("This is a tenant-submitted proof awaiting review — use "
              "Reject instead, so the tenant is told why.", "warning")
        return redirect(request.referrer or url_for("admin.payments"))
    if payment.payment_status == "voided":
        flash("This payment is already voided.", "info")
        return redirect(request.referrer or url_for("admin.payments"))

    reason = (request.form.get("reason") or "").strip()
    previous = payment.payment_status
    payment.payment_status = "voided"
    stamp = (f"[Voided {datetime.utcnow():%Y-%m-%d} by "
             f"{current_user.full_name}, was '{previous}'"
             + (f": {reason}" if reason else "") + "] ")
    payment.notes = (stamp + (payment.notes or ""))[:255]
    db.session.commit()

    month = f" for {payment.payment_month}" if payment.payment_month else ""
    flash(f"Payment of ₱{float(payment.amount):,.2f}{month} voided. It no "
          f"longer counts toward revenue or this tenant's paid months, and "
          f"the blockchain ledger is untouched.", "success")
    return redirect(request.referrer or url_for("admin.payments"))


@bp.post("/payments/<int:payment_id>/restore")
@login_required
def restore_payment(payment_id: int):
    """Put a voided payment back. Returns it to 'late' or 'verified' by
    re-deriving lateness from its own month, rather than trusting the
    status it happened to carry before."""
    _ensure_admin()
    payment = db.session.get(Payment, payment_id)
    if not payment:
        abort(404)
    if payment.payment_status != "voided":
        flash("Only a voided payment can be restored.", "warning")
        return redirect(request.referrer or url_for("admin.payments"))

    profile = payment.tenant_profile
    is_late = _is_rent_payment_late(profile, payment.paid_at,
                                    payment.payment_month or "") if profile else False
    payment.payment_status = "late" if is_late else "verified"
    payment.notes = (f"[Restored {datetime.utcnow():%Y-%m-%d} by "
                     f"{current_user.full_name}] " + (payment.notes or ""))[:255]
    db.session.commit()
    flash(f"Payment of ₱{float(payment.amount):,.2f} restored and counting "
          f"again.", "success")
    return redirect(request.referrer or url_for("admin.payments"))


@bp.get("/payments/export")
@login_required
def export_payments():
    _ensure_admin()
    import csv
    from io import StringIO
    from datetime import datetime

    payments = db.session.query(Payment).order_by(Payment.paid_at.desc()).all()

    output = StringIO()
    writer = csv.writer(output)

    # Header with Elis branding
    writer.writerow(["THE ELIS CENTER - Commercial and Residences"])
    writer.writerow(["Payments Report"])
    writer.writerow([f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"])
    writer.writerow([])  # Empty row

    # Column headers
    writer.writerow(["Date", "Tenant", "Unit", "Amount", "Reference", "Hash"])

    for p in payments:
        ledger = db.session.query(PaymentLedger).filter_by(payment_id=p.id).first()
        writer.writerow([
            p.paid_at.strftime("%Y-%m-%d %H:%M:%S"),
            p.tenant_profile.user.full_name,
            p.tenant_profile.unit.unit_code,
            p.amount,
            p.reference or "",
            ledger.hash if ledger else ""
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=Elis_Payments_Report.csv"}
    )
    return response


@bp.get("/payments/<int:payment_id>/ledger")
@login_required
def view_ledger(payment_id: int):
    _ensure_admin()
    payment = db.session.get(Payment, payment_id)
    if not payment:
        abort(404)

    ledger = db.session.query(PaymentLedger).filter_by(payment_id=payment_id).first()
    ledger_chain = db.session.query(PaymentLedger).order_by(PaymentLedger.id.asc()).all()

    return render_template("admin/ledger.html", payment=payment, ledger=ledger, ledger_chain=ledger_chain)


@bp.get("/announcements")
@login_required
def announcements():
    _ensure_admin()
    from datetime import date

    today = date.today()

    search_query = (request.args.get('search') or '').strip()
    category_filter = (request.args.get('category') or '').strip()
    status_filter = (request.args.get('status') or '').strip()
    sort_by = (request.args.get('sort') or 'newest').strip()

    query = db.session.query(Announcement)
    if search_query:
        query = query.filter(
            db.or_(Announcement.title.ilike(f"%{search_query}%"), Announcement.content.ilike(f"%{search_query}%"))
        )
    if category_filter:
        query = query.filter(Announcement.category == category_filter)
    if status_filter == 'active':
        query = query.filter(Announcement.is_active == True)  # noqa: E712
    elif status_filter == 'inactive':
        query = query.filter(Announcement.is_active == False)  # noqa: E712
    elif status_filter == 'pinned':
        query = query.filter(Announcement.is_pinned == True)  # noqa: E712

    if sort_by == 'oldest':
        query = query.order_by(Announcement.created_at.asc())
    elif sort_by == 'pinned':
        query = query.order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
    else:  # newest (default)
        query = query.order_by(Announcement.created_at.desc())

    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=20, error_out=False)
    announcements = pagination.items

    # Stat cards reflect ALL announcements, not just the current page/filter.
    this_month_start = today.replace(day=1)
    announcement_stats = {
        'total': db.session.query(Announcement).count(),
        'active': db.session.query(Announcement).filter(Announcement.is_active == True).count(),  # noqa: E712
        'this_month': db.session.query(Announcement).filter(Announcement.created_at >= this_month_start).count(),
        'pinned': db.session.query(Announcement).filter(Announcement.is_pinned == True).count(),  # noqa: E712
    }

    return render_template(
        "admin/announcements.html", announcements=announcements, pagination=pagination,
        announcement_stats=announcement_stats, today=today,
    )


@bp.post("/announcements/create")
@login_required
def create_announcement():
    _ensure_admin()
    from datetime import datetime
    
    title = (request.form.get("title") or "").strip()
    content = (request.form.get("content") or "").strip()
    category = (request.form.get("category") or "").strip()
    target_audience = (request.form.get("target_audience") or "all").strip()
    is_pinned = request.form.get("is_pinned") == "on"
    expires_at_str = (request.form.get("expires_at") or "").strip()

    if not title or not content:
        flash("Please enter title and content.", "warning")
        return redirect(url_for("admin.announcements"))

    expires_at = None
    if expires_at_str:
        try:
            expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d")
        except ValueError:
            pass

    announcement = Announcement(
        title=title,
        content=content,
        category=category,
        target_audience=target_audience,
        is_pinned=is_pinned,
        expires_at=expires_at,
        is_active=True,
    )
    db.session.add(announcement)
    db.session.commit()

    if target_audience in ("all", "tenants"):
        from ...socket_events import emit_announcement_notification
        emit_announcement_notification({
            "id": announcement.id,
            "title": announcement.title,
            "category": announcement.category,
        })

    flash("Announcement created successfully.", "success")
    return redirect(url_for("admin.announcements"))


@bp.get("/announcements/export")
@login_required
def export_announcements():
    _ensure_admin()
    import csv
    from io import StringIO
    from datetime import datetime

    announcements = db.session.query(Announcement).order_by(Announcement.created_at.desc()).all()

    output = StringIO()
    writer = csv.writer(output)

    # Header with Elis branding
    writer.writerow(["THE ELIS CENTER - Commercial and Residences"])
    writer.writerow(["Announcements Report"])
    writer.writerow([f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"])
    writer.writerow([])  # Empty row

    # Column headers
    writer.writerow(["Title", "Category", "Content", "Status", "Created At", "Updated At"])

    for a in announcements:
        writer.writerow([
            a.title,
            a.category or "General",
            a.content,
            "Active" if a.is_active else "Inactive",
            a.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            a.updated_at.strftime("%Y-%m-%d %H:%M:%S") if a.updated_at else ""
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=Elis_Announcements_Report.csv"}
    )
    return response


@bp.post("/announcements/<int:announcement_id>/toggle")
@login_required
def toggle_announcement(announcement_id: int):
    _ensure_admin()
    announcement = db.session.get(Announcement, announcement_id)
    if not announcement:
        abort(404)

    announcement.is_active = not announcement.is_active
    db.session.commit()
    flash(f"Announcement {'activated' if announcement.is_active else 'deactivated'}.", "success")
    return redirect(url_for("admin.announcements"))


@bp.post("/announcements/<int:announcement_id>/pin")
@login_required
def pin_announcement(announcement_id: int):
    _ensure_admin()
    announcement = db.session.get(Announcement, announcement_id)
    if not announcement:
        abort(404)

    announcement.is_pinned = not announcement.is_pinned
    db.session.commit()
    flash(f"Announcement {'pinned' if announcement.is_pinned else 'unpinned'}.", "success")
    return redirect(url_for("admin.announcements"))


@bp.post("/announcements/<int:announcement_id>/delete")
@login_required
def delete_announcement(announcement_id: int):
    _ensure_admin()
    announcement = db.session.get(Announcement, announcement_id)
    if not announcement:
        abort(404)

    db.session.delete(announcement)
    db.session.commit()
    flash("Announcement deleted successfully.", "success")
    return redirect(url_for("admin.announcements"))


@bp.get("/documents")
@login_required
def documents():
    _ensure_admin()
    from datetime import date, timedelta
    from sqlalchemy import func, extract
    from sqlalchemy.orm import joinedload
    
    # Filters
    search_query = request.args.get('search', '').strip()
    doc_type_filter = request.args.get('doc_type', '')
    building_filter = request.args.get('building', '')
    tenant_filter = request.args.get('tenant', '')
    viewed_filter = request.args.get('viewed', '')
    sort_by = request.args.get('sort', 'newest')
    
    # Base query with eager loading
    query = db.session.query(Document).options(
        joinedload(Document.tenant_profile).joinedload(TenantProfile.user),
        joinedload(Document.tenant_profile).joinedload(TenantProfile.unit).joinedload(Unit.building)
    )
    
    # Apply search filter
    if search_query:
        query = query.join(TenantProfile, TenantProfile.id == Document.tenant_profile_id).join(User, User.id == TenantProfile.user_id).join(Unit, Unit.id == TenantProfile.unit_id).filter(
            db.or_(
                Document.title.ilike(f"%{search_query}%"),
                User.full_name.ilike(f"%{search_query}%"),
                Unit.unit_code.ilike(f"%{search_query}%")
            )
        )
    
    # Apply document type filter
    if doc_type_filter:
        query = query.filter(Document.document_type == doc_type_filter)
    
    # Apply building filter
    if building_filter:
        if not search_query:  # Only join if not already joined
            query = query.join(TenantProfile, TenantProfile.id == Document.tenant_profile_id).join(Unit, Unit.id == TenantProfile.unit_id)
        query = query.filter(Unit.building_id == int(building_filter))
    
    # Apply tenant filter
    if tenant_filter:
        query = query.filter(Document.tenant_profile_id == int(tenant_filter))
    
    # Apply viewed filter
    if viewed_filter == 'viewed':
        query = query.filter(Document.is_viewed == True)
    elif viewed_filter == 'unviewed':
        query = query.filter(Document.is_viewed == False)
    
    # Apply sorting
    if sort_by == 'oldest':
        query = query.order_by(Document.uploaded_at.asc())
    elif sort_by == 'title_az':
        query = query.order_by(Document.title.asc())
    elif sort_by == 'title_za':
        query = query.order_by(Document.title.desc())
    elif sort_by == 'tenant_az':
        if not search_query and not building_filter:  # Only join if not already joined
            query = query.join(TenantProfile, TenantProfile.id == Document.tenant_profile_id).join(User, User.id == TenantProfile.user_id)
        query = query.order_by(User.full_name.asc())
    else:  # newest (default)
        query = query.order_by(Document.uploaded_at.desc())
    
    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=24, error_out=False)
    documents = pagination.items

    # Statistics
    today = date.today()
    this_month_start = today.replace(day=1)
    
    total_documents = db.session.query(Document).count()
    uploaded_this_month = db.session.query(Document).filter(
        Document.uploaded_at >= this_month_start
    ).count()
    tenants_with_docs = db.session.query(func.count(func.distinct(Document.tenant_profile_id))).scalar() or 0
    unviewed_count = db.session.query(Document).filter(Document.is_viewed == False).count()
    
    # Documents by type
    doc_types_count = db.session.query(
        Document.document_type,
        func.count(Document.id)
    ).group_by(Document.document_type).all()
    
    stats = {
        'total': total_documents,
        'this_month': uploaded_this_month,
        'tenants_with_docs': tenants_with_docs,
        'unviewed': unviewed_count,
        'by_type': {doc_type: count for doc_type, count in doc_types_count}
    }
    
    # Get all tenants and buildings for filters
    tenants = db.session.query(TenantProfile).order_by(TenantProfile.created_at.desc()).all()
    buildings = db.session.query(Building).order_by(Building.code.asc()).all()
    
    # Document types for filter — admin now only ever sends one of these two
    # (receipts/bills are handled in person, not as uploaded documents).
    doc_types = [
        ('lease_agreement', 'Lease Agreement'),
        ('rental_agreement', 'Kasunduan sa Pagpaupa'),
    ]
    
    return render_template(
        "admin/documents.html",
        tenants=tenants,
        documents=documents,
        pagination=pagination,
        buildings=buildings,
        doc_types=doc_types,
        stats=stats,
        today=today
    )


@bp.post("/documents/upload")
@login_required
def upload_document():
    _ensure_admin()
    from werkzeug.utils import secure_filename
    from pathlib import Path
    import os

    tenant_profile_id = int(request.form.get("tenant_profile_id") or "0")
    title = (request.form.get("title") or "").strip()
    document_type = (request.form.get("document_type") or "").strip()
    file = request.files.get("file")
    if file and file.filename:
        _ok, _why = validate_upload(file, DOCUMENT_TYPES, label="document")
        if not _ok:
            flash(_why, "warning")
            return redirect(url_for("admin.documents"))

    if not tenant_profile_id or not title or not document_type or not file:
        flash("Please fill all fields and select a file.", "warning")
        return redirect(url_for("admin.documents"))

    allowed_ext = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in allowed_ext:
        flash("Unsupported file type. Please upload an image (JPG/PNG/GIF/WEBP) or a PDF.", "warning")
        return redirect(url_for("admin.documents"))

    profile = db.session.get(TenantProfile, tenant_profile_id)
    if not profile:
        abort(404)

    # Save file to static/uploads folder
    upload_folder = Path("app/static/uploads")
    upload_folder.mkdir(parents=True, exist_ok=True)
    
    filename = secure_filename(file.filename)
    unique_filename = f"{tenant_profile_id}_{document_type}_{filename}"
    file_path = upload_folder / unique_filename
    file.save(str(file_path))

    # Persist to Supabase Storage when configured (survives Render redeploys);
    # otherwise keep the local relative path.
    from ... import supabase_storage
    _url = supabase_storage.upload_local_file(str(file_path), f"documents/{unique_filename}")
    relative_path = _url or f"uploads/{unique_filename}"

    document = Document(
        tenant_profile_id=profile.id,
        title=title,
        document_type=document_type,
        file_path=relative_path,
        uploaded_by=current_user.id,  # type: ignore[attr-defined]
        is_viewed=False,
    )
    db.session.add(document)
    db.session.commit()

    from ...socket_events import emit_document_notification
    emit_document_notification(profile.user_id, {
        "id": document.id,
        "title": document.title,
        "document_type": document.document_type,
    })

    # Send email notification to tenant
    _send_document_notification_email(
        tenant_name=profile.user.full_name,
        tenant_email=profile.user.email,
        document_title=title,
        document_type=document_type.replace('_', ' ').title(),
        unit_code=profile.unit.unit_code
    )
    
    flash(f"Document uploaded successfully and notification sent to {profile.user.full_name}.", "success")
    return redirect(url_for("admin.documents"))


def _send_document_notification_email(tenant_name: str, tenant_email: str, document_title: str, document_type: str, unit_code: str = "N/A") -> None:
    """Send email notification when admin uploads a document for tenant using Brevo HTTP API"""
    if not tenant_email:
        return
    
    from ...email_helper import send_document_notification_email
    
    send_document_notification_email(tenant_name, tenant_email, document_title, unit_code)


@bp.post("/documents/<int:document_id>/delete")
@login_required
def delete_document(document_id: int):
    _ensure_admin()
    document = db.session.get(Document, document_id)
    if not document:
        abort(404)
    
    # Delete the underlying file — Supabase Storage (production) or local disk (dev)
    from ... import supabase_storage
    if not supabase_storage.delete_public_url(document.file_path):
        import os
        try:
            file_path = os.path.join("app", "static", document.file_path.lstrip("/"))
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Failed to delete local file: {e}")

    db.session.delete(document)
    db.session.commit()
    flash("Document deleted successfully.", "success")
    return redirect(url_for("admin.documents"))


@bp.get("/blockchain/verify")
@login_required
def verify_blockchain():
    _ensure_admin()
    
    result = verify_blockchain_chain()
    
    if result["valid"]:
        flash(f"✓ {result['message']}", "success")
    else:
        flash(f"🚨 {result['message']}. Please investigate the tampered records below.", "danger")
    
    # Store result in session for display on next page
    from flask import session
    session["blockchain_verification"] = result
    
    return redirect(url_for("admin.payments"))


@bp.post("/blockchain/resolve")
@login_required
def resolve_blockchain_issue():
    _ensure_admin()
    from flask import session
    
    # Mark that admin has acknowledged the alert
    session['hide_blockchain_alert'] = True
    
    # In a real scenario, you might want to log WHO resolved this.
    if "blockchain_verification" in session:
        session.pop("blockchain_verification")
        
    flash("Integrity alert dismissed. Please ensure the database records are corrected to match original receipts.", "info")
    return redirect(url_for("admin.dashboard"))


@bp.get("/blockchain/reset-alert")
@login_required
def reset_blockchain_alert():
    """Reset the blockchain alert flag - accessible via URL"""
    _ensure_admin()
    from flask import session
    
    if 'hide_blockchain_alert' in session:
        session.pop('hide_blockchain_alert')
        flash("Blockchain alert flag has been reset. The alert will show again if tampering is detected.", "success")
    else:
        flash("No alert flag to reset. The alert should be visible if tampering exists.", "info")
    
    return redirect(url_for("admin.dashboard"))


@bp.get("/renewal-reminders/auto")
def auto_send_renewal_reminders():
    """Automatic scheduled task for renewal reminders (called by cron job)"""
    from datetime import date, timedelta
    
    today = date.today()
    threshold = today + timedelta(days=7)  # 1 week before expiration
    reminder_cooldown = today - timedelta(days=3)  # Send every 3 days if still not renewed
    
    # Find tenants with contracts expiring in 7 days or less
    # AND haven't received a reminder in the last 3 days
    # AND DON'T have a pending or approved renewal request yet
    expiring_tenants = db.session.query(TenantProfile).filter(
        TenantProfile.contract_end.isnot(None),
        TenantProfile.contract_end <= threshold,
        TenantProfile.contract_end > today,
        TenantProfile.is_active == True,
        db.or_(
            TenantProfile.last_renewal_reminder_sent == None,
            TenantProfile.last_renewal_reminder_sent < reminder_cooldown
        )
    ).all()
    
    reminders_sent = 0
    for profile in expiring_tenants:
        # Check if tenant already has a pending or approved renewal request
        has_active_request = db.session.query(RenewalRequest).filter(
            RenewalRequest.tenant_profile_id == profile.id,
            RenewalRequest.status.in_([RenewalRequestStatus.PENDING, RenewalRequestStatus.APPROVED])
        ).first()
        
        if has_active_request:
            continue

        days_remaining = (profile.contract_end - today).days
        unit = db.session.get(Unit, profile.unit_id)
        
        if unit and profile.user:
            _send_renewal_reminder_email(
                tenant_name=profile.user.full_name,
                tenant_email=profile.user.email,
                unit_code=unit.unit_code,
                contract_end=profile.contract_end,
                days_remaining=days_remaining
            )
            profile.last_renewal_reminder_sent = today
            reminders_sent += 1
    
    db.session.commit()
    return {"status": "success", "reminders_sent": reminders_sent}, 200


@bp.get("/documents/export")
@login_required
def export_documents():
    _ensure_admin()
    import csv
    from io import StringIO
    from datetime import datetime

    documents = db.session.query(Document).order_by(Document.uploaded_at.desc()).all()

    output = StringIO()
    writer = csv.writer(output)

    # Header with Elis branding
    writer.writerow(["THE ELIS CENTER - Commercial and Residences"])
    writer.writerow(["Documents Report"])
    writer.writerow([f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"])
    writer.writerow([])  # Empty row

    # Column headers
    writer.writerow(["Title", "Document Type", "Tenant", "Unit", "Uploaded At"])

    for doc in documents:
        writer.writerow([
            doc.title,
            doc.document_type.replace('_', ' ').title(),
            doc.tenant_profile.user.full_name,
            doc.tenant_profile.unit.unit_code,
            doc.uploaded_at.strftime("%Y-%m-%d %H:%M:%S")
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=Elis_Documents_Report.csv"}
    )
    return response


@bp.get("/renewals")
@login_required
def renewals():
    _ensure_admin()
    from datetime import date, timedelta
    from sqlalchemy import func
    
    # Filters
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    building_filter = request.args.get('building', '')
    urgency_filter = request.args.get('urgency', '')
    sort_by = request.args.get('sort', 'newest')
    
    # Base query with eager loading
    from sqlalchemy.orm import joinedload
    query = db.session.query(RenewalRequest).options(
        joinedload(RenewalRequest.tenant_profile).joinedload(TenantProfile.user),
        joinedload(RenewalRequest.tenant_profile).joinedload(TenantProfile.unit).joinedload(Unit.building)
    )
    
    # Apply search filter
    if search_query:
        query = query.join(TenantProfile, TenantProfile.id == RenewalRequest.tenant_profile_id).join(User, User.id == TenantProfile.user_id).join(Unit, Unit.id == TenantProfile.unit_id).filter(
            db.or_(
                User.full_name.ilike(f"%{search_query}%"),
                Unit.unit_code.ilike(f"%{search_query}%")
            )
        )
    
    # Apply status filter
    if status_filter:
        query = query.filter(RenewalRequest.status == RenewalRequestStatus(status_filter))
    
    # Apply building filter
    if building_filter:
        if not search_query:
            query = query.join(TenantProfile, TenantProfile.id == RenewalRequest.tenant_profile_id).join(Unit, Unit.id == TenantProfile.unit_id)
        query = query.filter(Unit.building_id == int(building_filter))
    
    # Apply urgency filter (contracts expiring soon)
    if urgency_filter == 'urgent':
        today = date.today()
        urgent_date = today + timedelta(days=30)
        if not search_query and not building_filter:
            query = query.join(TenantProfile, TenantProfile.id == RenewalRequest.tenant_profile_id)
        query = query.filter(
            TenantProfile.contract_end.isnot(None),
            TenantProfile.contract_end <= urgent_date,
            TenantProfile.contract_end >= today
        )
    
    # Apply sorting
    if sort_by == 'oldest':
        query = query.order_by(RenewalRequest.created_at.asc())
    elif sort_by == 'contract_end':
        if not search_query and not building_filter and urgency_filter != 'urgent':
            query = query.join(TenantProfile, TenantProfile.id == RenewalRequest.tenant_profile_id)
        query = query.order_by(TenantProfile.contract_end.asc())
    elif sort_by == 'tenant_az':
        if not search_query:
            query = query.join(TenantProfile, TenantProfile.id == RenewalRequest.tenant_profile_id).join(User, User.id == TenantProfile.user_id)
        query = query.order_by(User.full_name.asc())
    else:  # newest (default)
        query = query.order_by(RenewalRequest.created_at.desc())
    
    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=15, error_out=False)
    renewal_requests = pagination.items

    # Statistics
    today = date.today()
    this_month_start = today.replace(day=1)
    urgent_date = today + timedelta(days=30)
    
    total_renewals = db.session.query(RenewalRequest).count()
    pending_count = db.session.query(RenewalRequest).filter(
        RenewalRequest.status == RenewalRequestStatus.PENDING
    ).count()
    approved_this_month = db.session.query(RenewalRequest).filter(
        RenewalRequest.status == RenewalRequestStatus.APPROVED,
        RenewalRequest.updated_at >= this_month_start
    ).count()
    rejected_count = db.session.query(RenewalRequest).filter(
        RenewalRequest.status == RenewalRequestStatus.REJECTED
    ).count()
    
    # Contracts expiring soon (30 days)
    expiring_soon = db.session.query(TenantProfile).filter(
        TenantProfile.contract_end.isnot(None),
        TenantProfile.contract_end <= urgent_date,
        TenantProfile.contract_end >= today,
        TenantProfile.is_active == True
    ).count()
    
    # Average renewal duration (in months)
    approved_renewals = db.session.query(RenewalRequest).filter(
        RenewalRequest.status == RenewalRequestStatus.APPROVED
    ).all()
    
    total_months = 0
    count = 0
    for renewal in approved_renewals:
        if renewal.tenant_profile.contract_end and renewal.requested_end_date:
            # Calculate months difference
            months_diff = (renewal.requested_end_date.year - renewal.tenant_profile.contract_end.year) * 12
            months_diff += renewal.requested_end_date.month - renewal.tenant_profile.contract_end.month
            if months_diff > 0:
                total_months += months_diff
                count += 1
    
    avg_duration = round(total_months / count, 1) if count > 0 else 0
    
    stats = {
        'total': total_renewals,
        'pending': pending_count,
        'approved_this_month': approved_this_month,
        'rejected': rejected_count,
        'expiring_soon': expiring_soon,
        'avg_duration': avg_duration
    }
    
    # Get tenants with expiring contracts (for suggestions)
    expiring_tenants = db.session.query(TenantProfile).filter(
        TenantProfile.contract_end.isnot(None),
        TenantProfile.contract_end <= urgent_date,
        TenantProfile.contract_end >= today,
        TenantProfile.is_active == True
    ).order_by(TenantProfile.contract_end.asc()).all()
    
    # Check which expiring tenants already have pending requests
    expiring_tenant_ids = [t.id for t in expiring_tenants]
    pending_renewal_tenant_ids = [
        r.tenant_profile_id for r in db.session.query(RenewalRequest).filter(
            RenewalRequest.tenant_profile_id.in_(expiring_tenant_ids),
            RenewalRequest.status == RenewalRequestStatus.PENDING
        ).all()
    ]
    
    # Filter out tenants who already have pending requests
    expiring_without_request = [t for t in expiring_tenants if t.id not in pending_renewal_tenant_ids]
    
    buildings = db.session.query(Building).order_by(Building.code.asc()).all()
    
    return render_template(
        "admin/renewals.html",
        renewal_requests=renewal_requests,
        pagination=pagination,
        stats=stats,
        buildings=buildings,
        expiring_without_request=expiring_without_request,
        today=today
    )


@bp.get("/renewals/export")
@login_required
def export_renewals():
    _ensure_admin()
    import csv
    from io import StringIO
    from datetime import datetime

    renewal_requests = db.session.query(RenewalRequest).order_by(RenewalRequest.created_at.desc()).all()

    output = StringIO()
    writer = csv.writer(output)

    # Header with Elis branding
    writer.writerow(["THE ELIS CENTER - Commercial and Residences"])
    writer.writerow(["Renewal Requests Report"])
    writer.writerow([f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"])
    writer.writerow([])  # Empty row

    # Column headers
    writer.writerow(["Tenant", "Unit", "Current Contract End", "Requested End Date", "Status", "Notes", "Created At"])

    for r in renewal_requests:
        writer.writerow([
            r.tenant_profile.user.full_name,
            r.tenant_profile.unit.unit_code,
            r.tenant_profile.contract_end.strftime("%Y-%m-%d") if r.tenant_profile.contract_end else "",
            r.requested_end_date.strftime("%Y-%m-%d"),
            r.status.value.title(),
            r.notes or "",
            r.created_at.strftime("%Y-%m-%d %H:%M:%S")
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=Elis_Renewals_Report.csv"}
    )
    return response


@bp.post("/renewals/<int:renewal_id>/approve")
@login_required
def approve_renewal(renewal_id: int):
    _ensure_admin()
    renewal = db.session.get(RenewalRequest, renewal_id)
    if not renewal:
        abort(404)

    # Update tenant contract end date
    profile = db.session.get(TenantProfile, renewal.tenant_profile_id)
    if not profile:
        flash("Cannot approve — this renewal request has no linked tenant profile. Nothing was changed.", "danger")
        return redirect(url_for("admin.renewals"))

    renewal.status = RenewalRequestStatus.APPROVED
    old_end_date = profile.contract_end
    profile.contract_end = renewal.requested_end_date
    profile.is_active = True

    # Re-activate unit if it was auto-expired
    unit = db.session.get(Unit, profile.unit_id)
    if unit and unit.status == UnitStatus.AVAILABLE:
        unit.status = UnitStatus.OCCUPIED

    # Update original reservation move_out_date so deposit module stays accurate
    reservation = (
        db.session.query(Reservation)
        .filter(
            Reservation.user_id == profile.user_id,
            Reservation.unit_id == profile.unit_id,
            Reservation.status == ReservationStatus.APPROVED
        )
        .order_by(Reservation.created_at.desc())
        .first()
    )
    if reservation:
        reservation.move_out_date = renewal.requested_end_date

    # Send email notification
    _send_renewal_result_email(
        tenant_name=profile.user.full_name,
        tenant_email=profile.user.email,
        unit_code=profile.unit.unit_code,
        status='approved',
        old_end_date=old_end_date,
        new_end_date=renewal.requested_end_date
    )

    db.session.commit()
    flash(f"Renewal request approved and email sent to {profile.user.full_name}.", "success")
    return redirect(url_for("admin.renewals"))


@bp.post("/renewals/<int:renewal_id>/reject")
@login_required
def reject_renewal(renewal_id: int):
    _ensure_admin()
    renewal = db.session.get(RenewalRequest, renewal_id)
    if not renewal:
        abort(404)

    renewal.status = RenewalRequestStatus.REJECTED
    
    # Send email notification
    profile = renewal.tenant_profile
    _send_renewal_result_email(
        tenant_name=profile.user.full_name,
        tenant_email=profile.user.email,
        unit_code=profile.unit.unit_code,
        status='rejected',
        old_end_date=profile.contract_end,
        new_end_date=renewal.requested_end_date
    )
    
    db.session.commit()
    flash(f"Renewal request rejected and email sent to {profile.user.full_name}.", "info")
    return redirect(url_for("admin.renewals"))


def _send_renewal_result_email(tenant_name: str, tenant_email: str, unit_code: str, status: str, old_end_date, new_end_date) -> None:
    """Send email notification when renewal request is approved or rejected using Brevo HTTP API"""
    if not tenant_email:
        return
    
    from ...email_helper import send_renewal_result_email

    send_renewal_result_email(tenant_name, tenant_email, unit_code, status, old_end_date, new_end_date)


@bp.post("/move-out-notices/<int:notice_id>/respond")
@login_required
def respond_move_out_notice(notice_id: int):
    """Admin acknowledges a move-out notice, optionally replies with a
    message and/or corrects the planned date if the tenant's plan changed
    (e.g. they said half-month notice but are actually leaving full-month).
    Every edit is appended to admin_response so there's a visible trail."""
    _ensure_admin()
    notice = db.session.get(MoveOutNotice, notice_id)
    if not notice:
        abort(404)

    message = (request.form.get("message") or "").strip()
    new_date_str = (request.form.get("planned_move_out_date") or "").strip()

    log_lines = []
    if new_date_str:
        try:
            new_date = date.fromisoformat(new_date_str)
        except ValueError:
            flash("Invalid date format.", "warning")
            return redirect(url_for("admin.tenant_monitoring"))
        if new_date != notice.planned_move_out_date:
            log_lines.append(
                f"[{datetime.utcnow().strftime('%b %d, %Y')}] Date updated from "
                f"{notice.planned_move_out_date.strftime('%b %d, %Y')} to {new_date.strftime('%b %d, %Y')} by admin."
            )
            notice.planned_move_out_date = new_date

    if message:
        log_lines.append(message)

    if log_lines:
        notice.admin_response = ((notice.admin_response + "\n\n") if notice.admin_response else "") + "\n".join(log_lines)
    notice.admin_response_at = datetime.utcnow()
    notice.admin_response_by = current_user.id  # type: ignore[attr-defined]
    if notice.status == MoveOutNoticeStatus.PENDING:
        notice.status = MoveOutNoticeStatus.ACKNOWLEDGED

    db.session.commit()
    flash("Move-out notice updated.", "success")
    return redirect(url_for("admin.tenant_monitoring"))


@bp.post("/move-out-notices/<int:notice_id>/cancel")
@login_required
def cancel_move_out_notice_admin(notice_id: int):
    """Admin cancels a notice on the tenant's behalf (e.g. tenant called to
    say they're staying after all)."""
    _ensure_admin()
    notice = db.session.get(MoveOutNotice, notice_id)
    if not notice:
        abort(404)

    notice.status = MoveOutNoticeStatus.CANCELLED
    notice.admin_response = (
        (notice.admin_response + "\n\n") if notice.admin_response else ""
    ) + f"[{datetime.utcnow().strftime('%b %d, %Y')}] Cancelled by admin — tenant is staying."
    notice.admin_response_at = datetime.utcnow()
    notice.admin_response_by = current_user.id  # type: ignore[attr-defined]
    db.session.commit()

    flash("Move-out notice cancelled.", "success")
    return redirect(url_for("admin.tenant_monitoring"))


@bp.post("/tenants/<int:profile_id>/process-move-out")
@login_required
def process_move_out(profile_id: int):
    """Finalize a tenant's move-out: frees the unit, deactivates the
    profile, and — based on the actual move-out date — either applies a
    half/full month deduction to the security deposit (informed after the
    final cycle's due date already passed unpaid) or leaves it as a
    recommendation for a normal reduced final payment (informed in
    advance). See _compute_final_month_charge for the exact rule."""
    _ensure_admin()
    profile = db.session.get(TenantProfile, profile_id)
    if not profile:
        abort(404)

    move_out_date_str = (request.form.get("actual_move_out_date") or "").strip()
    if not move_out_date_str:
        flash("Please provide the actual move-out date.", "warning")
        return redirect(url_for("admin.tenant_monitoring"))
    try:
        actual_move_out_date = date.fromisoformat(move_out_date_str)
    except ValueError:
        flash("Invalid date format.", "warning")
        return redirect(url_for("admin.tenant_monitoring"))

    charge = _compute_final_month_charge(profile, actual_move_out_date)

    unit = db.session.get(Unit, profile.unit_id)
    user = db.session.get(User, profile.user_id)

    # Apply the deposit deduction only when the charge is late (unpaid,
    # due date already passed) — early-notice amounts are just shown to
    # admin as a heads-up; they're collected as a normal payment instead.
    deduction_applied = None
    if charge["needs_charge"] and charge["is_late"]:
        reservation = (
            db.session.query(Reservation)
            .filter(
                Reservation.user_id == profile.user_id,
                Reservation.unit_id == profile.unit_id,
                Reservation.status == ReservationStatus.APPROVED,
            )
            .order_by(Reservation.created_at.desc())
            .first()
        )
        if reservation:
            import json as _json
            # Read through the model's parser, which understands both the
            # JSON form and the display text this code used to write.
            deductions = [dict(d) for d in reservation.deduction_entries]
            reason = (
                f"Final month charge ({charge['half_or_full']} month, notified after due date) "
                f"— moved out {actual_move_out_date.strftime('%b %d, %Y')}"
            )
            deductions.append({
                "amount": charge["amount"],
                "reason": reason,
                "date": date.today().isoformat(),
            })
            total_deductions = sum(float(d["amount"]) for d in deductions if d.get("amount"))
            # Store JSON, not the text it happens to be displayed as. Writing
            # the rendered lines back made every earlier deduction unreadable
            # — the amounts were only recoverable by parsing prose.
            reservation.deposit_deductions = _json.dumps(deductions)
            return_amount = float(reservation.deposit_amount) - total_deductions
            reservation.deposit_return_amount = max(0, return_amount)
            reservation.deposit_status = "full_return" if total_deductions >= float(reservation.deposit_amount) else "partial_return"
            deduction_applied = charge["amount"]

    # Close out any active move-out notice for this tenant.
    active_notice = (
        db.session.query(MoveOutNotice)
        .filter(
            MoveOutNotice.tenant_profile_id == profile.id,
            MoveOutNotice.status.in_([MoveOutNoticeStatus.PENDING, MoveOutNoticeStatus.ACKNOWLEDGED]),
        )
        .first()
    )
    if active_notice:
        active_notice.status = MoveOutNoticeStatus.COMPLETED
        active_notice.planned_move_out_date = actual_move_out_date

    profile.is_active = False
    profile.contract_end = actual_move_out_date
    if unit and unit.status in (UnitStatus.OCCUPIED, UnitStatus.UNPAID):
        unit.status = UnitStatus.AVAILABLE

    # Archive the user account — same convention used when a tenant with an
    # expired commercial contract is archived from the Users page. Keeps
    # them out of active tenant lists everywhere, but their full record
    # (profile, payments, deductions) stays intact and is findable via
    # Users > Archived, instead of piling up in a brand-new list.
    if user:
        user.is_archived = True
        user.archived_at = datetime.utcnow()
        user.archive_reason = f"Moved out — {actual_move_out_date.strftime('%b %d, %Y')}"
        user.role = Role.USER

    db.session.add(ActivityLog(
        actor_user_id=current_user.id,  # type: ignore[attr-defined]
        action=f"tenant_moved_out:{profile.id}",
    ))
    db.session.commit()

    if deduction_applied:
        flash(
            f"{user.full_name if user else 'Tenant'} marked as moved out on {actual_move_out_date.strftime('%b %d, %Y')}. "
            f"₱{deduction_applied:.2f} ({charge['half_or_full']} month) deducted from security deposit.",
            "success",
        )
    elif charge["needs_charge"]:
        flash(
            f"{user.full_name if user else 'Tenant'} marked as moved out on {actual_move_out_date.strftime('%b %d, %Y')}. "
            f"Recommended final payment: ₱{charge['amount']:.2f} ({charge['half_or_full']} month) — record it via Payments when collected.",
            "info",
        )
    else:
        flash(
            f"{user.full_name if user else 'Tenant'} marked as moved out on {actual_move_out_date.strftime('%b %d, %Y')}. "
            f"Final billing cycle was already paid in full — no additional charge.",
            "success",
        )
    return redirect(url_for("admin.tenant_monitoring"))


@bp.get("/move-outs")
@login_required
def move_out_history():
    """Everyone who has left, and how their deposit was settled.

    Nothing here is new information — a move-out already deactivates the
    profile, closes the notice, archives the user and writes the deposit
    outcome onto the reservation. It simply had nowhere to be read. Once a
    tenant is archived they drop out of every active list, so the record of
    what was charged and what was returned became unreachable in the
    interface even though it was never deleted.
    """
    _ensure_admin()

    departed = (
        db.session.query(TenantProfile)
        .options(joinedload(TenantProfile.user), joinedload(TenantProfile.unit))
        .filter(db.or_(TenantProfile.is_active.is_(False),
                       TenantProfile.moved_out_on.isnot(None)))
        .order_by(TenantProfile.contract_end.desc().nullslast(),
                  TenantProfile.id.desc())
        .all()
    )

    # One query for the notices rather than one per tenant.
    notices = {}
    if departed:
        for n in (db.session.query(MoveOutNotice)
                  .filter(MoveOutNotice.tenant_profile_id.in_([p.id for p in departed]))
                  .order_by(MoveOutNotice.created_at.desc()).all()):
            notices.setdefault(n.tenant_profile_id, n)

    reservations = {}
    if departed:
        for r in (db.session.query(Reservation)
                  .filter(Reservation.user_id.in_([p.user_id for p in departed]),
                          Reservation.status == ReservationStatus.APPROVED)
                  .order_by(Reservation.created_at.desc()).all()):
            reservations.setdefault((r.user_id, r.unit_id), r)

    rows = []
    for p in departed:
        r = reservations.get((p.user_id, p.unit_id))
        n = notices.get(p.id)
        deposit = float(r.deposit_amount) if r and r.deposit_amount else 0.0
        returned = float(r.deposit_return_amount) if r and r.deposit_return_amount is not None else None
        deducted = float(r.total_deducted) if r else 0.0
        rows.append({
            "profile": p, "user": p.user, "unit": p.unit,
            "moved_out": p.moved_out_on or p.contract_end,
            "notice": n,
            "notice_days": ((p.moved_out_on or p.contract_end) - n.original_move_out_date).days
                           if n and (p.moved_out_on or p.contract_end) else None,
            "reservation": r,
            "deposit": deposit,
            "deducted": deducted,
            "returned": returned,
            "settled_on": r.deposit_return_date if r else None,
            "deductions": r.deduction_entries if r else [],
            "notes": r.deposit_notes if r else None,
        })

    settled = [x for x in rows if x["settled_on"]]
    totals = {
        "departed": len(rows),
        "settled": len(settled),
        "unsettled": len(rows) - len(settled),
        "deposit": sum(x["deposit"] for x in settled),
        "deducted": sum(x["deducted"] for x in settled),
        "returned": sum(x["returned"] or 0 for x in settled),
    }
    return render_template("admin/move_out_history.html", rows=rows, totals=totals)


@bp.get("/feedbacks")
@login_required
def feedbacks():
    _ensure_admin()
    from datetime import date, timedelta
    from sqlalchemy import func
    from sqlalchemy.orm import joinedload
    
    # Filters
    search_query = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '')
    rating_filter = request.args.get('rating', '')
    status_filter = request.args.get('status', '')
    building_filter = request.args.get('building', '')
    sort_by = request.args.get('sort', 'newest')
    
    # Base query with eager loading
    query = db.session.query(Feedback).options(
        joinedload(Feedback.tenant_profile).joinedload(TenantProfile.user),
        joinedload(Feedback.tenant_profile).joinedload(TenantProfile.unit).joinedload(Unit.building)
    )
    
    # Apply search filter
    if search_query:
        query = query.join(TenantProfile, TenantProfile.id == Feedback.tenant_profile_id).join(User, User.id == TenantProfile.user_id).join(Unit, Unit.id == TenantProfile.unit_id).filter(
            db.or_(
                User.full_name.ilike(f"%{search_query}%"),
                Unit.unit_code.ilike(f"%{search_query}%"),
                Feedback.comments.ilike(f"%{search_query}%")
            )
        )
    
    # Apply category filter
    if category_filter:
        query = query.filter(Feedback.category == category_filter)
    
    # Apply rating filter
    if rating_filter:
        if rating_filter == 'no_rating':
            query = query.filter(Feedback.rating.is_(None))
        else:
            query = query.filter(Feedback.rating == int(rating_filter))
    
    # Apply status filter
    if status_filter:
        query = query.filter(Feedback.status == FeedbackStatus(status_filter))
    
    # Apply building filter
    if building_filter:
        if not search_query:
            query = query.join(TenantProfile, TenantProfile.id == Feedback.tenant_profile_id).join(Unit, Unit.id == TenantProfile.unit_id)
        query = query.filter(Unit.building_id == int(building_filter))
    
    # Apply sorting
    if sort_by == 'oldest':
        query = query.order_by(Feedback.created_at.asc())
    elif sort_by == 'rating_high':
        query = query.order_by(Feedback.rating.desc().nullslast())
    elif sort_by == 'rating_low':
        query = query.order_by(Feedback.rating.asc().nullsfirst())
    elif sort_by == 'tenant_az':
        if not search_query:
            query = query.join(TenantProfile, TenantProfile.id == Feedback.tenant_profile_id).join(User, User.id == TenantProfile.user_id)
        query = query.order_by(User.full_name.asc())
    else:  # newest (default)
        query = query.order_by(Feedback.created_at.desc())
    
    # flagged_count needs to cover every feedback matching the current
    # filters (not just the current page), so it's computed against the
    # full filtered set before paginating the actual page of results.
    from ...ai_utils import analyze_sentiment
    flagged_count = sum(1 for f in query.all() if analyze_sentiment(f.comments, f.rating)["flag"])

    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=15, error_out=False)
    feedbacks = pagination.items

    # AI sentiment analysis (rule-based, bilingual) per feedback on this page
    sentiments = {f.id: analyze_sentiment(f.comments, f.rating) for f in feedbacks}

    # Statistics
    today = date.today()
    this_month_start = today.replace(day=1)
    
    total_feedbacks = db.session.query(Feedback).count()
    submitted_count = db.session.query(Feedback).filter(
        Feedback.status == FeedbackStatus.SUBMITTED
    ).count()
    reviewed_count = db.session.query(Feedback).filter(
        Feedback.status == FeedbackStatus.REVIEWED
    ).count()
    this_month_count = db.session.query(Feedback).filter(
        Feedback.created_at >= this_month_start
    ).count()
    
    # Average rating
    avg_rating = db.session.query(func.avg(Feedback.rating)).filter(
        Feedback.rating.isnot(None)
    ).scalar()
    avg_rating = round(float(avg_rating), 1) if avg_rating else 0
    
    # Rating distribution
    rating_dist = {}
    for i in range(1, 6):
        count = db.session.query(Feedback).filter(Feedback.rating == i).count()
        rating_dist[i] = count
    
    no_rating_count = db.session.query(Feedback).filter(Feedback.rating.is_(None)).count()
    rating_dist['no_rating'] = no_rating_count
    
    # Feedback by category
    category_counts = db.session.query(
        Feedback.category,
        func.count(Feedback.id)
    ).group_by(Feedback.category).all()
    
    category_stats = {cat: count for cat, count in category_counts}
    
    # Satisfaction score (% of 4-5 star ratings)
    total_with_rating = db.session.query(Feedback).filter(Feedback.rating.isnot(None)).count()
    positive_ratings = db.session.query(Feedback).filter(Feedback.rating >= 4).count()
    satisfaction_score = round((positive_ratings / total_with_rating * 100), 1) if total_with_rating > 0 else 0
    
    stats = {
        'total': total_feedbacks,
        'submitted': submitted_count,
        'reviewed': reviewed_count,
        'this_month': this_month_count,
        'avg_rating': avg_rating,
        'rating_dist': rating_dist,
        'category_stats': category_stats,
        'satisfaction_score': satisfaction_score
    }
    
    buildings = db.session.query(Building).order_by(Building.code.asc()).all()
    
    # Get unique categories from database
    categories = db.session.query(Feedback.category).distinct().all()
    categories = [cat[0] for cat in categories]
    
    return render_template(
        "admin/feedbacks.html",
        feedbacks=feedbacks,
        pagination=pagination,
        stats=stats,
        buildings=buildings,
        categories=categories,
        today=today,
        sentiments=sentiments,
        flagged_count=flagged_count,
    )


@bp.get("/feedbacks/export")
@login_required
def export_feedbacks():
    _ensure_admin()
    import csv
    from io import StringIO
    from datetime import datetime

    feedbacks = db.session.query(Feedback).order_by(Feedback.created_at.desc()).all()

    output = StringIO()
    writer = csv.writer(output)

    # Header with Elis branding
    writer.writerow(["THE ELIS CENTER - Commercial and Residences"])
    writer.writerow(["Feedback Report"])
    writer.writerow([f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"])
    writer.writerow([])  # Empty row

    # Column headers
    writer.writerow(["Tenant", "Unit", "Category", "Rating", "Comments", "Status", "Created At"])

    for f in feedbacks:
        writer.writerow([
            f.tenant_profile.user.full_name,
            f.tenant_profile.unit.unit_code,
            f.category,
            f.rating or "",
            f.comments,
            f.status.value,
            f.created_at.strftime("%Y-%m-%d %H:%M:%S")
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=Elis_Feedback_Report.csv"}
    )
    return response


@bp.post("/feedbacks/<int:feedback_id>/review")
@login_required
def review_feedback(feedback_id: int):
    _ensure_admin()
    feedback = db.session.get(Feedback, feedback_id)
    if not feedback:
        abort(404)

    admin_response = (request.form.get("admin_response") or "").strip()
    
    feedback.status = FeedbackStatus.REVIEWED
    
    if admin_response:
        feedback.admin_response = admin_response
        feedback.admin_response_at = datetime.utcnow()
        feedback.admin_response_by = current_user.id  # type: ignore[attr-defined]
    
    db.session.commit()
    
    if admin_response:
        flash(f"Feedback reviewed and response added.", "success")
    else:
        flash(f"Feedback marked as reviewed.", "success")
    
    return redirect(url_for("admin.feedbacks"))


@bp.post("/feedbacks/<int:feedback_id>/delete")
@login_required
def delete_feedback(feedback_id: int):
    _ensure_admin()
    feedback = db.session.get(Feedback, feedback_id)
    if not feedback:
        abort(404)

    db.session.delete(feedback)
    db.session.commit()
    flash("Feedback deleted.", "success")
    return redirect(url_for("admin.feedbacks"))


@bp.get("/concerns")
@login_required
def concerns():
    _ensure_admin()
    from sqlalchemy import func, or_
    
    # Get filter parameters
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    category_filter = request.args.get('category', '')
    
    # Base query
    query = (db.session.query(Concern)
             .join(TenantProfile, TenantProfile.id == Concern.tenant_profile_id)
             .join(User, User.id == TenantProfile.user_id)
             .join(Unit, Unit.id == TenantProfile.unit_id))
    
    # Apply search filter
    if search_query:
        query = query.filter(
            or_(
                User.full_name.ilike(f"%{search_query}%"),
                Unit.unit_code.ilike(f"%{search_query}%"),
                Concern.subject.ilike(f"%{search_query}%"),
                Concern.description.ilike(f"%{search_query}%")
            )
        )
    
    # Apply status filter
    if status_filter:
        query = query.filter(Concern.status == ConcernStatus(status_filter))
    
    # Apply priority filter
    if priority_filter:
        query = query.filter(Concern.priority == priority_filter)
    
    # Apply category filter
    if category_filter:
        query = query.filter(Concern.category == category_filter)
    
    # Order by priority (urgent first) then by created date
    priority_order = db.case(
        (Concern.priority == 'urgent', 1),
        (Concern.priority == 'high', 2),
        (Concern.priority == 'medium', 3),
        (Concern.priority == 'low', 4),
        else_=5
    )
    query = query.order_by(priority_order, Concern.created_at.desc())
    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=15, error_out=False)
    concerns = pagination.items

    # Calculate statistics
    total = db.session.query(Concern).count()
    pending = db.session.query(Concern).filter(Concern.status == ConcernStatus.PENDING).count()
    in_progress = db.session.query(Concern).filter(Concern.status == ConcernStatus.IN_PROGRESS).count()
    resolved = db.session.query(Concern).filter(Concern.status == ConcernStatus.RESOLVED).count()
    urgent_count = db.session.query(Concern).filter(Concern.priority == 'urgent').count()
    
    # Calculate average resolution time
    resolved_concerns = db.session.query(Concern).filter(Concern.status == ConcernStatus.RESOLVED).all()
    if resolved_concerns:
        total_days = sum([(c.updated_at - c.created_at).days for c in resolved_concerns if c.updated_at])
        avg_resolution_days = total_days / len(resolved_concerns) if resolved_concerns else 0
    else:
        avg_resolution_days = 0
    
    # Calculate response rate (concerns with admin response)
    total_concerns = db.session.query(Concern).count()
    responded_concerns = db.session.query(Concern).filter(Concern.admin_response.isnot(None)).count()
    response_rate = round((responded_concerns / total_concerns * 100), 1) if total_concerns > 0 else 0
    
    # Category statistics
    category_stats = db.session.query(
        Concern.category,
        func.count(Concern.id).label('count')
    ).group_by(Concern.category).order_by(func.count(Concern.id).desc()).all()
    
    stats = {
        'total': total,
        'pending': pending,
        'in_progress': in_progress,
        'resolved': resolved,
        'avg_resolution_days': avg_resolution_days,
        'response_rate': response_rate,
        'urgent_count': urgent_count
    }
    
    return render_template(
        "admin/concerns.html",
        concerns=concerns,
        pagination=pagination,
        stats=stats,
        category_stats=category_stats
    )


@bp.get("/concerns/export")
@login_required
def export_concerns():
    _ensure_admin()
    import csv
    from io import StringIO
    from datetime import datetime

    concerns = db.session.query(Concern).order_by(Concern.created_at.desc()).all()

    output = StringIO()
    writer = csv.writer(output)

    # Header with Elis branding
    writer.writerow(["THE ELIS CENTER - Commercial and Residences"])
    writer.writerow(["Concerns Report"])
    writer.writerow([f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"])
    writer.writerow([])  # Empty row

    # Column headers
    writer.writerow([
        "Tenant", "Unit", "Subject", "Description", "Status", "Priority", "Category",
        "Admin Response", "Responded By", "Response Date",
        "Created At", "Updated At"
    ])

    for c in concerns:
        writer.writerow([
            c.tenant_profile.user.full_name,
            c.tenant_profile.unit.unit_code,
            c.subject,
            c.description,
            c.status.value.title(),
            c.priority.title(),
            c.category.title(),
            c.admin_response or "",
            c.responder.full_name if c.responder else "",
            c.admin_response_at.strftime("%Y-%m-%d %H:%M:%S") if c.admin_response_at else "",
            c.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            c.updated_at.strftime("%Y-%m-%d %H:%M:%S") if c.updated_at else ""
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=Elis_Concerns_Report.csv"}
    )
    return response


@bp.post("/concerns/<int:concern_id>/update")
@login_required
def update_concern(concern_id: int):
    _ensure_admin()
    concern = db.session.get(Concern, concern_id)
    if not concern:
        abort(404)

    new_status = request.form.get("status")
    new_priority = request.form.get("priority")
    send_email = request.form.get("send_email") == "1"
    
    # Track status changes for timeline
    old_status = concern.status
    
    if new_status and new_status in [s.value for s in ConcernStatus]:
        concern.status = ConcernStatus(new_status)
        
        # Update timeline timestamps
        if concern.status == ConcernStatus.IN_PROGRESS and old_status != ConcernStatus.IN_PROGRESS:
            if not concern.in_progress_at:
                concern.in_progress_at = datetime.utcnow()
        elif concern.status == ConcernStatus.RESOLVED and old_status != ConcernStatus.RESOLVED:
            if not concern.resolved_at:
                concern.resolved_at = datetime.utcnow()
    
    if new_priority and new_priority in ['low', 'medium', 'high', 'urgent']:
        concern.priority = new_priority
    
    db.session.commit()
    
    # Send email notification if requested
    if send_email:
        _send_concern_status_email(
            tenant_name=concern.tenant_profile.user.full_name,
            tenant_email=concern.tenant_profile.user.email,
            subject=concern.subject,
            status=concern.status.value,
            unit_code=concern.tenant_profile.unit.unit_code
        )
    
    flash("Concern updated successfully.", "success")
    return redirect(url_for("admin.concerns"))


@bp.post("/concerns/<int:concern_id>/respond")
@login_required
def respond_concern(concern_id: int):
    _ensure_admin()
    concern = db.session.get(Concern, concern_id)
    if not concern:
        abort(404)

    admin_response = request.form.get("admin_response", "").strip()
    send_email = request.form.get("send_email") == "1"
    
    if not admin_response:
        flash("Response cannot be empty.", "warning")
        return redirect(url_for("admin.concerns"))
    
    concern.admin_response = admin_response
    concern.admin_response_at = datetime.utcnow()
    concern.admin_response_by = current_user.id  # type: ignore[attr-defined]
    
    db.session.commit()
    
    # Send email notification if requested
    if send_email:
        _send_concern_response_email(
            tenant_name=concern.tenant_profile.user.full_name,
            tenant_email=concern.tenant_profile.user.email,
            subject=concern.subject,
            admin_response=admin_response,
            unit_code=concern.tenant_profile.unit.unit_code
        )
    
    flash("Response added successfully.", "success")
    return redirect(url_for("admin.concerns"))


def _send_concern_status_email(tenant_name: str, tenant_email: str, subject: str, status: str, unit_code: str) -> None:
    """Send email notification when concern status is updated using Brevo HTTP API"""
    if not tenant_email:
        return
    
    from ...email_helper import send_concern_status_update_email
    
    # Convert status to display format
    status_text = status.replace('_', ' ').title()
    
    send_concern_status_update_email(tenant_name, tenant_email, subject, status_text, unit_code)


def _send_concern_response_email(tenant_name: str, tenant_email: str, subject: str, admin_response: str, unit_code: str) -> None:
    """Send email notification when admin responds to a concern using Brevo HTTP API"""
    if not tenant_email:
        return
    
    from ...email_helper import send_concern_response_email
    
    send_concern_response_email(tenant_name, tenant_email, subject, admin_response, unit_code)



# ============================================================================
# INQUIRIES MANAGEMENT
# ============================================================================

@bp.get("/inquiries")
@login_required
def inquiries():
    """View all inquiries from homepage contact form"""
    _ensure_admin()
    
    from ...models import Inquiry, InquiryStatus
    
    # Filters
    status_filter = request.args.get('status', '')
    search_query = request.args.get('search', '').strip()
    
    # Base query
    query = db.session.query(Inquiry)
    
    # Apply status filter
    if status_filter:
        query = query.filter(Inquiry.status == InquiryStatus(status_filter))
    
    # Apply search filter (name, email, subject)
    if search_query:
        query = query.filter(
            db.or_(
                Inquiry.full_name.ilike(f"%{search_query}%"),
                Inquiry.email.ilike(f"%{search_query}%"),
                Inquiry.subject.ilike(f"%{search_query}%")
            )
        )
    
    query = query.order_by(Inquiry.created_at.desc())
    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=25, error_out=False)
    inquiries = pagination.items

    # Statistics
    total_inquiries = db.session.query(Inquiry).count()
    pending_count = db.session.query(Inquiry).filter(Inquiry.status == InquiryStatus.PENDING).count()
    responded_count = db.session.query(Inquiry).filter(Inquiry.status == InquiryStatus.RESPONDED).count()
    contacted_count = db.session.query(Inquiry).filter(Inquiry.status == InquiryStatus.CONTACTED).count()
    
    stats = {
        'total': total_inquiries,
        'pending': pending_count,
        'responded': responded_count,
        'contacted': contacted_count
    }
    
    return render_template("admin/inquiries.html", inquiries=inquiries, pagination=pagination, stats=stats)


@bp.get("/inquiries/<int:inquiry_id>")
@login_required
def inquiry_details(inquiry_id: int):
    """View inquiry details and replies"""
    _ensure_admin()
    
    from ...models import Inquiry
    
    inquiry = db.session.get(Inquiry, inquiry_id)
    if not inquiry:
        abort(404)
    
    return render_template("admin/inquiry_details.html", inquiry=inquiry)


@bp.post("/inquiries/<int:inquiry_id>/reply")
@login_required
def reply_inquiry(inquiry_id: int):
    """Send reply to an inquiry"""
    _ensure_admin()
    
    from ...models import Inquiry, InquiryReply, InquiryStatus
    
    inquiry = db.session.get(Inquiry, inquiry_id)
    if not inquiry:
        abort(404)
    
    message = (request.form.get("message") or "").strip()
    
    if not message:
        flash("Reply message cannot be empty.", "warning")
        return redirect(url_for("admin.inquiry_details", inquiry_id=inquiry_id))
    
    # Create reply
    reply = InquiryReply(
        inquiry_id=inquiry_id,
        admin_user_id=current_user.id,  # type: ignore[attr-defined]
        message=message
    )
    db.session.add(reply)
    
    # Update inquiry status to responded
    inquiry.status = InquiryStatus.RESPONDED
    inquiry.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    # Send email to inquirer
    _send_inquiry_reply_email(
        inquirer_name=inquiry.full_name,
        inquirer_email=inquiry.email,
        subject=inquiry.subject,
        admin_reply=message,
        admin_name=current_user.full_name  # type: ignore[attr-defined]
    )
    
    flash("Reply sent successfully.", "success")
    return redirect(url_for("admin.inquiry_details", inquiry_id=inquiry_id))


@bp.post("/inquiries/<int:inquiry_id>/status")
@login_required
def update_inquiry_status(inquiry_id: int):
    """Update inquiry status"""
    _ensure_admin()
    
    from ...models import Inquiry, InquiryStatus
    
    inquiry = db.session.get(Inquiry, inquiry_id)
    if not inquiry:
        abort(404)
    
    new_status = request.form.get("status")
    
    if not new_status or new_status not in [s.value for s in InquiryStatus]:
        flash("Invalid status.", "warning")
        return redirect(url_for("admin.inquiry_details", inquiry_id=inquiry_id))
    
    inquiry.status = InquiryStatus(new_status)
    inquiry.updated_at = datetime.utcnow()
    db.session.commit()
    
    flash(f"Inquiry status updated to {new_status}.", "success")
    return redirect(url_for("admin.inquiry_details", inquiry_id=inquiry_id))


@bp.get("/inquiries/export")
@login_required
def export_inquiries():
    """Export inquiries to CSV"""
    _ensure_admin()
    
    from ...models import Inquiry
    import csv
    from io import StringIO
    
    inquiries = db.session.query(Inquiry).order_by(Inquiry.created_at.desc()).all()
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['ID', 'Full Name', 'Email', 'Phone', 'Subject', 'Message', 'Status', 'Created At', 'Updated At'])
    
    # Write data
    for inquiry in inquiries:
        writer.writerow([
            inquiry.id,
            inquiry.full_name,
            inquiry.email,
            inquiry.phone or '',
            inquiry.subject,
            inquiry.message,
            inquiry.status.value,
            inquiry.created_at.strftime('%Y-%m-%d %H:%M:%S') if inquiry.created_at else '',
            inquiry.updated_at.strftime('%Y-%m-%d %H:%M:%S') if inquiry.updated_at else ''
        ])
    
    # Create response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=inquiries_{date.today().strftime("%Y%m%d")}.csv'}
    )


def _send_inquiry_reply_email(inquirer_name: str, inquirer_email: str, subject: str, admin_reply: str, admin_name: str) -> None:
    """Send email notification when admin replies to an inquiry using Brevo HTTP API"""
    if not inquirer_email:
        return
    
    from ...email_helper import send_inquiry_response_email
    
    send_inquiry_response_email(inquirer_name, inquirer_email, subject, admin_reply)
