from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Date, Boolean
from datetime import datetime
from database import Base


class RecurringTransaction(Base):
    __tablename__ = "recurring_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Template fields (mirrors Expense, but does NOT duplicate logic)
    title = Column(String(200), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(50), nullable=False)
    subcategory = Column(String(50), nullable=True)
    notes = Column(String(200), nullable=True)
    payment_method = Column(String(50), nullable=True)

    # Scheduling
    frequency = Column(String(20), nullable=False)  # daily, weekly, monthly, yearly
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)           # NULL = indefinite
    next_run = Column(Date, nullable=False)

    # Status
    is_active = Column(Boolean, default=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
