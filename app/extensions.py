from flask_login import LoginManager
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()

# Socket.IO disabled for deployment compatibility with Python 3.14
# Real-time updates will use AJAX polling fallback
socketio = None

login_manager.login_view = "auth.login"

