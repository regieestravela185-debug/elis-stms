from flask_login import LoginManager
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
socketio = SocketIO(cors_allowed_origins="*", async_mode='eventlet')

# Rate limiter.
#
# There is deliberately NO default limit. A default applies to every route
# in the app, so it governs ordinary browsing — opening a page, loading a
# dashboard, following a link — where the correct number is "as often as
# they like". The previous default of 50 per hour locked users out of the
# site within minutes of normal use.
#
# What rate limiting is actually for here is stopping password and OTP
# guessing, and those endpoints carry their own explicit limits in
# app/blueprints/auth/routes.py. Add @limiter.limit to a route that needs
# one; do not reintroduce a blanket default.
#
# Storage is in-memory, which is correct only while the app runs as a
# single worker (see the Dockerfile's `-w 1`). Adding workers would give
# each its own counters — move to Redis before doing that.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
)

login_manager.login_view = "auth.login"

