"""Email verification at sign-up: a 6-digit code proves the user owns the address.

New accounts can't log in until verified. Accounts that never verify are
removed after UNVERIFIED_TTL_HOURS, so nobody can hold someone else's email.
"""
import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from auth.jwt_handler import SECRET_KEY
from models.email_verification_model import EmailVerification
from models.user_model import User
from services import email_service
from services.email_service import send_verification_code
from services.rate_limit import Limit

logger = logging.getLogger("email_verification")

CODE_TTL_MINUTES = 30
MAX_ATTEMPTS = 5              # wrong guesses allowed per code
UNVERIFIED_TTL_HOURS = 48     # unverified accounts are deleted after this
SENDS_PER_USER = Limit("verify-send", max_events=5, window_seconds=60 * 60)


def verification_enabled() -> bool:
    """Off only on a developer machine with no email set up (codes couldn't be delivered).
    In production it is always on, so a broken email setup can't silently disable it."""
    return email_service.is_configured() or os.getenv("APP_ENV", "").lower() == "production"


def _hash(code: str) -> str:
    return hmac.new(SECRET_KEY.encode(), ("verify:" + code).encode(), hashlib.sha256).hexdigest()


def _row(db: Session, user_id: int) -> EmailVerification | None:
    return db.query(EmailVerification).filter(EmailVerification.user_id == user_id).first()


def is_verified(db: Session, user: User) -> bool:
    row = _row(db, user.id)
    return row is None or row.verified_at is not None


def start(db: Session, user: User) -> None:
    """Call once at sign-up. Marks the new account as waiting for verification."""
    db.add(EmailVerification(user_id=user.id, verified_at=None if verification_enabled() else datetime.utcnow()))
    db.commit()


def send_code(db: Session, user: User, background_tasks=None) -> bool:
    """Email a fresh code (replacing any earlier one). Quietly does nothing past the hourly limit."""
    row = _row(db, user.id)
    if row is None or row.verified_at is not None:
        return False
    try:
        SENDS_PER_USER.use(user.id)
    except Exception:
        logger.info("Verification email limit reached for user %s", user.id)
        return False

    code = f"{secrets.randbelow(1_000_000):06d}"
    row.code_hash, row.attempts = _hash(code), 0
    row.expires_at = datetime.utcnow() + timedelta(minutes=CODE_TTL_MINUTES)
    db.commit()
    if background_tasks is not None:
        background_tasks.add_task(send_verification_code, user.email, user.name, code, CODE_TTL_MINUTES)
    else:
        send_verification_code(user.email, user.name, code, CODE_TTL_MINUTES)
    return True


def check_code(db: Session, user: User, code: str) -> bool:
    """True and marks the account verified if the code is right; counts wrong guesses."""
    row = _row(db, user.id)
    if row is None or row.verified_at is not None or not row.code_hash:
        return False
    if row.expires_at is None or row.expires_at < datetime.utcnow() or row.attempts >= MAX_ATTEMPTS:
        return False
    if not hmac.compare_digest(row.code_hash, _hash(code.strip())):
        row.attempts += 1
        db.commit()
        return False
    mark_verified(db, user)
    return True


def mark_verified(db: Session, user: User) -> None:
    """Also used after a password reset: the emailed reset code proves the same thing."""
    row = _row(db, user.id)
    if row is not None and row.verified_at is None:
        row.verified_at, row.code_hash = datetime.utcnow(), None
        db.commit()


def stale_unverified_user_ids(db: Session) -> list[int]:
    cutoff = datetime.utcnow() - timedelta(hours=UNVERIFIED_TTL_HOURS)
    rows = db.query(EmailVerification.user_id).filter(
        EmailVerification.verified_at.is_(None), EmailVerification.created_at < cutoff).all()
    return [user_id for (user_id,) in rows]
