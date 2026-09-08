from pathlib import Path

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from ...extensions import db
from ...upload_validation import validate_upload, DOCUMENT_TYPES, IMAGE_TYPES
from ...models import Role, Unit, UnitStatus
from ...ocr import scan_id_fields

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/units")
def units():
    # Used for polling on dashboards (real-time-ish).
    ids_raw = (request.args.get("ids") or "").strip()
    # Exclude archived units from API
    query = db.session.query(Unit).filter(Unit.is_archived == False)
    if ids_raw:
        try:
            ids = [int(x) for x in ids_raw.split(",") if x.strip().isdigit()]
            if ids:
                query = query.filter(Unit.id.in_(ids))
        except ValueError:
            pass
    units = query.all()
    return jsonify(
        {
            "units": [
                {
                    "id": u.id,
                    "unit_code": u.unit_code,
                    "building_id": u.building_id,
                    "unit_number": u.unit_number,
                    "status": u.status.value,
                    "price_monthly": float(u.price_monthly),
                }
                for u in units
            ]
        }
    )


@bp.get("/admin/metrics")
@login_required
def admin_metrics():
    if current_user.role != Role.ADMIN:  # type: ignore[attr-defined]
        return jsonify({"error": "forbidden"}), 403

    # Exclude archived units from metrics
    total = db.session.query(Unit).filter(Unit.is_archived == False).count()
    available = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.AVAILABLE).count()
    occupied = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.OCCUPIED).count()
    reserved = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.RESERVED).count()
    unpaid = db.session.query(Unit).filter(Unit.is_archived == False, Unit.status == UnitStatus.UNPAID).count()
    return jsonify(
        {
            "total": total,
            "available": available,
            "occupied": occupied,
            "reserved": reserved,
            "unpaid": unpaid,
        }
    )


@bp.post("/ocr-id")
@login_required
def ocr_id():
    upload = request.files.get("id_upload")
    if upload and upload.filename:
        _ok, _why = validate_upload(upload, DOCUMENT_TYPES, label="ID")
        if not _ok:
            return jsonify({"ok": False, "error": _why}), 400
    if not upload or not upload.filename:
        return jsonify({"id_type": "", "id_number": "", "message": "No file uploaded"}), 400

    filename = secure_filename(upload.filename)
    uploads_dir = Path(current_app.config["UPLOAD_FOLDER"])
    uploads_dir.mkdir(parents=True, exist_ok=True)
    save_path = uploads_dir / f"ocr_{filename}"
    upload.save(save_path)

    result = scan_id_fields(save_path)
    return jsonify(result)


@bp.get("/units/status")
@login_required
def units_status():
    """Real-time unit status endpoint with automatic unpaid detection"""
    if current_user.role != Role.ADMIN:  # type: ignore[attr-defined]
        return jsonify({"error": "forbidden"}), 403
    
    from datetime import date, timedelta
    from ...models import TenantProfile, Payment
    
    # Get all units (exclude archived)
    units = db.session.query(Unit).filter(Unit.is_archived == False).all()
    
    # Check for unpaid tenants (no payment in the last 30 days)
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    
    units_data = []
    stats = {
        'available': 0,
        'occupied': 0,
        'reserved': 0,
        'unpaid': 0
    }
    
    for unit in units:
        current_status = unit.status.value
        
        # If unit is occupied, check if tenant has paid in the last 30 days
        if unit.status == UnitStatus.OCCUPIED:
            tenant = db.session.query(TenantProfile).filter(
                TenantProfile.unit_id == unit.id,
                TenantProfile.is_active == True
            ).first()
            
            if tenant:
                # Check for recent payment
                recent_payment = db.session.query(Payment).filter(
                    Payment.tenant_profile_id == tenant.id,
                    Payment.paid_at >= thirty_days_ago
                ).first()
                
                # If no recent payment, mark as unpaid
                if not recent_payment:
                    if unit.status != UnitStatus.UNPAID:
                        unit.status = UnitStatus.UNPAID
                        db.session.commit()
                    current_status = 'unpaid'
                else:
                    # If there's a recent payment and status is unpaid, change back to occupied
                    if unit.status == UnitStatus.UNPAID:
                        unit.status = UnitStatus.OCCUPIED
                        db.session.commit()
                        current_status = 'occupied'
        
        units_data.append({
            'id': unit.id,
            'status': current_status
        })
        
        # Update stats
        stats[current_status] = stats.get(current_status, 0) + 1
    
    return jsonify({
        'units': units_data,
        'stats': stats,
        'timestamp': today.isoformat()
    })

