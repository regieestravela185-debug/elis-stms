from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for, Response
from flask_login import current_user, login_required
from dateutil.relativedelta import relativedelta

from ...extensions import db
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
    VerificationStatus,
)
from ...security import sha256_hex
from ...predictive_analytics import update_tenant_risk_profile
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
    """Global admin search across customers, units, reservations, payments."""
    _ensure_admin()
    from flask import jsonify
    from sqlalchemy import or_

    q = (request.args.get("q") or "").strip()
    results = {"customers": [], "units": [], "reservations": [], "payments": []}
    if len(q) < 2:
        return jsonify(results)
    like = f"%{q}%"

    for u in (db.session.query(User)
              .filter(User.role != Role.ADMIN,
                      or_(User.full_name.ilike(like), User.email.ilike(like)))
              .limit(5).all()):
        results["customers"].append({
            "label": u.full_name, "sub": u.email,
            "url": url_for("admin.user_details", user_id=u.id),
        })

    for un in (db.session.query(Unit).filter(Unit.unit_code.ilike(like))
               .order_by(Unit.unit_code.asc()).limit(5).all()):
        results["units"].append({
            "label": un.unit_code, "sub": (un.type or "Unit"),
            "url": url_for("admin.edit_unit", unit_id=un.id),
        })

    for r in (db.session.query(Reservation)
              .filter(or_(Reservation.full_name.ilike(like), Reservation.email.ilike(like)))
              .order_by(Reservation.created_at.desc()).limit(5).all()):
        results["reservations"].append({
            "label": r.full_name, "sub": r.email,
            "url": url_for("admin.reservations"),
        })

    for p in (db.session.query(Payment)
              .filter(or_(Payment.reference.ilike(like), Payment.receipt_number.ilike(like)))
              .order_by(Payment.paid_at.desc()).limit(5).all()):
        results["payments"].append({
            "label": (p.reference or p.receipt_number or ("Payment #%s" % p.id)),
            "sub": "₱{:,.2f}".format(float(p.amount)),
            "url": url_for("admin.payments"),
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
    if building.code == "B4":
        return 3
    if building.code == "B5":
        return 2
    return 4


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
            .filter(Payment.payment_status.notin_(["pending", "rejected"]))
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
    
    return {
        "valid": len(issues) == 0,
        "message": "Blockchain chain is valid" if len(issues) == 0 else f"Found {len(issues)} integrity issue(s)",
        "issues": issues,
        "total_ledgers": len(ledgers)
    }


def _send_reservation_result_email(to_email: str, status: ReservationStatus, unit_code: str, to_name: str = "Tenant") -> None:
    """Send reservation result email using Brevo HTTP API"""
    if not to_email:
        return
    
    from ...email_helper import send_reservation_result_email
    
    # Convert ReservationStatus enum to string
    status_str = status.value.lower()  # 'approved', 'rejected', 'cancelled'
    
    send_reservation_result_email(to_email, to_name, status_str, unit_code)


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
    total_payments = db.session.query(Payment).count()
    total_revenue = db.session.query(db.func.sum(Payment.amount)).scalar() or 0
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
        month_revenue = db.session.query(func.sum(Payment.amount)).filter(
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
    this_month_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.paid_at >= current_month_start
    ).scalar() or 0
    
    last_month_start = (current_month_start - relativedelta(months=1))
    last_month_end = current_month_start - timedelta(days=1)
    last_month_revenue = db.session.query(func.sum(Payment.amount)).filter(
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
        "total_deposits": total_deposits,
        "res_pending": res_pending,
        "res_approved": res_approved,
        "res_rejected": res_rejected,
        "res_cancelled": res_cancelled,
    }

    return render_template(
        "admin/dashboard.html",
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
    
    # Base query
    query = (
        db.session.query(TenantProfile)
        .join(User, TenantProfile.user_id == User.id)
        .join(Unit, TenantProfile.unit_id == Unit.id)
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
        
    today = date.today()
    threshold_urgent = today + timedelta(days=7)
    
    # Apply urgent filter (expiring in 1 week)
    if urgent_filter:
        query = query.filter(
            TenantProfile.contract_end.isnot(None),
            TenantProfile.contract_end <= threshold_urgent,
            TenantProfile.contract_end >= today
        )
    
    tenants = query.order_by(TenantProfile.contract_end.asc()).all()
    
    threshold_warning = today + timedelta(days=30) # 1 month
    
    # Active (pending/acknowledged) move-out notices, keyed by tenant_profile_id
    active_notices = (
        db.session.query(MoveOutNotice)
        .filter(MoveOutNotice.status.in_([MoveOutNoticeStatus.PENDING, MoveOutNoticeStatus.ACKNOWLEDGED]))
        .all()
    )
    notices_by_profile = {n.tenant_profile_id: n for n in active_notices}

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


        # Check for renewal request
        renewal = db.session.query(RenewalRequest).filter(
            RenewalRequest.tenant_profile_id == t.id,
            RenewalRequest.status == RenewalRequestStatus.PENDING
        ).first()

        # Renewal/churn risk (rule-based heuristic)
        late_payments = db.session.query(Payment).filter(
            Payment.tenant_profile_id == t.id, Payment.is_late == True
        ).count()
        open_concerns = db.session.query(Concern).filter(
            Concern.tenant_profile_id == t.id,
            Concern.status != ConcernStatus.RESOLVED
        ).count()
        avg_rating = db.session.query(func.avg(Feedback.rating)).filter(
            Feedback.tenant_profile_id == t.id, Feedback.rating.isnot(None)
        ).scalar()
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

    return render_template(
        "admin/tenant_monitoring.html",
        monitoring_data=monitoring_data,
        buildings=buildings,
        today=today
    )


@bp.get("/floorplan")
@login_required
def floorplan():
    _ensure_admin()
    buildings = db.session.query(Building).order_by(Building.code.asc()).all()
    building_floor_limits = {
        building.id: 3 if building.code == "B4" else 2 if building.code == "B5" else 4
        for building in buildings
    }
    # Exclude archived units from floorplan
    units = [
        unit
        for unit in db.session.query(Unit).filter(Unit.is_archived == False).order_by(Unit.building_id.asc(), Unit.unit_number.asc()).all()
        if (unit.floor or 0) <= building_floor_limits.get(unit.building_id, 4)
    ]
    return render_template("admin/floorplan.html", buildings=buildings, units=units)


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
    
    units = query.order_by(Unit.building_id.asc(), Unit.unit_number.asc()).all()
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

    return render_template("admin/units.html", buildings=buildings, units=units, stats=stats, show_archived=show_archived, building_floor_limits=building_floor_limits)


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

    try:
        price_monthly = float(price_monthly)
    except ValueError:
        flash("Invalid price amount.", "warning")
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

    # Handle image uploads (maximum 4 images)
    image_files = request.files.getlist("images")
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
    units = db.session.query(Unit).filter(Unit.is_archived == False).order_by(Unit.building_id.asc(), Unit.unit_number.asc()).all()
    
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

    return render_template("admin/units.html", buildings=buildings, units=units, stats=stats, edit_unit=unit, show_archived=False, building_floor_limits=building_floor_limits)


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

    try:
        price_monthly = float(price_monthly)
    except ValueError:
        flash("Invalid price amount.", "warning")
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

    # Handle image uploads (maximum 4 images)
    image_files = request.files.getlist("images")
    if image_files:
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        Path(upload_folder).mkdir(parents=True, exist_ok=True)

        image_urls = json.loads(unit.unit_images_json) if unit.unit_images_json else []

        # Calculate remaining slots
        remaining_slots = 4 - len(image_urls)
        
        if len(image_files) > remaining_slots:
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
    unit.status = UnitStatus(status)
    unit.description = description or None

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

    query = db.session.query(Reservation).order_by(Reservation.created_at.desc())
    if q:
        query = query.filter(
            (Reservation.full_name.ilike(f"%{q}%")) | (Reservation.email.ilike(f"%{q}%"))
        )
    if status in {"pending", "approved", "rejected", "cancelled"}:
        query = query.filter(Reservation.status == ReservationStatus(status))

    rows = query.limit(200).all()
    today = date.today()
    
    # Get all buildings for filter dropdown
    buildings = db.session.query(Building).order_by(Building.code.asc()).all()
    
    return render_template("admin/reservations.html", rows=rows, q=q, status=status, today=today, buildings=buildings)


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

    # Use customer's move-out date directly
    contract_start = r.move_in_date or date.today()
    contract_end = r.move_out_date

    # Create / replace tenant profile
    existing_profile = db.session.query(TenantProfile).filter_by(user_id=user.id).first()
    if existing_profile:
        existing_profile.unit_id = unit.id
        existing_profile.contract_start = contract_start
        existing_profile.contract_end = contract_end
        existing_profile.is_active = True
        profile = existing_profile
    else:
        profile = TenantProfile(user_id=user.id, unit_id=unit.id, contract_start=contract_start, contract_end=contract_end)
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
    
    monthly_payment = Payment(
        tenant_profile_id=profile.id,
        amount=float(unit.price_monthly),
        reference=f"Monthly - {unit.unit_code}",
        notes="First month payment",
        is_deposit=False,
        paid_at=paid_at_normalized
    )
    db.session.add(monthly_payment)

    deposit_payment = Payment(
        tenant_profile_id=profile.id,
        amount=float(r.deposit_amount),
        reference=f"Deposit - {unit.unit_code}",
        notes="Reservation deposit (refundable after contract ends)",
        is_deposit=True,
        deposit_transaction_type="deposit_paid",
        paid_at=paid_at_normalized
    )
    db.session.add(deposit_payment)
    db.session.flush()

    # Generate ledger entries for both payments
    _generate_payment_ledger(monthly_payment)
    _generate_payment_ledger(deposit_payment)

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
    flash("Reservation approved. User is now a Tenant. Deposit and monthly payment recorded.", "success")
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
        result["tenant"] = {
            "name": profile.user.full_name,
            "contract_end": profile.contract_end.strftime("%b %d, %Y") if profile.contract_end else None,
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

    tenants = db.session.query(TenantProfile).order_by(TenantProfile.created_at.desc()).limit(200).all()
    # Confirmed payments only — tenant-submitted proofs awaiting review live
    # in their own "Pending Payment Proofs" section below, and rejected ones
    # aren't real recorded payments, so neither belongs in this list/stats.
    payments = (
        db.session.query(Payment)
        .filter(Payment.payment_status.notin_(['pending', 'rejected']))
        .order_by(Payment.paid_at.desc())
        .limit(100)
        .all()
    )
    buildings = db.session.query(Building).order_by(Building.code.asc()).all()
    today = date.today()
    today_dt = dt.combine(today, dt.min.time())  # Convert to datetime for comparison

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
            .filter(Payment.payment_status.notin_(['pending', 'rejected']))
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

    return render_template(
        "admin/payments.html",
        tenants=tenants,
        payments=payments,
        buildings=buildings,
        today=today,
        today_dt=today_dt,
        timedelta=timedelta,
        unpaid_this_month=unpaid_this_month,
        blockchain_status=blockchain_status,
        pending_proofs=pending_proofs,
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


@bp.get("/deposits")
@login_required
def deposits():
    _ensure_admin()
    from datetime import date, timedelta
    
    reservations = (
        db.session.query(Reservation)
        .filter(Reservation.status == ReservationStatus.APPROVED)
        .order_by(Reservation.created_at.desc())
        .all()
    )
    
    buildings = db.session.query(Building).order_by(Building.code.asc()).all()
    today = date.today()
    
    return render_template("admin/deposits.html", reservations=reservations, buildings=buildings, today=today)


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
    elif sort_by == 'last_login':
        query = query.order_by(User.last_login_at.desc().nullslast())
    
    all_users = query.all()
    
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
    
    return render_template("admin/users.html", all_users=all_users, stats=stats)


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
        deduction_amount = float(request.form.get("deduction_amount") or "0")
        deduction_reason = (request.form.get("deduction_reason") or "").strip()
        
        if not deduction_amount or not deduction_reason:
            flash("Please provide deduction amount and reason.", "warning")
            return redirect(url_for("admin.deposits"))
        
        # Parse existing deductions or create new
        deductions = []
        if r.deposit_deductions:
            try:
                deductions = json.loads(r.deposit_deductions)
            except:
                # If it's old format (string), convert to list
                deductions = []
        
        deductions.append({
            "amount": deduction_amount,
            "reason": deduction_reason,
            "date": date.today().isoformat()
        })
        
        # Format deductions for display
        deduction_lines = []
        total_deductions = 0
        for d in deductions:
            total_deductions += d["amount"]
            deduction_lines.append(f"• ₱{d['amount']:.2f} - {d['reason']} ({d['date']})")
        
        r.deposit_deductions = "\n".join(deduction_lines)
        
        # Calculate return amount
        return_amount = r.deposit_amount - total_deductions
        r.deposit_return_amount = max(0, return_amount)
        
        if total_deductions >= r.deposit_amount:
            r.deposit_status = "full_return"
        else:
            r.deposit_status = "partial_return"
        
        flash(f"Deduction of ₱{deduction_amount:.2f} added. Total deductions: ₱{total_deductions:.2f}", "success")
        
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
                reference=f"Deposit Return - {r.unit.unit_code}",
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
                reference=f"Remaining Deposit Return - {r.unit.unit_code}",
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
    else:
        flash("Payment recorded (with ledger hash).", "success")
    return redirect(url_for("admin.payments"))


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

    flash("Payment proof approved and recorded (with ledger hash).", "success")
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
    
    announcements = (
        db.session.query(Announcement)
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .all()
    )
    
    today = date.today()
    
    return render_template("admin/announcements.html", announcements=announcements, today=today)


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
        query = query.join(TenantProfile).join(User).join(Unit).filter(
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
            query = query.join(TenantProfile).join(Unit)
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
            query = query.join(TenantProfile).join(User)
        query = query.order_by(User.full_name.asc())
    else:  # newest (default)
        query = query.order_by(Document.uploaded_at.desc())
    
    documents = query.all()
    
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
    
    # Document types for filter
    doc_types = [
        ('lease_agreement', 'Lease Agreement'),
        ('receipt', 'Receipt'),
        ('certificate', 'Certificate'),
        ('rules', 'Rules & Regulations'),
        ('electricity_bill', 'Electricity Bill'),
        ('water_bill', 'Water Bill'),
        ('internet_bill', 'Internet Bill'),
    ]
    
    return render_template(
        "admin/documents.html",
        tenants=tenants,
        documents=documents,
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
        query = query.join(TenantProfile).join(User).join(Unit).filter(
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
            query = query.join(TenantProfile).join(Unit)
        query = query.filter(Unit.building_id == int(building_filter))
    
    # Apply urgency filter (contracts expiring soon)
    if urgency_filter == 'urgent':
        today = date.today()
        urgent_date = today + timedelta(days=30)
        if not search_query and not building_filter:
            query = query.join(TenantProfile)
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
            query = query.join(TenantProfile)
        query = query.order_by(TenantProfile.contract_end.asc())
    elif sort_by == 'tenant_az':
        if not search_query:
            query = query.join(TenantProfile).join(User)
        query = query.order_by(User.full_name.asc())
    else:  # newest (default)
        query = query.order_by(RenewalRequest.created_at.desc())
    
    renewal_requests = query.all()
    
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
            deductions = []
            if reservation.deposit_deductions:
                try:
                    deductions = _json.loads(reservation.deposit_deductions)
                except Exception:
                    deductions = []
            reason = (
                f"Final month charge ({charge['half_or_full']} month, notified after due date) "
                f"— moved out {actual_move_out_date.strftime('%b %d, %Y')}"
            )
            deductions.append({
                "amount": charge["amount"],
                "reason": reason,
                "date": date.today().isoformat(),
            })
            deduction_lines = []
            total_deductions = 0.0
            for d in deductions:
                total_deductions += d["amount"]
                deduction_lines.append(f"• ₱{d['amount']:.2f} - {d['reason']} ({d['date']})")
            reservation.deposit_deductions = "\n".join(deduction_lines)
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
        query = query.join(TenantProfile).join(User).join(Unit).filter(
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
            query = query.join(TenantProfile).join(Unit)
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
            query = query.join(TenantProfile).join(User)
        query = query.order_by(User.full_name.asc())
    else:  # newest (default)
        query = query.order_by(Feedback.created_at.desc())
    
    feedbacks = query.all()

    # AI sentiment analysis (rule-based, bilingual) per feedback
    from ...ai_utils import analyze_sentiment
    sentiments = {f.id: analyze_sentiment(f.comments, f.rating) for f in feedbacks}
    flagged_count = sum(1 for s in sentiments.values() if s["flag"])

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
    query = db.session.query(Concern).join(TenantProfile).join(User).join(Unit)
    
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
    concerns = query.order_by(priority_order, Concern.created_at.desc()).all()
    
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
    
    inquiries = query.order_by(Inquiry.created_at.desc()).all()
    
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
    
    return render_template("admin/inquiries.html", inquiries=inquiries, stats=stats)


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
