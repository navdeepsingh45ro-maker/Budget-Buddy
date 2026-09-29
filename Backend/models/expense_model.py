
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Date
from datetime import datetime
from database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    amount= Column(Float, nullable=False)
    category = Column(String(50), nullable=False)
    subcategory = Column(String(50), nullable=True)
    note = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    payment_method = Column(String(50), nullable=True)
    expense_date = Column(Date, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)