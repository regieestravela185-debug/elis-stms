from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for, Response
from flask_login import current_user, login_required
from flask_mail import Message
from dateutil.relativedelta import relativedelta

from ...extensions import db, mail
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
    Payment,
    PaymentLedger,
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
from ...smart_notifications import get_notification_system, NotificationPriority, NotificationType
from ...models import NotificationHistory

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _ensure_admin():
    if current_user.role != Role.ADMIN:  # type: ignore[attr-defined]
        abort(403)


def _get_building_floor_limit(building_id: int) -> int:
    building = db.session.get(Building, building_id)
    if not building:
        return 4
    if building.code == "B4":
        return 3
    if building.code == "B5":
        return 2
    return 4


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
        return {"valid": True, "message": "No ledger entries to verify", "issues": []}
    
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


def _send_reservation_result_email(to_email: str, status: ReservationStatus, unit_code: str) -> None:
    if not to_email:
        return
    
    status_text = status.value.upper()
    
    if status == ReservationStatus.APPROVED:
        status_color = "#40c940"
        status_icon = "✓"
    elif status == ReservationStatus.REJECTED:
        status_color = "#ff5050"
        status_icon = "✗"
    else:  # CANCELLED
        status_color = "#ff5050"
        status_icon = "!"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reservation Status</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
        <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
                <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
            </div>
            <div style="padding: 40px 30px;">
                <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">Reservation {status_text}</h2>
                <div style="background: #f9f9f9; border: 2px solid {status_color}; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
                    <span style="font-size: 48px; font-weight: 700; color: {status_color};">{status_icon}</span>
                    <p style="margin: 12px 0 0 0; color: {status_color}; font-size: 18px; font-weight: 600;">{status_text}</p>
                </div>
                <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Your reservation for <strong>Unit {unit_code}</strong> has been {status_text.lower()}.</p>
                <p style="margin: 0 0 24px 0; color: #666666; line-height: 1.6;">
                    {f"Your account is now tagged as tenant. Please login again to access your tenant portal." if status == ReservationStatus.APPROVED else "You may contact us or submit another reservation request for other available units."}
                </p>
                <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B;">
                    <p style="margin: 0; color: #666666; font-size: 14px; line-height: 1.5;"><strong>Next Steps:</strong></p>
                    <ul style="margin: 8px 0 0 20px; padding: 0; color: #666666; font-size: 14px; line-height: 1.5;">
                        <li>{f"Complete your tenant profile setup" if status == ReservationStatus.APPROVED else "Browse available units on our website"}</li>
                        <li>{f"Review your contract details" if status == ReservationStatus.APPROVED else "Submit a new reservation request"}</li>
                        <li>Contact admin if you have questions</li>
                    </ul>
                </div>
            </div>
            <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
                <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {date.today().year} The Elis Center. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject=f"Reservation {status_text} - The Elis Center STMS",
        recipients=[to_email],
        html=html_body,
    )
    try:
        mail.send(msg)
    except Exception:
        pass


def _send_renewal_reminder_email(tenant_name: str, tenant_email: str, unit_code: str, contract_end: date, days_remaining: int) -> None:
    if not tenant_email:
        return
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Contract Renewal Reminder</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
        <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
                <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
            </div>
            <div style="padding: 40px 30px;">
                <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">Contract Renewal Reminder</h2>
                <div style="background: rgba(255, 80, 80, 0.1); border: 2px solid #ff5050; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
                    <span style="font-size: 48px; font-weight: 700; color: #ff5050;">⚠️</span>
                    <p style="margin: 12px 0 0 0; color: #ff5050; font-size: 18px; font-weight: 600;">Contract Expiring Soon</p>
                </div>
                <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{tenant_name}</strong>,</p>
                <p style="margin: 0 0 16px 0; color: #666666; line-height: 1.6;">
                    Your lease contract for <strong>Unit {unit_code}</strong> will expire on <strong>{contract_end.strftime('%B %d, %Y')}</strong>. 
                    You have <strong>{days_remaining} days</strong> remaining.
                </p>
                <p style="margin: 0 0 24px 0; color: #666666; line-height: 1.6;">
                    To continue your stay, please submit a renewal request through your tenant portal or contact our administration office.
                </p>
                <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B;">
                    <p style="margin: 0; color: #666666; font-size: 14px; line-height: 1.5;"><strong>Next Steps:</strong></p>
                    <ul style="margin: 8px 0 0 20px; padding: 0; color: #666666; font-size: 14px; line-height: 1.5;">
                        <li>Login to your tenant portal</li>
                        <li>Go to Renewal section</li>
                        <li>Submit your renewal request</li>
                        <li>Or contact us directly for assistance</li>
                    </ul>
                </div>
            </div>
            <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
                <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {date.today().year} The Elis Center. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject=f"Contract Renewal Reminder - {days_remaining} Days Remaining",
        recipients=[tenant_email],
        html=html_body,
    )
    try:
        mail.send(msg)
    except Exception:
        pass


@bp.post("/notifications/generate-automated")
@login_required
def generate_automated_notifications():
    """Generate automated smart notifications for tenants"""
    _ensure_admin()
    
    notification_system = get_notification_system()
    generated_count = 0
    
    tenants = db.session.query(TenantProfile).all()
    today = date.today()
    
    for tenant in tenants:
        if not tenant.is_active:
            continue
        
        user = tenant.user
        if not user:
            continue
        
        # Check for lease expiration notification
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
        
        # Check for high-risk notification
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
    
    flash(f"Generated {generated_count} automated notifications.", "success")
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
        pending_concerns=pending_concerns,
        pending_renewals=pending_renewals,
        pending_feedbacks=pending_feedbacks,
        pending_inquiries=pending_inquiries,
        avg_rating=avg_rating,
        today=today,
    )


@bp.post("/renewal-reminders/send")
@login_required
def send_renewal_reminders():
    _ensure_admin()
    
    from datetime import date, timedelta
    
    # Find tenants with contracts expiring in 7 days or less
    today = date.today()
    threshold = today + timedelta(days=7)


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
    
    monitoring_data = []
    for t in tenants:
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
                
        # Check for renewal request
        renewal = db.session.query(RenewalRequest).filter(
            RenewalRequest.tenant_profile_id == t.id,
            RenewalRequest.status == RenewalRequestStatus.PENDING
        ).first()
        
        monitoring_data.append({
            "profile": t,
            "days_remaining": days_remaining,
            "status": status,
            "has_pending_renewal": renewal is not None,
            "duration_days": duration_days
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
        
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        Path(upload_folder).mkdir(parents=True, exist_ok=True)

        for image_file in image_files:
            if image_file and image_file.filename:
                filename = secure_filename(f"{unit_code}_{image_file.filename}")
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

        for image_file in image_files:
            if image_file and image_file.filename:
                filename = secure_filename(f"{unit_code}_{image_file.filename}")
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
    
    # Generate new unit code
    import re
    match = re.match(r'(.+?)(\d+)$', original.unit_code)
    if match:
        prefix = match.group(1)
        number = int(match.group(2))
        new_code = f"{prefix}{number + 1}"
    else:
        new_code = f"{original.unit_code}_copy"

    max_floor = _get_building_floor_limit(original.building_id)
    duplicate_floor = original.floor or 1
    if duplicate_floor > max_floor:
        duplicate_floor = max_floor
    
    # Create duplicate
    duplicate = Unit(
        building_id=original.building_id,
        unit_number=f"{original.unit_number}_copy",
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


@bp.get("/payments")
@login_required
def payments():
    _ensure_admin()
    from datetime import date, datetime as dt, timedelta
    tenants = db.session.query(TenantProfile).order_by(TenantProfile.created_at.desc()).limit(200).all()
    payments = db.session.query(Payment).order_by(Payment.paid_at.desc()).limit(100).all()
    buildings = db.session.query(Building).order_by(Building.code.asc()).all()
    today = date.today()
    today_dt = dt.combine(today, dt.min.time())  # Convert to datetime for comparison
    return render_template("admin/payments.html", tenants=tenants, payments=payments, buildings=buildings, today=today, today_dt=today_dt, timedelta=timedelta)


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
    
    # Get tenant profile if exists
    tenant_profile = None
    payments = []
    if user.role == Role.TENANT:
        tenant_profile = db.session.query(TenantProfile).filter(TenantProfile.user_id == user_id).first()
        if tenant_profile:
            payments = db.session.query(Payment).filter(Payment.tenant_profile_id == tenant_profile.id).order_by(Payment.paid_at.desc()).limit(10).all()
    
    return render_template("admin/user_details.html", 
                         user=user, 
                         reservations=reservations, 
                         tenant_profile=tenant_profile,
                         payments=payments)


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
    
    # Send email notification to banned user
    try:
        from flask_mail import Message
        from app.extensions import mail
        
        msg = Message(
            subject="Account Suspended - The Elis Center",
            recipients=[user.email]
        )
        msg.body = f"""
Dear {user.full_name},

Your account at The Elis Center Smart Tenant Management System has been suspended.

Reason: {user.ban_reason}

If you believe this is a mistake or would like to appeal this decision, please contact the administrator.

Thank you,
The Elis Center Management
"""
        msg.html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #dc3545; color: white; padding: 20px; text-align: center; }}
        .content {{ background-color: #f8f9fa; padding: 20px; margin-top: 20px; }}
        .reason {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 15px 0; }}
        .footer {{ text-align: center; margin-top: 20px; color: #6c757d; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ Account Suspended</h1>
        </div>
        <div class="content">
            <p>Dear <strong>{user.full_name}</strong>,</p>
            
            <p>Your account at <strong>The Elis Center Smart Tenant Management System</strong> has been suspended.</p>
            
            <div class="reason">
                <strong>Reason:</strong> {user.ban_reason}
            </div>
            
            <p>If you believe this is a mistake or would like to appeal this decision, please contact the administrator.</p>
            
            <p>Thank you,<br>
            <strong>The Elis Center Management</strong></p>
        </div>
        <div class="footer">
            <p>This is an automated message. Please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""
        mail.send(msg)
    except Exception as e:
        print(f"Failed to send ban notification email: {e}")
    
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
    
    # Send email notification to unbanned user
    try:
        from flask_mail import Message
        from app.extensions import mail
        
        msg = Message(
            subject="Account Reactivated - The Elis Center",
            recipients=[user.email]
        )
        msg.body = f"""
Dear {user.full_name},

Good news! Your account at The Elis Center Smart Tenant Management System has been reactivated.

You can now log in and access all features again.

If you have any questions, please contact the administrator.

Thank you,
The Elis Center Management
"""
        msg.html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #28a745; color: white; padding: 20px; text-align: center; }}
        .content {{ background-color: #f8f9fa; padding: 20px; margin-top: 20px; }}
        .message {{ background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px; margin: 15px 0; }}
        .footer {{ text-align: center; margin-top: 20px; color: #6c757d; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✅ Account Reactivated</h1>
        </div>
        <div class="content">
            <p>Dear <strong>{user.full_name}</strong>,</p>
            
            <div class="message">
                <p><strong>Good news!</strong> Your account at <strong>The Elis Center Smart Tenant Management System</strong> has been reactivated.</p>
            </div>
            
            <p>You can now log in and access all features again.</p>
            
            <p>If you have any questions, please contact the administrator.</p>
            
            <p>Thank you,<br>
            <strong>The Elis Center Management</strong></p>
        </div>
        <div class="footer">
            <p>This is an automated message. Please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""
        mail.send(msg)
    except Exception as e:
        print(f"Failed to send unban notification email: {e}")
    
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
        user.role = Role.USER

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

    # Create payment with normalized timestamp for blockchain consistency
    from datetime import datetime
    paid_at_normalized = datetime.utcnow().replace(microsecond=0)
    p = Payment(tenant_profile_id=profile.id, amount=amount, reference=reference, paid_at=paid_at_normalized)
    db.session.add(p)
    db.session.flush()

    _generate_payment_ledger(p)

    # Optional: mark unit as occupied (and clear unpaid flag)
    unit = db.session.get(Unit, profile.unit_id)
    if unit and unit.status == UnitStatus.UNPAID:
        unit.status = UnitStatus.OCCUPIED

    db.session.commit()
    flash("Payment recorded (with ledger hash).", "success")
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

    # Store relative path for serving (without 'static/' prefix for url_for)
    relative_path = f"uploads/{unique_filename}"

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
    
    # Send email notification to tenant
    _send_document_notification_email(
        tenant_name=profile.user.full_name,
        tenant_email=profile.user.email,
        document_title=title,
        document_type=document_type.replace('_', ' ').title()
    )
    
    flash(f"Document uploaded successfully and notification sent to {profile.user.full_name}.", "success")
    return redirect(url_for("admin.documents"))


def _send_document_notification_email(tenant_name: str, tenant_email: str, document_title: str, document_type: str) -> None:
    """Send email notification when admin uploads a document for tenant"""
    if not tenant_email:
        return
    
    # Get the base URL from Flask request context
    from flask import request
    base_url = request.url_root.rstrip('/')
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>New Document Available</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
        <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
                <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
            </div>
            <div style="padding: 40px 30px;">
                <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">📄 New Document Available</h2>
                <div style="background: rgba(215, 179, 91, 0.1); border: 2px solid rgba(215, 179, 91, 0.3); border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
                    <span style="font-size: 48px; font-weight: 700; color: #D7B35B;">📄</span>
                    <p style="margin: 12px 0 0 0; color: #D7B35B; font-size: 18px; font-weight: 600;">Document Uploaded</p>
                </div>
                <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{tenant_name}</strong>,</p>
                <p style="margin: 0 0 16px 0; color: #666666; line-height: 1.6;">
                    A new document has been uploaded to your account by the admin.
                </p>
                <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B; margin: 24px 0;">
                    <p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Document Type:</strong></p>
                    <p style="margin: 0 0 16px 0; color: #1a1a1a; font-size: 16px; font-weight: 600;">{document_type}</p>
                    <p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Title:</strong></p>
                    <p style="margin: 0; color: #1a1a1a; font-size: 16px; font-weight: 600;">{document_title}</p>
                </div>
                <p style="margin: 0 0 24px 0; color: #666666; line-height: 1.6;">
                    Please login to your tenant portal to view and download this document.
                </p>
                <div style="text-align: center; margin: 24px 0;">
                    <a href="{base_url}/tenant/documents" style="display: inline-block; background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 16px;">
                        View Document
                    </a>
                </div>
                <div style="background: rgba(59, 130, 246, 0.08); padding: 12px; border-radius: 8px; border: 1px solid rgba(59, 130, 246, 0.2); margin-top: 24px;">
                    <p style="margin: 0; font-size: 12px; line-height: 1.6; color: #1e40af;">
                        <strong>ℹ️ Note:</strong> This is an automated notification. Please do not reply to this email.
                    </p>
                </div>
            </div>
            <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
                <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {date.today().year} The Elis Center. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject=f"New Document: {document_title} - The Elis Center",
        recipients=[tenant_email],
        html=html_body,
    )
    try:
        mail.send(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")


@bp.post("/documents/<int:document_id>/delete")
@login_required
def delete_document(document_id: int):
    _ensure_admin()
    document = db.session.get(Document, document_id)
    if not document:
        abort(404)
    
    # Delete file from filesystem
    import os
    try:
        file_path = os.path.join("static", document.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Failed to delete file: {e}")
    
    db.session.delete(document)
    db.session.commit()
    flash("Document deleted successfully.", "success")
    return redirect(url_for("admin.documents"))
    db.session.commit()
    flash("Document uploaded.", "success")
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

    renewal.status = RenewalRequestStatus.APPROVED
    # Update tenant contract end date
    profile = db.session.get(TenantProfile, renewal.tenant_profile_id)
    if profile:
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
    """Send email notification when renewal request is approved or rejected"""
    if not tenant_email:
        return
    
    from flask import request
    base_url = request.url_root.rstrip('/')
    
    if status == 'approved':
        status_color = "#10b981"
        status_icon = "✓"
        status_text = "APPROVED"
        message = f"Your contract renewal request has been approved! Your new contract end date is <strong>{new_end_date.strftime('%B %d, %Y')}</strong>."
    else:
        status_color = "#ef4444"
        status_icon = "✗"
        status_text = "REJECTED"
        message = "Your contract renewal request has been rejected. Please contact the admin office for more information."
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Renewal Request {status_text}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
        <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
                <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
            </div>
            <div style="padding: 40px 30px;">
                <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">↻ Renewal Request {status_text}</h2>
                <div style="background: rgba({status_color.replace('#', '')}, 0.1); border: 2px solid {status_color}; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
                    <span style="font-size: 48px; font-weight: 700; color: {status_color};">{status_icon}</span>
                    <p style="margin: 12px 0 0 0; color: {status_color}; font-size: 18px; font-weight: 600;">{status_text}</p>
                </div>
                <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{tenant_name}</strong>,</p>
                <p style="margin: 0 0 16px 0; color: #666666; line-height: 1.6;">
                    {message}
                </p>
                <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B; margin: 24px 0;">
                    <p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Unit:</strong></p>
                    <p style="margin: 0 0 16px 0; color: #1a1a1a; font-size: 16px; font-weight: 600;">{unit_code}</p>
                    {f'<p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Previous Contract End:</strong></p><p style="margin: 0 0 16px 0; color: #1a1a1a; font-size: 16px;">{old_end_date.strftime("%B %d, %Y") if old_end_date else "N/A"}</p>' if status == 'approved' else ''}
                    {f'<p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>New Contract End:</strong></p><p style="margin: 0; color: #10b981; font-size: 18px; font-weight: 700;">{new_end_date.strftime("%B %d, %Y")}</p>' if status == 'approved' else ''}
                </div>
                <div style="text-align: center; margin: 24px 0;">
                    <a href="{base_url}/tenant/renewal" style="display: inline-block; background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 16px;">
                        View Renewal Status
                    </a>
                </div>
            </div>
            <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
                <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {date.today().year} The Elis Center. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject=f"Renewal Request {status_text} - The Elis Center",
        recipients=[tenant_email],
        html=html_body,
    )
    try:
        mail.send(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")


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
        today=today
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
            priority=concern.priority
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
            admin_name=current_user.full_name  # type: ignore[attr-defined]
        )
    
    flash("Response added successfully.", "success")
    return redirect(url_for("admin.concerns"))


def _send_concern_status_email(tenant_name: str, tenant_email: str, subject: str, status: str, priority: str) -> None:
    """Send email notification when concern status is updated"""
    if not tenant_email:
        return
    
    status_colors = {
        'pending': '#eab308',
        'in_progress': '#3b82f6',
        'resolved': '#10b981'
    }
    
    status_icons = {
        'pending': '⏳',
        'in_progress': '🔄',
        'resolved': '✓'
    }
    
    priority_colors = {
        'low': '#10b981',
        'medium': '#eab308',
        'high': '#f97316',
        'urgent': '#ef4444'
    }
    
    status_color = status_colors.get(status, '#666666')
    status_icon = status_icons.get(status, '📋')
    priority_color = priority_colors.get(priority, '#666666')
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Concern Status Update</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
        <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
                <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
            </div>
            <div style="padding: 40px 30px;">
                <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">Concern Status Updated</h2>
                <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{tenant_name}</strong>,</p>
                <p style="margin: 0 0 24px 0; color: #666666; line-height: 1.6;">
                    Your concern "<strong>{subject}</strong>" has been updated.
                </p>
                <div style="background: #f9f9f9; border: 2px solid {status_color}; border-radius: 8px; padding: 20px; margin: 24px 0;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                        <div>
                            <span style="font-size: 14px; color: #666;">Status:</span>
                            <div style="font-size: 18px; font-weight: 600; color: {status_color}; margin-top: 4px;">
                                {status_icon} {status.replace('_', ' ').title()}
                            </div>
                        </div>
                        <div>
                            <span style="font-size: 14px; color: #666;">Priority:</span>
                            <div style="font-size: 18px; font-weight: 600; color: {priority_color}; margin-top: 4px;">
                                {priority.title()}
                            </div>
                        </div>
                    </div>
                </div>
                <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B;">
                    <p style="margin: 0; color: #666666; font-size: 14px; line-height: 1.5;">
                        You can view the full details and any responses by logging into your tenant portal.
                    </p>
                </div>
            </div>
            <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
                <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {date.today().year} The Elis Center. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject=f"Concern Status Updated - {subject}",
        recipients=[tenant_email],
        html=html_body,
    )
    try:
        mail.send(msg)
    except Exception:
        pass


def _send_concern_response_email(tenant_name: str, tenant_email: str, subject: str, admin_response: str, admin_name: str) -> None:
    """Send email notification when admin responds to a concern"""
    if not tenant_email:
        return
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Admin Response to Your Concern</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
        <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
                <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
            </div>
            <div style="padding: 40px 30px;">
                <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">💬 Admin Response</h2>
                <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{tenant_name}</strong>,</p>
                <p style="margin: 0 0 24px 0; color: #666666; line-height: 1.6;">
                    Our admin team has responded to your concern "<strong>{subject}</strong>".
                </p>
                <div style="background: rgba(215, 179, 91, 0.1); border-left: 4px solid #D7B35B; padding: 20px; border-radius: 8px; margin: 24px 0;">
                    <div style="font-size: 12px; color: #D7B35B; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px;">
                        Response from {admin_name}
                    </div>
                    <p style="margin: 0; color: #374151; line-height: 1.6; font-size: 15px;">
                        {admin_response}
                    </p>
                </div>
                <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #3b82f6;">
                    <p style="margin: 0; color: #666666; font-size: 14px; line-height: 1.5;">
                        If you have any follow-up questions, please login to your tenant portal or contact us directly.
                    </p>
                </div>
            </div>
            <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
                <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {date.today().year} The Elis Center. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject=f"Admin Response - {subject}",
        recipients=[tenant_email],
        html=html_body,
    )
    try:
        mail.send(msg)
    except Exception:
        pass



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
    """Send email notification when admin replies to an inquiry"""
    if not inquirer_email:
        return
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reply to Your Inquiry</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
        <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
                <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
            </div>
            <div style="padding: 40px 30px;">
                <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">💬 Reply to Your Inquiry</h2>
                <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{inquirer_name}</strong>,</p>
                <p style="margin: 0 0 24px 0; color: #666666; line-height: 1.6;">
                    Thank you for your inquiry regarding "<strong>{subject}</strong>". Here is our response:
                </p>
                <div style="background: rgba(215, 179, 91, 0.1); border-left: 4px solid #D7B35B; padding: 20px; border-radius: 8px; margin: 24px 0;">
                    <div style="font-size: 12px; color: #D7B35B; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px;">
                        Response from {admin_name}
                    </div>
                    <p style="margin: 0; color: #374151; line-height: 1.6; font-size: 15px;">
                        {admin_reply}
                    </p>
                </div>
                <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #3b82f6;">
                    <p style="margin: 0; color: #666666; font-size: 14px; line-height: 1.5;">
                        <strong>Need more help?</strong><br/>
                        If you have any follow-up questions, feel free to reply to this email or contact us directly:<br/>
                        <strong>Phone:</strong> 0918-912-6340 or 0918-920-5645<br/>
                        <strong>Hours:</strong> Mon–Sat, 9:00 AM – 6:00 PM
                    </p>
                </div>
            </div>
            <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
                <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {date.today().year} The Elis Center. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject=f"Reply to Your Inquiry - {subject}",
        recipients=[inquirer_email],
        html=html_body,
    )
    try:
        mail.send(msg)
    except Exception:
        pass
