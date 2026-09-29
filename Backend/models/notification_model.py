from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship
from database import Base
import datetime

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    # Source
    source = Column(String(50), default="system") # ai, budget, scheduler, system, admin

    # Content
    title = Column(String(255), nullable=False)
    message = Column(String(1000), nullable=False)
    icon = Column(String(50), nullable=True)

    # Routing
    action_type = Column(String(100), nullable=True)
    action_payload = Column(JSON, nullable=True)

    # Categorization
    category = Column(String(50), nullable=False) # ai, budget, monthly, system, etc.
    priority = Column(String(50), default="info") # info, success, warning, critical

    # Lifecycle State
    status = Column(String(50), default="pending") # pending, delivered, failed, cancelled
    is_read = Column(Boolean, default=False, index=True)
    is_archived = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    scheduled_for = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    # Extensibility
    metadata_json = Column(JSON, nullable=True)

    owner = relationship("User")
