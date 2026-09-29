from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import datetime

class NotificationPreferences(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True)
    
    # Core toggles
    notify_ai = Column(Boolean, default=True)
    notify_budget = Column(Boolean, default=True)
    notify_reminders = Column(Boolean, default=True)
    notify_weekly = Column(Boolean, default=True)
    notify_monthly = Column(Boolean, default=True)
    notify_system = Column(Boolean, default=True)
    
    # Future feature toggles
    future_notify_bills = Column(Boolean, default=True)
    future_notify_goals = Column(Boolean, default=True)
    future_notify_savings = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User")
