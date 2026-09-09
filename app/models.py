from __future__ import annotations

import enum
import calendar
from datetime import datetime, date

from flask_login import UserMixin
from sqlalchemy import UniqueConstraint

from .extensions import db


def _enum_values(obj):
    return [e.value for e in obj]


class Role(str, enum.Enum):
    USER = "user"  # registered but not tenant
    TENANT = "tenant"  # approved
    ADMIN = "admin"


class UnitStatus(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    OCCUPIED = "occupied"
    UNPAID = "unpaid"  # admin can flag (advanced color)


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"


class ConcernStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class RenewalRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MoveOutNoticeStatus(str, enum.Enum):
    PENDING = "pending"          # submitted, admin hasn't acted yet
    ACKNOWLEDGED = "acknowledged"  # admin has seen/confirmed it, move-out not yet processed
    CANCELLED = "cancelled"        # tenant changed their mind, or admin cancelled it
    COMPLETED = "completed"        # move-out has been processed (see Process Move-Out)


class FeedbackStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"


class InquiryStatus(str, enum.Enum):
    PENDING = "pending"
    RESPONDED = "responded"
    CONTACTED = "contacted"


class DepositStatus(str, enum.Enum):
    HELD = "held"
    PARTIAL_RETURN = "partial_return"
    FULL_RETURN = "full_return"


class PaymentRiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class NotificationPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class NotificationType(str, enum.Enum):
    PAYMENT_REMINDER = "payment_reminder"
    RENEWAL_REMINDER = "renewal_reminder"
    CONCERN_ALERT = "concern_alert"
    RESERVATION_ALERT = "reservation_alert"


class NotificationStatus(str, enum.Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(190), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(
        db.Enum(Role, values_callable=_enum_values, native_enum=False),
        nullable=False,
        default=Role.USER,
    )
    is_email_verified = db.Column(db.Boolean, nullable=False, default=False)
    otp_code = db.Column(db.String(10), nullable=True)
    otp_expires_at = db.Column(db.DateTime, nullable=True)
    
    # Password reset fields
    reset_token = db.Column(db.String(100), nullable=True, unique=True, index=True)
    reset_token_expires_at = db.Column(db.DateTime, nullable=True)
    
    # Google OAuth fields (Phase 2)
    google_id = db.Column(db.String(255), nullable=True, unique=True, index=True)
    oauth_provider = db.Column(db.String(50), nullable=False, default='email')  # 'email' or 'google'
    profile_picture = db.Column(db.String(500), nullable=True)  # Google profile picture URL

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    # Account moderation fields
    is_banned = db.Column(db.Boolean, nullable=False, default=False)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    banned_at = db.Column(db.DateTime, nullable=True)
    archived_at = db.Column(db.DateTime, nullable=True)
    ban_reason = db.Column(db.String(255), nullable=True)
    # Why this account was archived — e.g. "Moved out", "Contract expired",
    # "Manually archived by admin". Shown next to the Archived badge so
    # admin doesn't have to guess.
    archive_reason = db.Column(db.String(255), nullable=True)

    tenant_profile = db.relationship("TenantProfile", back_populates="user", uselist=False)


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(120), nullable=False)
    meta_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Building(db.Model):
    __tablename__ = "buildings"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False)  # B1..B5
    name = db.Column(db.String(120), nullable=False)

    units = db.relationship("Unit", back_populates="building")


class Unit(db.Model):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("building_id", "unit_number", name="uq_unit_building_num"),)

    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), nullable=False, index=True)
    unit_number = db.Column(db.String(32), nullable=False)  # 001.. etc
    unit_code = db.Column(db.String(64), unique=True, nullable=False)  # B1-001

    price_monthly = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    status = db.Column(
        db.Enum(UnitStatus, values_callable=_enum_values, native_enum=False),
        nullable=False,
        default=UnitStatus.AVAILABLE,
    )

    floor = db.Column(db.Integer, nullable=True)
    type = db.Column(db.String(64), nullable=True)  # commercial/residential/etc
    description = db.Column(db.Text, nullable=True)

    # Occupant-count bracket for residential units — "1-2", "3-4", "5-6" —
    # used to compute the fixed monthly water bill (see
    # ai_utils.compute_water_bill). Not applicable to commercial units,
    # which pay their own electric/water directly.
    pax_range = db.Column(db.String(10), nullable=True)
    unit_images_json = db.Column(db.Text, nullable=True)  # JSON array of image URLs

    # Archive functionality (soft delete)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    archived_at = db.Column(db.DateTime, nullable=True)
    archived_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    building = db.relationship("Building", back_populates="units")


class Reservation(db.Model):
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=False, index=True)

    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(190), nullable=False)
    contact = db.Column(db.String(50), nullable=False)
    id_type = db.Column(db.String(64), nullable=True)
    id_number = db.Column(db.String(120), nullable=True)
    move_in_date = db.Column(db.Date, nullable=False)
    # NULL for residential units — no fixed lease end, rent continues
    # month-to-month until the tenant gives move-out notice. Still required
    # for commercial units, which are contract-term based.
    move_out_date = db.Column(db.Date, nullable=True)
    id_upload_path = db.Column(db.String(255), nullable=True)
    ocr_name = db.Column(db.String(120), nullable=True)
    ocr_id_number = db.Column(db.String(80), nullable=True)

    status = db.Column(
        db.Enum(ReservationStatus, values_callable=_enum_values, native_enum=False),
        nullable=False,
        default=ReservationStatus.PENDING,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Deposit fields
    deposit_amount = db.Column(db.Numeric(10, 2), nullable=False, default=5000.00)
    deposit_status = db.Column(
        db.Enum(DepositStatus, values_callable=_enum_values, native_enum=False),
        nullable=False,
        default=DepositStatus.HELD,
    )
    deposit_deductions = db.Column(db.Text, nullable=True)  # JSON string for damages, bills
    deposit_return_amount = db.Column(db.Numeric(10, 2), nullable=True)
    deposit_return_date = db.Column(db.Date, nullable=True)
    deposit_notes = db.Column(db.Text, nullable=True)

    @property
    def deduction_entries(self):
        """Deductions as a list of {amount, reason, date}.

        They were once stored as the display text they were shown as,
        which meant they could not be read back — the code that tried
        json.loads on it discarded every earlier deduction. Rows written
        then are returned as one historical entry rather than dropped.
        """
        import json as _json
        raw = self.deposit_deductions
        if not raw:
            return []
        try:
            parsed = _json.loads(raw)
        except (ValueError, TypeError):
            return [{"amount": None, "reason": line.lstrip("\u2022 ").strip(),
                     "date": None, "legacy": True}
                    for line in str(raw).split("\n") if line.strip()]
        return parsed if isinstance(parsed, list) else []

    @property
    def total_deducted(self):
        from decimal import Decimal
        return sum((Decimal(str(d["amount"])) for d in self.deduction_entries
                    if d.get("amount")), Decimal("0"))

    # AI-Assisted Identity Verification fields
    selfie_image = db.Column(db.String(255), nullable=True)  # Path to uploaded selfie image
    face_match_score = db.Column(db.Numeric(5, 4), nullable=True)  # Face matching score (0-1)
    verification_status = db.Column(
        db.Enum(VerificationStatus, values_callable=_enum_values, native_enum=False),
        nullable=False,
        default=VerificationStatus.PENDING,
    )
    fake_id_flag = db.Column(db.Boolean, nullable=False, default=False)  # Flag for potential fake ID
    id_authenticity_score = db.Column(db.Numeric(5, 4), nullable=True)  # ID authenticity score (0-1, higher = more authentic)

    user = db.relationship("User")
    unit = db.relationship("Unit")


class FaceMatchResult(str, enum.Enum):
    MATCH = "match"
    NO_MATCH = "no_match"
    INCONCLUSIVE = "inconclusive"


class VerificationResult(str, enum.Enum):
    PASSED = "passed"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"


class IdentityVerification(db.Model):
    """Identity Verification Logs for audit trail"""
    __tablename__ = "identity_verifications"

    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservations.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    # ID Document Analysis
    id_image_path = db.Column(db.String(255), nullable=True)
    id_type_detected = db.Column(db.String(64), nullable=True)
    id_number_detected = db.Column(db.String(120), nullable=True)
    ocr_confidence = db.Column(db.Numeric(5, 4), nullable=True)

    # Fake ID Detection Results
    fake_score = db.Column(db.Numeric(5, 4), nullable=True)
    is_fake = db.Column(db.Boolean, nullable=False, default=False)
    ela_score = db.Column(db.Numeric(8, 2), nullable=True)
    noise_score = db.Column(db.Numeric(8, 2), nullable=True)
    has_exif = db.Column(db.Boolean, nullable=False, default=False)
    image_format = db.Column(db.String(20), nullable=True)
    qr_detected = db.Column(db.Boolean, nullable=False, default=False)
    qr_valid = db.Column(db.Boolean, nullable=False, default=False)
    qr_data = db.Column(db.Text, nullable=True)
    detection_reasons_json = db.Column(db.Text, nullable=True)

    # Face Verification Results
    selfie_image_path = db.Column(db.String(255), nullable=True)
    face_detected_in_id = db.Column(db.Boolean, nullable=False, default=False)
    face_detected_in_selfie = db.Column(db.Boolean, nullable=False, default=False)
    face_match_score = db.Column(db.Numeric(5, 4), nullable=True)
    face_match_result = db.Column(
        db.Enum(FaceMatchResult, values_callable=_enum_values, native_enum=False),
        nullable=True,
    )

    # Overall Result
    verification_result = db.Column(
        db.Enum(VerificationResult, values_callable=_enum_values, native_enum=False),
        nullable=False,
        default=VerificationResult.MANUAL_REVIEW,
    )
    verified_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Admin Review (if manual)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_notes = db.Column(db.Text, nullable=True)

    reservation = db.relationship("Reservation", foreign_keys=[reservation_id])
    user = db.relationship("User", foreign_keys=[user_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])


def _add_one_month(d):
    """Same day next month, clamped to that month's length."""
    year, month = (d.year + (d.month // 12)), (d.month % 12) + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


class TenantProfile(db.Model):
    __tablename__ = "tenant_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=False)

    contract_start = db.Column(db.Date, nullable=False, default=date.today)
    contract_end = db.Column(db.Date, nullable=True)

    # The rent agreed in THIS tenant's contract, captured when the contract
    # was created. Rent is a term of the contract, not a live attribute of
    # the unit: raising Unit.price_monthly sets the asking price for the
    # next tenant and must not silently revalue an existing tenant's unpaid
    # months. Read it through contract_rent, never off the unit directly.
    monthly_rent = db.Column(db.Numeric(12, 2), nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_renewal_reminder_sent = db.Column(db.Date, nullable=True)
    last_payment_reminder_sent = db.Column(db.Date, nullable=True)

    # "YYYY-MM" of a billing cycle admin has manually excused from the
    # Outstanding-This-Month list for this ONE tenant (e.g. they've already
    # given move-out notice for that period, so being unpaid isn't
    # delinquency). Naturally stops applying once the cycle rolls over.
    dismissed_outstanding_month = db.Column(db.String(7), nullable=True)

    # When the tenant actually vacated. Residential tenants are month to
    # month and do not always give notice, so this is recorded when the
    # administrator learns of it rather than derived from a contract end.
    # The security deposit is held for a month afterwards to leave time to
    # total the final charges — see deposit_releasable_on.
    moved_out_on = db.Column(db.Date, nullable=True)

    # Email preferences
    email_announcements = db.Column(db.Boolean, nullable=False, default=True)
    email_payment_reminders = db.Column(db.Boolean, nullable=False, default=True)
    email_concern_updates = db.Column(db.Boolean, nullable=False, default=True)
    password_changed_at = db.Column(db.DateTime, nullable=True)

    # Predictive Analytics fields
    payment_risk_level = db.Column(
        db.Enum(PaymentRiskLevel, values_callable=_enum_values, native_enum=False),
        nullable=False,
        default=PaymentRiskLevel.LOW,
    )
    prediction_score = db.Column(db.Numeric(5, 4), nullable=True)  # AI prediction score (0-1)
    payment_behavior_history = db.Column(db.Text, nullable=True)  # JSON string for ML analysis

    user = db.relationship("User", back_populates="tenant_profile")
    unit = db.relationship("Unit")

    @property
    def deposit_releasable_on(self):
        """One month after move-out. The deposit is held until then so the
        final rent, utilities and any damage can be totalled before
        anything is returned."""
        if not self.moved_out_on:
            return None
        return _add_one_month(self.moved_out_on)

    @property
    def contract_rent(self) -> float:
        """What this tenant actually owes per month.

        Falls back to the unit's current price for profiles created before
        monthly_rent existed and never backfilled — those tenants behave
        exactly as they did before, rather than suddenly owing nothing."""
        if self.monthly_rent is not None:
            return float(self.monthly_rent)
        if self.unit and self.unit.price_monthly:
            return float(self.unit.price_monthly)
        return 0.0


class UnitInventoryItem(db.Model):
    """One fixture or furnishing that comes with a unit, with how many
    there are and what state they are in.

    These are the rows of the Kasunduan's "MGA GAMIT NA NASA LOOB NG UNIT"
    table, which used to be printed blank and filled in by hand. Recording
    them means the contract generates already filled, prospective tenants
    can see what a unit includes, and the condition agreed at move-in is
    on file to compare against at move-out.

    The label is stored on the row rather than referencing a shared key,
    so revising app/inventory.py's standard list never rewrites what a
    unit was already inventoried under.
    """
    __tablename__ = "unit_inventory_items"
    __table_args__ = (
        UniqueConstraint("unit_id", "label", name="uq_unit_inventory_label"),
    )

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=False, index=True)

    label = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    # One of app/inventory.py's INVENTORY_CONDITIONS keys.
    condition = db.Column(db.String(20), nullable=False, default="good")
    notes = db.Column(db.String(255), nullable=True)

    # What it costs to replace or repair ONE of these. Used to price damage
    # at move-out so the deduction is a figure both sides can check, rather
    # than a number the administrator has to justify from memory. Zero means
    # unpriced — damage is then reported but not auto-charged.
    replacement_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    # What it costs to REPAIR one of these. An item worn to "fair" is put
    # right rather than written off, so charging it the replacement price
    # would overcharge the tenant for ordinary wear. Zero means unpriced.
    repair_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    # Standard items keep their position from STANDARD_UNIT_INVENTORY;
    # anything the administrator adds sorts after them.
    sort_order = db.Column(db.Integer, nullable=False, default=999)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    unit = db.relationship("Unit", backref=db.backref(
        "inventory_items", cascade="all, delete-orphan", lazy="select"))

    @property
    def condition_label(self) -> str:
        from .inventory import CONDITION_LABELS
        return CONDITION_LABELS.get(self.condition, self.condition or "—")

    @property
    def needs_attention(self) -> bool:
        from .inventory import CONDITION_NEEDS_ATTENTION
        return self.condition in CONDITION_NEEDS_ATTENTION

    @property
    def priced(self) -> dict:
        """This row's condition, what happens to it, and what it costs.

        See price_item() in app/inventory.py — the three chargeable
        conditions are priced differently on purpose: fair against the
        repair cost, damaged and missing against the replacement cost.
        """
        from .inventory import price_item
        return price_item(self)

    @property
    def outcome_label(self) -> str:
        from .inventory import condition_outcome
        return condition_outcome(self.condition)["outcome"]

    @property
    def line_total(self) -> float:
        """Quantity times whichever cost this condition is charged at."""
        return self.priced["line_total"]

    @property
    def value_total(self) -> float:
        """What these are worth at replacement price, condition aside."""
        return round(float(self.replacement_cost or 0) * (self.quantity or 0), 2)


# Statuses that must never count as money received: a tenant-submitted
# proof still awaiting review, one that was rejected, and one an
# administrator voided after entering it by mistake. A voided payment is
# kept, not deleted — the ledger hash covers the row's amount, reference
# and timestamp, so removing it would break the chain, while changing only
# the status leaves every hash valid.
#
# Use this everywhere a query means "real payments". The one deliberate
# exception is the admin payments LIST, which shows voided rows so they can
# be reviewed and restored.
PAYMENT_STATUSES_NOT_COUNTED = ("pending", "rejected", "voided")


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    tenant_profile_id = db.Column(db.Integer, db.ForeignKey("tenant_profiles.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    paid_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    reference = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.String(255), nullable=True)

    # Deposit fields
    is_deposit = db.Column(db.Boolean, nullable=False, default=False)
    deposit_transaction_type = db.Column(db.String(50), nullable=True)  # 'deposit_paid', 'deposit_returned', 'deposit_deducted'

    # Payment improvements
    payment_status = db.Column(db.String(20), nullable=False, default='verified')  # verified, late, pending, rejected, voided
    is_late = db.Column(db.Boolean, nullable=False, default=False)
    breakdown_json = db.Column(db.Text, nullable=True)  # JSON: {rent, utilities, late_fee, other}
    receipt_number = db.Column(db.String(50), nullable=True)  # OR number
    payment_month = db.Column(db.String(7), nullable=True)  # "YYYY-MM" billing cycle this payment covers

    # Tenant-submitted proof of payment (e.g. bank transfer screenshot/receipt).
    # Set when a tenant self-reports a payment for admin to verify; NULL for
    # payments admin enters directly.
    proof_file = db.Column(db.String(500), nullable=True)

    # How the tenant paid: 'cash', 'bank_transfer', 'other'. Tenant-submitted
    # proofs are always 'bank_transfer'; admin picks it when entering a
    # payment manually.
    payment_method = db.Column(db.String(20), nullable=True)

    tenant_profile = db.relationship("TenantProfile")

    @property
    def ledger(self):
        return db.session.query(PaymentLedger).filter_by(payment_id=self.id).first()


class PaymentLedger(db.Model):
    __tablename__ = "payment_ledger"

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=False, unique=True)
    payload_json = db.Column(db.Text, nullable=False)
    previous_hash = db.Column(db.String(64), nullable=True)
    hash = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class UtilityBill(db.Model):
    """One per-tenant, per-month Electric+Water bill for RESIDENTIAL tenants
    only. Commercial tenants are never billed here — they pay electric/water
    directly to the utility company (see Unit.pax_range comment and
    app/contract_generator.py). Unlike rent, utilities have no late penalty:
    an unpaid charge is copied into next month's bill instead of blocking
    anything (see get_or_create_utility_bill() in app/billing_utils.py).

    Electric and water are settled INDEPENDENTLY: a tenant may pay the
    electric and leave the water, and only the water then carries over.
    That is why the carry-over is kept in two buckets rather than one
    lump sum — carried_over_electric accumulates unpaid electric and
    carried_over_water accumulates unpaid water, so an accumulated
    balance stays traceable to the charge it came from.

    rent_amount_snapshot is for itemized display only — rent collection
    itself stays entirely in Payment/PaymentLedger. Unpaid rent
    accumulates there instead, and is computed by
    get_rent_arrears() in app/billing_utils.py."""
    __tablename__ = "utility_bills"
    __table_args__ = (
        UniqueConstraint("tenant_profile_id", "billing_month", name="uq_utility_bill_tenant_month"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_profile_id = db.Column(db.Integer, db.ForeignKey("tenant_profiles.id"), nullable=False, index=True)
    billing_month = db.Column(db.String(7), nullable=False, index=True)  # "YYYY-MM"

    electric_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)  # admin-entered, no formula
    water_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)  # prefilled from compute_water_bill(), editable
    rent_amount_snapshot = db.Column(db.Numeric(12, 2), nullable=False, default=0)  # display only
    # Kept as the SUM of the two buckets below so existing reads keep working;
    # always write it through _sync_totals() rather than on its own.
    carried_over_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    carried_over_electric = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    carried_over_water = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    due_date = db.Column(db.Date, nullable=False)  # same contract_start.day anchor as rent

    # is_paid stays a real column (queries filter on it) but is derived:
    # it is True only when BOTH components are settled. Maintain it through
    # _sync_totals(), never on its own.
    is_paid = db.Column(db.Boolean, nullable=False, default=False)
    paid_at = db.Column(db.DateTime, nullable=True)
    marked_paid_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    electric_paid = db.Column(db.Boolean, nullable=False, default=False)
    electric_paid_at = db.Column(db.DateTime, nullable=True)
    water_paid = db.Column(db.Boolean, nullable=False, default=False)
    water_paid_at = db.Column(db.DateTime, nullable=True)

    reminder_sent_at = db.Column(db.Date, nullable=True)  # dedup, per-bill not per-tenant

    # Set when the tenant has told the administrator they will settle next
    # month. Suppresses the automated reminder for THIS bill only — next
    # month's bill is a new row and starts unpaused.
    reminders_paused = db.Column(db.Boolean, nullable=False, default=False)
    reminders_paused_at = db.Column(db.DateTime, nullable=True)
    reminders_paused_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reminders_paused_note = db.Column(db.String(255), nullable=True)

    # The electricity bill itself. A submetered unit's charge is a share of one
    # Meralco bill, so "why is mine this high" can only be answered by showing
    # the bill — which used to mean sending a photo over Messenger. Attaching
    # it here keeps the proof beside the charge it explains.
    electric_bill_path = db.Column(db.String(500), nullable=True)
    electric_bill_name = db.Column(db.String(255), nullable=True)
    electric_bill_uploaded_at = db.Column(db.DateTime, nullable=True)
    electric_note = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant_profile = db.relationship("TenantProfile")

    @property
    def has_electric_bill(self):
        return bool(self.electric_bill_path)

    @property
    def electric_bill_url(self):
        """A path usable in an href, whether it went to Supabase or local disk."""
        path = self.electric_bill_path
        if not path:
            return None
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return "/" + path.lstrip("/")

    @property
    def electric_bill_is_pdf(self):
        return (self.electric_bill_name or self.electric_bill_path or "").lower().endswith(".pdf")
    marked_paid_by_user = db.relationship("User", foreign_keys=[marked_paid_by])
    reminders_paused_by_user = db.relationship("User", foreign_keys=[reminders_paused_by])

    # --- amounts -------------------------------------------------------
    @property
    def electric_due(self):
        """This month's electric plus every earlier electric left unpaid."""
        return float(self.electric_amount or 0) + float(self.carried_over_electric or 0)

    @property
    def water_due(self):
        """This month's water plus every earlier water left unpaid."""
        return float(self.water_amount or 0) + float(self.carried_over_water or 0)

    @property
    def electric_outstanding(self):
        return 0.0 if self.electric_paid else self.electric_due

    @property
    def water_outstanding(self):
        return 0.0 if self.water_paid else self.water_due

    @property
    def total_due(self):
        """Everything billed this cycle, whether or not it has been paid."""
        return self.electric_due + self.water_due

    @property
    def total_outstanding(self):
        """Only what is still unsettled — this is what carries forward."""
        return self.electric_outstanding + self.water_outstanding

    @property
    def grand_total_with_rent(self):
        return self.total_due + float(self.rent_amount_snapshot or 0)

    # --- state ---------------------------------------------------------
    def sync_totals(self):
        """Keep the two derived columns (carried_over_amount, is_paid) in
        step with the buckets and per-component flags they summarize.
        Call after changing any of them, before commit."""
        self.carried_over_amount = (float(self.carried_over_electric or 0)
                                    + float(self.carried_over_water or 0))
        self.is_paid = bool(self.electric_paid and self.water_paid)
        if self.is_paid and self.paid_at is None:
            self.paid_at = datetime.utcnow()
        elif not self.is_paid:
            self.paid_at = None
        return self

    @property
    def unpaid_components(self):
        """Labels of what is still owed, for reminders and status chips."""
        out = []
        if not self.electric_paid and self.electric_due > 0:
            out.append("Electric")
        if not self.water_paid and self.water_due > 0:
            out.append("Water")
        return out


class BlockchainAlarmDismissal(db.Model):
    """Track when admin dismisses blockchain alarm"""
    __tablename__ = "blockchain_alarm_dismissal"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    dismissed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class ChatLog(db.Model):
    """NLP chat conversation logs"""
    __tablename__ = "chat_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    user_role = db.Column(db.String(20), nullable=False)  # admin, tenant, customer
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    detected_intent = db.Column(db.String(100), nullable=True)
    chatbot_confidence_score = db.Column(db.Numeric(5, 4), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class NotificationHistory(db.Model):
    """Smart notification history"""
    __tablename__ = "notification_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    notification_type = db.Column(
        db.Enum(NotificationType, values_callable=_enum_values, native_enum=False),
        nullable=False,
    )
    notification_priority = db.Column(
        db.Enum(NotificationPriority, values_callable=_enum_values, native_enum=False),
        nullable=False,
    )
    automated_trigger_type = db.Column(db.String(100), nullable=True)
    message = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(
        db.Enum(NotificationStatus, values_callable=_enum_values, native_enum=False),
        nullable=False,
        default=NotificationStatus.SENT,
    )

    user = db.relationship("User")


class Concern(db.Model):
    __tablename__ = "concerns"

    id = db.Column(db.Integer, primary_key=True)
    tenant_profile_id = db.Column(db.Integer, db.ForeignKey("tenant_profiles.id"), nullable=False, index=True)
    subject = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.Enum(ConcernStatus, values_callable=_enum_values, native_enum=False),
        nullable=False,
        default=ConcernStatus.PENDING,
    )
    priority = db.Column(db.String(20), nullable=False, default='medium')  # low, medium, high, urgent
    category = db.Column(db.String(50), nullable=False, default='general')  # maintenance, billing, noise, security, etc.
    admin_response = db.Column(db.Text, nullable=True)  # Admin's response to the concern
    admin_response_at = db.Column(db.DateTime, nullable=True)  # When admin responded
    admin_response_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # Which admin responded
    attachments_json = db.Column(db.Text, nullable=True)  # JSON array of file paths

    # Set when this concern was raised from a fixture recorded as damaged or
    # missing in the unit's inventory, so the repair and the item it is about
    # stay connected — closing the concern is the cue to update the item's
    # condition, and the settlement stops charging for it once repaired.
    unit_inventory_item_id = db.Column(
        db.Integer, db.ForeignKey("unit_inventory_items.id"), nullable=True, index=True)
    is_cancelled = db.Column(db.Boolean, nullable=False, default=False)  # Tenant cancelled
    cancelled_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)  # When marked as resolved
    in_progress_at = db.Column(db.DateTime, nullable=True)  # When marked as in progress
    satisfaction_rating = db.Column(db.Integer, nullable=True)  # 1-5 stars after resolution
    satisfaction_feedback = db.Column(db.Text, nullable=True)  # Optional feedback
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    inventory_item = db.relationship("UnitInventoryItem")
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant_profile = db.relationship("TenantProfile")
    responder = db.relationship("User", foreign_keys=[admin_response_by])
    follow_ups = db.relationship("ConcernFollowUp", back_populates="concern", order_by="ConcernFollowUp.created_at.asc()")


class ConcernFollowUp(db.Model):
    __tablename__ = "concern_follow_ups"

    id = db.Column(db.Integer, primary_key=True)
    concern_id = db.Column(db.Integer, db.ForeignKey("concerns.id"), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    attachments_json = db.Column(db.Text, nullable=True)  # JSON array of file paths

    # Set when this concern was raised from a fixture recorded as damaged or
    # missing in the unit's inventory, so the repair and the item it is about
    # stay connected — closing the concern is the cue to update the item's
    # condition, and the settlement stops charging for it once repaired.
    unit_inventory_item_id = db.Column(
        db.Integer, db.ForeignKey("unit_inventory_items.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    concern = db.relationship("Concern", back_populates="follow_ups")


class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=True)  # rule_update, maintenance, general, emergency, event
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_pinned = db.Column(db.Boolean, nullable=False, default=False)  # Pinned announcements show at top
    target_audience = db.Column(db.String(20), nullable=False, default='all')  # all, tenants, public
    expires_at = db.Column(db.DateTime, nullable=True)  # Auto-deactivate after this date
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class AnnouncementRead(db.Model):
    __tablename__ = "announcement_reads"

    id = db.Column(db.Integer, primary_key=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey("announcements.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    read_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    announcement = db.relationship("Announcement")
    user = db.relationship("User")


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    tenant_profile_id = db.Column(db.Integer, db.ForeignKey("tenant_profiles.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)  # lease_agreement, receipt, certificate, rules, electricity_bill, water_bill, internet_bill
    file_path = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)  # Admin who uploaded
    is_viewed = db.Column(db.Boolean, nullable=False, default=False)  # Has tenant viewed it
    viewed_at = db.Column(db.DateTime, nullable=True)  # When tenant viewed it

    tenant_profile = db.relationship("TenantProfile")
    uploader = db.relationship("User", foreign_keys=[uploaded_by])


class DocumentView(db.Model):
    __tablename__ = "document_views"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    viewed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    downloaded = db.Column(db.Boolean, nullable=False, default=False)

    document = db.relationship("Document")
    user = db.relationship("User")


class RenewalRequest(db.Model):
    __tablename__ = "renewal_requests"

    id = db.Column(db.Integer, primary_key=True)
    tenant_profile_id = db.Column(db.Integer, db.ForeignKey("tenant_profiles.id"), nullable=False, index=True)
    requested_end_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.Enum(RenewalRequestStatus, values_callable=_enum_values, native_enum=False),
        nullable=False,
        default=RenewalRequestStatus.PENDING,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant_profile = db.relationship("TenantProfile")


class MoveOutNotice(db.Model):
    """Residential-only equivalent of a renewal request — residential units
    have no fixed contract end, so instead of renewing, a tenant gives
    advance notice of the date they intend to move out. Admin reviews it,
    can message back, edit the date if the tenant's plan changes, or
    cancel it if the tenant decides to stay after all. Full history is kept
    (nothing is deleted) so early-vs-late notice can be reconstructed later.
    """
    __tablename__ = "move_out_notices"

    id = db.Column(db.Integer, primary_key=True)
    tenant_profile_id = db.Column(db.Integer, db.ForeignKey("tenant_profiles.id"), nullable=False, index=True)

    # The tenant's originally-submitted date — preserved even if admin later
    # edits planned_move_out_date, so "did they give early or late notice"
    # can always be answered against what was actually first said.
    original_move_out_date = db.Column(db.Date, nullable=False)
    # Current planned date — starts equal to original_move_out_date; admin
    # may adjust this if the tenant's plans change before the actual move-out.
    planned_move_out_date = db.Column(db.Date, nullable=False)

    notes = db.Column(db.Text, nullable=True)  # tenant's message
    admin_response = db.Column(db.Text, nullable=True)  # admin's reply / edit log
    admin_response_at = db.Column(db.DateTime, nullable=True)
    admin_response_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    status = db.Column(
        db.Enum(MoveOutNoticeStatus, values_callable=_enum_values, native_enum=False),
        nullable=False,
        default=MoveOutNoticeStatus.PENDING,
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant_profile = db.relationship("TenantProfile", foreign_keys=[tenant_profile_id])
    responder = db.relationship("User", foreign_keys=[admin_response_by])


class Feedback(db.Model):
    __tablename__ = "feedbacks"

    id = db.Column(db.Integer, primary_key=True)
    tenant_profile_id = db.Column(db.Integer, db.ForeignKey("tenant_profiles.id"), nullable=False, index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=True, index=True)  # Unit being rated
    category = db.Column(db.String(50), nullable=False)  # building_services, maintenance, security, etc.
    rating = db.Column(db.Integer, nullable=True)  # 1-5 stars
    comments = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.Enum(FeedbackStatus, values_callable=_enum_values, native_enum=False),
        nullable=False,
        default=FeedbackStatus.SUBMITTED,
    )
    admin_response = db.Column(db.Text, nullable=True)  # Admin's response to feedback
    admin_response_at = db.Column(db.DateTime, nullable=True)  # When admin responded
    admin_response_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # Which admin responded
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    tenant_profile = db.relationship("TenantProfile")
    unit = db.relationship("Unit", foreign_keys=[unit_id])
    responder = db.relationship("User", foreign_keys=[admin_response_by])


class Inquiry(db.Model):
    __tablename__ = "inquiries"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(190), nullable=False, index=True)
    phone = db.Column(db.String(50), nullable=True)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.Enum(InquiryStatus, values_callable=_enum_values, native_enum=False),
        nullable=False,
        default=InquiryStatus.PENDING,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    replies = db.relationship("InquiryReply", back_populates="inquiry", order_by="InquiryReply.created_at.asc()")


class InquiryReply(db.Model):
    __tablename__ = "inquiry_replies"

    id = db.Column(db.Integer, primary_key=True)
    inquiry_id = db.Column(db.Integer, db.ForeignKey("inquiries.id"), nullable=False, index=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    inquiry = db.relationship("Inquiry", back_populates="replies")
    admin = db.relationship("User")
