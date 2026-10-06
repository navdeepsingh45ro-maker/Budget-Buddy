from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from database import Base


class UserConsent(Base):
    """What a user agreed to at sign-up: age group, Terms/Privacy version, and parent consent for minors.

    Kept so we can show who accepted which version of the terms, and that users
    aged 13-17 confirmed a parent or guardian agrees. Under-13s are refused before
    anything is stored, so they never get a row here.
    """
    __tablename__ = "user_consents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    age_group = Column(String(10), nullable=False)          # "13_17" or "18_plus"
    terms_version = Column(String(20), nullable=False)      # the "Last updated" date of Terms/Privacy
    terms_accepted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    guardian_consent_at = Column(DateTime, nullable=True)   # set only for 13-17
