from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from schemas.budget_schema import BudgetResponse, BudgetCreate
from models.budget_model import Budget
from models.user_model import User

from auth.auth2 import get_current_user 
from database import get_db
from datetime import datetime

router = APIRouter()
current_month = datetime.now().month
current_year = datetime.now().year
@router.post("/budget/")
def create_budget(budget: BudgetCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db),current_month = datetime.now().month,current_year = datetime.now().year):
    new_budget = Budget(monthly_budget = budget.monthly_budget, month = current_month, year = current_year, user_id = current_user.id)
    existing_budget = db.query(Budget).filter(Budget.user_id == current_user.id, Budget.month == current_month, Budget.year == current_year).first()
    if existing_budget:
        raise HTTPException(status_code=400, detail="Budget for this month already exists")
    else:
        db.add(new_budget)
        db.commit()
        db.refresh(new_budget)
        return new_budget

