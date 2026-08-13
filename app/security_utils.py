"""
Security utilities for ELIS STMS
- Rate limiting
- Account lockout tracking
- IP-based attempt tracking
- Security headers
"""

from datetime import datetime, timedelta
from functools import wraps
from flask import request, flash, session, current_app
from flask_login import current_user
import logging

logger = logging.getLogger(__name__)

# In-memory storage for failed attempts (use Redis in production for scaling)
# Format: {"ip:email": {"count": 3, "locked_until": datetime, "last_attempt": datetime}}
failed_attempts = {}
login_attempts = {}

# Configuration
MAX_LOGIN_ATTEMPTS = 5
MAX_REGISTER_ATTEMPTS = 5
MAX_OTP_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
ATTEMPT_WINDOW_MINUTES = 30


def get_client_ip():
    """Get client IP address, handling proxies"""
    if request.headers.get('X-Forwarded-For'):
        # Get first IP if multiple (client, proxy1, proxy2...)
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr or 'unknown'


def get_attempt_key(identifier, attempt_type='login'):
    """Generate key for tracking attempts"""
    ip = get_client_ip()
    return f"{attempt_type}:{ip}:{identifier}"


def is_locked_out(identifier, attempt_type='login'):
    """Check if account/IP is locked out"""
    key = get_attempt_key(identifier, attempt_type)
    
    if key not in failed_attempts:
        return False, None
    
    attempt_data = failed_attempts[key]
    locked_until = attempt_data.get('locked_until')
    
    if locked_until and datetime.utcnow() < locked_until:
        remaining = (locked_until - datetime.utcnow()).seconds // 60 + 1
        return True, remaining
    
    # Lockout expired, clean up
    if locked_until and datetime.utcnow() >= locked_until:
        del failed_attempts[key]
    
    return False, None


def record_failed_attempt(identifier, attempt_type='login'):
    """Record a failed login/register/OTP attempt"""
    key = get_attempt_key(identifier, attempt_type)
    now = datetime.utcnow()
    
    if key not in failed_attempts:
        failed_attempts[key] = {
            'count': 0,
            'first_attempt': now,
            'last_attempt': now,
            'locked_until': None
        }
    
    attempt_data = failed_attempts[key]
    
    # Reset counter if attempts are outside the window
    if (now - attempt_data['last_attempt']).seconds > (ATTEMPT_WINDOW_MINUTES * 60):
        attempt_data['count'] = 0
        attempt_data['first_attempt'] = now
    
    attempt_data['count'] += 1
    attempt_data['last_attempt'] = now
    
    # Apply lockout if max attempts reached
    max_attempts = {
        'login': MAX_LOGIN_ATTEMPTS,
        'register': MAX_REGISTER_ATTEMPTS,
        'otp': MAX_OTP_ATTEMPTS
    }.get(attempt_type, MAX_LOGIN_ATTEMPTS)
    
    if attempt_data['count'] >= max_attempts:
        attempt_data['locked_until'] = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        logger.warning(
            f"Account locked: {attempt_type} - {identifier} - IP: {get_client_ip()} - "
            f"{attempt_data['count']} failed attempts"
        )
        return True, LOCKOUT_DURATION_MINUTES
    
    remaining = max_attempts - attempt_data['count']
    return False, remaining


def clear_failed_attempts(identifier, attempt_type='login'):
    """Clear failed attempts after successful login/verification"""
    key = get_attempt_key(identifier, attempt_type)
    if key in failed_attempts:
        del failed_attempts[key]


def get_remaining_attempts(identifier, attempt_type='login'):
    """Get number of remaining attempts before lockout"""
    key = get_attempt_key(identifier, attempt_type)
    
    if key not in failed_attempts:
        max_attempts = {
            'login': MAX_LOGIN_ATTEMPTS,
            'register': MAX_REGISTER_ATTEMPTS,
            'otp': MAX_OTP_ATTEMPTS
        }.get(attempt_type, MAX_LOGIN_ATTEMPTS)
        return max_attempts
    
    attempt_data = failed_attempts[key]
    max_attempts = {
        'login': MAX_LOGIN_ATTEMPTS,
        'register': MAX_REGISTER_ATTEMPTS,
        'otp': MAX_OTP_ATTEMPTS
    }.get(attempt_type, MAX_LOGIN_ATTEMPTS)
    
    return max(0, max_attempts - attempt_data['count'])


def check_rate_limit(identifier, attempt_type='login'):
    """
    Check if user/IP is rate limited
    Returns: (is_locked, message)
    """
    is_locked, remaining_minutes = is_locked_out(identifier, attempt_type)
    
    if is_locked:
        msg = (
            f"🔒 Too many {attempt_type} attempts. "
            f"Account locked for {remaining_minutes} minutes. "
            f"Please try again later or contact support."
        )
        return True, msg
    
    return False, None


def apply_security_headers(response):
    """Apply security headers to response"""
    # XSS Protection
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # HSTS - Force HTTPS (only in production)
    if not current_app.debug:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
    
    # Content Security Policy (adjust as needed)
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://accounts.google.com https://www.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
        "img-src 'self' data: https: http:; "
        "connect-src 'self' https://accounts.google.com https://api.open-meteo.com; "
        "frame-src https://accounts.google.com https://www.google.com https://maps.google.com;"
    )
    
    # Referrer Policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Permissions Policy
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    
    return response


def log_security_event(event_type, details):
    """Log security events for monitoring"""
    logger.warning(
        f"Security Event: {event_type} - "
        f"IP: {get_client_ip()} - "
        f"User: {current_user.email if current_user.is_authenticated else 'anonymous'} - "
        f"Details: {details}"
    )


# Cleanup old entries periodically (call this from a scheduled task)
def cleanup_old_attempts():
    """Remove expired lockout entries"""
    now = datetime.utcnow()
    expired_keys = []
    
    for key, data in failed_attempts.items():
        # Remove if lockout expired and no recent attempts
        if data.get('locked_until') and now > data['locked_until']:
            if (now - data['last_attempt']).seconds > (ATTEMPT_WINDOW_MINUTES * 60 * 2):
                expired_keys.append(key)
        # Remove if last attempt was long ago and not locked
        elif (now - data['last_attempt']).seconds > (ATTEMPT_WINDOW_MINUTES * 60 * 2):
            expired_keys.append(key)
    
    for key in expired_keys:
        del failed_attempts[key]
    
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired attempt records")
