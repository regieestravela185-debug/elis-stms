from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, session, url_for, current_app, jsonify
from flask_login import login_required, login_user, logout_user, current_user

from ...extensions import db, login_manager, limiter
from ...models import User, Role
from ...security import generate_otp_code, hash_password, otp_expiry, verify_password
from ...security_utils import (
    check_rate_limit, 
    record_failed_attempt, 
    clear_failed_attempts,
    get_remaining_attempts,
    log_security_event
)

bp = Blueprint("auth", __name__, url_prefix="/auth")


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


def _send_otp_email(recipient_email: str, otp_code: str) -> tuple[bool, str | None]:
    """Send OTP email using Brevo HTTP API (works on Render free tier)"""
    if not recipient_email or not otp_code:
        return False, "Missing recipient or OTP code"
    
    try:
        from app.email_helper import send_otp_email
        # Extract name from email (before @)
        recipient_name = recipient_email.split('@')[0].capitalize()
        send_otp_email(recipient_email, recipient_name, otp_code)
        current_app.logger.info("OTP email sent to %s", recipient_email)
        return True, None
    except Exception as exc:
        current_app.logger.exception("OTP email send failed to %s: %s", recipient_email, str(exc))
        return False, str(exc)


def _redirect_by_role(user: User):
    if user.role == Role.ADMIN:
        return redirect(url_for("admin.dashboard"))
    if user.role == Role.TENANT:
        return redirect(url_for("tenant.dashboard"))
    return redirect(url_for("public.home"))


def _home_auth_modal(modal: str = "login"):
    return redirect(url_for("public.home") + f"?auth={modal}")


def _dev_mode() -> bool:
    return bool(current_app.debug)


@bp.get("/login")
def login():
    return _home_auth_modal("login")


@bp.post("/login")
@limiter.limit("10 per minute")  # General rate limit
def login_post():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    # Email validation - must end with @gmail.com
    if not email.endswith("@gmail.com"):
        flash("Email must end with @gmail.com", "warning")
        return _home_auth_modal("login")
    
    # Check if account is locked due to too many failed attempts
    is_locked, lock_msg = check_rate_limit(email, 'login')
    if is_locked:
        log_security_event('login_lockout', f'Email: {email}')
        flash(lock_msg, "danger")
        return _home_auth_modal("login")

    user = db.session.query(User).filter_by(email=email).first()

    # Google-only accounts: user signed up via Google and never set a password
    if user and user.oauth_provider == 'google' and not verify_password(user.password_hash, password):
        locked, remaining = record_failed_attempt(email, 'login')
        log_security_event('failed_login', f'Email: {email} (Google account)')
        if locked:
            flash(f"🔒 Too many failed attempts. Account locked for 15 minutes.", "danger")
        else:
            flash(f"Invalid email or password. {remaining} attempts remaining.", "danger")
        return _home_auth_modal("login")

    if not user or not verify_password(user.password_hash, password):
        locked, remaining = record_failed_attempt(email, 'login')
        log_security_event('failed_login', f'Email: {email}')
        if locked:
            flash(f"🔒 Too many failed attempts. Account locked for 15 minutes.", "danger")
        else:
            flash(f"Invalid email or password. {remaining} attempts remaining.", "danger")
        return _home_auth_modal("login")

    # Check if user is banned
    if user.is_banned:
        log_security_event('banned_login_attempt', f'Email: {email}')
        flash("Your account has been banned. Please contact support for assistance.", "danger")
        return _home_auth_modal("login")

    # Successful login - clear failed attempts
    clear_failed_attempts(email, 'login')
    log_security_event('successful_login', f'Email: {email}')
    
    login_user(user, remember=True)
    session["boot_id"] = current_app.config.get("SERVER_BOOT_ID")
    user.last_login_at = datetime.utcnow()
    db.session.commit()

    if not user.is_email_verified:
        if not user.otp_code or not user.otp_expires_at or datetime.utcnow() > user.otp_expires_at:
            user.otp_code = generate_otp_code()
            user.otp_expires_at = otp_expiry(10)
            db.session.commit()
        sent, mail_err = _send_otp_email(user.email, user.otp_code)
        if sent:
            msg = "Please verify OTP to continue."
            if _dev_mode():
                msg += f" OTP sent to {user.email}. (DEV OTP: {user.otp_code})"
            flash(msg, "info")
        else:
            flash(
                f"Please verify OTP to continue. Email send failed: {mail_err or 'unknown error'} (DEV OTP: {user.otp_code}).",
                "warning",
            )
        return _home_auth_modal("verify")

    return _redirect_by_role(user)


@bp.get("/register")
def register():
    return _home_auth_modal("register")


@bp.post("/register")
@limiter.limit("5 per hour")  # Stricter limit for registration
def register_post():
    full_name = (request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    if not full_name or not email or not password:
        flash("Please complete the form.", "warning")
        return _home_auth_modal("register")

    # Email validation - must end with @gmail.com
    if not email.endswith("@gmail.com"):
        flash("Email must end with @gmail.com", "warning")
        return _home_auth_modal("register")
    
    # Check if IP/email is locked due to too many registration attempts
    is_locked, lock_msg = check_rate_limit(email, 'register')
    if is_locked:
        log_security_event('register_lockout', f'Email: {email}')
        flash(lock_msg, "danger")
        return _home_auth_modal("register")

    # Password validation - must have 8+ chars, 1 uppercase, 1 lowercase, 1 number, 1 special char
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "warning")
        return _home_auth_modal("register")

    if not re.search(r"[A-Z]", password):
        flash("Password must contain at least 1 uppercase letter.", "warning")
        return _home_auth_modal("register")

    if not re.search(r"[a-z]", password):
        flash("Password must contain at least 1 lowercase letter.", "warning")
        return _home_auth_modal("register")

    if not re.search(r"[0-9]", password):
        flash("Password must contain at least 1 number.", "warning")
        return _home_auth_modal("register")

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        flash("Password must contain at least 1 special character.", "warning")
        return _home_auth_modal("register")

    existing = db.session.query(User).filter_by(email=email).first()
    if existing and existing.is_email_verified:
        flash("Email is already registered.", "warning")
        return _home_auth_modal("register")

    otp = generate_otp_code()
    session.permanent = True  # Make session persistent
    session["pending_registration"] = {
        "full_name": full_name,
        "email": email,
        "password_hash": hash_password(password),
        "otp_code": otp,
        "otp_expires_at": otp_expiry(10).isoformat(),
    }
    sent, mail_err = _send_otp_email(email, otp)
    if sent:
        msg = "OTP sent to your email. Verify first to complete registration."
        if _dev_mode():
            msg += f" Sent to {email}. (DEV OTP: {otp})"
        flash(msg, "info")
    else:
        flash(
            f"OTP generated but email send failed: {mail_err or 'unknown error'} (DEV OTP: {otp}). Tap Resend OTP.",
            "warning",
        )
    return _home_auth_modal("verify")


@bp.get("/verify-otp")
def verify_otp():
    if current_user.is_authenticated and current_user.is_email_verified:
        return _redirect_by_role(current_user)
    pending = session.get("pending_registration")
    if current_user.is_authenticated and not current_user.is_email_verified:
        return _home_auth_modal("verify")
    if pending:
        return _home_auth_modal("verify")
    flash("Start with Login or Register first.", "warning")
    return _home_auth_modal("login")


@bp.post("/verify-otp")
@limiter.limit("10 per 5 minutes")  # Allow 10 OTP attempts per 5 minutes
def verify_otp_post():
    code = (request.form.get("otp") or "").strip()
    
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json

    if current_user.is_authenticated and not current_user.is_email_verified:
        user: User = current_user  # type: ignore
        
        # Check rate limit
        is_locked, lock_msg = check_rate_limit(user.email, 'otp')
        if is_locked:
            log_security_event('otp_lockout', f'Email: {user.email}')
            msg = lock_msg
            if is_ajax:
                return jsonify({"success": False, "message": msg}), 429
            flash(msg, "danger")
            return _home_auth_modal("verify")

        if not user.otp_code or not user.otp_expires_at:
            msg = "OTP not found. Please request a new one."
            if is_ajax:
                return jsonify({"success": False, "message": msg}), 400
            flash(msg, "warning")
            return _home_auth_modal("verify")

        if datetime.utcnow() > user.otp_expires_at:
            msg = "OTP expired. Please request a new one."
            if is_ajax:
                return jsonify({"success": False, "message": msg}), 400
            flash(msg, "warning")
            return _home_auth_modal("verify")

        if code != user.otp_code:
            # Record failed OTP attempt
            locked, remaining = record_failed_attempt(user.email, 'otp')
            log_security_event('failed_otp', f'Email: {user.email}')
            
            if locked:
                msg = "🔒 Too many failed OTP attempts. Account locked for 15 minutes."
            else:
                msg = f"❌ Invalid OTP. {remaining} attempts remaining."
            
            if is_ajax:
                return jsonify({"success": False, "message": msg}), 400
            flash(msg, "danger")
            return _home_auth_modal("verify")

        try:
            # Successful OTP verification - clear failed attempts
            clear_failed_attempts(user.email, 'otp')
            log_security_event('successful_otp', f'Email: {user.email}')
            
            user.is_email_verified = True
            user.otp_code = None
            user.otp_expires_at = None
            db.session.commit()

            msg = "✅ Email verified successfully! Welcome to ELIS STMS!"
            if is_ajax:
                redirect_url = url_for('public.home') if user.role == Role.USER else url_for('admin.dashboard') if user.role == Role.ADMIN else url_for('tenant.dashboard')
                return jsonify({"success": True, "message": msg, "redirect": redirect_url}), 200
            flash(msg, "success")
            return _redirect_by_role(user)
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error verifying user email: {e}")
            msg = "Verification failed. Please try again."
            if is_ajax:
                return jsonify({"success": False, "message": msg}), 500
            flash(msg, "danger")
            return _home_auth_modal("verify")

    pending = session.get("pending_registration")
    if not pending:
        msg = "OTP session not found. Please register again."
        if is_ajax:
            return jsonify({"success": False, "message": msg, "redirect": url_for('public.home', auth='register')}), 400
        flash(msg, "warning")
        return _home_auth_modal("register")
    
    email = (pending.get("email") or "").strip().lower()
    
    # Check rate limit for pending registration OTP
    is_locked, lock_msg = check_rate_limit(email, 'otp')
    if is_locked:
        log_security_event('otp_lockout_pending', f'Email: {email}')
        msg = lock_msg
        if is_ajax:
            return jsonify({"success": False, "message": msg}), 429
        flash(msg, "danger")
        return _home_auth_modal("verify")

    otp_code = pending.get("otp_code")
    otp_expires_at_raw = pending.get("otp_expires_at")
    if not otp_code or not otp_expires_at_raw:
        msg = "OTP not found. Please register again."
        if is_ajax:
            return jsonify({"success": False, "message": msg, "redirect": url_for('public.home', auth='register')}), 400
        flash(msg, "warning")
        session.pop("pending_registration", None)
        return _home_auth_modal("register")

    try:
        otp_expires_at = datetime.fromisoformat(otp_expires_at_raw)
    except ValueError:
        msg = "OTP data is invalid. Please register again."
        if is_ajax:
            return jsonify({"success": False, "message": msg, "redirect": url_for('public.home', auth='register')}), 400
        flash(msg, "warning")
        session.pop("pending_registration", None)
        return _home_auth_modal("register")

    if datetime.utcnow() > otp_expires_at:
        msg = "OTP expired. Please request a new one."
        if is_ajax:
            return jsonify({"success": False, "message": msg}), 400
        flash(msg, "warning")
        return _home_auth_modal("verify")

    if code != otp_code:
        # Record failed OTP attempt for pending registration
        locked, remaining = record_failed_attempt(email, 'otp')
        log_security_event('failed_otp_pending', f'Email: {email}')
        
        if locked:
            msg = "🔒 Too many failed OTP attempts. Account locked for 15 minutes."
        else:
            msg = f"❌ Invalid OTP. {remaining} attempts remaining."
        
        if is_ajax:
            return jsonify({"success": False, "message": msg}), 400
        flash(msg, "danger")
        return _home_auth_modal("verify")

    full_name = (pending.get("full_name") or "").strip()
    password_hash = pending.get("password_hash") or ""
    if not email or not full_name or not password_hash:
        msg = "Registration data is incomplete. Please register again."
        if is_ajax:
            return jsonify({"success": False, "message": msg, "redirect": url_for('public.home', auth='register')}), 400
        flash(msg, "warning")
        session.pop("pending_registration", None)
        return _home_auth_modal("register")

    existing = db.session.query(User).filter_by(email=email).first()
    if existing and existing.is_email_verified:
        flash("Email is already registered. Please login.", "warning")
        session.pop("pending_registration", None)
        return _home_auth_modal("login")
    if existing and not existing.is_email_verified:
        try:
            # Successful verification - clear failed attempts
            clear_failed_attempts(email, 'otp')
            log_security_event('successful_registration', f'Email: {email} (existing user updated)')
            
            existing.full_name = full_name
            existing.password_hash = password_hash
            existing.is_email_verified = True
            existing.otp_code = None
            existing.otp_expires_at = None
            db.session.commit()
            
            # Clear pending registration
            session.pop("pending_registration", None)
            
            # Auto-login
            login_user(existing, remember=True)
            session["boot_id"] = current_app.config.get("SERVER_BOOT_ID")
            
            flash("✅ Registration completed! Your email has been verified. Welcome to ELIS STMS!", "success")
            
            if existing.role == Role.USER:
                return redirect(url_for("public.home"))
            else:
                return _redirect_by_role(existing)
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error updating user: {e}")
            flash("Verification failed. Please try again.", "danger")
            return _home_auth_modal("verify")

    user = User(
        full_name=full_name,
        email=email,
        password_hash=password_hash,
        role=Role.USER,
        is_email_verified=True,
        otp_code=None,
        otp_expires_at=None,
    )
    
    try:
        # Successful verification - clear failed attempts
        clear_failed_attempts(email, 'otp')
        log_security_event('successful_registration', f'Email: {email} (new user)')
        
        db.session.add(user)
        db.session.commit()
        
        # Clear pending registration from session
        session.pop("pending_registration", None)
        
        # Auto-login the new user
        login_user(user, remember=True)
        session["boot_id"] = current_app.config.get("SERVER_BOOT_ID")
        
        # Success message
        flash("✅ Registration completed! Your email has been verified. Welcome to ELIS STMS!", "success")
        
        # Redirect to user dashboard (for Role.USER)
        if user.role == Role.USER:
            return redirect(url_for("public.home"))  # Users go to homepage
        else:
            return _redirect_by_role(user)
            
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error saving user to database: {e}")
        flash("Registration failed. Please try again or contact support.", "danger")
        return _home_auth_modal("register")


@bp.post("/resend-otp")
@limiter.limit("3 per 10 minutes")  # Limit OTP resend requests
def resend_otp():
    if current_user.is_authenticated and not current_user.is_email_verified:
        user: User = current_user  # type: ignore
        
        # Check if locked out
        is_locked, lock_msg = check_rate_limit(user.email, 'otp')
        if is_locked:
            flash(lock_msg, "danger")
            return _home_auth_modal("verify")
        
        user.otp_code = generate_otp_code()
        user.otp_expires_at = otp_expiry(10)
        db.session.commit()
        sent, mail_err = _send_otp_email(user.email, user.otp_code)
        if sent:
            msg = "OTP sent. Check your email."
            if _dev_mode():
                msg += f" Sent to {user.email}. (DEV OTP: {user.otp_code})"
            flash(msg, "info")
        else:
            flash(f"Email send failed: {mail_err or 'unknown error'} (DEV OTP: {user.otp_code}).", "warning")
        return _home_auth_modal("verify")
    if current_user.is_authenticated and current_user.is_email_verified:
        return _redirect_by_role(current_user)

    pending = session.get("pending_registration")
    if not pending:
        flash("No pending registration found. Please register first.", "warning")
        return _home_auth_modal("register")

    otp = generate_otp_code()
    pending["otp_code"] = otp
    pending["otp_expires_at"] = otp_expiry(10).isoformat()
    session["pending_registration"] = pending
    target_email = (pending.get("email") or "").strip().lower()
    sent, mail_err = _send_otp_email(target_email, otp)
    if sent:
        msg = "OTP sent. Check your email."
        if _dev_mode():
            msg += f" Sent to {target_email}. (DEV OTP: {otp})"
        flash(msg, "info")
    else:
        flash(f"OTP refreshed but email send failed: {mail_err or 'unknown error'} (DEV OTP: {otp}).", "warning")
    return _home_auth_modal("verify")


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("public.home"))



def _send_password_reset_email(recipient_email: str, reset_token: str) -> tuple[bool, str | None]:
    """Send password reset email using Brevo HTTP API (works on Render free tier)"""
    if not recipient_email or not reset_token:
        return False, "Missing recipient or reset token"

    reset_url = url_for("auth.reset_password", token=reset_token, _external=True)
    
    try:
        from app.email_helper import send_password_reset_email
        # Extract name from email (before @)
        recipient_name = recipient_email.split('@')[0].capitalize()
        send_password_reset_email(recipient_email, recipient_name, reset_token, reset_url)
        current_app.logger.info("Password reset email sent to %s", recipient_email)
        return True, None
    except Exception as exc:
        current_app.logger.exception("Password reset email send failed to %s: %s", recipient_email, str(exc))
        return False, str(exc)


@bp.get("/forgot-password")
def forgot_password():
    """Display forgot password form"""
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)
    return _home_auth_modal("forgot_password")


@bp.post("/forgot-password")
def forgot_password_post():
    """Handle forgot password form submission"""
    email = (request.form.get("email") or "").strip().lower()

    if not email:
        flash("Please enter your email address.", "warning")
        return _home_auth_modal("forgot_password")

    # Email validation - must end with @gmail.com
    if not email.endswith("@gmail.com"):
        flash("Email must end with @gmail.com", "warning")
        return _home_auth_modal("forgot_password")

    user = db.session.query(User).filter_by(email=email).first()

    # Always show success message (security best practice - don't reveal if email exists)
    if not user or not user.is_email_verified:
        flash("If an account exists with this email, you will receive a password reset link shortly.", "info")
        return _home_auth_modal("login")

    # Generate secure reset token
    reset_token = secrets.token_urlsafe(32)
    user.reset_token = reset_token
    user.reset_token_expires_at = datetime.utcnow() + timedelta(hours=1)
    db.session.commit()

    # Send reset email
    sent, mail_err = _send_password_reset_email(user.email, reset_token)
    if sent:
        flash("Password reset link has been sent to your email. Please check your inbox and follow the instructions.", "success")
    else:
        flash(
            f"Password reset link generated but email send failed: {mail_err or 'unknown error'}. Please try again later.",
            "warning",
        )

    return _home_auth_modal("login")


@bp.get("/reset-password/<token>")
def reset_password(token: str):
    """Display reset password form"""
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    user = db.session.query(User).filter_by(reset_token=token).first()

    if not user:
        flash("Invalid or expired password reset link.", "danger")
        return _home_auth_modal("forgot_password")

    if not user.reset_token_expires_at or datetime.utcnow() > user.reset_token_expires_at:
        flash("This password reset link has expired. Please request a new one.", "warning")
        user.reset_token = None
        user.reset_token_expires_at = None
        db.session.commit()
        return _home_auth_modal("forgot_password")

    return redirect(url_for("public.home") + f"?auth=reset_password&token={token}")


@bp.post("/reset-password/<token>")
def reset_password_post(token: str):
    """Handle reset password form submission"""
    password = request.form.get("password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    if not password or not confirm_password:
        flash("Please fill in all fields.", "warning")
        return redirect(url_for("public.home") + f"?auth=reset_password&token={token}")

    if password != confirm_password:
        flash("Passwords do not match.", "warning")
        return redirect(url_for("public.home") + f"?auth=reset_password&token={token}")

    # Password validation - must have 8+ chars, 1 uppercase, 1 lowercase, 1 number, 1 special char
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "warning")
        return redirect(url_for("public.home") + f"?auth=reset_password&token={token}")

    if not re.search(r"[A-Z]", password):
        flash("Password must contain at least 1 uppercase letter.", "warning")
        return redirect(url_for("public.home") + f"?auth=reset_password&token={token}")

    if not re.search(r"[a-z]", password):
        flash("Password must contain at least 1 lowercase letter.", "warning")
        return redirect(url_for("public.home") + f"?auth=reset_password&token={token}")

    if not re.search(r"[0-9]", password):
        flash("Password must contain at least 1 number.", "warning")
        return redirect(url_for("public.home") + f"?auth=reset_password&token={token}")

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        flash("Password must contain at least 1 special character.", "warning")
        return redirect(url_for("public.home") + f"?auth=reset_password&token={token}")

    user = db.session.query(User).filter_by(reset_token=token).first()

    if not user:
        flash("Invalid or expired password reset link.", "danger")
        return _home_auth_modal("forgot_password")

    if not user.reset_token_expires_at or datetime.utcnow() > user.reset_token_expires_at:
        flash("This password reset link has expired. Please request a new one.", "warning")
        user.reset_token = None
        user.reset_token_expires_at = None
        db.session.commit()
        return _home_auth_modal("forgot_password")

    # Update password and clear reset token
    user.password_hash = hash_password(password)
    user.reset_token = None
    user.reset_token_expires_at = None
    db.session.commit()

    flash("Your password has been reset successfully. You can now login with your new password.", "success")
    return _home_auth_modal("login")



# ============================================================================
# GOOGLE OAUTH ROUTES (Phase 2)
# ============================================================================

@bp.get("/google")
def google_login():
    """Initiate Google OAuth flow"""
    from app import oauth
    
    # Check if Google OAuth is configured
    if not current_app.config.get("GOOGLE_CLIENT_ID") or not current_app.config.get("GOOGLE_CLIENT_SECRET"):
        flash("Google OAuth is not configured. Please contact the administrator.", "warning")
        return redirect(url_for("auth.login"))
    
    # Check for placeholder credentials
    if current_app.config.get("GOOGLE_CLIENT_ID") == "your_google_client_id_here":
        flash("Google OAuth credentials need to be configured. Please contact the administrator.", "warning")
        return redirect(url_for("auth.login"))
    
    # Generate redirect URI
    redirect_uri = url_for("auth.google_callback", _external=True)
    
    # Initiate OAuth flow with account selection prompt
    # Forces Google to show account chooser every time
    return oauth.google.authorize_redirect(redirect_uri, prompt='select_account')


@bp.get("/google/callback")
def google_callback():
    """Handle Google OAuth callback"""
    from app import oauth
    
    try:
        # Get access token from Google
        token = oauth.google.authorize_access_token()
        
        # Get user info from Google
        user_info = token.get('userinfo')
        
        if not user_info:
            flash("Failed to get user information from Google.", "danger")
            return redirect(url_for("auth.login"))
        
        # Extract user data
        google_id = user_info.get('sub')  # Google's unique user ID
        email = user_info.get('email')
        full_name = user_info.get('name')
        profile_picture = user_info.get('picture')
        
        if not google_id or not email:
            flash("Failed to get required information from Google.", "danger")
            return redirect(url_for("auth.login"))
        
        # Check if user already exists with this Google ID
        user = db.session.query(User).filter_by(google_id=google_id).first()
        
        if user:
            # CHECK IF USER IS BANNED
            if user.is_banned:
                flash("Your account has been suspended. Please contact the administrator.", "danger")
                return redirect(url_for("public.home") + "?show_login=1")
            
            # Existing Google user - just login
            user.last_login_at = datetime.utcnow()
            user.profile_picture = profile_picture  # Update profile picture
            db.session.commit()
            
            login_user(user, remember=True)
            session["boot_id"] = current_app.config.get("SERVER_BOOT_ID")
            
            flash(f"Welcome back, {user.full_name}!", "success")
            return _redirect_by_role(user)
        
        # Check if user exists with this email (email-based account)
        existing_user = db.session.query(User).filter_by(email=email).first()
        
        if existing_user:
            # CHECK IF USER IS BANNED
            if existing_user.is_banned:
                flash("Your account has been suspended. Please contact the administrator.", "danger")
                return redirect(url_for("public.home") + "?show_login=1")
            
            # Link Google account to existing email account
            existing_user.google_id = google_id
            existing_user.oauth_provider = 'google'
            existing_user.profile_picture = profile_picture
            existing_user.is_email_verified = True  # Google emails are verified
            existing_user.last_login_at = datetime.utcnow()
            db.session.commit()
            
            login_user(existing_user, remember=True)
            session["boot_id"] = current_app.config.get("SERVER_BOOT_ID")
            
            flash(f"Google account linked successfully! Welcome back, {existing_user.full_name}!", "success")
            return _redirect_by_role(existing_user)
        
        # New user - create account
        new_user = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),  # Random password (won't be used)
            google_id=google_id,
            oauth_provider='google',
            profile_picture=profile_picture,
            role=Role.USER,
            is_email_verified=True,  # Google emails are pre-verified
            otp_code=None,
            otp_expires_at=None,
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user, remember=True)
        session["boot_id"] = current_app.config.get("SERVER_BOOT_ID")
        
        flash(f"Account created successfully! Welcome, {new_user.full_name}!", "success")
        return _redirect_by_role(new_user)
        
    except Exception as e:
        current_app.logger.exception("Google OAuth error: %s", str(e))
        # In debug mode, show actual error to help diagnose
        if current_app.debug:
            flash(f"Google sign-in error: {type(e).__name__}: {str(e)}", "danger")
        else:
            flash("An error occurred during Google sign-in. Please try again or use email login.", "danger")
        return redirect(url_for("auth.login"))
