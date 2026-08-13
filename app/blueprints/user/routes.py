from __future__ import annotations

import base64
import uuid
from datetime import date
from pathlib import Path
import re

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ...extensions import db
from ...models import (
    Building,
    DepositStatus,
    FaceMatchResult,
    IdentityVerification,
    Reservation,
    ReservationStatus,
    Role,
    Unit,
    UnitStatus,
    VerificationResult,
    VerificationStatus,
)
from ...ocr import scan_id_fields

try:
    from ...face_verification import (
        verify_identity, 
        detect_fake_id,
        FACE_VERIFICATION_AVAILABLE,
        LIVENESS_DETECTION_AVAILABLE,
    )
except ImportError:
    FACE_VERIFICATION_AVAILABLE = False
    LIVENESS_DETECTION_AVAILABLE = False
    verify_identity = None
    detect_fake_id = None

bp = Blueprint("user", __name__, url_prefix="/user")


def _ensure_user_role():
    if current_user.role not in (Role.USER,):  # type: ignore[attr-defined]
        abort(403)


@bp.get("/dashboard")
@login_required
def dashboard():
    _ensure_user_role()

    buildings = db.session.query(Building).order_by(Building.code.asc()).all()
    # Exclude archived units from user view
    units = (
        db.session.query(Unit)
        .filter(Unit.is_archived == False)
        .order_by(Unit.building_id.asc(), Unit.unit_number.asc())
        .all()
    )
    
    # Group units by building
    units_by_building = {}
    for u in units:
        if u.building_id not in units_by_building:
            units_by_building[u.building_id] = []
        units_by_building[u.building_id].append(u)
    
    reservations = (
        db.session.query(Reservation)
        .filter(Reservation.user_id == current_user.id)  # type: ignore[attr-defined]
        .order_by(Reservation.created_at.desc())
        .all()
    )
    return render_template("user/dashboard.html", buildings=buildings, units_by_building=units_by_building, reservations=reservations)


@bp.get("/reserve/<int:unit_id>")
@login_required
def reserve(unit_id: int):
    _ensure_user_role()
    unit = db.session.get(Unit, unit_id)
    if not unit:
        abort(404)
    if unit.status != UnitStatus.AVAILABLE:
        flash("Unit is not available.", "warning")
        return redirect(url_for("user.dashboard"))
    return render_template("user/reserve.html", unit=unit, today=date.today())


@bp.post("/reserve/<int:unit_id>")
@login_required
def reserve_post(unit_id: int):
    _ensure_user_role()

    unit = db.session.get(Unit, unit_id)
    if not unit:
        abort(404)
    if unit.status != UnitStatus.AVAILABLE:
        flash("Unit is not available.", "warning")
        return redirect(url_for("public.home") + "#units")

    full_name = (request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    contact = (request.form.get("contact") or "").strip()
    id_type = (request.form.get("id_type") or "").strip()
    id_number = (request.form.get("id_number") or "").strip()
    move_in_date_raw = request.form.get("move_in_date") or ""
    move_out_date_raw = request.form.get("move_out_date") or ""

    if not full_name or not email or not contact or not move_in_date_raw or not move_out_date_raw:
        flash("Please complete the reservation form.", "warning")
        return redirect(url_for("public.home") + "#units")
    if not re.fullmatch(r"\d{11}", contact):
        flash("Contact number must be exactly 11 digits.", "warning")
        return redirect(url_for("public.home") + "#units")

    try:
        move_in = date.fromisoformat(move_in_date_raw)
    except ValueError:
        flash("Invalid move-in date.", "warning")
        return redirect(url_for("public.home") + "#units")

    try:
        move_out = date.fromisoformat(move_out_date_raw)
    except ValueError:
        flash("Invalid move-out date.", "warning")
        return redirect(url_for("public.home") + "#units")

    if move_out <= move_in:
        flash("Move-out date must be after move-in date.", "warning")
        return redirect(url_for("public.home") + "#units")

    upload = request.files.get("id_upload")
    selfie_upload = request.files.get("selfie_upload")
    selfie_data_url = (request.form.get("selfie_data_url") or "").strip()
    upload_path = None
    selfie_path = None
    id_local_path = None      # local file (for OCR / face verification)
    selfie_local_path = None  # local file (for face verification)
    ocr_result: dict[str, str] = {"id_type": "", "id_number": ""}
    
    # Handle ID upload
    if upload and upload.filename:
        filename = secure_filename(upload.filename)
        uploads_dir = Path(current_app.config["UPLOAD_FOLDER"])
        uploads_dir.mkdir(parents=True, exist_ok=True)
        save_path = uploads_dir / filename
        upload.save(save_path)
        id_local_path = str(save_path)
        ocr_result = scan_id_fields(save_path)  # OCR needs the local file
        from ... import supabase_storage
        _url = supabase_storage.upload_local_file(str(save_path), f"ids/{filename}")
        upload_path = _url or str(save_path).replace("app/static/", "")
    
    # Handle selfie - prefer live-captured base64 data URL over file upload
    uploads_dir = Path(current_app.config["UPLOAD_FOLDER"])
    uploads_dir.mkdir(parents=True, exist_ok=True)
    if selfie_data_url and selfie_data_url.startswith("data:image"):
        try:
            header, encoded = selfie_data_url.split(",", 1)
            ext = "png" if "png" in header else "jpg"
            filename = f"selfie_{uuid.uuid4().hex}.{ext}"
            save_path = uploads_dir / filename
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(encoded))
            selfie_local_path = str(save_path)
            from ... import supabase_storage
            _surl = supabase_storage.upload_local_file(str(save_path), f"selfies/{filename}")
            selfie_path = _surl or str(save_path).replace("app/static/", "")
        except Exception as e:
            current_app.logger.warning(f"Failed to decode selfie data URL: {e}")
    elif selfie_upload and selfie_upload.filename:
        filename = secure_filename(selfie_upload.filename)
        save_path = uploads_dir / filename
        selfie_upload.save(save_path)
        selfie_local_path = str(save_path)
        from ... import supabase_storage
        _surl = supabase_storage.upload_local_file(str(save_path), f"selfies/{filename}")
        selfie_path = _surl or str(save_path).replace("app/static/", "")
    
    # AI-Assisted Identity Verification
    face_match_score = None
    verification_status = VerificationStatus.PENDING
    fake_id_flag = False
    id_authenticity_score = None
    fake_detection_data = {}
    
    # Run fake ID detection on uploaded ID (uses the LOCAL file)
    if id_local_path and FACE_VERIFICATION_AVAILABLE and detect_fake_id:
        fake_detection_data = detect_fake_id(id_local_path)
        fake_id_flag = fake_detection_data.get("is_fake", False)
        id_authenticity_score = 1.0 - fake_detection_data.get("fake_score", 0.0)

    if id_local_path and selfie_local_path and FACE_VERIFICATION_AVAILABLE and verify_identity:
        # Run face verification on the LOCAL files
        verification_result = verify_identity(id_local_path, selfie_local_path)
        
        if verification_result.get("success"):
            face_match_score = verification_result.get("face_match_score")
            verification_status = VerificationStatus.VERIFIED if verification_result.get("verification_status") == "verified" else VerificationStatus.FAILED
            fake_id_flag = fake_id_flag or verification_result.get("fake_id_flag", False)
            
            # If verification failed, show warning
            if verification_status == VerificationStatus.FAILED:
                flash("Identity verification failed. Your reservation will require manual review.", "warning")
            elif fake_id_flag:
                flash("Potential fake ID detected. Your reservation will require manual review.", "warning")
        else:
            verification_status = VerificationStatus.MANUAL_REVIEW
            flash("Identity verification unavailable. Your reservation will require manual review.", "warning")
    elif upload_path and selfie_path:
        # Face verification not available, set to manual review
        verification_status = VerificationStatus.MANUAL_REVIEW
        flash("Face verification temporarily unavailable. Your reservation will require manual review.", "warning")
    
    if not id_type and not ocr_result.get("id_type"):
        flash("ID Type is required. OCR could not detect it, please type manually.", "warning")
        return redirect(url_for("public.home") + "#units")
    if not id_number and not ocr_result.get("id_number"):
        flash("ID Number is required. OCR could not detect it, please type manually.", "warning")
        return redirect(url_for("public.home") + "#units")

    reservation = Reservation(
        user_id=current_user.id,  # type: ignore[attr-defined]
        unit_id=unit.id,
        full_name=full_name,
        email=email,
        contact=contact,
        id_type=id_type or ocr_result.get("id_type") or None,
        id_number=id_number or ocr_result.get("id_number") or None,
        move_in_date=move_in,
        move_out_date=move_out,
        id_upload_path=upload_path,
        ocr_name=ocr_result.get("name"),
        ocr_id_number=ocr_result.get("id_number"),
        selfie_image=selfie_path,
        face_match_score=face_match_score,
        verification_status=verification_status,
        fake_id_flag=fake_id_flag,
        id_authenticity_score=id_authenticity_score,
        deposit_amount=5000.00,
        deposit_status=DepositStatus.HELD,
        status=ReservationStatus.PENDING,
    )
    if verification_status == VerificationStatus.VERIFIED:
        unit.status = UnitStatus.RESERVED

    db.session.add(reservation)
    db.session.flush()  # Get reservation.id for verification log
    
    # Create identity verification log for audit trail
    import json
    qr_check = fake_detection_data.get("qr_check", {})
    verification_log = IdentityVerification(
        reservation_id=reservation.id,
        user_id=current_user.id,
        id_image_path=upload_path,
        id_type_detected=ocr_result.get("id_type"),
        id_number_detected=ocr_result.get("id_number"),
        fake_score=fake_detection_data.get("fake_score"),
        is_fake=fake_id_flag,
        ela_score=fake_detection_data.get("ela_score"),
        noise_score=fake_detection_data.get("noise_score"),
        has_exif=fake_detection_data.get("has_exif", False),
        image_format=fake_detection_data.get("format"),
        qr_detected=qr_check.get("has_qr_visual", False),
        qr_valid=qr_check.get("valid_format", False),
        qr_data=qr_check.get("data"),
        detection_reasons_json=json.dumps(fake_detection_data.get("reasons", [])),
        selfie_image_path=selfie_path,
        face_detected_in_id=True if face_match_score else False,
        face_detected_in_selfie=True if selfie_path else False,
        face_match_score=face_match_score,
        face_match_result=FaceMatchResult.MATCH if face_match_score and face_match_score >= 0.6 else (
            FaceMatchResult.NO_MATCH if face_match_score else FaceMatchResult.INCONCLUSIVE
        ),
        verification_result=VerificationResult.PASSED if verification_status == VerificationStatus.VERIFIED else (
            VerificationResult.FAILED if verification_status == VerificationStatus.FAILED else VerificationResult.MANUAL_REVIEW
        ),
    )
    db.session.add(verification_log)
    db.session.commit()

    flash("Reservation submitted. Waiting for admin approval.", "success")
    return redirect(url_for("public.home") + "#units")


@bp.post("/api/verify-id")
@login_required
def api_verify_id():
    """
    Step 1 of two-step verification: validate uploaded ID before showing selfie capture.
    Runs OCR + advanced fake ID detection. Returns JSON.
    """
    _ensure_user_role()
    
    upload = request.files.get("id_upload")
    if not upload or not upload.filename:
        return jsonify({"ok": False, "error": "No ID file uploaded."}), 400
    
    # Save to temp location for analysis
    filename = secure_filename(upload.filename)
    uploads_dir = Path(current_app.config["UPLOAD_FOLDER"])
    uploads_dir.mkdir(parents=True, exist_ok=True)
    tmp_name = f"tmp_id_{uuid.uuid4().hex}_{filename}"
    save_path = uploads_dir / tmp_name
    upload.save(save_path)
    
    try:
        # Run OCR
        ocr_result = scan_id_fields(save_path)
        
        # Run advanced fake ID detection
        fake_check = {"fake_score": 0.0, "is_fake": False, "reasons": []}
        if detect_fake_id:
            fake_check = detect_fake_id(str(save_path))
        
        return jsonify({
            "ok": not fake_check.get("is_fake", False),
            "ocr": {
                "id_type": ocr_result.get("id_type", ""),
                "id_number": ocr_result.get("id_number", ""),
                "name": ocr_result.get("name", ""),
            },
            "fake_detection": {
                "is_fake": fake_check.get("is_fake", False),
                "fake_score": round(fake_check.get("fake_score", 0.0), 3),
                "reasons": fake_check.get("reasons", []),
                "ela_score": round(fake_check.get("ela_score", 0.0), 2),
                "noise_score": round(fake_check.get("noise_score", 0.0), 2),
                "qr_check": {
                    "has_qr_visual": fake_check.get("qr_check", {}).get("has_qr_visual", False),
                    "decoded": fake_check.get("qr_check", {}).get("decoded", False),
                    "valid_format": fake_check.get("qr_check", {}).get("valid_format", False),
                    "data_preview": fake_check.get("qr_check", {}).get("data_preview", ""),
                },
            },
            "message": (
                "ID rejected: looks suspicious or tampered. Please upload a clear photo of your original government ID."
                if fake_check.get("is_fake")
                else "ID accepted. Proceed to selfie verification."
            ),
        })
    finally:
        # Clean up temp file
        try:
            save_path.unlink()
        except Exception:
            pass


@bp.post("/api/verify-face")
@login_required
def api_verify_face():
    """
    Step 2: Verify face match between ID photo and selfie.
    Expects: id_upload (file) and selfie_data_url (base64)
    Returns JSON with match result.
    """
    _ensure_user_role()
    
    id_upload = request.files.get("id_upload")
    selfie_data_url = request.form.get("selfie_data_url", "")
    
    if not id_upload or not id_upload.filename:
        return jsonify({"ok": False, "error": "No ID file uploaded."}), 400
    
    if not selfie_data_url:
        return jsonify({"ok": False, "error": "No selfie captured."}), 400
    
    uploads_dir = Path(current_app.config["UPLOAD_FOLDER"])
    uploads_dir.mkdir(parents=True, exist_ok=True)
    
    # Save ID temporarily
    id_filename = secure_filename(id_upload.filename)
    tmp_id_name = f"tmp_id_{uuid.uuid4().hex}_{id_filename}"
    id_path = uploads_dir / tmp_id_name
    id_upload.save(id_path)
    
    # Save selfie from base64
    selfie_path = None
    try:
        if selfie_data_url.startswith("data:image"):
            header, encoded = selfie_data_url.split(",", 1)
            selfie_bytes = base64.b64decode(encoded)
            selfie_filename = f"tmp_selfie_{uuid.uuid4().hex}.jpg"
            selfie_path = uploads_dir / selfie_filename
            with open(selfie_path, "wb") as f:
                f.write(selfie_bytes)
    except Exception as e:
        current_app.logger.warning(f"Failed to decode selfie: {e}")
        return jsonify({"ok": False, "error": "Invalid selfie data."}), 400
    
    try:
        # Run face verification
        if not FACE_VERIFICATION_AVAILABLE or not verify_identity:
            return jsonify({
                "ok": True,
                "match": True,
                "score": None,
                "message": "Face verification unavailable. Proceeding with manual review.",
                "manual_review": True,
            })
        
        result = verify_identity(str(id_path), str(selfie_path))
        
        if not result.get("success"):
            return jsonify({
                "ok": False,
                "match": False,
                "score": None,
                "message": result.get("error", "Face verification failed. Please try again."),
            })
        
        face_match_score = result.get("face_match_score", 0)
        # Lower threshold to 35% - ID photos are often low quality
        is_match = face_match_score >= 0.35
        
        return jsonify({
            "ok": True,
            "match": is_match,
            "score": round(face_match_score, 3) if face_match_score else None,
            "message": (
                f"Face verified! Match score: {int(face_match_score * 100)}%"
                if is_match
                else f"Face mismatch ({int(face_match_score * 100)}%). Ensure good lighting and face the camera directly."
            ),
        })
    finally:
        # Clean up temp files
        try:
            id_path.unlink()
        except Exception:
            pass
        try:
            if selfie_path:
                selfie_path.unlink()
        except Exception:
            pass

