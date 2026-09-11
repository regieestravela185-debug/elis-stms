import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    
    # Session configuration - Make sessions more persistent
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"  # True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)  # Session lasts 24 hours
    SESSION_COOKIE_NAME = "elis_stms_session"  # Custom session cookie name

    # Database Configuration - Supports both MySQL and PostgreSQL
    DB_TYPE = os.getenv("DB_TYPE", "mysql")  # mysql or postgresql
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = os.getenv("DB_PORT", "3306")  # 3306 for MySQL, 5432 for PostgreSQL
    DB_NAME = os.getenv("DB_NAME", "stms_elis")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    # Dynamic connection string based on database type
    if DB_TYPE == "postgresql":
        SQLALCHEMY_DATABASE_URI = (
            f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
    else:  # mysql (default)
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Supabase's pooler closes idle connections, and the web host puts the
    # service to sleep between visits, so a pooled connection is very often
    # already dead by the time the next request reaches for it. Without a
    # pre-ping that surfaces as a stalled query rather than a quick
    # reconnect. Recycling well inside the pooler's own idle timeout keeps
    # the pool from handing out connections that are about to be dropped.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": 5,
        "max_overflow": 5,
        "pool_timeout": 20,
        "connect_args": {"connect_timeout": 10},
    }

    REMEMBER_COOKIE_DURATION = timedelta(days=14)

    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "app/static/uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", "10")) * 1024 * 1024

    # OCR.space key for reading an uploaded ID. Without one the code falls
    # back to the shared demo key, which is rate-limited to the point of
    # returning nothing — which is what "OCR API returned no results" means.
    OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY", "")

    # Supabase Storage (persistent file uploads).
    # When SUPABASE_URL + SUPABASE_SERVICE_KEY are set, uploads go to Supabase
    # Storage instead of the local (ephemeral on Render) filesystem.
    SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
    SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "unit-images")

    MAIL_SERVER = os.getenv("MAIL_SERVER", "")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "1") == "1"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "0") == "1"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "")

    RESERVATION_AUTO_CANCEL_HOURS = int(os.getenv("RESERVATION_AUTO_CANCEL_HOURS", "48"))
    
    # Brevo HTTP API (for sending emails on platforms that block SMTP)
    BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
    BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "no-reply@example.com")
    
    # Google OAuth (Phase 2)
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:5001/auth/google/callback")

