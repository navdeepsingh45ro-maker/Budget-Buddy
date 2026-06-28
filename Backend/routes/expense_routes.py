

from services.ai_categorizer import AICategorizer
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from schemas.expense_schema import ExpenseCreate
from models.expense_model import Expense
from models.user_model import User
from models.budget_model import Budget
from auth.auth2 import get_current_user
from database import get_db

router = APIRouter()


@router.post("/expense/")
def create_expense(expense: ExpenseCreate,current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    subcategory = None
    if expense.note:
        ai = AICategorizer()
        ai_result = ai.categorize_expense(expense.note)
        subcategory = ai_result.get("subcategory", "Other")

    new_expense = Expense(amount=expense.amount,category=expense.category,subcategory=subcategory,note=expense.note,user_id=current_user.id)
    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)
    return new_expense

@router.get("/expenses")
def get_expenses(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    expenses = db.query(Expense).filter(Expense.user_id == current_user.id).all()
    return expenses

@router.delete("/expense/{expense_id}")
def delete_expense(expense_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.user_id == current_user.id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
    return {"message": "Expense deleted successfully"}

@router.put("/expense/{expense_id}")
def update_expense(expense_id: int, expense_data: ExpenseCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.user_id == current_user.id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    expense.amount = expense_data.amount
    expense.category = expense_data.category
    expense.note = expense_data.note
    db.commit()
    db.refresh(expense)
    return expense

@router.get("/analytics")
def get_analytics(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    expenses = db.query(Expense).filter(Expense.user_id == current_user.id).all()
    budget = db.query(Budget).filter(Budget.user_id == current_user.id).first()
    if not budget:
       raise HTTPException(status_code=404, detail="Budget not found")
    total_spent = sum(expense.amount for expense in expenses)
    remaining_budget = budget.monthly_budget - total_spent
    
    expenses_by_category = {}
    for expense in expenses:
        if expense.category in expenses_by_category:
            expenses_by_category[expense.category] += expense.amount
        else:
            expenses_by_category[expense.category] = expense.amount

    top_category = (max(expenses_by_category, key=expenses_by_category.get)
        if expenses_by_category else None)
    expense_count = len(expenses)
    percentage_spent = ((total_spent / budget.monthly_budget) * 100
    if budget.monthly_budget > 0 else 0)        
    return {
        "total_spent": total_spent,
        "remaining_budget": remaining_budget,
        "category_breakdown": expenses_by_category,
        "top_category": top_category,
        "expense_count": expense_count,
        "percentage_spent": round(percentage_spent, 2)
    }