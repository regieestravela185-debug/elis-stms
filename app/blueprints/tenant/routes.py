from flask import Blueprint, abort, render_template, request, redirect, url_for, flash, current_app
from flask_login import current_user, login_required
from datetime import date
import json
import re
from ...security import hash_password

from ...extensions import db
from ...upload_validation import validate_upload, DOCUMENT_TYPES, IMAGE_TYPES
from ...models import (
    Announcement, AnnouncementRead, Concern, ConcernFollowUp, ConcernStatus, Document, Feedback, FeedbackStatus,
    MoveOutNotice, MoveOutNoticeStatus,
    Payment, RenewalRequest, RenewalRequestStatus, Reservation, ReservationStatus,
    Role, TenantProfile, Unit, UnitStatus, User,
    PAYMENT_STATUSES_NOT_COUNTED,
    payment_revenue_amount,
)

bp = Blueprint("tenant", __name__, url_prefix="/tenant")


@bp.context_processor
def _inject_tenant_context():
    """Make is_expired / is_commercial_tenant available in all tenant
    templates for the sidebar and contract-related banners. Commercial
    units are contract-term based (Renewal Request applies); residential
    units are month-to-month with no fixed end (Move-Out Notice applies
    instead)."""
    empty = {"is_expired": False, "is_commercial_tenant": False}
    if not current_user.is_authenticated or current_user.role != Role.TENANT:
        return empty
    profile = db.session.query(TenantProfile).filter_by(user_id=current_user.id).first()
    if not profile:
        return empty
    is_expired = bool(profile.contract_end and profile.contract_end < date.today())
    is_commercial = bool(profile.unit and "commercial" in (profile.unit.type or "").lower())
    return {"is_expired": is_expired, "is_commercial_tenant": is_commercial}


def _ensure_tenant():
    if current_user.role != Role.TENANT:  # type: ignore[attr-defined]
        abort(403)


def _get_tenant_profile():
    """Return (profile, is_expired). Auto-deactivates expired contracts."""
    profile = db.session.query(TenantProfile).filter_by(user_id=current_user.id).first()  # type: ignore[attr-defined]
    if not profile:
        abort(403)

    is_expired = False
    if profile.contract_end and profile.contract_end < date.today():
        is_expired = True
        # Auto-mark unit as available if still occupied
        unit = db.session.get(Unit, profile.unit_id)
        if unit and unit.status == UnitStatus.OCCUPIED:
            unit.status = UnitStatus.AVAILABLE
            db.session.commit()

    return profile, is_expired


def _ensure_active_contract(profile, is_expired):
    """Block access for expired tenants — redirect to dashboard with warning."""
    if is_expired:
        flash("Your contract has expired. Please submit a renewal request or contact admin.", "warning")
        return redirect(url_for("tenant.dashboard"))


def _fetch_file_bytes(file_path: str):
    """Read a stored file's raw bytes regardless of where it lives —
    Supabase Storage (absolute URL) or the local static folder (relative
    path). Needed because the browser's `<a download>` attribute is
    unreliable for cross-origin URLs (which Supabase Storage links are):
    most browsers just navigate to/preview the file instead of saving it.
    Returns None if the file can't be read."""
    if not file_path:
        return None
    if file_path.startswith(("http://", "https://")):
        import requests
        try:
            resp = requests.get(file_path, timeout=15)
            return resp.content if resp.status_code == 200 else None
        except Exception:
            return None
    import os
    local_path = os.path.join("app", "static", file_path)
    if os.path.exists(local_path):
        with open(local_path, "rb") as f:
            return f.read()
    return None


@bp.get("/dashboard")
@login_required
def dashboard():
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()

    unit = db.session.get(Unit, profile.unit_id)

    # Parse unit images
    unit_images = []
    if unit and unit.unit_images_json:
        try:
            parsed_images = json.loads(unit.unit_images_json)
            if isinstance(parsed_images, list):
                # Strip leading slashes and create proper URLs
                for img in parsed_images:
                    img_str = str(img).strip()
                    if img_str:
                        # Keep the raw path/URL as-is — templates resolve it via
                        # media_url(), which passes absolute URLs (Supabase
                        # Storage) through untouched and only falls back to the
                        # local static folder for relative paths. Wrapping it in
                        # url_for('static', ...) here always mangled Supabase
                        # URLs (e.g. "/static/https://...").
                        unit_images.append(img_str.lstrip('/'))
        except Exception:
            unit_images = []

    # Statistics
    total_payments = db.session.query(Payment).filter(Payment.tenant_profile_id == profile.id).count()
    active_concerns = db.session.query(Concern).filter(
        Concern.tenant_profile_id == profile.id,
        Concern.status != ConcernStatus.RESOLVED
    ).count()
    pending_renewals = db.session.query(RenewalRequest).filter(
        RenewalRequest.tenant_profile_id == profile.id,
        RenewalRequest.status == RenewalRequestStatus.PENDING
    ).count()

    # Get reservation for deposit info
    reservation = db.session.query(Reservation).filter(
        Reservation.user_id == current_user.id,  # type: ignore[attr-defined]
        Reservation.unit_id == profile.unit_id,
        Reservation.status == ReservationStatus.APPROVED
    ).first()
    
    deposit_info = None
    if reservation:
        # Read through the model property so this page and the admin page
        # agree, and so rows written in the old display-text format are
        # still shown rather than dropped.
        deductions_list = reservation.deduction_entries
                
        deposit_info = {
            "amount": float(reservation.deposit_amount),
            "status": reservation.deposit_status,
            "deductions_list": deductions_list,
            "return_amount": float(reservation.deposit_return_amount) if reservation.deposit_return_amount else float(reservation.deposit_amount),
            "return_date": reservation.deposit_return_date,
            "notes": reservation.deposit_notes
        }

    # Recent announcements (for tenants or all)
    from datetime import datetime as _dt
    _not_expired = db.or_(Announcement.expires_at.is_(None), Announcement.expires_at >= _dt.utcnow())
    recent_announcements = (
        db.session.query(Announcement)
        .filter(Announcement.is_active == True)
        .filter(_not_expired)
        .filter(db.or_(
            Announcement.target_audience == 'all',
            Announcement.target_audience == 'tenants'
        ))
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .limit(5)
        .all()
    )

    # Count unread announcements
    read_announcement_ids = db.session.query(AnnouncementRead.announcement_id).filter(
        AnnouncementRead.user_id == current_user.id  # type: ignore[attr-defined]
    ).all()
    read_ids = [r[0] for r in read_announcement_ids]

    unread_count = (
        db.session.query(Announcement)
        .filter(Announcement.is_active == True)
        .filter(_not_expired)
        .filter(db.or_(
            Announcement.target_audience == 'all',
            Announcement.target_audience == 'tenants'
        ))
        .filter(~Announcement.id.in_(read_ids) if read_ids else True)
        .count()
    )
    
    # Count unread documents
    unread_documents_count = db.session.query(Document).filter(
        Document.tenant_profile_id == profile.id,
        Document.is_viewed == False
    ).count()

    # Recent activities (concerns, feedback, renewal requests)
    from datetime import datetime, timedelta
    recent_date = datetime.utcnow() - timedelta(days=30)

    recent_concerns = db.session.query(Concern).filter(
        Concern.tenant_profile_id == profile.id,
        Concern.created_at >= recent_date
    ).order_by(Concern.created_at.desc()).limit(5).all()

    recent_feedbacks = db.session.query(Feedback).filter(
        Feedback.tenant_profile_id == profile.id,
        Feedback.created_at >= recent_date
    ).order_by(Feedback.created_at.desc()).limit(5).all()

    recent_renewals = db.session.query(RenewalRequest).filter(
        RenewalRequest.tenant_profile_id == profile.id,
        RenewalRequest.created_at >= recent_date
    ).order_by(RenewalRequest.created_at.desc()).limit(5).all()

    # Recent payments
    recent_payments = db.session.query(Payment).filter(
        Payment.tenant_profile_id == profile.id
    ).order_by(Payment.paid_at.desc()).limit(5).all()

    # Calculate days until next payment (assuming monthly on contract start day)
    from datetime import date, timedelta
    # Which month is owed, not merely the next date on the calendar: this
    # counted forward from the contract day and ignored what had been paid,
    # so a tenant who had just settled September was still told rent was due
    # in eleven days. next_rent_due answers from the payment record, and the
    # Payments page reads the same answer.
    days_until_payment = None
    next_rent = None
    if profile.contract_start and not is_expired:
        today = date.today()
        from ...billing_utils import next_rent_due
        next_rent = next_rent_due(profile, today)
        if next_rent:
            days_until_payment = (next_rent["due_date"] - today).days

    # Calculate contract progress and days remaining
    days_remaining = None
    contract_progress = 0
    if profile.contract_start and profile.contract_end:
        today = date.today()
        total_days = (profile.contract_end - profile.contract_start).days
        days_elapsed = (today - profile.contract_start).days + 1  # Include current day
        days_remaining = (profile.contract_end - today).days
        
        if total_days > 0:
            contract_progress = int((days_elapsed / total_days) * 100)
            # Ensure progress is between 0 and 100
            contract_progress = max(0, min(100, contract_progress))

    # Get contract end date from profile
    is_commercial = bool(unit and "commercial" in (unit.type or "").lower())
    if profile.contract_end:
        contract_end_date = profile.contract_end.strftime("%B %d, %Y")
    else:
        contract_end_date = "N/A" if is_commercial else "Month-to-month"

    # --- Smart Insights: rule-based highlights computed from this tenant's
    # own real history (no external AI/LLM — same approach as the rest of
    # the system's "smart" features). ---
    rent_payments = [p for p in db.session.query(Payment).filter(
        Payment.tenant_profile_id == profile.id, Payment.is_deposit == False
    ).all()]
    on_time_rate = None
    if rent_payments:
        on_time_rate = round(sum(1 for p in rent_payments if not p.is_late) / len(rent_payments) * 100)
    total_rent_paid = sum(float(p.amount) for p in rent_payments)

    tenure_months = None
    if profile.contract_start:
        today = date.today()
        tenure_months = (today.year - profile.contract_start.year) * 12 + (today.month - profile.contract_start.month)
        if today.day < profile.contract_start.day:
            tenure_months -= 1
        tenure_months = max(0, tenure_months)

    # A single, priority-ordered recommendation — most actionable/urgent first.
    if is_expired:
        insight_message = "Your contract has expired. Submit a renewal request to continue your stay."
        insight_tone = "urgent"
    elif days_remaining is not None and days_remaining <= 30 and pending_renewals == 0:
        insight_message = f"Your contract ends in {days_remaining} day{'s' if days_remaining != 1 else ''}. Consider submitting a renewal request now so there's no gap in your stay."
        insight_tone = "warning"
    elif days_until_payment is not None and days_until_payment <= 3:
        insight_message = f"Rent is due in {days_until_payment} day{'s' if days_until_payment != 1 else ''}. Pay early to keep your on-time streak going."
        insight_tone = "warning"
    elif on_time_rate is not None and on_time_rate < 70:
        insight_message = f"Your on-time payment rate is {on_time_rate}%. Paying by the due date helps keep your account in good standing."
        insight_tone = "warning"
    elif on_time_rate == 100 and len(rent_payments) >= 2:
        insight_message = "You've paid on time every time so far — thank you for being a reliable tenant."
        insight_tone = "good"
    else:
        insight_message = "Everything looks good right now — no urgent action needed on your account."
        insight_tone = "good"

    from ...ai_utils import compute_water_bill
    water_bill_amount = compute_water_bill(unit.pax_range) if unit else None

    # Utilities begin the month AFTER move-in, so say which month that is
    # rather than leaving a tenant to wonder why their first month carried
    # no electric or water bill.
    from ...billing_utils import first_utility_month
    _first_um = first_utility_month(profile) if profile else None
    first_utility_month_label = None
    if _first_um:
        _y, _m = (int(x) for x in _first_um.split("-"))
        first_utility_month_label = date(_y, _m, 1).strftime("%B %Y")

    return render_template(
        "tenant/dashboard.html",
        on_time_rate=on_time_rate,
        total_rent_paid=total_rent_paid,
        rent_payment_count=len(rent_payments),
        tenure_months=tenure_months,
        insight_message=insight_message,
        insight_tone=insight_tone,
        profile=profile,
        unit=unit,
        water_bill_amount=water_bill_amount,
        first_utility_month_label=first_utility_month_label,
        contract_end_date=contract_end_date,
        days_until_payment=days_until_payment,
        next_rent=next_rent,
        days_remaining=days_remaining,
        contract_progress=contract_progress,
        unit_images=unit_images,
        total_payments=total_payments,
        active_concerns=active_concerns,
        pending_renewals=pending_renewals,
        recent_announcements=recent_announcements,
        recent_concerns=recent_concerns,
        recent_feedbacks=recent_feedbacks,
        recent_renewals=recent_renewals,
        recent_payments=recent_payments,
        deposit_info=deposit_info,
        unread_announcements_count=unread_count,
        unread_documents_count=unread_documents_count,
        is_expired=is_expired,
    )


@bp.get("/concerns")
@login_required
def concerns():
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()
    blocked = _ensure_active_contract(profile, is_expired)
    if blocked:
        return blocked

    # Get filter parameters
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    priority_filter = request.args.get('priority', '').strip()
    category_filter = request.args.get('category', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    # Base query
    query = db.session.query(Concern).filter(
        Concern.tenant_profile_id == profile.id,
        Concern.is_cancelled == False
    )

    # Apply filters
    if search:
        query = query.filter(
            db.or_(
                Concern.subject.ilike(f'%{search}%'),
                Concern.description.ilike(f'%{search}%')
            )
        )
    
    if status_filter:
        query = query.filter(Concern.status == ConcernStatus(status_filter))
    
    if priority_filter:
        query = query.filter(Concern.priority == priority_filter)
    
    if category_filter:
        query = query.filter(Concern.category == category_filter)
    
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Concern.created_at >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            from datetime import datetime, timedelta
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Concern.created_at < date_to_obj)
        except ValueError:
            pass

    query = query.order_by(Concern.created_at.desc())
    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=15, error_out=False)
    concerns = pagination.items

    # Calculate statistics from ALL concerns (not filtered)
    all_concerns = db.session.query(Concern).filter(
        Concern.tenant_profile_id == profile.id,
        Concern.is_cancelled == False
    ).all()

    from datetime import datetime, timedelta
    total_concerns = len(all_concerns)
    pending_concerns = sum(1 for c in all_concerns if c.status == ConcernStatus.PENDING)
    resolved_concerns = sum(1 for c in all_concerns if c.status == ConcernStatus.RESOLVED)
    
    # Calculate average response time
    response_times = []
    for c in all_concerns:
        if c.admin_response_at and c.created_at:
            delta = c.admin_response_at - c.created_at
            response_times.append(delta.total_seconds() / 3600)  # hours
    
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    # Calculate resolution rate
    resolution_rate = (resolved_concerns / total_concerns * 100) if total_concerns > 0 else 0
    
    # Most common category
    from collections import Counter
    categories = [c.category for c in all_concerns]
    most_common_category = Counter(categories).most_common(1)[0][0] if categories else 'N/A'

    stats = {
        'total': total_concerns,
        'pending': pending_concerns,
        'in_progress': sum(1 for c in all_concerns if c.status == ConcernStatus.IN_PROGRESS),
        'resolved': resolved_concerns,
        'avg_response_hours': avg_response_time,
        'resolution_rate': resolution_rate,
        'most_common_category': most_common_category
    }

    return render_template("tenant/concerns.html", concerns=concerns, pagination=pagination, stats=stats)


def _notify_admins_of_concern(*, subject, heading, profile, rows):
    """Email every admin about a concern.

    The concern itself is already committed by the time this runs, so this
    never raises: a mail outage must not turn a saved concern into a 500
    for the tenant who filed it. Replaces an import of app.email_utils,
    a module that does not exist — the import alone was the error.
    """
    from ...email_helper import send_email_async

    body = "".join(
        f"<p><strong>{label}:</strong> {value}</p>" for label, value in rows
    )
    html = (
        f"<h2>{heading}</h2>"
        f"<p><strong>Tenant:</strong> {profile.user.full_name if profile.user else '-'}</p>"
        f"<p><strong>Unit:</strong> {profile.unit.unit_code if profile.unit else '-'}</p>"
        f"{body}"
        f'<p><a href="{url_for("admin.concerns", _external=True)}">View in Admin Panel</a></p>'
    )
    try:
        admins = db.session.query(User).filter(User.role == Role.ADMIN).all()
        for admin in admins:
            send_email_async(subject, admin.email, admin.full_name or "Admin", html)
    except Exception as exc:                       # pragma: no cover - best effort
        current_app.logger.warning("concern notification failed: %s", exc)


@bp.post("/concerns")
@login_required
def create_concern():
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()
    blocked = _ensure_active_contract(profile, is_expired)
    if blocked:
        return blocked

    subject = (request.form.get("subject") or "").strip()
    description = (request.form.get("description") or "").strip()
    priority = (request.form.get("priority") or "medium").strip()
    category = (request.form.get("category") or "other").strip()
    
    if not subject or not description:
        flash("Please enter subject and description.", "warning")
        return redirect(url_for("tenant.concerns"))
    
    # Validate priority and category
    if priority not in ['low', 'medium', 'high', 'urgent']:
        priority = 'medium'
    
    if category not in ['maintenance', 'billing', 'noise', 'security', 'cleanliness', 'facilities', 'other']:
        category = 'other'
    
    # Handle file attachments
    attachments_list = []
    if 'attachments' in request.files:
        files = request.files.getlist('attachments')
        # Limit to 4 files
        files = files[:4]
        
        for file in files:
            if file and file.filename:
                # accept="..." is only a picker hint; check the real bytes
                _ok, _why = validate_upload(file, DOCUMENT_TYPES, label="attachment")
                if not _ok:
                    flash(_why, "warning")
                    return redirect(request.referrer or url_for("tenant.concerns"))
                from werkzeug.utils import secure_filename
                import os
                from datetime import datetime
                
                filename = secure_filename(file.filename)
                # Add timestamp to avoid conflicts
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_{filename}"
                
                # Save to uploads/concerns directory
                upload_dir = os.path.join('app', 'static', 'uploads', 'concerns')
                os.makedirs(upload_dir, exist_ok=True)
                
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)

                # Persist to Supabase Storage when configured; else local path
                from ... import supabase_storage
                _url = supabase_storage.upload_local_file(filepath, f"attachments/{filename}")
                attachments_list.append(_url or f"uploads/concerns/{filename}")
    
    # Convert attachments list to JSON
    import json
    attachments_json = json.dumps(attachments_list) if attachments_list else None

    c = Concern(
        tenant_profile_id=profile.id,
        subject=subject,
        description=description,
        status=ConcernStatus.PENDING,
        priority=priority,
        category=category,
        attachments_json=attachments_json
    )
    db.session.add(c)
    db.session.commit()
    
    # Tell the admins, but never at the tenant's expense: the concern is
    # already committed above, so a mail failure must not reach the browser.
    _notify_admins_of_concern(
        subject=f"New Concern Submitted: {subject}",
        heading="New Concern Submitted",
        profile=profile,
        rows=[("Subject", subject), ("Priority", priority.upper()),
              ("Category", category.title()), ("Description", description)],
    )

    from ...socket_events import emit_concern_notification
    emit_concern_notification({
        "id": c.id,
        "subject": c.subject,
        "tenant_name": profile.user.full_name if profile.user else None,
        "unit_code": profile.unit.unit_code if profile.unit else None,
    })

    flash("Concern submitted successfully.", "success")
    return redirect(url_for("tenant.concerns"))


@bp.post("/concerns/<int:concern_id>/follow-up")
@login_required
def add_concern_follow_up(concern_id: int):
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()
    blocked = _ensure_active_contract(profile, is_expired)
    if blocked:
        return blocked
    
    concern = db.session.get(Concern, concern_id)
    if not concern or concern.tenant_profile_id != profile.id:
        abort(404)
    
    message = (request.form.get("message") or "").strip()
    if not message:
        flash("Please enter a message.", "warning")
        return redirect(url_for("tenant.concerns"))
    
    # Handle file attachments
    attachments_list = []
    if 'attachments' in request.files:
        files = request.files.getlist('attachments')
        files = files[:4]
        
        for file in files:
            if file and file.filename:
                # accept="..." is only a picker hint; check the real bytes
                _ok, _why = validate_upload(file, DOCUMENT_TYPES, label="attachment")
                if not _ok:
                    flash(_why, "warning")
                    return redirect(request.referrer or url_for("tenant.concerns"))
                from werkzeug.utils import secure_filename
                import os
                from datetime import datetime
                
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_{filename}"
                
                upload_dir = os.path.join('app', 'static', 'uploads', 'concerns')
                os.makedirs(upload_dir, exist_ok=True)
                
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)

                from ... import supabase_storage
                _url = supabase_storage.upload_local_file(filepath, f"attachments/{filename}")
                attachments_list.append(_url or f"uploads/concerns/{filename}")
    
    import json
    attachments_json = json.dumps(attachments_list) if attachments_list else None
    
    follow_up = ConcernFollowUp(
        concern_id=concern_id,
        message=message,
        attachments_json=attachments_json
    )
    db.session.add(follow_up)
    db.session.commit()
    
    flash("Follow-up added successfully.", "success")
    return redirect(url_for("tenant.concerns"))


@bp.post("/concerns/<int:concern_id>/escalate")
@login_required
def escalate_concern(concern_id: int):
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()
    blocked = _ensure_active_contract(profile, is_expired)
    if blocked:
        return blocked
    
    concern = db.session.get(Concern, concern_id)
    if not concern or concern.tenant_profile_id != profile.id:
        abort(404)
    
    # Escalate priority
    if concern.priority == 'low':
        concern.priority = 'medium'
    elif concern.priority == 'medium':
        concern.priority = 'high'
    elif concern.priority == 'high':
        concern.priority = 'urgent'
    
    db.session.commit()
    
    _notify_admins_of_concern(
        subject=f"Concern Escalated to {concern.priority.upper()}: {concern.subject}",
        heading="Concern Escalated",
        profile=profile,
        rows=[("Subject", concern.subject),
              ("New Priority", concern.priority.upper())],
    )
    
    flash(f"Concern escalated to {concern.priority.upper()} priority.", "success")
    return redirect(url_for("tenant.concerns"))


@bp.post("/concerns/<int:concern_id>/cancel")
@login_required
def cancel_concern(concern_id: int):
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()
    blocked = _ensure_active_contract(profile, is_expired)
    if blocked:
        return blocked
    
    concern = db.session.get(Concern, concern_id)
    if not concern or concern.tenant_profile_id != profile.id:
        abort(404)
    
    from datetime import datetime
    concern.is_cancelled = True
    concern.cancelled_at = datetime.utcnow()
    db.session.commit()
    
    flash("Concern cancelled successfully.", "success")
    return redirect(url_for("tenant.concerns"))


@bp.post("/concerns/<int:concern_id>/rate")
@login_required
def rate_concern(concern_id: int):
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()
    blocked = _ensure_active_contract(profile, is_expired)
    if blocked:
        return blocked
    
    concern = db.session.get(Concern, concern_id)
    if not concern or concern.tenant_profile_id != profile.id:
        abort(404)
    
    rating = request.form.get("rating")
    feedback = (request.form.get("feedback") or "").strip()
    
    if not rating:
        flash("Please select a rating.", "warning")
        return redirect(url_for("tenant.concerns"))
    
    concern.satisfaction_rating = int(rating)
    concern.satisfaction_feedback = feedback if feedback else None
    db.session.commit()
    
    flash("Thank you for your feedback!", "success")
    return redirect(url_for("tenant.concerns"))


@bp.get("/payments")
@login_required
def payments():
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()

    # Get filter parameters
    search = request.args.get('search', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    year = request.args.get('year', '').strip()
    month = request.args.get('month', '').strip()
    method = request.args.get('method', '').strip()

    # Base query
    query = db.session.query(Payment).filter(Payment.tenant_profile_id == profile.id)

    # Apply filters
    if search:
        query = query.filter(
            db.or_(
                Payment.reference.ilike(f'%{search}%'),
                Payment.receipt_number.ilike(f'%{search}%')
            )
        )

    if method:
        if method == 'cash':
            # Payments recorded before payment_method existed default to Cash.
            query = query.filter(db.or_(Payment.payment_method == 'cash', Payment.payment_method.is_(None)))
        else:
            query = query.filter(Payment.payment_method == method)

    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Payment.paid_at >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            from datetime import datetime, timedelta
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Payment.paid_at < date_to_obj)
        except ValueError:
            pass
    
    if year:
        try:
            year_int = int(year)
            query = query.filter(db.extract('year', Payment.paid_at) == year_int)
        except ValueError:
            pass
    
    if month:
        try:
            month_int = int(month)
            query = query.filter(db.extract('month', Payment.paid_at) == month_int)
        except ValueError:
            pass

    # Calculate statistics — pending/rejected proof submissions aren't
    # confirmed money received yet, so they're shown in the list (tenant
    # needs to see their status) but excluded from the totals. Computed
    # against the full filtered set (not just the current page), so these
    # stay correct no matter which page is open. Built off the unordered
    # `query` — an aggregate SELECT with a leftover ORDER BY on a
    # non-aggregated/non-grouped column is invalid in Postgres.
    from sqlalchemy import func as _func
    confirmed_query = query.filter(Payment.payment_status.notin_(PAYMENT_STATUSES_NOT_COUNTED))
    # A deposit given back is its own Payment row; it is money the tenant
    # received, so it must not swell the total they have paid.
    total_amount = float(confirmed_query.with_entities(
        _func.coalesce(_func.sum(payment_revenue_amount()), 0)).scalar() or 0)
    total_count = confirmed_query.count()
    last_payment = confirmed_query.order_by(Payment.paid_at.desc()).first()

    query = query.order_by(Payment.paid_at.desc())
    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=20, error_out=False)
    payments = pagination.items

    # Next payment due (assuming monthly on contract start day)
    next_payment_due = None
    if profile.contract_start:
        from datetime import date
        today = date.today()
        contract_day = profile.contract_start.day
        next_payment_day = date(today.year, today.month, contract_day)
        if next_payment_day <= today:
            # Move to next month
            if today.month == 12:
                next_payment_day = date(today.year + 1, 1, contract_day)
            else:
                try:
                    next_payment_day = date(today.year, today.month + 1, contract_day)
                except ValueError:
                    # Handle months with fewer days
                    next_payment_day = date(today.year, today.month + 1, 28)
        next_payment_due = next_payment_day
    
    # Get available years for filter (confirmed payments only)
    all_payments = db.session.query(Payment).filter(
        Payment.tenant_profile_id == profile.id,
        Payment.payment_status.notin_(PAYMENT_STATUSES_NOT_COUNTED),
    ).all()
    available_years = sorted(set(p.paid_at.year for p in all_payments), reverse=True)

    # Yearly totals summary — always computed from full payment history,
    # independent of whatever filters are currently applied to the list.
    from collections import defaultdict
    yearly_totals = defaultdict(lambda: {'total': 0.0, 'count': 0})
    for p in all_payments:
        y = p.paid_at.year
        # Same sign rule as total_amount above: a returned deposit is money
        # that came back to the tenant, not another payment they made.
        sign = -1 if p.deposit_transaction_type == "deposit_returned" else 1
        yearly_totals[y]['total'] += sign * float(p.amount)
        yearly_totals[y]['count'] += 1
    yearly_summary = [
        {'year': y, 'total': v['total'], 'count': v['count']}
        for y, v in sorted(yearly_totals.items(), reverse=True)
    ]

    pending_count = query.filter(Payment.payment_status == 'pending').count()

    stats = {
        'total_amount': total_amount,
        'total_count': total_count,
        'last_payment': last_payment,
        'next_payment_due': next_payment_due,
        'available_years': available_years,
        'yearly_summary': yearly_summary,
        'pending_count': pending_count,
    }

    # Current unpaid utility bill (residential only — see UtilityBill docstring),
    # if any, for the itemized Rent+Electric+Water=Total card.
    from ...models import UtilityBill
    from ...billing_utils import get_rent_arrears

    # Unpaid rent accumulates in Payment/PaymentLedger, not on the bill row,
    # so the itemized card reads it from there to show the true total owed.
    rent_arrears = get_rent_arrears(profile)
    # Which bill the card shows. Viewing a month on the admin billing page
    # creates it, so a tenant can have rows for months that have not started
    # — and taking the newest unpaid one showed a tenant who was fully
    # settled a December bill due in 102 days, labelled as this month's.
    #
    # Among months that HAVE started, the newest unpaid one is the right
    # choice: carry-over means it already includes every earlier unpaid
    # balance. Only when nothing owing has started do we look ahead, and
    # then to the nearest month, so the tenant still sees what is coming.
    # Own import: this function also does `from datetime import date` inside a
    # conditional above, which makes `date` function-local and unbound here
    # whenever that branch is skipped.
    from datetime import date as _date
    _this_month = _date.today().strftime("%Y-%m")
    _unpaid = db.session.query(UtilityBill).filter(
        UtilityBill.tenant_profile_id == profile.id,
        UtilityBill.is_paid == False,  # noqa: E712
    )
    current_utility_bill = (
        _unpaid.filter(UtilityBill.billing_month <= _this_month)
        .order_by(UtilityBill.billing_month.desc())
        .first()
        or _unpaid.filter(UtilityBill.billing_month > _this_month)
        .order_by(UtilityBill.billing_month.asc())
        .first()
    )

    # Full utility history, newest first. The card above shows only what is
    # currently owed; without this the tenant has no way to see what they
    # settled and when, and has to ask the administrator.
    utility_bill_history = (
        db.session.query(UtilityBill)
        .filter(UtilityBill.tenant_profile_id == profile.id)
        .order_by(UtilityBill.billing_month.desc())
        .all()
    )

    # The month the tenant actually owes next. The proof form's month picker
    # used to open blank, so the tenant guessed — one picked October while
    # September was still unpaid, which recorded a month ahead and left the
    # real one owing, with nothing on either side saying so.
    from ...billing_utils import next_rent_due
    next_rent = next_rent_due(profile)

    return render_template(
        "tenant/payments.html", payments=payments, pagination=pagination, stats=stats,
        profile=profile, current_utility_bill=current_utility_bill,
        this_month=_this_month,
        next_rent=next_rent,
        rent_arrears=rent_arrears,
        utility_bill_history=utility_bill_history,
    )


@bp.post("/payments/submit-proof")
@login_required
def submit_payment_proof():
    """Tenant self-reports a bank transfer payment with a receipt/screenshot.

    Creates a Payment row with payment_status='pending' — it does NOT count
    toward totals or generate a ledger hash until an admin reviews and
    approves it (see admin.approve_payment_proof).
    """
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()
    blocked = _ensure_active_contract(profile, is_expired)
    if blocked:
        return blocked

    amount = request.form.get("amount") or "0"
    reference = (request.form.get("reference") or "").strip()
    payment_month = (request.form.get("payment_month") or "").strip()
    notes = (request.form.get("notes") or "").strip()
    proof = request.files.get("proof")
    if proof and proof.filename:
        ok, why = validate_upload(proof, DOCUMENT_TYPES, label="proof of payment")
        if not ok:
            flash(why, "warning")
            return redirect(url_for("tenant.payments"))

    try:
        amount_val = float(amount)
    except ValueError:
        amount_val = 0

    if amount_val <= 0:
        flash("Please enter a valid payment amount.", "warning")
        return redirect(url_for("tenant.payments"))

    if not reference:
        flash("Please enter the bank transfer reference number.", "warning")
        return redirect(url_for("tenant.payments"))

    if not proof or not proof.filename:
        flash("Please attach a screenshot or photo of your payment receipt.", "warning")
        return redirect(url_for("tenant.payments"))

    allowed_ext = {"jpg", "jpeg", "png", "webp", "gif", "pdf"}
    ext = proof.filename.rsplit(".", 1)[-1].lower() if "." in proof.filename else ""
    if ext not in allowed_ext:
        flash("Receipt must be an image (JPG/PNG/WEBP/GIF) or a PDF.", "warning")
        return redirect(url_for("tenant.payments"))

    from werkzeug.utils import secure_filename
    import os
    from datetime import datetime as _dt

    filename = secure_filename(proof.filename)
    filename = f"{profile.id}_{_dt.now().strftime('%Y%m%d_%H%M%S')}_{filename}"

    upload_dir = os.path.join("app", "static", "uploads", "payment_proofs")
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    proof.save(filepath)

    from ... import supabase_storage
    _url = supabase_storage.upload_local_file(filepath, f"payment_proofs/{filename}")
    proof_path = _url or f"uploads/payment_proofs/{filename}"

    payment = Payment(
        tenant_profile_id=profile.id,
        amount=amount_val,
        reference=reference,
        notes=notes or None,
        payment_month=payment_month or None,
        payment_status="pending",
        proof_file=proof_path,
        payment_method="bank_transfer",
        is_deposit=False,
    )
    db.session.add(payment)
    db.session.commit()

    from ...socket_events import emit_payment_proof_notification
    emit_payment_proof_notification({
        "id": payment.id,
        "amount": amount_val,
        "tenant_name": profile.user.full_name if profile.user else None,
        "unit_code": profile.unit.unit_code if profile.unit else None,
    })

    flash("Payment proof submitted. Admin will review and verify it shortly.", "success")
    return redirect(url_for("tenant.payments"))


@bp.get("/payments/export")
@login_required
def export_payments():
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()

    payments = (
        db.session.query(Payment)
        .filter(Payment.tenant_profile_id == profile.id)
        .order_by(Payment.paid_at.desc())
        .all()
    )

    # Create CSV
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Date', 'Receipt Number', 'Reference', 'Amount', 'Status', 'Notes'])
    
    # Data
    for p in payments:
        writer.writerow([
            p.paid_at.strftime('%Y-%m-%d %H:%M'),
            p.receipt_number or 'N/A',
            p.reference or 'N/A',
            f"₱{float(p.amount):,.2f}",
            'Late Payment' if p.is_late else 'On Time',
            p.notes or ''
        ])
    
    output.seek(0)
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=payment_history_{profile.user.full_name.replace(" ", "_")}.csv'}
    )


@bp.get("/payments/<int:payment_id>/receipt")
@login_required
def payment_receipt(payment_id: int):
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()
    
    payment = db.session.get(Payment, payment_id)
    if not payment or payment.tenant_profile_id != profile.id:
        abort(404)
    if payment.payment_status in ('pending', 'rejected'):
        flash("This payment hasn't been verified by admin yet, so there's no official receipt for it.", "warning")
        return redirect(url_for("tenant.payments"))

    # Generate PDF receipt
    from flask import make_response
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from io import BytesIO
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#D7B35B'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    elements.append(Paragraph("OFFICIAL RECEIPT", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Receipt info
    receipt_data = [
        ['Receipt Number:', payment.receipt_number or f'OR-{payment.id:06d}'],
        ['Date:', payment.paid_at.strftime('%B %d, %Y %I:%M %p')],
        ['', ''],
        ['Received from:', profile.user.full_name],
        ['Unit:', profile.unit.unit_code],
        ['', ''],
    ]
    
    # Parse breakdown if exists
    breakdown = {}
    if payment.breakdown_json:
        try:
            breakdown = json.loads(payment.breakdown_json)
        except:
            pass
    
    # reportlab's base PDF font has no glyph for ₱ (renders as a broken
    # box) — spelled out as "Php" instead, same fix as the lease contract
    # generator.
    if breakdown:
        receipt_data.append(['Payment Breakdown:', ''])
        if breakdown.get('rent'):
            receipt_data.append(['  Monthly Rent:', f"Php {float(breakdown['rent']):,.2f}"])
        if breakdown.get('utilities'):
            receipt_data.append(['  Utilities:', f"Php {float(breakdown['utilities']):,.2f}"])
        if breakdown.get('late_fee'):
            receipt_data.append(['  Late Fee:', f"Php {float(breakdown['late_fee']):,.2f}"])
        if breakdown.get('other'):
            receipt_data.append(['  Other Charges:', f"Php {float(breakdown['other']):,.2f}"])
        receipt_data.append(['', ''])

    receipt_data.extend([
        ['Total Amount:', f"Php {float(payment.amount):,.2f}"],
        ['Payment Method:', 'Cash/Bank Transfer'],
        ['Reference:', payment.reference or 'N/A'],
        ['Status:', 'PAID' if payment.payment_status == 'verified' else payment.payment_status.upper()],
    ])
    
    if payment.notes:
        receipt_data.append(['Notes:', payment.notes])
    
    table = Table(receipt_data, colWidths=[2.5*inch, 4*inch])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 0.5*inch))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    elements.append(Paragraph("This is a computer-generated receipt.", footer_style))
    elements.append(Paragraph("STMS - Student Tenant Management System", footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    # Download and Print pointed at this same URL and both opened a tab, so
    # the two buttons did exactly the same thing. ?download=1 now saves the
    # file; without it the PDF opens inline, which is what Print wants.
    disposition = "attachment" if request.args.get("download") == "1" else "inline"
    response.headers['Content-Disposition'] = (
        f'{disposition}; filename=receipt_{payment.id}.pdf'
    )
    
    return response


@bp.get("/announcements")
@login_required
def announcements():
    _ensure_tenant()
    from datetime import datetime
    
    # Get filter parameters
    search = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()
    
    # Base query - Get announcements for tenants
    not_expired = db.or_(Announcement.expires_at.is_(None), Announcement.expires_at >= datetime.utcnow())
    query = db.session.query(Announcement).filter(
        Announcement.is_active == True
    ).filter(not_expired).filter(db.or_(
        Announcement.target_audience == 'all',
        Announcement.target_audience == 'tenants'
    ))
    
    # Apply filters
    if search:
        query = query.filter(
            db.or_(
                Announcement.title.ilike(f'%{search}%'),
                Announcement.content.ilike(f'%{search}%')
            )
        )
    
    if category_filter:
        query = query.filter(Announcement.category == category_filter)
    
    query = query.order_by(
        Announcement.is_pinned.desc(),
        Announcement.created_at.desc()
    )

    # Get read announcement IDs
    read_announcement_ids = db.session.query(AnnouncementRead.announcement_id).filter(
        AnnouncementRead.user_id == current_user.id  # type: ignore[attr-defined]
    ).all()
    read_ids = [r[0] for r in read_announcement_ids]

    # Stats reflect the full filtered set, not just the current page.
    all_matching_announcements = query.all()
    total_announcements = len(all_matching_announcements)
    unread_count = sum(1 for a in all_matching_announcements if a.id not in read_ids)
    latest_announcement = all_matching_announcements[0] if all_matching_announcements else None

    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=10, error_out=False)
    announcements = pagination.items

    # Get available categories
    all_announcements = db.session.query(Announcement).filter(
        Announcement.is_active == True
    ).filter(not_expired).filter(db.or_(
        Announcement.target_audience == 'all',
        Announcement.target_audience == 'tenants'
    )).all()
    
    available_categories = sorted(set(a.category for a in all_announcements if a.category))
    
    stats = {
        'total': total_announcements,
        'unread': unread_count,
        'latest': latest_announcement,
        'available_categories': available_categories
    }
    
    return render_template("tenant/announcements.html", announcements=announcements, pagination=pagination, read_ids=read_ids, stats=stats)


@bp.post("/announcements/<int:announcement_id>/mark-read")
@login_required
def mark_announcement_read(announcement_id: int):
    _ensure_tenant()
    from datetime import datetime
    
    # Check if already marked as read
    existing = db.session.query(AnnouncementRead).filter(
        AnnouncementRead.announcement_id == announcement_id,
        AnnouncementRead.user_id == current_user.id  # type: ignore[attr-defined]
    ).first()
    
    if not existing:
        read_record = AnnouncementRead(
            announcement_id=announcement_id,
            user_id=current_user.id,  # type: ignore[attr-defined]
            read_at=datetime.utcnow()
        )
        db.session.add(read_record)
        db.session.commit()
    
    return redirect(url_for("tenant.announcements"))


@bp.get("/documents")
@login_required
def documents():
    _ensure_tenant()
    from datetime import datetime
    
    profile, is_expired = _get_tenant_profile()

    # Get filter parameters
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'newest').strip()

    # Base query
    query = db.session.query(Document).filter(Document.tenant_profile_id == profile.id)

    # Apply search
    if search:
        query = query.filter(Document.title.ilike(f'%{search}%'))

    # Apply sorting
    if sort_by == 'oldest':
        query = query.order_by(Document.uploaded_at.asc())
    elif sort_by == 'name':
        query = query.order_by(Document.title.asc())
    else:  # newest (default)
        query = query.order_by(Document.uploaded_at.desc())

    # Stat cards (per-type counts, latest upload, total size) reflect the
    # full filtered set, not just the current page — computed here before
    # pagination narrows `documents` down to one page's worth.
    all_matching_docs = query.all()
    docs_by_type = {}
    for doc in all_matching_docs:
        docs_by_type.setdefault(doc.document_type, []).append(doc)
    latest_upload = all_matching_docs[0].uploaded_at if all_matching_docs else None

    import os
    total_size = 0
    for doc in all_matching_docs:
        try:
            file_path = os.path.join('app', 'static', doc.file_path)
            if os.path.exists(file_path):
                total_size += os.path.getsize(file_path)
        except:
            pass
    total_size_mb = total_size / (1024 * 1024)

    stats = {
        'total_size_mb': total_size_mb,
        'latest_upload': latest_upload
    }

    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=12, error_out=False)
    documents = pagination.items

    # Auto-mark documents as viewed — only the ones actually shown on this
    # page, not every document matching the filter.
    for doc in documents:
        if not doc.is_viewed:
            doc.is_viewed = True
            doc.viewed_at = datetime.utcnow()

            # Track view in DocumentView table
            from ...models import DocumentView
            view_record = DocumentView(
                document_id=doc.id,
                user_id=current_user.id,  # type: ignore[attr-defined]
                viewed_at=datetime.utcnow(),
                downloaded=False
            )
            db.session.add(view_record)

    db.session.commit()

    # Flag utility bills that are likely outdated (a newer billing cycle has
    # probably passed). No stored "expiry date" exists for documents, so this
    # is a simple rule-based heuristic off the upload date — same approach as
    # the rest of the system's "smart" features (no external AI involved).
    UTILITY_BILL_TYPES = {'electricity_bill', 'water_bill', 'internet_bill'}
    STALE_BILL_DAYS = 35
    for doc in documents:
        doc.is_stale_bill = (
            doc.document_type in UTILITY_BILL_TYPES
            and (datetime.utcnow() - doc.uploaded_at).days > STALE_BILL_DAYS
        )

    return render_template("tenant/documents.html", documents=documents, pagination=pagination, docs_by_type=docs_by_type, stats=stats)


@bp.get("/documents/<int:document_id>/download")
@login_required
def download_document(document_id: int):
    """Proxies the file through our own server so the browser actually
    saves it, instead of just opening/previewing it — the HTML `download`
    attribute doesn't reliably work for cross-origin URLs like Supabase
    Storage links."""
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()

    doc = db.session.get(Document, document_id)
    if not doc or doc.tenant_profile_id != profile.id:
        abort(404)

    data = _fetch_file_bytes(doc.file_path)
    if data is None:
        flash("Couldn't retrieve this file. Please try again or contact admin.", "danger")
        return redirect(url_for("tenant.documents"))

    from ...models import DocumentView
    view_record = (
        db.session.query(DocumentView)
        .filter(DocumentView.document_id == doc.id, DocumentView.user_id == current_user.id)  # type: ignore[attr-defined]
        .order_by(DocumentView.viewed_at.desc())
        .first()
    )
    if view_record:
        view_record.downloaded = True
    db.session.commit()

    import os
    from flask import Response
    _, ext = os.path.splitext(doc.file_path.split("?")[0])
    safe_filename = f"{doc.document_type}_{doc.title[:50]}{ext}".replace(" ", "_")
    return Response(
        data,
        mimetype="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


@bp.get("/documents/download-all")
@login_required
def download_all_documents():
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()

    documents = db.session.query(Document).filter(Document.tenant_profile_id == profile.id).all()

    if not documents:
        flash("No documents to download.", "warning")
        return redirect(url_for("tenant.documents"))

    # Create ZIP file
    import zipfile
    from io import BytesIO
    import os

    memory_file = BytesIO()

    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for doc in documents:
            data = _fetch_file_bytes(doc.file_path)
            if data:
                _, ext = os.path.splitext(doc.file_path.split("?")[0])
                # Create safe filename
                safe_filename = f"{doc.document_type}_{doc.title[:50]}{ext}".replace(' ', '_')
                zf.writestr(safe_filename, data)

    memory_file.seek(0)
    
    from flask import send_file
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'documents_{profile.user.full_name.replace(" ", "_")}.zip'
    )


@bp.get("/renewal")
@login_required
def renewal():
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()

    if profile.unit and "commercial" not in (profile.unit.type or "").lower():
        flash("Residential units are month-to-month — use Move-Out Notice instead.", "info")
        return redirect(url_for("tenant.move_out_notice"))

    # Get filter parameters
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    sort_by = request.args.get('sort', 'newest').strip()

    # Base query
    query = db.session.query(RenewalRequest).filter(RenewalRequest.tenant_profile_id == profile.id)

    # Apply filters
    if search:
        query = query.filter(
            db.or_(
                RenewalRequest.notes.ilike(f'%{search}%'),
                db.cast(RenewalRequest.requested_end_date, db.String).ilike(f'%{search}%')
            )
        )
    
    if status_filter:
        query = query.filter(RenewalRequest.status == RenewalRequestStatus(status_filter))
    
    # Apply sorting
    if sort_by == 'oldest':
        query = query.order_by(RenewalRequest.created_at.asc())
    else:  # newest (default)
        query = query.order_by(RenewalRequest.created_at.desc())

    renewal_requests = query.all()

    # Calculate statistics
    from datetime import date, timedelta
    total_requests = len(renewal_requests)
    pending_requests = sum(1 for r in renewal_requests if r.status == RenewalRequestStatus.PENDING)
    approved_requests = sum(1 for r in renewal_requests if r.status == RenewalRequestStatus.APPROVED)
    rejected_requests = sum(1 for r in renewal_requests if r.status == RenewalRequestStatus.REJECTED)
    
    # Calculate days until contract expires
    days_until_expiry = None
    expiry_status = 'safe'  # safe, soon, urgent
    if profile.contract_end:
        today = date.today()
        days_until_expiry = (profile.contract_end - today).days

        if days_until_expiry <= 7:
            expiry_status = 'urgent'
        elif days_until_expiry <= 14:
            expiry_status = 'soon'
        else:
            expiry_status = 'safe'

    # Contract progress (% of lease term elapsed) — same calc as the dashboard's
    # Contract Monitoring bar, so both pages agree on the number.
    contract_progress = None
    if profile.contract_start and profile.contract_end:
        today = date.today()
        total_days = (profile.contract_end - profile.contract_start).days
        days_elapsed = (today - profile.contract_start).days + 1
        if total_days > 0:
            contract_progress = max(0, min(100, int((days_elapsed / total_days) * 100)))

    stats = {
        'total': total_requests,
        'pending': pending_requests,
        'approved': approved_requests,
        'rejected': rejected_requests,
        'days_until_expiry': days_until_expiry,
        'expiry_status': expiry_status,
        'contract_progress': contract_progress,
    }

    return render_template("tenant/renewal.html", profile=profile, renewal_requests=renewal_requests, stats=stats)


@bp.post("/renewal")
@login_required
def create_renewal_request():
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()

    requested_end_date_str = request.form.get("requested_end_date")
    notes = (request.form.get("notes") or "").strip()

    if not requested_end_date_str:
        flash("Please select a requested end date.", "warning")
        return redirect(url_for("tenant.renewal"))

    try:
        requested_end_date = date.fromisoformat(requested_end_date_str)
    except ValueError:
        flash("Invalid date format.", "warning")
        return redirect(url_for("tenant.renewal"))

    renewal = RenewalRequest(
        tenant_profile_id=profile.id,
        requested_end_date=requested_end_date,
        notes=notes,
        status=RenewalRequestStatus.PENDING,
    )
    db.session.add(renewal)
    db.session.commit()

    from ...socket_events import emit_renewal_notification
    emit_renewal_notification({
        "id": renewal.id,
        "tenant_name": profile.user.full_name if profile.user else None,
        "unit_code": profile.unit.unit_code if profile.unit else None,
        "requested_end_date": requested_end_date.isoformat(),
    })

    flash("Renewal request submitted.", "success")
    return redirect(url_for("tenant.renewal"))


@bp.post("/renewal/<int:renewal_id>/cancel")
@login_required
def cancel_renewal_request(renewal_id: int):
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()
    
    renewal = db.session.get(RenewalRequest, renewal_id)
    if not renewal or renewal.tenant_profile_id != profile.id:
        abort(404)
    
    # Only allow cancellation of pending requests
    if renewal.status != RenewalRequestStatus.PENDING:
        flash("Only pending requests can be cancelled.", "warning")
        return redirect(url_for("tenant.renewal"))
    
    # Delete the request
    db.session.delete(renewal)
    db.session.commit()
    
    flash("Renewal request cancelled successfully.", "success")
    return redirect(url_for("tenant.renewal"))


@bp.get("/move-out-notice")
@login_required
def move_out_notice():
    """Residential-only page — no fixed contract end, so instead of
    renewing, tenants give advance notice of their intended move-out date."""
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()

    if profile.unit and "commercial" in (profile.unit.type or "").lower():
        flash("Commercial units are contract-based — use Renewal Request instead.", "info")
        return redirect(url_for("tenant.renewal"))

    notices = (
        db.session.query(MoveOutNotice)
        .filter(MoveOutNotice.tenant_profile_id == profile.id)
        .order_by(MoveOutNotice.created_at.desc())
        .all()
    )

    return render_template(
        "tenant/move_out_notice.html",
        profile=profile,
        notices=notices,
        today=date.today().isoformat(),
    )


@bp.post("/move-out-notice")
@login_required
def create_move_out_notice():
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()

    move_out_date_str = request.form.get("move_out_date")
    notes = (request.form.get("notes") or "").strip()

    if not move_out_date_str:
        flash("Please select your intended move-out date.", "warning")
        return redirect(url_for("tenant.move_out_notice"))

    try:
        move_out_date = date.fromisoformat(move_out_date_str)
    except ValueError:
        flash("Invalid date format.", "warning")
        return redirect(url_for("tenant.move_out_notice"))

    if move_out_date < date.today():
        flash("Move-out date can't be in the past.", "warning")
        return redirect(url_for("tenant.move_out_notice"))

    # Only one active (pending/acknowledged) notice at a time — resubmitting
    # should update the existing one, not create a stray duplicate.
    existing = (
        db.session.query(MoveOutNotice)
        .filter(
            MoveOutNotice.tenant_profile_id == profile.id,
            MoveOutNotice.status.in_([MoveOutNoticeStatus.PENDING, MoveOutNoticeStatus.ACKNOWLEDGED]),
        )
        .first()
    )
    if existing:
        flash("You already have an active move-out notice. Cancel it first if you'd like to submit a different date.", "warning")
        return redirect(url_for("tenant.move_out_notice"))

    notice = MoveOutNotice(
        tenant_profile_id=profile.id,
        original_move_out_date=move_out_date,
        planned_move_out_date=move_out_date,
        notes=notes or None,
        status=MoveOutNoticeStatus.PENDING,
    )
    db.session.add(notice)
    db.session.commit()

    from ...socket_events import emit_move_out_notice_notification
    emit_move_out_notice_notification({
        "id": notice.id,
        "tenant_name": profile.user.full_name if profile.user else None,
        "unit_code": profile.unit.unit_code if profile.unit else None,
        "move_out_date": move_out_date.isoformat(),
    })

    flash("Move-out notice submitted. Admin will review it shortly.", "success")
    return redirect(url_for("tenant.move_out_notice"))


@bp.post("/move-out-notice/<int:notice_id>/cancel")
@login_required
def cancel_move_out_notice(notice_id: int):
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()

    notice = db.session.get(MoveOutNotice, notice_id)
    if not notice or notice.tenant_profile_id != profile.id:
        abort(404)

    if notice.status not in (MoveOutNoticeStatus.PENDING, MoveOutNoticeStatus.ACKNOWLEDGED):
        flash("This notice can no longer be cancelled.", "warning")
        return redirect(url_for("tenant.move_out_notice"))

    notice.status = MoveOutNoticeStatus.CANCELLED
    db.session.commit()

    flash("Move-out notice cancelled. You're staying — no changes to your account.", "success")
    return redirect(url_for("tenant.move_out_notice"))


@bp.get("/feedback")
@login_required
def feedback():
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()
    blocked = _ensure_active_contract(profile, is_expired)
    if blocked:
        return blocked

    # Get filter parameters
    search = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()
    status_filter = request.args.get('status', '').strip()
    rating_filter = request.args.get('rating', '').strip()

    # Base query
    query = db.session.query(Feedback).filter(Feedback.tenant_profile_id == profile.id)

    # Apply filters
    if search:
        query = query.filter(
            db.or_(
                Feedback.comments.ilike(f'%{search}%'),
                Feedback.category.ilike(f'%{search}%')
            )
        )
    
    if category_filter:
        query = query.filter(Feedback.category == category_filter)
    
    if status_filter:
        query = query.filter(Feedback.status == FeedbackStatus(status_filter))
    
    if rating_filter:
        query = query.filter(Feedback.rating == int(rating_filter))

    query = query.order_by(Feedback.created_at.desc())

    # Stats and the "Print all feedback" JSON payload reflect the full
    # filtered set (not just the current page) — printing should include
    # everything matching the current filter, not just what's visible.
    all_matching_feedbacks = query.all()
    total_feedback = len(all_matching_feedbacks)
    submitted_count = sum(1 for f in all_matching_feedbacks if f.status == FeedbackStatus.SUBMITTED)
    reviewed_count = sum(1 for f in all_matching_feedbacks if f.status == FeedbackStatus.REVIEWED)

    # Calculate average rating
    ratings = [f.rating for f in all_matching_feedbacks if f.rating is not None]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0

    # Most used category
    from collections import Counter
    categories = [f.category for f in all_matching_feedbacks]
    most_common_category = Counter(categories).most_common(1)[0][0] if categories else 'N/A'

    stats = {
        'total': total_feedback,
        'submitted': submitted_count,
        'reviewed': reviewed_count,
        'avg_rating': avg_rating,
        'most_common_category': most_common_category.replace('_', ' ').title()
    }

    feedbacks_json = [
        {
            "category": f.category,
            "rating": f.rating,
            "comments": f.comments,
            "status": {"value": f.status.value},
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in all_matching_feedbacks
    ]

    page = request.args.get('page', 1, type=int)
    pagination = db.paginate(query, page=page, per_page=15, error_out=False)
    feedbacks = pagination.items

    return render_template("tenant/feedback.html", feedbacks=feedbacks, pagination=pagination, feedbacks_json=feedbacks_json, stats=stats, profile=profile)


@bp.post("/feedback")
@login_required
def create_feedback():
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()
    blocked = _ensure_active_contract(profile, is_expired)
    if blocked:
        return blocked

    category = (request.form.get("category") or "").strip()
    rating_str = request.form.get("rating")
    comments = (request.form.get("comments") or "").strip()

    if not category or not comments:
        flash("Please enter category and comments.", "warning")
        return redirect(url_for("tenant.feedback"))

    rating = int(rating_str) if rating_str else None

    feedback = Feedback(
        tenant_profile_id=profile.id,
        unit_id=profile.unit_id,  # Add unit_id for unit-specific ratings
        category=category,
        rating=rating,
        comments=comments,
        status=FeedbackStatus.SUBMITTED,
    )
    db.session.add(feedback)
    db.session.commit()

    from ...socket_events import emit_feedback_notification
    emit_feedback_notification({
        "id": feedback.id,
        "tenant_name": profile.user.full_name if profile.user else None,
        "unit_code": profile.unit.unit_code if profile.unit else None,
        "rating": feedback.rating,
    })

    flash("Feedback submitted.", "success")
    return redirect(url_for("tenant.feedback"))


@bp.post("/feedback/<int:feedback_id>/edit")
@login_required
def edit_feedback(feedback_id: int):
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()
    blocked = _ensure_active_contract(profile, is_expired)
    if blocked:
        return blocked
    
    feedback = db.session.get(Feedback, feedback_id)
    if not feedback or feedback.tenant_profile_id != profile.id:
        abort(404)
    
    # Only allow editing of submitted feedback
    if feedback.status != FeedbackStatus.SUBMITTED:
        flash("Only submitted feedback can be edited.", "warning")
        return redirect(url_for("tenant.feedback"))
    
    category = (request.form.get("category") or "").strip()
    rating_str = request.form.get("rating")
    comments = (request.form.get("comments") or "").strip()
    
    if not category or not comments:
        flash("Please enter category and comments.", "warning")
        return redirect(url_for("tenant.feedback"))
    
    feedback.category = category
    feedback.rating = int(rating_str) if rating_str else None
    feedback.comments = comments
    
    db.session.commit()
    flash("Feedback updated successfully.", "success")
    return redirect(url_for("tenant.feedback"))


@bp.post("/feedback/<int:feedback_id>/delete")
@login_required
def delete_feedback(feedback_id: int):
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()
    blocked = _ensure_active_contract(profile, is_expired)
    if blocked:
        return blocked
    
    feedback = db.session.get(Feedback, feedback_id)
    if not feedback or feedback.tenant_profile_id != profile.id:
        abort(404)
    
    # Only allow deletion of submitted feedback
    if feedback.status != FeedbackStatus.SUBMITTED:
        flash("Only submitted feedback can be deleted.", "warning")
        return redirect(url_for("tenant.feedback"))
    
    db.session.delete(feedback)
    db.session.commit()
    
    flash("Feedback deleted successfully.", "success")
    return redirect(url_for("tenant.feedback"))


@bp.get("/settings")
@login_required
def settings():
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()

    # Calculate activity summary
    total_concerns = db.session.query(Concern).filter(Concern.tenant_profile_id == profile.id).count()
    total_feedback = db.session.query(Feedback).filter(Feedback.tenant_profile_id == profile.id).count()
    total_payments = db.session.query(Payment).filter(Payment.tenant_profile_id == profile.id).count()
    total_renewals = db.session.query(RenewalRequest).filter(RenewalRequest.tenant_profile_id == profile.id).count()

    activity_stats = {
        'concerns': total_concerns,
        'feedback': total_feedback,
        'payments': total_payments,
        'renewals': total_renewals
    }

    # Calculate days since password changed
    days_since_password_change = None
    if profile.password_changed_at:
        from datetime import datetime
        delta = datetime.utcnow() - profile.password_changed_at
        days_since_password_change = delta.days

    return render_template("tenant/settings.html", profile=profile, activity_stats=activity_stats, days_since_password_change=days_since_password_change)


@bp.post("/settings")
@login_required
def update_settings():
    _ensure_tenant()
    profile, is_expired = _get_tenant_profile()

    full_name = (request.form.get("full_name") or "").strip()
    current_password = (request.form.get("current_password") or "").strip()
    new_password = (request.form.get("new_password") or "").strip()
    confirm_password = (request.form.get("confirm_password") or "").strip()

    # An unticked checkbox sends nothing, so a POST that never carried the
    # preference block reads identically to one where the tenant turned all
    # three off. The avatar form posts only full_name — without this marker
    # it silently switched every notification off. Only the form that owns
    # these fields may change them.
    prefs_submitted = request.form.get("prefs_form") == "1"
    email_announcements = request.form.get("email_announcements") == "on"
    email_payment_reminders = request.form.get("email_payment_reminders") == "on"
    email_concern_updates = request.form.get("email_concern_updates") == "on"

    if not full_name:
        flash("Please enter your full name.", "warning")
        return redirect(url_for("tenant.settings"))

    # Update name
    current_user.full_name = full_name  # type: ignore[attr-defined]

    # Profile photo (optional)
    avatar_file = request.files.get("avatar")
    if avatar_file and avatar_file.filename:
        allowed_ext = {"jpg", "jpeg", "png", "webp", "gif"}
        ext = avatar_file.filename.rsplit(".", 1)[-1].lower() if "." in avatar_file.filename else ""
        if ext not in allowed_ext:
            flash("Profile photo must be a JPG, PNG, WEBP, or GIF image.", "warning")
            return redirect(url_for("tenant.settings"))

        from werkzeug.utils import secure_filename
        import os
        from datetime import datetime as _dt

        filename = secure_filename(avatar_file.filename)
        filename = f"{current_user.id}_{_dt.now().strftime('%Y%m%d_%H%M%S')}_{filename}"  # type: ignore[attr-defined]

        upload_dir = os.path.join("app", "static", "uploads", "avatars")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        avatar_file.save(filepath)

        from ... import supabase_storage
        _url = supabase_storage.upload_local_file(filepath, f"avatars/{filename}")
        current_user.profile_picture = _url or f"uploads/avatars/{filename}"  # type: ignore[attr-defined]

    if prefs_submitted:
        profile.email_announcements = email_announcements
        profile.email_payment_reminders = email_payment_reminders
        profile.email_concern_updates = email_concern_updates

    # Update password if provided
    if new_password:
        if not current_password:
            flash("Please enter your current password to change password.", "warning")
            return redirect(url_for("tenant.settings"))

        from ...security import verify_password
        # verify_password takes (stored_value, candidate). The arguments were
        # the other way round here, which a plain-text equality check hid —
        # with real hashing it would have rejected every correct password.
        if not verify_password(current_user.password_hash, current_password):  # type: ignore[attr-defined]
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("tenant.settings"))

        if new_password != confirm_password:
            flash("New passwords do not match.", "warning")
            return redirect(url_for("tenant.settings"))

        # Password validation - must have 8+ chars, 1 uppercase, 1 lowercase, 1 number, 1 special char
        if len(new_password) < 8:
            flash("Password must be at least 8 characters.", "warning")
            return redirect(url_for("tenant.settings"))

        if not re.search(r"[A-Z]", new_password):
            flash("Password must contain at least 1 uppercase letter.", "warning")
            return redirect(url_for("tenant.settings"))

        if not re.search(r"[a-z]", new_password):
            flash("Password must contain at least 1 lowercase letter.", "warning")
            return redirect(url_for("tenant.settings"))

        if not re.search(r"[0-9]", new_password):
            flash("Password must contain at least 1 number.", "warning")
            return redirect(url_for("tenant.settings"))

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", new_password):
            flash("Password must contain at least 1 special character.", "warning")
            return redirect(url_for("tenant.settings"))

        current_user.password_hash = hash_password(new_password)  # type: ignore[attr-defined]
        
        # Update password changed timestamp
        from datetime import datetime
        profile.password_changed_at = datetime.utcnow()

    db.session.commit()
    flash("Settings updated successfully.", "success")
    return redirect(url_for("tenant.settings"))

