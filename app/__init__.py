from flask import Flask
from flask import session
from flask import url_for
from flask_login import current_user, logout_user
from sqlalchemy import text
from authlib.integrations.flask_client import OAuth

from .config import Config
from .extensions import db, login_manager, mail, socketio, limiter
from .jobs import start_scheduler
from .security_utils import apply_security_headers, cleanup_old_attempts
from datetime import datetime

# Fix eventlet DNS resolution issues in Docker containers
import os
os.environ.setdefault('EVENTLET_NO_GREENDNS', 'yes')

# Initialize OAuth
oauth = OAuth()


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_object)
    app.config["SERVER_BOOT_ID"] = datetime.utcnow().isoformat()

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    socketio.init_app(app)
    limiter.init_app(app)  # Initialize rate limiter
    
    # Initialize OAuth
    oauth.init_app(app)
    
    # Configure Google OAuth
    oauth.register(
        name='google',
        client_id=app.config.get('GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

    from .blueprints.public.routes import bp as public_bp
    from .blueprints.auth.routes import bp as auth_bp
    from .blueprints.user.routes import bp as user_bp
    from .blueprints.tenant.routes import bp as tenant_bp
    from .blueprints.admin.routes import bp as admin_bp
    from .blueprints.api.routes import bp as api_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(tenant_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    # Register SocketIO event handlers
    from . import socket_events

    @app.context_processor
    def _inject_globals():
        def media_url(path):
            """Resolve an image/file path for templates.

            Absolute URLs (e.g. Supabase Storage) are returned as-is; relative
            paths fall back to the local static folder.
            """
            if not path:
                return ""
            if str(path).startswith(("http://", "https://", "//")):
                return path
            return url_for("static", filename=str(path).lstrip("/"))

        return {"current_year": datetime.utcnow().year, "media_url": media_url}

    @app.context_processor
    def _inject_admin_nav():
        """Pending-item counts + recent notifications for the admin shell.

        Powers sidebar badges and the topbar notification bell. Runs only for
        authenticated admins; any DB hiccup degrades to empty (never breaks a page).
        """
        empty = {"nav_counts": {}, "nav_notifications": [], "nav_notif_total": 0}
        try:
            from flask_login import current_user
            from .models import Role
            if not (current_user.is_authenticated and current_user.role == Role.ADMIN):
                return empty

            from .extensions import db
            from .models import (
                Reservation, ReservationStatus, Concern, ConcernStatus,
                RenewalRequest, RenewalRequestStatus, Inquiry, InquiryStatus,
            )

            counts = {
                "reservations": db.session.query(Reservation).filter(
                    Reservation.status == ReservationStatus.PENDING).count(),
                "concerns": db.session.query(Concern).filter(
                    Concern.status != ConcernStatus.RESOLVED).count(),
                "renewals": db.session.query(RenewalRequest).filter(
                    RenewalRequest.status == RenewalRequestStatus.PENDING).count(),
                "inquiries": db.session.query(Inquiry).filter(
                    Inquiry.status == InquiryStatus.PENDING).count(),
            }

            notifs = []
            for r in (db.session.query(Reservation)
                      .filter(Reservation.status == ReservationStatus.PENDING)
                      .order_by(Reservation.created_at.desc()).limit(5).all()):
                notifs.append({
                    "type": "Reservation",
                    "title": getattr(r, "full_name", None) or "New reservation",
                    "subtitle": (r.unit.unit_code if getattr(r, "unit", None) else "Pending review"),
                    "time": r.created_at, "url": url_for("admin.reservations"),
                })
            for c in (db.session.query(Concern)
                      .filter(Concern.status != ConcernStatus.RESOLVED)
                      .order_by(Concern.created_at.desc()).limit(5).all()):
                notifs.append({
                    "type": "Concern", "title": c.subject or "Concern",
                    "subtitle": "Needs attention", "time": c.created_at,
                    "url": url_for("admin.concerns"),
                })
            for i in (db.session.query(Inquiry)
                      .filter(Inquiry.status == InquiryStatus.PENDING)
                      .order_by(Inquiry.created_at.desc()).limit(5).all()):
                notifs.append({
                    "type": "Inquiry",
                    "title": getattr(i, "full_name", None) or getattr(i, "subject", None) or "New inquiry",
                    "subtitle": "Awaiting response", "time": i.created_at,
                    "url": url_for("admin.inquiries"),
                })
            notifs.sort(key=lambda n: n["time"] or datetime.min, reverse=True)
            notifs = notifs[:8]

            return {
                "nav_counts": counts,
                "nav_notifications": notifs,
                "nav_notif_total": counts["reservations"] + counts["concerns"] + counts["inquiries"],
            }
        except Exception:
            return empty

    # Add custom Jinja2 filters
    @app.template_filter('from_json')
    def from_json_filter(value):
        """Convert JSON string to Python object"""
        if not value:
            return []
        try:
            import json
            return json.loads(value)
        except (ValueError, TypeError):
            return []

    @app.template_filter('to_ph')
    def to_ph_filter(value):
        """Convert UTC datetime to Philippine time (UTC+8) for display."""
        if not value:
            return value
        from datetime import timedelta
        return value + timedelta(hours=8)

    @app.before_request
    def _invalidate_old_sessions():
        # Force fresh public state on every new server run.
        boot_id = session.get("boot_id")
        current_boot = app.config.get("SERVER_BOOT_ID")
        if current_user.is_authenticated and boot_id != current_boot:
            # Preserve pending_registration even when clearing session
            pending_reg = session.get("pending_registration")
            logout_user()
            session.clear()
            if pending_reg:
                session["pending_registration"] = pending_reg
    
    @app.after_request
    def _add_security_headers(response):
        """Add security headers to all responses"""
        return apply_security_headers(response)

    with app.app_context():
        # Tables are created via MySQL import SQL; keep this as a safe fallback.
        db.create_all()
        _apply_non_breaking_schema_updates()

    start_scheduler(app)
    return app


def _apply_non_breaking_schema_updates() -> None:
    """Best-effort additive schema updates for local/dev runs."""
    from flask import current_app
    
    # Detect database type
    db_type = current_app.config.get('DB_TYPE', 'mysql').lower()
    
    if db_type == 'postgresql':
        # PostgreSQL syntax
        stmts = [
            "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS id_type VARCHAR(64) NULL",
            "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS id_number VARCHAR(120) NULL",
            "ALTER TABLE units ADD COLUMN IF NOT EXISTS description TEXT NULL",
            "ALTER TABLE units ADD COLUMN IF NOT EXISTS unit_images_json TEXT NULL",
            "ALTER TABLE tenant_profiles ADD COLUMN IF NOT EXISTS last_renewal_reminder_sent DATE NULL",
            "ALTER TABLE tenant_profiles ADD COLUMN IF NOT EXISTS last_payment_reminder_sent DATE NULL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_at TIMESTAMP NULL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP NULL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason VARCHAR(255) NULL",
            # New tables for tenant modules (PostgreSQL)
            "CREATE TABLE IF NOT EXISTS announcements (id SERIAL PRIMARY KEY, title VARCHAR(200) NOT NULL, content TEXT NOT NULL, category VARCHAR(50), is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, target_audience VARCHAR(20) DEFAULT 'all', is_pinned BOOLEAN DEFAULT FALSE)",
            "CREATE TABLE IF NOT EXISTS documents (id SERIAL PRIMARY KEY, tenant_profile_id INT NOT NULL, title VARCHAR(200) NOT NULL, document_type VARCHAR(50) NOT NULL, file_path VARCHAR(255) NOT NULL, uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, uploaded_by INT, is_viewed BOOLEAN DEFAULT FALSE, FOREIGN KEY (tenant_profile_id) REFERENCES tenant_profiles(id))",
            "CREATE INDEX IF NOT EXISTS idx_documents_tenant ON documents(tenant_profile_id)",
            "CREATE TABLE IF NOT EXISTS renewal_requests (id SERIAL PRIMARY KEY, tenant_profile_id INT NOT NULL, requested_end_date DATE NOT NULL, notes TEXT, status VARCHAR(20) DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (tenant_profile_id) REFERENCES tenant_profiles(id))",
            "CREATE INDEX IF NOT EXISTS idx_renewal_requests_tenant ON renewal_requests(tenant_profile_id)",
            "CREATE TABLE IF NOT EXISTS feedbacks (id SERIAL PRIMARY KEY, tenant_profile_id INT NOT NULL, unit_id INT, category VARCHAR(50) NOT NULL, rating INT, comments TEXT NOT NULL, status VARCHAR(20) DEFAULT 'submitted', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (tenant_profile_id) REFERENCES tenant_profiles(id), FOREIGN KEY (unit_id) REFERENCES units(id))",
            "CREATE INDEX IF NOT EXISTS idx_feedbacks_tenant ON feedbacks(tenant_profile_id)",
            "CREATE INDEX IF NOT EXISTS idx_feedbacks_unit ON feedbacks(unit_id)",
        ]
    else:
        # MySQL syntax (original)
        stmts = [
            "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS id_type VARCHAR(64) NULL",
            "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS id_number VARCHAR(120) NULL",
            "ALTER TABLE units ADD COLUMN IF NOT EXISTS description TEXT NULL",
            "ALTER TABLE units ADD COLUMN IF NOT EXISTS unit_images_json TEXT NULL",
            "ALTER TABLE tenant_profiles ADD COLUMN IF NOT EXISTS last_renewal_reminder_sent DATE NULL",
            "ALTER TABLE tenant_profiles ADD COLUMN IF NOT EXISTS last_payment_reminder_sent DATE NULL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_at DATETIME NULL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS archived_at DATETIME NULL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason VARCHAR(255) NULL",
            # New tables for tenant modules (MySQL)
            "CREATE TABLE IF NOT EXISTS announcements (id INT AUTO_INCREMENT PRIMARY KEY, title VARCHAR(200) NOT NULL, content TEXT NOT NULL, category VARCHAR(50), is_active BOOLEAN DEFAULT TRUE, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP)",
            "CREATE TABLE IF NOT EXISTS documents (id INT AUTO_INCREMENT PRIMARY KEY, tenant_profile_id INT NOT NULL, title VARCHAR(200) NOT NULL, document_type VARCHAR(50) NOT NULL, file_path VARCHAR(255) NOT NULL, uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (tenant_profile_id) REFERENCES tenant_profiles(id), INDEX (tenant_profile_id))",
            "CREATE TABLE IF NOT EXISTS renewal_requests (id INT AUTO_INCREMENT PRIMARY KEY, tenant_profile_id INT NOT NULL, requested_end_date DATE NOT NULL, notes TEXT, status VARCHAR(20) DEFAULT 'pending', created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, FOREIGN KEY (tenant_profile_id) REFERENCES tenant_profiles(id), INDEX (tenant_profile_id))",
            "CREATE TABLE IF NOT EXISTS feedbacks (id INT AUTO_INCREMENT PRIMARY KEY, tenant_profile_id INT NOT NULL, category VARCHAR(50) NOT NULL, rating INT, comments TEXT NOT NULL, status VARCHAR(20) DEFAULT 'submitted', created_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (tenant_profile_id) REFERENCES tenant_profiles(id), INDEX (tenant_profile_id))",
        ]
    
    for stmt in stmts:
        try:
            db.session.execute(text(stmt))
            db.session.commit()
        except Exception as e:
            # Log error but continue with other statements
            print(f"Schema update skipped (may already exist): {str(e)[:100]}")
            db.session.rollback()

