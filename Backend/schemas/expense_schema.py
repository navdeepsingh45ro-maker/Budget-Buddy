from datetime import date

from pydantic import BaseModel, Field
from enum import Enum

MAX_AMOUNT = 1_000_000_000  # sanity cap: no single expense or budget above ₹100 crore


class ExpenseCategory(str, Enum):
    FOOD = "Food"
    TRANSPORT = "Transport"
    ENTERTAINMENT = "Entertainment"
    SHOPPING = "Shopping"
    BILLS = "Bills"
    HEALTH = "Health"
    EDUCATION = "Education"
    SUBSCRIPTIONS = "Subscriptions"
    EMI_LOANS = "EMI Loans"
    RENT = "Rent"
    INVESTMENTS = "Investments"
    SAVINGS = "Savings"
    TRAVEL = "Travel"
    FAMILY = "Family"
    PERSONAL_CARE   = "Personal Care"
    GIFTS = "Gifts"
    DONATIONS = "Donations"
    INSURANCE = "Insurance"
    TAXES = "Taxes"
    OTHER = "Other"
    

class ExpenseCreate(BaseModel):
    amount: float = Field(..., gt=0, le=MAX_AMOUNT, allow_inf_nan=False, description="The amount of the expense")
    category: ExpenseCategory = Field(..., description="The category of the expense")
    subcategory: str | None = Field(None, max_length=60, description="The subcategory of the expense")
    note: str | None = Field(None, max_length=500, description="A note about the expense")
    payment_method: str | None = Field(None, max_length=40, description="Cash, Card, UPI, Bank Transfer, etc.")
    expense_date: date | None = Field(None, ge=date(2000, 1, 1), le=date(2100, 12, 31), description="Date when the expense actually happened")