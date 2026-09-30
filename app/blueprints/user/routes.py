from __future__ import annotations

import base64
import uuid
from datetime import date
from pathlib import Path
import re

from dateutil.relativedelta import relativedelta
from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ...extensions import db
from ...upload_validation import validate_upload, DOCUMENT_TYPES, IMAGE_TYPES
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
    TenantProfile,
)
from ...ocr import scan_id_fields

# face_verification pulls in OpenCV and NumPy, which together cost about
# 527 MB of resident memory and 25 seconds to import. Loading that at
# startup put the whole process over the 512 MB the web host allows, so it
# was killed and restarted on virtually every request — roughly a minute
# of delay on every page, including static files. It is needed only when a
# reservation actually carries an ID image, so it is loaded on first use
# and then cached.
_face_module = None


def _face():
    """The face_verification module, imported on first use.

    Returns a stand-in whose availability flags are all False when the
    import fails, so callers can read the flags without guarding.
    """
    global _face_module
    if _face_module is None:
        try:
            from ... import face_verification as _fv
            _face_module = _fv
        except Exception as exc:  # a missing system lib raises more than ImportError
            print(f"WARNING: face_verification unavailable, fake-ID/ID-authenticity "
                  f"checks disabled: {exc!r}")

            class _Unavailable:
                FACE_VERIFICATION_AVAILABLE = False
                FAKE_ID_DETECTION_AVAILABLE = False
                LIVENESS_DETECTION_AVAILABLE = False
                verify_identity = None
                detect_fake_id = None

            _face_module = _Unavailable()
    return _face_module

bp = Blueprint("user", __name__, url_prefix="/user")


def _deposit_basis_text(unit) -> str:
    """How the deposit for this unit was arrived at, for the tenant's email."""
    from ...deposits import is_commercial, COMMERCIAL_FLAT, COMMERCIAL_MONTHS, RESIDENTIAL_FLAT
    if is_commercial(unit):
        head = f"{COMMERCIAL_MONTHS} months' rent + ₱{COMMERCIAL_FLAT:,.0f}"
    else:
        head = f"one month's rent + ₱{RESIDENTIAL_FLAT:,.0f}"
    return f"{head}, refundable after your contract ends minus damages and unpaid bills"


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

    # One tenant holds one unit here. Someone already renting could still
    # fill in and submit this form; the administrator then could not approve
    # it, so the reservation simply sat there and nobody was told why. Say it
    # at the point they try. Browsing and viewing stay open — this only
    # blocks a second reservation.
    held = (db.session.query(TenantProfile)
            .filter(TenantProfile.user_id == current_user.id,
                    TenantProfile.is_active.is_(True))
            .first())
    if held and held.unit_id != unit.id:
        where = held.unit.unit_code if held.unit else "a unit"
        flash(f"You are currently renting {where}. A tenant may hold only one "
              f"unit at a time, so please arrange your move-out first if you "
              f"would like to transfer.", "warning")
        return redirect(url_for("public.home") + "#units")

    # One reservation per person per unit. Several people may hold a
    # reservation on the same unit — it goes to whoever pays first — but a
    # second one from the same person adds nothing: it cannot improve their
    # position and it makes the queue on that unit read longer than it is.
    # Other units stay open to them until one is approved.
    already = (db.session.query(Reservation)
               .filter(Reservation.user_id == current_user.id,  # type: ignore[attr-defined]
                       Reservation.unit_id == unit.id,
                       Reservation.status == ReservationStatus.PENDING)
               .first())
    if already:
        flash(f"You already have a reservation on {unit.unit_code} waiting for "
              f"review. Please wait for the office to act on it — you are "
              f"welcome to reserve a different unit in the meantime.", "warning")
        return redirect(url_for("public.home") + "#units")

    full_name = (request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    contact = (request.form.get("contact") or "").strip()
    id_type = (request.form.get("id_type") or "").strip()
    id_number = (request.form.get("id_number") or "").strip()
    move_in_date_raw = request.form.get("move_in_date") or ""
    move_out_date_raw = request.form.get("move_out_date") or ""

    # Commercial units are contract-term based (fixed move-out/lease end).
    # Residential units are month-to-month — no move-out date is collected;
    # the tenant just keeps paying monthly until they submit a Move-Out
    # Notice later, from their portal.
    is_commercial = "commercial" in (unit.type or "").lower()

    if not full_name or not email or not contact or not move_in_date_raw or (is_commercial and not move_out_date_raw):
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

    move_out = None
    if is_commercial:
        try:
            move_out = date.fromisoformat(move_out_date_raw)
        except ValueError:
            flash("Invalid move-out date.", "warning")
            return redirect(url_for("public.home") + "#units")

        if move_out <= move_in:
            flash("Move-out date must be after move-in date.", "warning")
            return redirect(url_for("public.home") + "#units")

        # Minimum stay: commercial units are 1-year contract terms.
        min_move_out = move_in + relativedelta(years=1)
        if move_out < min_move_out:
            flash(f"Minimum contract term for this unit is 1 year. Please choose a move-out date on or after {min_move_out.strftime('%B %d, %Y')}.", "warning")
            return redirect(url_for("public.home") + "#units")

    upload = request.files.get("id_upload")
    # accept="image/*" is a hint to the file picker, not a rule: a scripted
    # request could send anything. Check the extension, the declared type
    # and the file's own leading bytes before it is stored or OCR'd.
    if upload and upload.filename:
        ok, why = validate_upload(upload, DOCUMENT_TYPES, label="ID")
        if not ok:
            flash(why, "warning")
            return redirect(request.referrer or url_for("public.home"))
    upload_path = None
    id_local_path = None      # local file (for OCR / fake-ID detection)
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

    # ID-only verification (selfie / face match removed)
    face_match_score = None
    verification_status = VerificationStatus.PENDING
    fake_id_flag = False
    id_authenticity_score = None
    fake_detection_data = {}

    # Fake ID detection on the uploaded ID (uses the LOCAL file)
    # Gated on the fake-ID checks' own dependencies, not on face
    # recognition — see FAKE_ID_DETECTION_AVAILABLE.
    _fv = _face() if id_local_path else None
    if _fv and _fv.FAKE_ID_DETECTION_AVAILABLE and _fv.detect_fake_id:
        fake_detection_data = _fv.detect_fake_id(id_local_path)
        fake_id_flag = fake_detection_data.get("is_fake", False)
        id_authenticity_score = 1.0 - fake_detection_data.get("fake_score", 0.0)
        if fake_id_flag:
            verification_status = VerificationStatus.MANUAL_REVIEW
            flash("Potential fake ID detected. Your reservation will require manual review.", "warning")

    if not id_type and not ocr_result.get("id_type"):
        flash("ID Type is required. OCR could not detect it, please type manually.", "warning")
        return redirect(url_for("public.home") + "#units")
    if not id_number and not ocr_result.get("id_number"):
        flash("ID Number is required. OCR could not detect it, please type manually.", "warning")
        return redirect(url_for("public.home") + "#units")

    # ── Does the declared ID match the photo? ─────────────────────────
    # Until now the typed value simply won: a PhilHealth card uploaded as a
    # "National ID" with an invented number was accepted outright, because
    # the only test was that the field was not empty. What the person types
    # is a claim; the photo is the evidence. Where the two can be compared
    # and disagree, or where OCR read nothing and there is nothing to
    # compare against, the reservation goes to a human rather than through.
    id_review_reason = None
    ocr_type = (ocr_result.get("id_type") or "").strip()
    ocr_num = (ocr_result.get("id_number") or "").strip()

    def _digits(v):
        return "".join(ch for ch in (v or "") if ch.isalnum()).upper()

    if ocr_type and id_type and ocr_type.lower() != id_type.lower():
        id_review_reason = (f"Declared {id_type}, but the photo reads as "
                            f"{ocr_type}.")
    elif ocr_num and id_number and _digits(ocr_num) != _digits(id_number):
        id_review_reason = (f"Declared ID number does not match the number "
                            f"read from the photo ({ocr_num}).")
    elif not ocr_type and not ocr_num:
        id_review_reason = ("The ID could not be read, so the declared type "
                            "and number were not confirmed against it.")

    if id_review_reason:
        verification_status = VerificationStatus.MANUAL_REVIEW
        flash("Reservation submitted. Your ID needs a quick check by our "
              "staff before it is approved.", "info")

    from ...deposits import security_deposit_for

    deposit_amount = security_deposit_for(unit)

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
        id_review_reason=id_review_reason,
        selfie_image=None,
        face_match_score=face_match_score,
        verification_status=verification_status,
        fake_id_flag=fake_id_flag,
        id_authenticity_score=id_authenticity_score,
        deposit_amount=deposit_amount,
        deposit_status=DepositStatus.HELD,
        status=ReservationStatus.PENDING,
    )
    # The unit deliberately stays AVAILABLE. A reservation is an expression
    # of interest, not a claim: the unit goes to whoever pays first, not to
    # whoever filled in the form first, so several people may hold a
    # reservation on the same unit at once and the listing must keep
    # accepting them. It is the first payment that reserves the unit and
    # cancels the others — see admin.record_reservation_payment.

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
        selfie_image_path=None,
        face_detected_in_id=False,
        face_detected_in_selfie=False,
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

    from ...socket_events import emit_unit_status_update
    emit_unit_status_update()

    from ...email_helper import send_reservation_submitted_email
    try:
        send_reservation_submitted_email(
            to_email=email,
            to_name=full_name,
            unit_code=unit.unit_code,
            unit_type=(unit.type or "Unit").title(),
            floor=unit.floor,
            monthly_price=unit.price_monthly,
            deposit_amount=deposit_amount,
            move_in_date=move_in,
            move_out_date=move_out,
            deposit_basis=_deposit_basis_text(unit),
        )
    except Exception:
        current_app.logger.exception("Failed to send reservation submitted email to %s", email)

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
    ok, why = validate_upload(upload, DOCUMENT_TYPES, label="ID")
    if not ok:
        return jsonify({"ok": False, "error": why}), 400
    
    # Save to temp location for analysis
    filename = secure_filename(upload.filename)
    uploads_dir = Path(current_app.config["UPLOAD_FOLDER"])
    uploads_dir.mkdir(parents=True, exist_ok=True)
    tmp_name = f"tmp_id_{uuid.uuid4().hex}_{filename}"
    save_path = uploads_dir / tmp_name
    upload.save(save_path)
    
    try:
        # Run OCR. A crash in here used to escape the route, and Flask
        # answered with its HTML error page — which the browser then tried to
        # read as JSON, producing "Unexpected token '<'" in the caller's
        # console and nothing useful on screen. Whatever happens, this
        # endpoint answers with JSON.
        ocr_result = scan_id_fields(save_path)

        # Run advanced fake ID detection
        fake_check = {"fake_score": 0.0, "is_fake": False, "reasons": []}
        try:
            _fv = _face()
            if _fv.FAKE_ID_DETECTION_AVAILABLE and _fv.detect_fake_id:
                fake_check = _fv.detect_fake_id(str(save_path))
        except Exception as exc:
            # Tampering analysis is an extra check, not the point of the
            # step. If it cannot run, the ID still gets read.
            current_app.logger.warning("fake-ID detection unavailable: %s", exc)
            fake_check["reasons"] = ["Tampering analysis unavailable for this upload."]

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
    except Exception as exc:
        current_app.logger.exception("verify-id failed")
        return jsonify({
            "ok": False,
            "error": "server_error",
            "message": ("The ID could not be read on the server. Please try "
                        "again, or take the photo in better light with the "
                        "whole ID inside the frame."),
            "detail": str(exc)[:200],
        }), 200
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
    if id_upload and id_upload.filename:
        ok, why = validate_upload(id_upload, DOCUMENT_TYPES, label="ID")
        if not ok:
            flash(why, "warning")
            return redirect(request.referrer or url_for("public.home"))
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
        _fv = _face()
        if not _fv.FACE_VERIFICATION_AVAILABLE or not _fv.verify_identity:
            return jsonify({
                "ok": True,
                "match": True,
                "score": None,
                "message": "Face verification unavailable. Proceeding with manual review.",
                "manual_review": True,
            })
        
        result = _fv.verify_identity(str(id_path), str(selfie_path))
        
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

