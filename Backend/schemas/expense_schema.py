from datetime import date

from pydantic import BaseModel, Field
from enum import Enum

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
    amount: float = Field(..., gt=0, description="The amount of the expense")
    category: ExpenseCategory = Field(..., description="The category of the expense")
    subcategory: str | None = Field(None, description="The subcategory of the expense")
    note: str | None = Field(None, description="A note about the expense")
    payment_method: str | None = Field(None,description="Cash, Card, UPI, Bank Transfer, etc.")
    expense_date: date | None = Field(None,description="Date when the expense actually happened")