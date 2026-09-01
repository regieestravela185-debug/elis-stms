import json
from datetime import datetime

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user
from ...extensions import db
from ...models import Building, Unit, Announcement, ChatLog
from ...nlp_chatbot import process_chat_message

bp = Blueprint("public", __name__)


def _unit_inclusion(unit, is_commercial, inclusions_by_unit):
    """A readable one-line summary of what a unit includes.

    Built from the recorded inventory so the listing reflects what the
    tenant will actually sign for in the Kasunduan, rather than the fixed
    "Bedframe, CR" every unit used to claim."""
    if is_commercial:
        return "Commercial space"
    items = inclusions_by_unit.get(unit.id) or []
    if not items:
        return "Studio type unit"
    shown = ", ".join(items[:4])
    return shown + (f", +{len(items) - 4} more" if len(items) > 4 else "")


@bp.get("/")
def home():
    buildings = db.session.query(Building).order_by(Building.code.asc()).all()
    building_floor_limits = {
        building.id: 3 if building.code in ("B3", "B4", "B5") else 4
        for building in buildings
    }
    building_unit_types = {
        building.id: "commercial" if building.code == "B5" else "residential"
        for building in buildings
    }
    residential_buildings = [b for b in buildings if building_unit_types.get(b.id) == "residential"]
    commercial_buildings = [b for b in buildings if building_unit_types.get(b.id) == "commercial"]
    # Exclude archived units from public view
    units = (
        db.session.query(Unit)
        .filter(Unit.is_archived == False)
        .order_by(Unit.building_id.asc(), Unit.unit_number.asc())
        .all()
    )
    
    # Calculate unit-specific ratings
    from ...models import Feedback
    from sqlalchemy import func
    
    unit_ratings = {}
    for unit in units:
        avg_rating = db.session.query(func.avg(Feedback.rating)).filter(
            Feedback.unit_id == unit.id,
            Feedback.rating.isnot(None)
        ).scalar()
        
        rating_count = db.session.query(Feedback).filter(
            Feedback.unit_id == unit.id,
            Feedback.rating.isnot(None)
        ).count()
        
        unit_ratings[unit.id] = {
            'avg': round(float(avg_rating), 1) if avg_rating else 0,
            'count': rating_count
        }
    
    # What each unit actually includes, read once for the whole page rather
    # than per unit. Only items with a quantity are listed — a zero means the
    # unit does not have that fixture.
    from ...models import UnitInventoryItem
    inclusions_by_unit = {}
    for row in (db.session.query(UnitInventoryItem)
                .filter(UnitInventoryItem.quantity > 0)
                .order_by(UnitInventoryItem.unit_id, UnitInventoryItem.sort_order)
                .all()):
        # Fixtures read better to a prospective tenant without the
        # sub-category prefix the Kasunduan needs ("CR/Bathroom Fixtures —
        # Shower" becomes "Shower").
        label = row.label.split("—")[-1].strip() if "—" in row.label else row.label
        inclusions_by_unit.setdefault(row.unit_id, []).append(label)

    # Group units by building and floor
    units_by_building = {}
    for u in units:
        if u.building_id not in units_by_building:
            units_by_building[u.building_id] = {
                "floor_1": [],
                "floor_2": [],
                "floor_3": [],
                "floor_4": []
            }

        unit_floor = u.floor or 1
        if unit_floor > building_floor_limits.get(u.building_id, 4):
            continue

        images: list[str] = []
        if u.unit_images_json:
            try:
                parsed = json.loads(u.unit_images_json)
                if isinstance(parsed, list):
                    # Strip leading slash from paths for url_for compatibility
                    images = [str(x).lstrip('/') for x in parsed if str(x).strip()]
            except Exception:
                images = []
        if not images:
            images = ["img/elis-building.jpg", "img/elis-building.jpg", "img/elis-building.jpg", "img/elis-building.jpg"]

        # Ensure we always have exactly 4 images (pad with last image if needed)
        while len(images) < 4:
            images.append(images[-1] if images else "img/elis-building.jpg")

        unit_type = (u.type or "unit").lower()
        is_commercial = "commercial" in unit_type
        unit_data = {
            "id": u.id,
            "unit_code": u.unit_code,
            "status": u.status.value,
            "price_monthly": float(u.price_monthly),
            "type_label": (u.type or "Unit").title(),
            "images": images,
            "description": (u.description or "").strip(),
            # What the unit actually comes with, from its recorded inventory
            # (the Kasunduan fixture list). Falls back to the old generic
            # wording for commercial units and for any unit not yet
            # inventoried, so a listing never reads as empty.
            "inclusion": _unit_inclusion(u, is_commercial, inclusions_by_unit),
            "contract_note": "Minimum 1-year contract" if is_commercial else "Studio type unit",
            "floor": unit_floor,
            "rating": unit_ratings[u.id]['avg'],
            "rating_count": unit_ratings[u.id]['count']
        }

        # Group by floor (1, 2, 3, or 4)
        if unit_floor == 1:
            units_by_building[u.building_id]["floor_1"].append(unit_data)
        elif unit_floor == 2:
            units_by_building[u.building_id]["floor_2"].append(unit_data)
        elif unit_floor == 3:
            units_by_building[u.building_id]["floor_3"].append(unit_data)
        elif unit_floor == 4:
            units_by_building[u.building_id]["floor_4"].append(unit_data)
        else:
            # Default to floor 1 if no floor specified
            units_by_building[u.building_id]["floor_1"].append(unit_data)
    
    building_unit_counts = {
        building.id: sum(len(v) for v in units_by_building.get(building.id, {}).values())
        for building in buildings
    }

    can_reserve = bool(
        current_user.is_authenticated
        and getattr(current_user, "role", None)
        and getattr(current_user.role, "value", "") == "user"
        and getattr(current_user, "is_email_verified", False)
    )
    can_view_details = bool(current_user.is_authenticated and getattr(current_user, "is_email_verified", False))
    pending = session.get("pending_registration") or {}
    target_email = ""
    dev_otp = ""
    if current_user.is_authenticated and not current_user.is_email_verified:
        target_email = current_user.email
        if current_app.debug and current_user.otp_code:
            dev_otp = current_user.otp_code
    elif pending.get("email"):
        target_email = pending.get("email")
        if current_app.debug and pending.get("otp_code"):
            dev_otp = pending.get("otp_code")
    
    # Get active announcements for public/all
    announcements = (
        db.session.query(Announcement)
        .filter(Announcement.is_active == True)
        .filter(db.or_(
            Announcement.expires_at.is_(None),
            Announcement.expires_at >= datetime.utcnow()
        ))
        .filter(db.or_(
            Announcement.target_audience == 'all',
            Announcement.target_audience == 'public'
        ))
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .limit(3)
        .all()
    )
    
    # Get tenant satisfaction rating for homepage
    from ...models import Feedback, TenantProfile, User
    from sqlalchemy.orm import joinedload
    
    avg_rating = db.session.query(func.avg(Feedback.rating)).filter(
        Feedback.rating.isnot(None)
    ).scalar()
    avg_rating = round(float(avg_rating), 1) if avg_rating else 0
    
    total_feedbacks = db.session.query(Feedback).filter(
        Feedback.rating.isnot(None)
    ).count()
    
    # Satisfaction score (% of 4-5 star ratings)
    total_with_rating = db.session.query(Feedback).filter(Feedback.rating.isnot(None)).count()
    positive_ratings = db.session.query(Feedback).filter(Feedback.rating >= 4).count()
    satisfaction_score = round((positive_ratings / total_with_rating * 100), 1) if total_with_rating > 0 else 0
    
    # Get testimonials for carousel (feedbacks with ratings, reviewed status)
    testimonials = (
        db.session.query(Feedback)
        .options(
            joinedload(Feedback.tenant_profile).joinedload(TenantProfile.user),
            joinedload(Feedback.unit)
        )
        .filter(Feedback.rating.isnot(None))
        .filter(Feedback.status == 'reviewed')  # Only show reviewed feedbacks
        .order_by(Feedback.rating.desc(), Feedback.created_at.desc())
        .limit(20)  # Get top 20 for carousel
        .all()
    )
    
    # Reset token (for reset password modal)
    reset_token = request.args.get("token")

    return render_template(
        "public/home.html",
        otp_target_email=target_email,
        otp_dev_code=dev_otp,
        buildings=buildings,
        residential_buildings=residential_buildings,
        commercial_buildings=commercial_buildings,
        building_floor_limits=building_floor_limits,
        building_unit_types=building_unit_types,
        building_unit_counts=building_unit_counts,
        units_by_building=units_by_building,
        can_reserve=can_reserve,
        can_view_details=can_view_details,
        announcements=announcements,
        avg_rating=avg_rating,
        total_feedbacks=total_feedbacks,
        satisfaction_score=satisfaction_score,
        testimonials=testimonials,
        reset_token=reset_token,
    )


@bp.post("/chatbot")
def chatbot():
    """Customer-facing replies only (no admin/floorplan/internal payment systems)."""
    msg = (request.json or {}).get("message", "").strip()
    m = msg.lower()
    
    # Get user role for logging
    user_role = "customer"
    if current_user.is_authenticated:
        user_role = current_user.role.value  # type: ignore[attr-defined]

    def both(tl: str, en: str) -> str:
        return f"{tl} / {en}"

    # Price / rent (general)
    if any(k in m for k in ("price", "presyo", "halaga", "magkano", "rent", "upa", "monthly", "rate")):
        reply = both(
            "Residential units ay studio type. Sample rates ay nasa Units section. "
            "Commercial units ay may minimum 1-year contract. Para sa updated availability at details, "
            "mag-sign in at makipag-ugnayan sa office.",
            "Residential units are studio type. Sample rates are in the Units section. "
            "Commercial units have a minimum 1-year contract. For updated availability and details, "
            "sign in and contact our office.",
        )
        _log_chat_message(msg, reply, user_role, "unit_inquiry", 1.0)
        return jsonify({"reply": reply})

    # Location / directions / landmarks
    if any(
        k in m
        for k in (
            "location",
            "lokasyon",
            "saan",
            "address",
            "matatagpuan",
            "landmark",
            "lpu",
            "nu laguna",
            "waltermart",
            "sm ",
            "highway",
        )
    ):
        return jsonify(
            {
                "reply": both(
                    "Lokasyon: The Elis Center, #2 Purok 1 Brgy. Milagrosa, Calamba City, Laguna. "
                    "Along the highway at malapit sa landmarks. Para sa tawag, tingnan ang Contact.",
                    "Location: The Elis Center, #2 Purok 1 Brgy. Milagrosa, Calamba City, Laguna. "
                    "Along the highway near landmarks. See Contact for phone numbers.",
                )
            }
        )

    # Viewing / schedule / appointment
    if any(k in m for k in ("viewing", "bisita", "inspect", "tour", "schedule", "appointment", "punta")):
        return jsonify(
            {
                "reply": both(
                    "Oo, maaaring mag-schedule ng viewing. Tumawag sa office hours (tingnan ang Contact) "
                    "para mag-set ng oras na safe at convenient.",
                    "Yes—you can schedule a viewing. Call during office hours (see Contact) to set a convenient time.",
                )
            }
        )

    # Requirements / documents / reserve
    if any(
        k in m
        for k in (
            "requirement",
            "requirements",
            "kailangan",
            "dokumento",
            "valid id",
            "reserve",
            "reservation",
            "magpareserba",
        )
    ):
        return jsonify(
            {
                "reply": both(
                    "Requirement para sa contract: valid ID ng tenants na titira. "
                    "Mag-sign in para mag-submit ng reservation at sundan ang instructions ng staff.",
                    "Contract requirement: a valid ID of the tenants who will stay. "
                    "Sign in to submit a reservation and follow staff instructions.",
                )
            }
        )

    # Billing / payment (office only — no internal process details)
    if any(
        k in m for k in ("bayad", "billing", "invoice", "receipt", "payment", "transfer", "cash", "bank")
    ):
        return jsonify(
            {
                "reply": both(
                    "Payment methods: cash at bank transfer. Power at water bills ay exclusive (separate payment). "
                    "Para sa official instructions at receipts, tumawag sa office gamit ang Contact numbers.",
                    "Payment methods: cash and bank transfer. Power and water bills are exclusive (paid separately). "
                    "For official instructions and receipts, call the office using the Contact numbers.",
                )
            }
        )

    # Safety / CCTV
    if any(k in m for k in ("cctv", "safe", "ligtas", "security", "crime")):
        return jsonify(
            {
                "reply": both(
                    "May CCTV sa common areas bilang bahagi ng seguridad. Para sa personal safety, i-lock ang unit at "
                    "i-report ang concerns sa office hours.",
                    "CCTV is used in common areas for safety. Lock your unit and report concerns during office hours.",
                )
            }
        )

    # Hours / contact
    if any(k in m for k in ("contact", "tawag", "telepono", "number", "hours", "oras", "open", "0918")):
        return jsonify(
            {
                "reply": both(
                    "Makipag-ugnayan: 0918-912-6340 o 0918-920-5645. Karaniwang Mon–Sat, 9AM–6PM.",
                    "Contact: 0918-912-6340 or 0918-920-5645. Typically Mon–Sat, 9AM–6PM.",
                )
            }
        )

    # Parking / pets (generic helpful)
    if "parking" in m or "parada" in m:
        return jsonify(
            {
                "reply": both(
                    "Tungkol sa parking, itanong sa office dahil maaaring mag-iba depende sa unit at rules ng property.",
                    "Parking rules can vary—please ask the office for accurate details.",
                )
            }
        )
    if "pet" in m or "aso" in m or "pusa" in m or "alaga" in m:
        return jsonify(
            {
                "reply": both(
                    "Ang pet policy ay depende sa unit at lease terms. Magtanong sa office bago mag-commit.",
                    "Pet policies depend on the unit and lease—ask the office before committing.",
                )
            }
        )

    # Greetings / help
    if any(
        k in m
        for k in (
            "hello",
            "kumusta",
            "kamusta",
            "musta",
            "magandang umaga",
            "magandang hapon",
            "good morning",
            "good afternoon",
            "help",
            "tulong",
        )
    ) or m in ("hi", "hey"):
        return jsonify(
            {
                "reply": both(
                    "Kumusta! Pwede kitang tulungan tungkol sa presyo, lokasyon, viewing, requirements, oras ng office, "
                    "reservation, maintenance, move-in/move-out, guest policy, noise/curfew, bills, o paano mag-reserve.",
                    "Hi! I can help with pricing, location, viewing, requirements, office hours, reservation, maintenance, "
                    "move-in/move-out, guest policy, noise/curfew, bills, and more.",
                )
            }
        )

    # Maintenance / repairs
    if any(k in m for k in ("maintenance", "repair", "sira", "ayos", "fix", "broken", "paayos", "tubero", "elektriko")):
        return jsonify(
            {
                "reply": both(
                    "Para sa maintenance requests, mag-sign in sa tenant portal at mag-submit ng ticket. "
                    "Para sa emergency repairs, tumawag sa office hours.",
                    "For maintenance requests, sign in to the tenant portal and submit a ticket. "
                    "For emergency repairs, call the office during office hours.",
                )
            }
        )

    # Move-in / move-out
    if any(k in m for k in ("move in", "move out", "lipat", "check in", "check out", "move-in", "move-out", "alis", "paglipat")):
        return jsonify(
            {
                "reply": both(
                    "Sa move-in, kailangan ng valid ID at signed contract. Sa move-out, mag-abiso ng 30 days. "
                    "Kumpletuhin ang clearance sa office bago i-release ang security deposit.",
                    "For move-in, bring a valid ID and signed contract. For move-out, give 30 days notice. "
                    "Complete the office clearance before the security deposit is released.",
                )
            }
        )

    # Guest / visitor policy
    if any(k in m for k in ("guest", "visitor", "bisita", "overnight", "friend", "relative", "kamag-anak", "kaibigan")):
        return jsonify(
            {
                "reply": both(
                    "Guests ay pinapayagan sa common areas. Para sa overnight guests, abisuhan ang office. "
                    "Ang tenant ang responsable sa kanilang bisita.",
                    "Guests are allowed in common areas. For overnight guests, inform the office. "
                    "The tenant is responsible for their visitors.",
                )
            }
        )

    # Noise / curfew
    if any(k in m for k in ("noise", "curfew", "ingay", "tahimik", "quiet", "gabi", "night", "disturb", "tapusin")):
        return jsonify(
            {
                "reply": both(
                    "Quiet hours ay 10PM - 6AM. Iwasan ang maingay na activities para sa respeto ng kapitbahay. "
                    "I-report ang noise concerns sa office.",
                    "Quiet hours are 10PM - 6AM. Avoid noisy activities to respect neighbors. "
                    "Report noise concerns to the office.",
                )
            }
        )

    # Aircon / electricity
    if any(k in m for k in ("aircon", "electric", "kuryente", "fan", "outlet", "socket", "appliances", "kuryente", "ilaw")):
        return jsonify(
            {
                "reply": both(
                    "Power bills ay exclusive (separate payment) at depende sa consumption. "
                    "Ang bawat unit ay may sariling meter. Tanungin ang office para sa rate.",
                    "Power bills are exclusive (separate payment) and depend on consumption. "
                    "Each unit has its own meter. Ask the office for the rate.",
                )
            }
        )

    # Water supply
    if any(k in m for k in ("water", "tubig", "supply", "tubig", "mainit", "malamig")):
        return jsonify(
            {
                "reply": both(
                    "Water bills ay exclusive (separate payment). May regular water supply. "
                    "I-report agad ang water interruptions sa office.",
                    "Water bills are exclusive (separate payment). Regular water supply is available. "
                    "Report water interruptions to the office immediately.",
                )
            }
        )

    # Garbage disposal
    if any(k in m for k in ("garbage", "basura", "trash", "dispose", "tapon", "segregate")):
        return jsonify(
            {
                "reply": both(
                    "Segregate ang basura (biodegradable/non-biodegradable). Sundin ang schedule ng collection. "
                    "Huwag mag-iwan ng basura sa hallways.",
                    "Segregate garbage (biodegradable/non-biodegradable). Follow the collection schedule. "
                    "Do not leave trash in hallways.",
                )
            }
        )

    # Laundry
    if any(k in m for k in ("laundry", "laba", "wash", "labahan", "dry", "plantsa")):
        return jsonify(
            {
                "reply": both(
                    "Maaaring maglaba sa loob ng unit o sa designated laundry area. "
                    "I-check ang rules para sa laundry hanging at drying.",
                    "You may do laundry inside the unit or in the designated laundry area. "
                    "Check the rules for laundry hanging and drying.",
                )
            }
        )

    # Deposit / refund
    if any(k in m for k in ("deposit", "refund", "advance", "security deposit", "security", "balik", "bawian", "bangko")):
        return jsonify(
            {
                "reply": both(
                    "Security deposit ay typically 1-2 months rent. "
                    "Ire-release pagkatapos ng move-out clearance kung walang damages o unpaid bills.",
                    "Security deposit is typically 1-2 months rent. "
                    "Released after move-out clearance if there are no damages or unpaid bills.",
                )
            }
        )

    # Tenant portal / account help
    if any(k in m for k in ("dashboard", "account", "profile", "portal", "login help", "password reset", "account ko", "profile ko")):
        return jsonify(
            {
                "reply": both(
                    "Mag-sign in sa homepage para ma-access ang tenant dashboard. "
                    "Para sa password reset, gamitin ang 'Forgot Password' link sa login modal.",
                    "Sign in on the homepage to access the tenant dashboard. "
                    "For password reset, use the 'Forgot Password' link in the login modal.",
                )
            }
        )

    # Default - Use NLP chatbot as fallback
    nlp_result = process_chat_message(msg, user_role)
    reply = nlp_result.get("response", both(
        "Pwede mong tanungin: presyo (general), lokasyon, viewing schedule, requirements, oras ng office, "
        "reservation, maintenance, move-in/move-out, guest policy, noise/curfew, bills, deposit, laundry, o paano mag-reserve.",
        "Ask about: pricing, location, viewing, requirements, office hours, reservation, maintenance, "
        "move-in/move-out, guest policy, noise/curfew, bills, deposit, laundry, and more.",
    ))
    
    _log_chat_message(
        msg, 
        reply, 
        user_role, 
        nlp_result.get("intent", "fallback"), 
        nlp_result.get("confidence", 0.5)
    )
    
    return jsonify({"reply": reply})


def _log_chat_message(message: str, response: str, user_role: str, intent: str, confidence: float):
    """Log chat message to database (works for both authenticated and anonymous users)"""
    try:
        user_id = current_user.id if current_user.is_authenticated else None  # type: ignore[attr-defined]
        
        chat_log = ChatLog(
            user_id=user_id,
            user_role=user_role,
            message=message,
            response=response,
            detected_intent=intent,
            chatbot_confidence_score=confidence,
        )
        
        db.session.add(chat_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Log error but don't interrupt chat functionality
        print(f"Error logging chat message: {e}")
        db.session.rollback()


@bp.get("/api/unit/<int:unit_id>/reviews")
def get_unit_reviews(unit_id: int):
    """Get all reviews for a specific unit - public endpoint"""
    from ...models import Feedback, TenantProfile, User
    from sqlalchemy.orm import joinedload
    
    # Get all reviewed feedbacks for this unit
    feedbacks = (
        db.session.query(Feedback)
        .options(
            joinedload(Feedback.tenant_profile).joinedload(TenantProfile.user)
        )
        .filter(Feedback.unit_id == unit_id)
        .filter(Feedback.rating.isnot(None))
        .filter(Feedback.status == 'reviewed')  # Only show reviewed feedbacks
        .order_by(Feedback.created_at.desc())
        .all()
    )
    
    reviews = []
    for feedback in feedbacks:
        reviews.append({
            'id': feedback.id,
            'rating': feedback.rating,
            'comments': feedback.comments,
            'category': feedback.category,
            'tenant_name': feedback.tenant_profile.user.full_name if feedback.tenant_profile and feedback.tenant_profile.user else 'Anonymous',
            'created_at': feedback.created_at.isoformat() if feedback.created_at else None
        })
    
    return jsonify({
        'unit_id': unit_id,
        'reviews': reviews,
        'count': len(reviews)
    })


@bp.post("/inquiry/submit")
def submit_inquiry():
    """Submit an inquiry from the homepage contact form"""
    from ...models import Inquiry
    
    data = request.form
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    subject = (data.get("subject") or "").strip()
    message = (data.get("message") or "").strip()
    
    if not full_name or not email or not subject or not message:
        return jsonify({"success": False, "message": "Please fill all required fields."}), 400
    
    # Create inquiry
    inquiry = Inquiry(
        full_name=full_name,
        email=email,
        phone=phone or None,
        subject=subject,
        message=message
    )
    db.session.add(inquiry)
    db.session.commit()
    
    # Send auto-reply email to inquirer using Brevo HTTP API
    from ...email_helper import send_inquiry_confirmation_email
    
    send_inquiry_confirmation_email(full_name, email, subject, message)
    
    return jsonify({
        "success": True,
        "message": "Your inquiry has been submitted successfully. We'll get back to you soon!"
    })



@bp.get("/terms")
def terms():
    """Terms and Conditions page"""
    return redirect(url_for("public.home") + "?auth=terms")


@bp.get("/privacy")
def privacy():
    """Privacy Policy page"""
    return redirect(url_for("public.home") + "?auth=privacy")
