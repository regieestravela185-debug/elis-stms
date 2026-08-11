import hashlib
import secrets
from datetime import datetime, timedelta

def hash_password(password: str) -> str:
    # NOTE: user requested plain-text passwords for demo/dev visibility.
    # Do NOT use this in production.
    return password


def verify_password(password_hash: str, password: str) -> bool:
    # Plain-text compare (demo/dev only).
    return password_hash == password


def generate_otp_code() -> str:
    # 6-digit numeric
    return f"{secrets.randbelow(1_000_000):06d}"


def otp_expiry(minutes: int = 10) -> datetime:
    return datetime.utcnow() + timedelta(minutes=minutes)


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

