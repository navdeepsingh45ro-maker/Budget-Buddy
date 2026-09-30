"""Password reset: email a 6-digit code, then exchange it for a new password."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.hashing import hash_password
from auth.jwt_handler import SECRET_KEY
from database import get_db
from models.password_reset_model import PasswordReset
from models.user_model import User
from services.email_service import send_password_reset_code

router = APIRouter(prefix="/auth", tags=["auth"])

CODE_TTL_MINUTES = 15
MAX_ATTEMPTS = 5            # wrong guesses allowed per code
MAX_CODES_PER_HOUR = 5      # emails sent per user per hour
MIN_PASSWORD_LENGTH = 8

GENERIC_MESSAGE = "If an account exists for that email, a reset code has been sent."


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


def _hash_code(code: str) -> str:
    return hmac.new(SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()


@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Same response whether or not the email exists, so accounts can't be discovered.
    user = db.query(User).filter(User.email == request.email.strip().lower()).first()
    if not user:
        user = db.query(User).filter(User.email == request.email.strip()).first()
    if not user:
        return {"message": GENERIC_MESSAGE}

    now = datetime.utcnow()
    recent = db.query(PasswordReset).filter(
        PasswordReset.user_id == user.id,
        PasswordReset.created_at > now - timedelta(hours=1),
    ).count()
    if recent >= MAX_CODES_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many reset requests. Please try again in an hour.")

    # A new code replaces any earlier unused ones.
    db.query(PasswordReset).filter(
        PasswordReset.user_id == user.id, PasswordReset.used == False  # noqa: E712
    ).update({"used": True})

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(PasswordReset(
        user_id=user.id,
        code_hash=_hash_code(code),
        expires_at=now + timedelta(minutes=CODE_TTL_MINUTES),
    ))
    db.commit()

    background_tasks.add_task(send_password_reset_code, user.email, user.name, code, CODE_TTL_MINUTES)
    return {"message": GENERIC_MESSAGE}


@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    if len(request.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")

    invalid = HTTPException(status_code=400, detail="Invalid or expired code")

    user = db.query(User).filter(User.email == request.email.strip().lower()).first()
    if not user:
        user = db.query(User).filter(User.email == request.email.strip()).first()
    if not user:
        raise invalid

    reset = db.query(PasswordReset).filter(
        PasswordReset.user_id == user.id,
        PasswordReset.used == False,  # noqa: E712
        PasswordReset.expires_at > datetime.utcnow(),
    ).order_by(PasswordReset.created_at.desc()).first()
    if not reset:
        raise invalid

    if reset.attempts >= MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many wrong attempts. Please request a new code.")

    if not hmac.compare_digest(reset.code_hash, _hash_code(request.code.strip())):
        reset.attempts += 1
        db.commit()
        raise invalid

    user.password = hash_password(request.new_password)
    reset.used = True
    db.commit()
    return {"message": "Password updated"}
