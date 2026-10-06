from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from database import Base


class EmailVerification(Base):
    """Proof that a user owns their email address.

    A row is created at sign-up with verified_at empty; the user can't log in
    until they enter the emailed code. No row = an account created before
    verification existed, which counts as verified.
    """
    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    code_hash = Column(String(64), nullable=True)   # HMAC-SHA256 of the current 6-digit code
    expires_at = Column(DateTime, nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
