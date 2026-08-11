from __future__ import annotations

import enum
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
    move_out_date = db.Column(db.Date, nullable=False)
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


class TenantProfile(db.Model):
    __tablename__ = "tenant_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=False)

    contract_start = db.Column(db.Date, nullable=False, default=date.today)
    contract_end = db.Column(db.Date, nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_renewal_reminder_sent = db.Column(db.Date, nullable=True)

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
    payment_status = db.Column(db.String(20), nullable=False, default='verified')  # verified, pending, late
    is_late = db.Column(db.Boolean, nullable=False, default=False)
    breakdown_json = db.Column(db.Text, nullable=True)  # JSON: {rent, utilities, late_fee, other}
    receipt_number = db.Column(db.String(50), nullable=True)  # OR number

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
    is_cancelled = db.Column(db.Boolean, nullable=False, default=False)  # Tenant cancelled
    cancelled_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)  # When marked as resolved
    in_progress_at = db.Column(db.DateTime, nullable=True)  # When marked as in progress
    satisfaction_rating = db.Column(db.Integer, nullable=True)  # 1-5 stars after resolution
    satisfaction_feedback = db.Column(db.Text, nullable=True)  # Optional feedback
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
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
