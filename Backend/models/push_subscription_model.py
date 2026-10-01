from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from database import Base


class PushSubscription(Base):
    """One browser/installed-app push endpoint for a user (one row per device)."""
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    endpoint = Column(String(1000), nullable=False, unique=True)  # push service URL for this device
    p256dh = Column(String(255), nullable=False)                  # device's encryption public key
    auth = Column(String(255), nullable=False)                    # device's auth secret
    user_agent = Column(String(300), nullable=True)
    failure_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_success_at = Column(DateTime, nullable=True)
