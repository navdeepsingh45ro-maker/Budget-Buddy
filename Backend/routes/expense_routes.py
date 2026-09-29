

from services.ai_categorizer import AICategorizer
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from schemas.expense_schema import ExpenseCreate
from models.expense_model import Expense
from models.user_model import User
from models.budget_model import Budget
from auth.auth2 import get_current_user
from database import get_db
from services.insight_updater import refresh_user_insight
from services.trigger_service import evaluate_budget_triggers
from services.expense_service import ExpenseService

router = APIRouter()


@router.post("/expense/")
def create_expense(expense: ExpenseCreate, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    new_expense = ExpenseService.process_new_expense(
        db=db,
        user_id=current_user.id,
        amount=expense.amount,
        category=expense.category,
        subcategory=expense.subcategory,
        note=expense.note,
        payment_method=expense.payment_method,
        expense_date=expense.expense_date,
        background_tasks=background_tasks
    )
    return new_expense

@router.get("/expenses")
def get_expenses(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    expenses = db.query(Expense).filter(Expense.user_id == current_user.id).all()
    return expenses

@router.delete("/expense/{expense_id}")
def delete_expense(expense_id: int, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.user_id == current_user.id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
    background_tasks.add_task(refresh_user_insight, current_user.id)
    background_tasks.add_task(evaluate_budget_triggers, current_user.id)
    return {"message": "Expense deleted successfully"}

@router.put("/expense/{expense_id}")
def update_expense(expense_id: int, expense_data: ExpenseCreate, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.user_id == current_user.id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    expense.amount = expense_data.amount
    expense.category = expense_data.category
    expense.subcategory = expense_data.subcategory
    expense.payment_method = expense_data.payment_method
    expense.expense_date = expense_data.expense_date
    expense.note = expense_data.note
    db.commit()
    db.refresh(expense)
    background_tasks.add_task(refresh_user_insight, current_user.id)
    background_tasks.add_task(evaluate_budget_triggers, current_user.id)
    return expense

@router.get("/analytics")
def get_analytics(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import datetime
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    all_expenses = db.query(Expense).filter(Expense.user_id == current_user.id).all()
    expenses = []
    for e in all_expenses:
        effective_date = e.expense_date if e.expense_date else e.created_at
        if effective_date.month == current_month and effective_date.year == current_year:
            expenses.append(e)
    
    budget = db.query(Budget).filter(Budget.user_id == current_user.id, Budget.month == current_month, Budget.year == current_year).first()
    monthly_budget = budget.monthly_budget if budget else 0.0
    
    total_spent = sum(expense.amount for expense in expenses)
    remaining_budget = (monthly_budget - total_spent) if budget else 0.0
    
    expenses_by_category = {}
    for expense in expenses:
        if expense.category in expenses_by_category:
            expenses_by_category[expense.category] += expense.amount
        else:
            expenses_by_category[expense.category] = expense.amount

    top_category = (max(expenses_by_category, key=expenses_by_category.get)
        if expenses_by_category else None)
    expense_count = len(expenses)
    percentage_spent = ((total_spent / monthly_budget) * 100
    if monthly_budget > 0 else 0)        
    return {
        "total_spent": total_spent,
        "remaining_budget": remaining_budget,
        "category_breakdown": expenses_by_category,
        "top_category": top_category,
        "expense_count": expense_count,
        "percentage_spent": round(percentage_spent, 2)
    }

@router.get("/expenses/query")
def query_expenses(
    search: str = None,
    category: str = None,
    start_date: str = None,
    end_date: str = None,
    min_amount: float = None,
    max_amount: float = None,
    sort: str = "newest",
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from datetime import date as date_type
    from services.expense_query_service import ExpenseQueryService

    parsed_start = None
    parsed_end = None
    if start_date:
        parsed_start = date_type.fromisoformat(start_date)
    if end_date:
        parsed_end = date_type.fromisoformat(end_date)

    result = ExpenseQueryService.query(
        db=db,
        user_id=current_user.id,
        search=search,
        category=category,
        start_date=parsed_start,
        end_date=parsed_end,
        min_amount=min_amount,
        max_amount=max_amount,
        sort=sort,
        page=page,
        limit=limit
    )
    return result