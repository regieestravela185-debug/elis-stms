import hashlib
import secrets
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

def hash_password(password: str) -> str:
    """Hash a password for storage.

    Uses Werkzeug's scrypt, which is already a dependency through Flask —
    no new package, and the result fits the 255-character column.
    """
    return generate_password_hash(password)


def is_legacy_password(password_hash: str) -> bool:
    """True when the stored value is a password in the clear.

    Every account created before hashing was introduced holds the password
    itself in this column. Werkzeug writes "method$salt$digest", so a value
    with no '$' has never been hashed.
    """
    return "$" not in (password_hash or "")


def verify_password(password_hash: str, password: str) -> bool:
    """Check a password against the stored value.

    Accepts a legacy plain-text value so accounts created before hashing
    can still sign in; those are upgraded to a hash on the next successful
    login (see upgrade_password_hash). Comparison for the legacy path uses
    compare_digest so it does not leak the answer through timing.
    """
    if not password_hash:
        return False
    if is_legacy_password(password_hash):
        return secrets.compare_digest(password_hash, password or "")
    try:
        return check_password_hash(password_hash, password or "")
    except Exception:
        return False


def upgrade_password_hash(user, password: str) -> bool:
    """Re-store a verified password as a hash if it is still in the clear.

    Called right after a successful sign-in. The caller commits. Returns
    whether anything changed, so a caller can decide whether to commit.
    """
    if not is_legacy_password(user.password_hash):
        return False
    user.password_hash = hash_password(password)
    return True


def generate_otp_code() -> str:
    # 6-digit numeric
    return f"{secrets.randbelow(1_000_000):06d}"


def otp_expiry(minutes: int = 10) -> datetime:
    return datetime.utcnow() + timedelta(minutes=minutes)


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

