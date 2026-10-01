

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
from services.summary_service import FinancialSummaryGenerator
from services.budget_carryover import ensure_budget_carried_over
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
    ensure_budget_carried_over(db, current_user.id)
    s = FinancialSummaryGenerator.generate_summary(current_user.id, db)
    has_budget = s["monthly_budget"] > 0
    return {
        "total_spent": s["total_spent"],
        "remaining_budget": s["remaining_budget"] if has_budget else 0.0,
        "category_breakdown": s["category_totals"],
        "top_category": s["top_category"],
        "expense_count": s["expense_count"],
        "percentage_spent": s["percentage_spent"],
        # Same calendar/pace numbers the Coach Insight uses, so screens always agree.
        "monthly_budget": s["monthly_budget"],
        "days_left": s["days_left"],
        "days_in_month": s["days_in_month"],
        "safe_daily_limit": s["safe_daily_limit"],
        "average_daily_spending": s["average_daily_spending"],
        "projected_month_total": s["projected_month_total"],
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