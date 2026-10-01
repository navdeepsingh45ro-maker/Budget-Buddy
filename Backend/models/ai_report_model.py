from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from database import Base


class AIReport(Base):
    """Cached AI part of a monthly report. Regenerated only when facts_hash changes."""
    __tablename__ = "ai_reports"
    __table_args__ = (UniqueConstraint("user_id", "year", "month", name="uq_ai_report_user_month"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    facts_hash = Column(String(64), nullable=False)
    content = Column(JSON, nullable=False)  # {"take": str, "tips": [str]}
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
