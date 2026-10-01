from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer

from database import Base


class UserSettings(Base):
    """Per-user app settings. A missing row means defaults (and a pre-existing account)."""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    carry_over_budget = Column(Boolean, default=True, nullable=False)
    onboarding_completed_at = Column(DateTime, nullable=True)  # None = show the new-user tutorial
    created_at = Column(DateTime, default=datetime.utcnow)
