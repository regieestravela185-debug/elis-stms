from flask import Flask
from flask import session
from flask_login import current_user, logout_user
from sqlalchemy import text
from authlib.integrations.flask_client import OAuth

from .config import Config
from .extensions import db, login_manager, mail, socketio
from .jobs import start_scheduler
from datetime import datetime

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
        return {"current_year": datetime.utcnow().year}

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
            logout_user()
            session.clear()

    with app.app_context():
        # Tables are created via MySQL import SQL; keep this as a safe fallback.
        db.create_all()
        _apply_non_breaking_schema_updates()

    start_scheduler(app)
    return app


def _apply_non_breaking_schema_updates() -> None:
    """Best-effort additive schema updates for local/dev runs."""
    stmts = [
        "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS id_type VARCHAR(64) NULL",
        "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS id_number VARCHAR(120) NULL",
        "ALTER TABLE units ADD COLUMN IF NOT EXISTS description TEXT NULL",
        "ALTER TABLE units ADD COLUMN IF NOT EXISTS unit_images_json TEXT NULL",
        "ALTER TABLE tenant_profiles ADD COLUMN IF NOT EXISTS last_renewal_reminder_sent DATE NULL",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_at DATETIME NULL",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS archived_at DATETIME NULL",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason VARCHAR(255) NULL",
        # New tables for tenant modules
        "CREATE TABLE IF NOT EXISTS announcements (id INT AUTO_INCREMENT PRIMARY KEY, title VARCHAR(200) NOT NULL, content TEXT NOT NULL, category VARCHAR(50), is_active BOOLEAN DEFAULT TRUE, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS documents (id INT AUTO_INCREMENT PRIMARY KEY, tenant_profile_id INT NOT NULL, title VARCHAR(200) NOT NULL, document_type VARCHAR(50) NOT NULL, file_path VARCHAR(255) NOT NULL, uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (tenant_profile_id) REFERENCES tenant_profiles(id), INDEX (tenant_profile_id))",
        "CREATE TABLE IF NOT EXISTS renewal_requests (id INT AUTO_INCREMENT PRIMARY KEY, tenant_profile_id INT NOT NULL, requested_end_date DATE NOT NULL, notes TEXT, status VARCHAR(20) DEFAULT 'pending', created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, FOREIGN KEY (tenant_profile_id) REFERENCES tenant_profiles(id), INDEX (tenant_profile_id))",
        "CREATE TABLE IF NOT EXISTS feedbacks (id INT AUTO_INCREMENT PRIMARY KEY, tenant_profile_id INT NOT NULL, category VARCHAR(50) NOT NULL, rating INT, comments TEXT NOT NULL, status VARCHAR(20) DEFAULT 'submitted', created_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (tenant_profile_id) REFERENCES tenant_profiles(id), INDEX (tenant_profile_id))",
    ]
    for stmt in stmts:
        try:
            db.session.execute(text(stmt))
            db.session.commit()
        except Exception:
            db.session.rollback()

